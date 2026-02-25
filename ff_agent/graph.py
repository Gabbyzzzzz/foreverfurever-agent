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

def preprocess(state: GraphState) -> dict:
    """Detect language and ensure system prompt is present."""
    messages = state.get("messages", [])

    # Detect language from the last human message
    language = "en"
    for msg in reversed(messages):
        if isinstance(msg, HumanMessage):
            if any("\u4e00" <= ch <= "\u9fff" for ch in msg.content):
                language = "zh"
            break

    # Ensure system prompt is the first message
    has_system = any(isinstance(m, SystemMessage) for m in messages)
    new_messages = []
    if not has_system:
        new_messages.append(SystemMessage(content=SYSTEM_PROMPT))

    return {
        "language": language,
        "messages": new_messages,
    }


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


def agent_node(state: GraphState) -> dict:
    """Call Gemini with conversation history and tools."""
    messages = state["messages"]
    response = _get_agent().invoke(messages)
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

    # Generate dynamic quick reply actions based on content,
    # but only if the user hasn't already answered the question.
    content_lower = content.lower()

    # Collect all user messages to check if they already answered
    user_texts = " ".join(
        msg.content.lower() for msg in messages if isinstance(msg, HumanMessage)
    )

    if "?" in content or "\uff1f" in content:
        if any(kw in content_lower for kw in ["budget", "price", "spend", "\u9884\u7b97"]):
            # Only show budget buttons if user hasn't mentioned a price yet
            already_answered = any(kw in user_texts for kw in ["under $", "budget", "$50", "$100", "\u9884\u7b97"])
            if not already_answered:
                ui_actions.append({"type": "quick_reply", "label": "Under $50", "value": "I'd like something under $50"})
                ui_actions.append({"type": "quick_reply", "label": "Under $100", "value": "I'd like something under $100"})
        elif any(kw in content_lower for kw in ["gift", "yourself", "personal", "\u9001\u793c", "\u81ea\u7528"]):
            # Only show gift/personal buttons if user hasn't answered yet
            already_answered = any(kw in user_texts for kw in ["gift", "myself", "personal", "keepsake", "\u9001\u793c", "\u81ea\u7528"])
            if not already_answered:
                ui_actions.append({"type": "quick_reply", "label": "It's a gift", "value": "It's a gift for someone"})
                ui_actions.append({"type": "quick_reply", "label": "For myself", "value": "It's for myself as a personal keepsake"})

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
    escalation_keywords = ["support@foreverfurever.org", "support team", "contact us"]
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
