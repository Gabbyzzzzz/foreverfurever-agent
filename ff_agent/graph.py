"""LangGraph state graph for the ForeverFurEver agent.

Architecture: preprocess → agent ↔ tools → postprocess
The agent (Gemini) autonomously decides when to search products,
ask clarification questions, or answer directly.
"""

from __future__ import annotations

import json
import os
import re
from typing import Annotated, Any

from langchain_core.messages import HumanMessage, AIMessage, BaseMessage, SystemMessage, ToolMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from langgraph.graph import StateGraph, END
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode
from typing_extensions import TypedDict

from ff_agent.prompts import SYSTEM_PROMPT
from ff_agent.tools import ALL_TOOLS
from ff_agent.knowledge import search_knowledge as _search_kb


# ==========================
# Graph State
# ==========================

class GraphState(TypedDict):
    messages: Annotated[list[BaseMessage], add_messages]
    language: str            # "en" or "zh"
    ui_actions: list[dict]   # dynamic buttons for frontend
    products: list[dict]     # product cards for frontend
    thread_id: str
    viewed_handles: list[str]  # track shown products to avoid repeats


# ==========================
# Node: preprocess
# ==========================

_POLICY_KEYWORDS = [
    "refund", "return", "shipping", "delivery", "care", "customs",
    "damaged", "lost", "engraving", "personali", "customiz", "how long",
    "when will", "return policy", "退款", "退货", "运费", "发货", "快递",
]


def preprocess(state: GraphState) -> dict:
    """Detect language from the latest user message."""
    messages = state.get("messages", [])

    # Detect language from the last human message
    language = "en"
    for msg in reversed(messages):
        if isinstance(msg, HumanMessage):
            if any("\u4e00" <= ch <= "\u9fff" for ch in msg.content):
                language = "zh"
            break

    return {"language": language}


# ==========================
# Node: agent (Gemini + tools)
# ==========================

_agent_with_tools = None


def _get_agent():
    """Lazy-initialize the Gemini LLM with tools (deferred until first call
    so that environment variables from dotenv are available)."""
    global _agent_with_tools
    if _agent_with_tools is None:
        api_key = os.environ.get("GOOGLE_API_KEY") or os.environ.get("GEMINI_API_KEY")
        llm = ChatGoogleGenerativeAI(
            model="gemini-2.0-flash",
            temperature=0.3,
            google_api_key=api_key,
        )
        _agent_with_tools = llm.bind_tools(ALL_TOOLS)
    return _agent_with_tools


def _build_kb_context(user_text: str) -> str | None:
    """Search knowledge base for policy questions, return context string or None."""
    query_lower = user_text.lower()
    if not any(kw in query_lower for kw in _POLICY_KEYWORDS):
        return None
    # Map common intents to better search queries
    search_query = user_text
    if any(kw in query_lower for kw in ["refund", "return", "退款", "退货"]):
        search_query = "return refund policy"
    elif any(kw in query_lower for kw in ["shipping", "delivery", "how long", "when will", "运费", "发货"]):
        search_query = "shipping delivery time"
    elif any(kw in query_lower for kw in ["damaged", "broken", "wrong"]):
        search_query = "damaged item replacement"
    elif any(kw in query_lower for kw in ["engraving", "personali", "customiz"]):
        search_query = "personalization engraving customization"
    try:
        results = _search_kb(search_query)
        if results:
            return "\n\n".join(results)
    except Exception:
        pass
    return None


def agent_node(state: GraphState) -> dict:
    """Call Gemini with conversation history, system prompt, and KB context.

    We build the message list here (not in preprocess) to guarantee correct
    ordering: SystemMessage first, then conversation history.
    """
    messages = state["messages"]

    # Build the system prompt, optionally enriched with KB results
    prompt = SYSTEM_PROMPT
    last_human_text = ""
    for msg in reversed(messages):
        if isinstance(msg, HumanMessage):
            last_human_text = msg.content
            break

    kb_context = _build_kb_context(last_human_text)
    if kb_context:
        prompt += f"\n\n[Knowledge Base — use this to answer the current question]\n{kb_context}"

    # Ensure correct order: system prompt first, then conversation
    llm_messages = [SystemMessage(content=prompt)]
    for msg in messages:
        if not isinstance(msg, SystemMessage):
            llm_messages.append(msg)

    response = _get_agent().invoke(llm_messages)
    return {"messages": [response]}


# ==========================
# Node: postprocess
# ==========================

def postprocess(state: GraphState) -> dict:
    """Extract product references and generate UI actions from the agent's response."""
    messages = state.get("messages", [])
    products: list[dict] = []
    ui_actions: list[dict] = []

    # Find the last AI message (non-tool-call)
    last_ai_msg = None
    for msg in reversed(messages):
        if isinstance(msg, AIMessage) and not msg.tool_calls:
            last_ai_msg = msg
            break

    if not last_ai_msg:
        return {"products": [], "ui_actions": []}

    content = last_ai_msg.content or ""

    # Build product cards from ToolMessage results in message history
    seen_handles: set[str] = set()
    for msg in messages:
        if not isinstance(msg, ToolMessage):
            continue
        try:
            tool_data = json.loads(msg.content) if isinstance(msg.content, str) else msg.content
            if isinstance(tool_data, list):
                for p in tool_data:
                    if isinstance(p, dict) and p.get("handle") and p["handle"] not in seen_handles:
                        seen_handles.add(p["handle"])
                        products.append(p)
            elif isinstance(tool_data, dict) and tool_data.get("handle") and tool_data["handle"] not in seen_handles:
                seen_handles.add(tool_data["handle"])
                products.append(tool_data)
        except (json.JSONDecodeError, TypeError):
            pass

    content_lower = content.lower()

    # Filter out products already shown in this conversation
    previously_viewed = set(state.get("viewed_handles", []))
    new_products = [p for p in products if p.get("handle") not in previously_viewed]
    # If all products were already viewed, don't re-show them
    display_products = new_products[:6]

    # Track all shown handles
    new_viewed = list(
        previously_viewed | {p.get("handle", "") for p in display_products}
    )

    if display_products:
        ui_actions.append({
            "type": "open_url",
            "label": "Browse all products",
            "url": "https://foreverfurever.org/collections/all",
        })

    # Show "Contact Support" button when agent mentions escalation
    escalation_keywords = [
        "support@foreverfurever.org", "support team", "contact us",
        "contact support", "customer support", "email us", "reach out",
        "contact our", "refund", "return policy",
    ]
    if any(kw in content_lower for kw in escalation_keywords):
        ui_actions.append({
            "type": "open_url",
            "label": "Email Support",
            "url": "mailto:support@foreverfurever.org",
        })

    return {
        "products": display_products,
        "ui_actions": ui_actions,
        "viewed_handles": new_viewed,
    }


# ==========================
# Routing: should we call tools or postprocess?
# ==========================

def should_continue(state: GraphState) -> str:
    """After agent node, decide: call tools or go to postprocess."""
    messages = state.get("messages", [])
    last_message = messages[-1] if messages else None

    if last_message and hasattr(last_message, "tool_calls") and last_message.tool_calls:
        return "tools"
    return "postprocess"


# ==========================
# Build Graph
# ==========================

def build_graph(checkpointer=None):
    """Construct the LangGraph state graph.

    Args:
        checkpointer: LangGraph checkpointer for conversation persistence.
                      If None, no persistence (useful for testing).
    """
    tool_node = ToolNode(ALL_TOOLS)

    g = StateGraph(GraphState)

    g.add_node("preprocess", preprocess)
    g.add_node("agent", agent_node)
    g.add_node("tools", tool_node)
    g.add_node("postprocess", postprocess)

    g.set_entry_point("preprocess")
    g.add_edge("preprocess", "agent")
    g.add_conditional_edges(
        "agent",
        should_continue,
        {"tools": "tools", "postprocess": "postprocess"},
    )
    g.add_edge("tools", "agent")
    g.add_edge("postprocess", END)

    return g.compile(checkpointer=checkpointer)
