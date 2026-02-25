# ForeverFurEver Agent Full Optimization — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Rewrite the ForeverFurEver AI shopping agent from hardcoded routing to LLM-driven decision-making with Gemini, ChromaDB knowledge retrieval, SQLite persistence, and a modern chat UI with product cards.

**Architecture:** 3-node LangGraph state graph (preprocess → agent ↔ tools → postprocess) replacing the current 7-node hardcoded pipeline. Gemini handles all routing/clarification/answering via function calling. ChromaDB + Gemini Embedding for knowledge retrieval. SQLite for conversation persistence. Vanilla HTML/CSS/JS frontend with product cards and dynamic buttons.

**Tech Stack:** Python 3.12, FastAPI, LangGraph, Google Generative AI (Gemini), ChromaDB, SQLite, Shopify Storefront GraphQL API

---

## Phase 1: Core Agent Restructure

### Task 1: Update dependencies

**Files:**
- Modify: `requirements.txt`

**Step 1: Replace requirements.txt**

```
fastapi
uvicorn
python-dotenv
langgraph
langchain-google-genai
google-generativeai
chromadb
requests
aiosqlite
```

Key changes:
- Remove: `openai`, `langchain-openai`
- Add: `langchain-google-genai`, `google-generativeai` (Gemini LLM + Embedding)
- Add: `chromadb` (vector knowledge base)
- Add: `aiosqlite` (required by LangGraph SqliteSaver)

**Step 2: Install dependencies**

Run: `cd /Users/zhangjiabei/PycharmProjects/ForeverFurEver-Agent && pip install -r requirements.txt`
Expected: All packages install successfully

**Step 3: Verify Gemini import works**

Run: `python -c "from langchain_google_genai import ChatGoogleGenerativeAI; print('OK')"`
Expected: `OK`

**Step 4: Commit**

```bash
git add requirements.txt
git commit -m "chore: switch dependencies from OpenAI to Gemini + add ChromaDB"
```

---

### Task 2: Create prompts.py

**Files:**
- Create: `ff_agent/prompts.py`

**Step 1: Write prompts.py**

```python
"""System prompt management for ForeverFurEver Agent."""

SYSTEM_PROMPT = """You are a customer service agent for ForeverFurEver (foreverfurever.org), a pet memorial products store.

## Language
- Default to English.
- Switch to Chinese if the user writes in Chinese.

## Behavior
- Use the provided tools to search products, check policies, and answer questions.
- ONLY recommend products returned by the search_products or get_collection tools. NEVER invent or hallucinate products.
- When user needs are unclear, ask 1-2 short clarifying questions (never more than 2).
- Keep responses concise: 2-4 sentences for answers, bullet points for product lists.
- When recommending products, always include the product title and price.

## Tone
- Warm, empathetic, and supportive — customers may be grieving the loss of a pet.
- Professional but not overly formal.
- Avoid overly cheerful or exclamatory language.

## Capabilities
- Product recommendations and search
- Policy inquiries (shipping, returns, customization)
- Product customization guidance (text-only engraving)
- General store questions and FAQ

## Product Recommendation Guidelines
- If the user mentions a budget, prioritize products within that budget.
- If no products match within budget, say so honestly and suggest the closest alternative.
- Always mention if a product supports personalization/engraving.
- When listing multiple products, use a brief bullet format with title + price.

## Constraints
- Do not process orders or payments.
- Do not access customer account information.
- For complex complaints or issues you cannot resolve, direct the customer to support@foreverfurever.org.
"""
```

**Step 2: Verify syntax**

Run: `python -c "from ff_agent.prompts import SYSTEM_PROMPT; print(len(SYSTEM_PROMPT), 'chars')"`
Expected: prints character count without error

**Step 3: Commit**

```bash
git add ff_agent/prompts.py
git commit -m "feat: add centralized system prompt module"
```

---

### Task 3: Upgrade shopify_storefront.py

**Files:**
- Modify: `ff_agent/shopify_storefront.py`

**Step 1: Rewrite shopify_storefront.py with image support and new endpoints**

The current file returns `{title, handle, available, price, url}`. Upgrade to also return `image_url`, `description`, and add `get_product_details()` and `get_collection()` functions.

```python
"""Shopify Storefront API client for ForeverFurEver."""

import os
import requests
from dotenv import load_dotenv

load_dotenv()

SHOP = os.getenv("SHOPIFY_STORE_DOMAIN")
TOKEN = os.getenv("SHOPIFY_STOREFRONT_TOKEN")
STORE_URL = "https://foreverfurever.org"

API_VERSION = "2024-07"
ENDPOINT = f"https://{SHOP}/api/{API_VERSION}/graphql.json"


def storefront_query(query: str, variables: dict | None = None) -> dict:
    if not SHOP or not TOKEN:
        raise RuntimeError("Missing SHOPIFY_STORE_DOMAIN or SHOPIFY_STOREFRONT_TOKEN in .env")

    resp = requests.post(
        ENDPOINT,
        headers={
            "Content-Type": "application/json",
            "X-Shopify-Storefront-Access-Token": TOKEN,
        },
        json={"query": query, "variables": variables or {}},
        timeout=20,
    )
    resp.raise_for_status()
    data = resp.json()

    if "errors" in data:
        raise RuntimeError(f"Shopify GraphQL errors: {data['errors']}")
    return data["data"]


def _node_to_product(node: dict) -> dict:
    """Convert a Shopify product node to our standard product dict."""
    price_info = node.get("priceRange", {}).get("minVariantPrice", {})
    images = node.get("images", {}).get("edges", [])
    image_url = images[0]["node"]["url"] if images else None

    return {
        "title": node["title"],
        "handle": node["handle"],
        "available": node.get("availableForSale", False),
        "price": f'{price_info.get("amount", "0")} {price_info.get("currencyCode", "USD")}',
        "url": f"{STORE_URL}/products/{node['handle']}",
        "image_url": image_url,
    }


_PRODUCT_FIELDS = """
    title
    handle
    availableForSale
    priceRange {
      minVariantPrice { amount currencyCode }
    }
    images(first: 1) {
      edges { node { url } }
    }
"""


def search_products(query: str, max_results: int = 6) -> list[dict]:
    """Search the Shopify store for products by keyword.
    Falls back to latest products if no results found.
    """
    query_text = (query or "").strip()
    results: list[dict] = []

    if query_text:
        q = f'title:*{query_text}* OR product_type:*{query_text}* OR tag:*{query_text}*'
        gql = f"""
        query SearchProducts($q: String!, $first: Int!) {{
          products(first: $first, query: $q, sortKey: UPDATED_AT, reverse: true) {{
            edges {{ node {{ {_PRODUCT_FIELDS} }} }}
          }}
        }}
        """
        data = storefront_query(gql, {"q": q, "first": max_results})
        for edge in data.get("products", {}).get("edges", []):
            results.append(_node_to_product(edge["node"]))

    # Fallback: return latest products
    if not results:
        gql = f"""
        query LatestProducts($first: Int!) {{
          products(first: $first, sortKey: UPDATED_AT, reverse: true) {{
            edges {{ node {{ {_PRODUCT_FIELDS} }} }}
          }}
        }}
        """
        data = storefront_query(gql, {"first": max_results})
        for edge in data.get("products", {}).get("edges", []):
            results.append(_node_to_product(edge["node"]))

    return results


def get_product_details(handle: str) -> dict | None:
    """Get detailed info for a single product by handle."""
    gql = """
    query ProductByHandle($handle: String!) {
      product(handle: $handle) {
        title
        handle
        description
        availableForSale
        priceRange {
          minVariantPrice { amount currencyCode }
        }
        images(first: 5) {
          edges { node { url altText } }
        }
        variants(first: 10) {
          edges {
            node {
              title
              availableForSale
              price { amount currencyCode }
            }
          }
        }
      }
    }
    """
    data = storefront_query(gql, {"handle": handle})
    product = data.get("product")
    if not product:
        return None

    price_info = product.get("priceRange", {}).get("minVariantPrice", {})
    images = [e["node"]["url"] for e in product.get("images", {}).get("edges", [])]
    variants = []
    for e in product.get("variants", {}).get("edges", []):
        v = e["node"]
        variants.append({
            "title": v["title"],
            "available": v["availableForSale"],
            "price": f'{v["price"]["amount"]} {v["price"]["currencyCode"]}',
        })

    return {
        "title": product["title"],
        "handle": product["handle"],
        "description": product.get("description", ""),
        "available": product.get("availableForSale", False),
        "price": f'{price_info.get("amount", "0")} {price_info.get("currencyCode", "USD")}',
        "url": f"{STORE_URL}/products/{product['handle']}",
        "images": images,
        "variants": variants,
    }


def get_collection(collection_handle: str, max_results: int = 12) -> list[dict]:
    """Browse products in a specific collection."""
    gql = f"""
    query CollectionProducts($handle: String!, $first: Int!) {{
      collection(handle: $handle) {{
        title
        products(first: $first) {{
          edges {{ node {{ {_PRODUCT_FIELDS} }} }}
        }}
      }}
    }}
    """
    data = storefront_query(gql, {"handle": collection_handle, "first": max_results})
    collection = data.get("collection")
    if not collection:
        return []

    return [
        _node_to_product(edge["node"])
        for edge in collection.get("products", {}).get("edges", [])
    ]
```

**Step 2: Verify the module loads**

Run: `python -c "from ff_agent.shopify_storefront import search_products, get_product_details, get_collection; print('OK')"`
Expected: `OK`

**Step 3: Commit**

```bash
git add ff_agent/shopify_storefront.py
git commit -m "feat: upgrade Shopify client with image support, product details, and collections"
```

---

### Task 4: Create tools.py

**Files:**
- Create: `ff_agent/tools.py`

**Step 1: Write tools.py with LangChain @tool definitions**

```python
"""LangGraph tools for the ForeverFurEver agent.

Each tool is a function that Gemini can call via function calling.
The agent autonomously decides when to invoke each tool.
"""

from langchain_core.tools import tool

from ff_agent.shopify_storefront import (
    search_products as _search_products,
    get_product_details as _get_product_details,
    get_collection as _get_collection,
)


@tool
def search_products(query: str, max_results: int = 6) -> list[dict]:
    """Search the Shopify store for products by keyword.

    Use this when a customer asks about products, wants recommendations,
    or mentions a specific type of item. Returns product title, price,
    availability, URL, and image.

    Args:
        query: Search keywords (e.g. "memorial", "urn", "keepsake", "engraved")
        max_results: Maximum number of results to return (default 6)
    """
    return _search_products(query, max_results)


@tool
def get_product_details(handle: str) -> dict:
    """Get detailed information about a specific product.

    Use this when a customer asks for more details about a particular product,
    wants to know about variants, customization options, or see more images.

    Args:
        handle: The product handle/slug (e.g. "eternal-glow-a-soulful-tribute")
    """
    result = _get_product_details(handle)
    if result is None:
        return {"error": f"Product '{handle}' not found"}
    return result


@tool
def get_collection(collection_name: str) -> list[dict]:
    """Browse products by collection or category.

    Use this when a customer wants to browse a specific category of products
    rather than search for something specific.

    Args:
        collection_name: The collection handle (e.g. "all", "memorial-urns", "keepsakes")
    """
    return _get_collection(collection_name)


# Collected list of all tools for the agent
ALL_TOOLS = [search_products, get_product_details, get_collection]
```

Note: `search_knowledge` tool will be added in Phase 2 after ChromaDB is set up.

**Step 2: Verify imports**

Run: `python -c "from ff_agent.tools import ALL_TOOLS; print(len(ALL_TOOLS), 'tools')"`
Expected: `3 tools`

**Step 3: Commit**

```bash
git add ff_agent/tools.py
git commit -m "feat: add LangChain tool definitions for Shopify operations"
```

---

### Task 5: Rewrite graph.py

**Files:**
- Modify: `ff_agent/graph.py` (full rewrite)

**Step 1: Rewrite graph.py with 3-node architecture + Gemini**

This is the core change. Replace the 7-node hardcoded graph with a 3-node LLM-driven graph.

```python
"""LangGraph state graph for the ForeverFurEver agent.

Architecture: preprocess → agent ↔ tools → postprocess
The agent (Gemini) autonomously decides when to search products,
ask clarification questions, or answer directly.
"""

import re
from typing import Annotated, Any

from langchain_core.messages import HumanMessage, AIMessage, BaseMessage, SystemMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from langgraph.graph import StateGraph, END
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
from langgraph.checkpoint.sqlite import SqliteSaver
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
        "messages": new_messages,  # add_messages will merge
    }


# ==========================
# Node: agent (Gemini + tools)
# ==========================

llm = ChatGoogleGenerativeAI(
    model="gemini-2.0-flash",
    temperature=0.3,
)

agent_with_tools = llm.bind_tools(ALL_TOOLS)


def agent_node(state: GraphState) -> dict:
    """Call Gemini with conversation history and tools."""
    messages = state["messages"]
    response = agent_with_tools.invoke(messages)
    return {"messages": [response]}


# ==========================
# Node: postprocess
# ==========================

def postprocess(state: GraphState) -> dict:
    """Extract product references and generate UI actions from the agent's response."""
    messages = state.get("messages", [])
    products: list[dict] = []
    ui_actions: list[dict] = []

    # Find the last AI message
    last_ai_msg = None
    for msg in reversed(messages):
        if isinstance(msg, AIMessage) and not msg.tool_calls:
            last_ai_msg = msg
            break

    if not last_ai_msg:
        return {"products": [], "ui_actions": []}

    content = last_ai_msg.content or ""

    # Extract product URLs mentioned in the response
    product_urls = re.findall(
        r"https://foreverfurever\.org/products/([\w-]+)", content
    )

    # Scan tool messages for product data to build cards
    for msg in messages:
        if hasattr(msg, "content") and isinstance(msg.content, str):
            # Tool responses contain product dicts as string
            pass
        if hasattr(msg, "artifact") and msg.artifact:
            pass

    # Build product cards from tool call results in message history
    seen_handles = set()
    for msg in messages:
        if hasattr(msg, "name") and msg.name in ("search_products", "get_collection", "get_product_details"):
            try:
                import json
                tool_data = json.loads(msg.content) if isinstance(msg.content, str) else msg.content
                if isinstance(tool_data, list):
                    for p in tool_data:
                        if isinstance(p, dict) and p.get("handle") and p["handle"] not in seen_handles:
                            seen_handles.add(p["handle"])
                            products.append(p)
                elif isinstance(tool_data, dict) and tool_data.get("handle"):
                    if tool_data["handle"] not in seen_handles:
                        seen_handles.add(tool_data["handle"])
                        products.append(tool_data)
            except (json.JSONDecodeError, TypeError):
                pass

    # Generate dynamic quick reply actions based on content
    content_lower = content.lower()

    # If agent is asking a question, suggest quick replies
    if "?" in content or "？" in content:
        if any(kw in content_lower for kw in ["budget", "price", "spend", "预算"]):
            ui_actions.append({"type": "quick_reply", "label": "Under $50", "value": "I'd like something under $50"})
            ui_actions.append({"type": "quick_reply", "label": "Under $100", "value": "I'd like something under $100"})
        elif any(kw in content_lower for kw in ["gift", "yourself", "personal", "送礼", "自用"]):
            ui_actions.append({"type": "quick_reply", "label": "It's a gift", "value": "It's a gift for someone"})
            ui_actions.append({"type": "quick_reply", "label": "For myself", "value": "It's for myself as a personal keepsake"})

    # Always offer browse all
    if products:
        ui_actions.append({
            "type": "open_url",
            "label": "Browse all products",
            "url": "https://foreverfurever.org/collections/all",
        })

    return {
        "products": products[:6],  # limit to 6 product cards
        "ui_actions": ui_actions,
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
    g.add_edge("tools", "agent")  # after tool execution, go back to agent
    g.add_edge("postprocess", END)

    return g.compile(checkpointer=checkpointer)
```

**Step 2: Verify the graph builds**

Run: `python -c "from ff_agent.graph import build_graph; g = build_graph(); print('Graph built OK')"`
Expected: `Graph built OK`

**Step 3: Commit**

```bash
git add ff_agent/graph.py
git commit -m "feat: rewrite LangGraph to 3-node architecture with Gemini tool calling"
```

---

### Task 6: Update api_server.py

**Files:**
- Modify: `ff_agent/api_server.py`

**Step 1: Rewrite api_server.py with new response structure and SQLite persistence**

```python
"""FastAPI server for the ForeverFurEver agent."""

import uuid
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from dotenv import load_dotenv
from langgraph.checkpoint.sqlite import SqliteSaver
from langchain_core.messages import HumanMessage, AIMessage

from ff_agent.graph import build_graph

load_dotenv()

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://foreverfurever.org",
        "https://www.foreverfurever.org",
        "http://127.0.0.1:8000",
        "http://localhost:8000",
        "https://foreverfurever.myshopify.com",
        "https://admin.shopify.com",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

PROJECT_ROOT = Path(__file__).resolve().parents[1]
STATIC_DIR = PROJECT_ROOT / "static"
DATA_DIR = PROJECT_ROOT / "data"

DATA_DIR.mkdir(exist_ok=True)

API_VERSION = "1.0.0"

# ---------- Static files ----------

@app.get("/")
def root():
    return FileResponse(STATIC_DIR / "chat.html")

app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

# ---------- Request/Response models ----------

class ChatRequest(BaseModel):
    message: str
    thread_id: str = ""

class FeedbackRequest(BaseModel):
    thread_id: str
    message_index: int = 0
    rating: str  # "helpful" | "not_helpful"
    comment: str = ""

# ---------- Graph initialization ----------

DB_PATH = str(DATA_DIR / "conversations.db")

# SqliteSaver for persistent conversation history
checkpointer = SqliteSaver.from_conn_string(DB_PATH)
graph = build_graph(checkpointer=checkpointer)

# ---------- Helpers ----------

def extract_response(state: dict) -> dict:
    """Build the API response from the final graph state."""
    messages = state.get("messages", [])
    products = state.get("products", [])
    ui_actions = state.get("ui_actions", [])

    # Find the last AI message (non-tool-call)
    content = ""
    for msg in reversed(messages):
        if isinstance(msg, AIMessage) and not msg.tool_calls:
            content = msg.content or ""
            break

    return {
        "type": "answer",
        "content": content,
        "products": products or [],
        "actions": ui_actions or [],
        "thread_id": state.get("thread_id", ""),
        "version": API_VERSION,
    }

# ---------- Endpoints ----------

@app.get("/health")
def health():
    return {"ok": True, "version": API_VERSION}


@app.post("/chat")
def chat(req: ChatRequest):
    thread_id = req.thread_id or str(uuid.uuid4())

    try:
        result = graph.invoke(
            {
                "messages": [HumanMessage(content=req.message)],
                "thread_id": thread_id,
            },
            config={"configurable": {"thread_id": thread_id}},
        )

        response = extract_response(result)
        response["thread_id"] = thread_id
        return response

    except Exception as e:
        return {
            "type": "error",
            "content": "Sorry, something went wrong. Please try again.",
            "products": [],
            "actions": [],
            "thread_id": thread_id,
            "version": API_VERSION,
            "error_detail": str(e),
        }


@app.post("/feedback")
def feedback(req: FeedbackRequest):
    # For now, log to stdout. Phase 4 can persist to DB.
    import logging
    logging.info(f"Feedback: thread={req.thread_id} rating={req.rating} comment={req.comment}")
    return {"ok": True}
```

**Step 2: Verify the server starts**

Run: `cd /Users/zhangjiabei/PycharmProjects/ForeverFurEver-Agent && timeout 5 python -c "from ff_agent.api_server import app; print('Server module OK')" || true`
Expected: `Server module OK`

**Step 3: Commit**

```bash
git add ff_agent/api_server.py
git commit -m "feat: update API server with new response structure, SQLite persistence, feedback endpoint"
```

---

### Task 7: Smoke test the core agent

**Step 1: Start the server locally and test with curl**

Run: `cd /Users/zhangjiabei/PycharmProjects/ForeverFurEver-Agent && python -m uvicorn ff_agent.api_server:app --port 8000 &`

Wait 3 seconds, then:

Run: `curl -s -X POST http://127.0.0.1:8000/chat -H "Content-Type: application/json" -d '{"message": "I want a pet memorial under $60"}' | python -m json.tool`

Expected: JSON response with `type: "answer"`, `content` containing product recommendations, `products` array with items from Shopify.

**Step 2: Test health endpoint**

Run: `curl -s http://127.0.0.1:8000/health`
Expected: `{"ok": true, "version": "1.0.0"}`

**Step 3: Test Chinese input**

Run: `curl -s -X POST http://127.0.0.1:8000/chat -H "Content-Type: application/json" -d '{"message": "我想买一个宠物纪念品，预算60美元以内"}' | python -m json.tool`

Expected: Response in Chinese with product recommendations.

**Step 4: Kill the server and commit**

Run: `kill %1 || true`

```bash
git add -A
git commit -m "test: verify core agent smoke test passes"
```

---

## Phase 2: Knowledge Base (ChromaDB + Gemini Embedding)

### Task 8: Create knowledge files

**Files:**
- Create: `knowledge/brand.md`
- Create: `knowledge/policies.md`
- Create: `knowledge/faq.md`

**Step 1: Create knowledge directory**

Run: `mkdir -p /Users/zhangjiabei/PycharmProjects/ForeverFurEver-Agent/knowledge`

**Step 2: Write brand.md**

Based on existing `docs/01_store_knowledge.md`, expand into English:

```markdown
# ForeverFurEver Brand Guide

## About Us
ForeverFurEver is an emotional pet memorial brand dedicated to helping pet owners honor and remember their beloved companions. We believe the bond with a pet doesn't end — it transforms into a lasting memory.

## Brand Values
- **Compassion**: We understand the grief of losing a pet and approach every interaction with empathy.
- **Quality**: Every product is crafted with care, designed to be a lasting tribute.
- **Personalization**: We offer text engraving to make each memorial uniquely meaningful.
- **Accompaniment**: We support customers through their grief journey, not just as a store but as a companion.

## Brand Voice
- Warm and supportive, never pushy or salesy
- Professional but approachable
- Avoid overly cheerful or exclamatory language
- Acknowledge the customer's feelings when appropriate
- Focus on the idea of "continuing the journey" with your pet's memory

## Website
- Official site: https://foreverfurever.org
- Contact: support@foreverfurever.org
```

**Step 3: Write policies.md**

```markdown
# ForeverFurEver Store Policies

## Shipping
- We ship to the United States and select international destinations.
- Standard processing time is 3-5 business days.
- Personalized/engraved items may take an additional 2-3 business days for processing.
- Tracking information is provided via email once the order ships.
- Free shipping on orders over $75 within the US.

## Returns & Refunds
- Standard (non-personalized) items can be returned within 30 days of delivery.
- Items must be unused and in original packaging.
- Personalized/engraved items are final sale and cannot be returned.
- To initiate a return, contact support@foreverfurever.org with your order number.
- Refunds are processed within 5-7 business days after we receive the returned item.

## Customization & Engraving
- We offer TEXT-ONLY engraving (no images or logos).
- Engraving is available in English and Chinese characters.
- Common engraving choices: pet's name, dates, short memorial phrases.
- Engraving is complimentary (free) on products that support it.
- Please double-check your text before submitting — engraved items cannot be modified after production.

## Payment
- We accept major credit cards (Visa, Mastercard, Amex), PayPal, and Shop Pay.
- All prices are in USD.
- Payment is processed securely through Shopify's checkout system.
```

**Step 4: Write faq.md**

```markdown
# Frequently Asked Questions

## Products

### What products do you sell?
We sell pet memorial products including memorial keepsakes, personalized night lights, and portable pet urns with engraving. All designed to honor and remember your beloved pet.

### Is the TravelStar Companion a traditional urn?
No. The TravelStar Companion is more of an emotional keepsake than a traditional ashes urn. It's portable and designed for people who want to keep a small part of their pet's memory close, whether at home or while traveling.

### Can I personalize my product?
Yes! We offer free text engraving on eligible products. You can add your pet's name, important dates, or a short memorial phrase. Engraving supports both English and Chinese characters.

### What is the Eternal Glow?
The Eternal Glow is a soulful tribute night light that can be customized with your pet's image and name. It creates a warm, comforting glow as a daily reminder of your pet. Priced around $47.

## Orders & Shipping

### How long does shipping take?
Standard orders ship within 3-5 business days. Personalized items may take an additional 2-3 days for engraving. You'll receive tracking info via email.

### Do you ship internationally?
Yes, we ship to select international destinations. Shipping times and costs vary by location.

### Can I track my order?
Yes, tracking information is sent to your email once the order ships.

## Returns

### Can I return a personalized item?
No, personalized/engraved items are final sale because they are custom-made for you. Please double-check your engraving text before placing the order.

### What is your return window?
Non-personalized items can be returned within 30 days of delivery, unused and in original packaging.

## Support

### How do I contact customer support?
Email us at support@foreverfurever.org. We typically respond within 24 hours on business days.

### I'm grieving the loss of my pet. Do you have any resources?
We understand how difficult it is to lose a beloved companion. We provide emotional support guides on our website and community resources to help you through this time. Remember, it's okay to grieve, and honoring your pet's memory is a beautiful way to celebrate the bond you shared.
```

**Step 5: Commit**

```bash
git add knowledge/
git commit -m "feat: add structured knowledge base files (brand, policies, FAQ)"
```

---

### Task 9: Create knowledge.py (ChromaDB wrapper)

**Files:**
- Create: `ff_agent/knowledge.py`

**Step 1: Write knowledge.py**

```python
"""ChromaDB-based knowledge retrieval for ForeverFurEver agent."""

import os
from pathlib import Path

import chromadb
from chromadb.utils.embedding_functions import GoogleGenerativeAiEmbeddingFunction

PROJECT_ROOT = Path(__file__).resolve().parents[1]
CHROMA_DIR = str(PROJECT_ROOT / "data" / "chroma")
KNOWLEDGE_DIR = PROJECT_ROOT / "knowledge"


def get_embedding_function():
    """Create Gemini embedding function for ChromaDB."""
    api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    if not api_key:
        raise RuntimeError("Missing GEMINI_API_KEY or GOOGLE_API_KEY in environment")
    return GoogleGenerativeAiEmbeddingFunction(
        api_key=api_key,
        model_name="models/text-embedding-004",
    )


def get_collection():
    """Get or create the knowledge ChromaDB collection."""
    client = chromadb.PersistentClient(path=CHROMA_DIR)
    embedding_fn = get_embedding_function()
    return client.get_or_create_collection(
        name="store_knowledge",
        embedding_function=embedding_fn,
    )


def search_knowledge(query: str, category: str = "all", n_results: int = 3) -> list[str]:
    """Search the knowledge base and return relevant text chunks.

    Args:
        query: The search query.
        category: Filter by category ('brand', 'policy', 'faq', or 'all').
        n_results: Number of results to return.

    Returns:
        List of relevant text chunks.
    """
    collection = get_collection()

    if collection.count() == 0:
        return ["Knowledge base is empty. Please run: python -m ff_agent.index_knowledge"]

    where_filter = None
    if category != "all":
        where_filter = {"category": category}

    results = collection.query(
        query_texts=[query],
        n_results=n_results,
        where=where_filter,
    )

    documents = results.get("documents", [[]])[0]
    return documents
```

**Step 2: Verify import**

Run: `python -c "from ff_agent.knowledge import search_knowledge; print('OK')"`
Expected: `OK`

**Step 3: Commit**

```bash
git add ff_agent/knowledge.py
git commit -m "feat: add ChromaDB knowledge retrieval module"
```

---

### Task 10: Create index_knowledge.py

**Files:**
- Create: `ff_agent/index_knowledge.py`

**Step 1: Write the indexing script**

```python
"""Index knowledge files into ChromaDB for retrieval.

Usage: python -m ff_agent.index_knowledge
"""

import re
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

from ff_agent.knowledge import get_collection, KNOWLEDGE_DIR


def split_markdown_sections(text: str) -> list[str]:
    """Split markdown into sections by headers. Each section includes its header."""
    sections = re.split(r"(?=^#{1,3} )", text, flags=re.MULTILINE)
    chunks = []
    for section in sections:
        section = section.strip()
        if len(section) > 20:  # skip tiny fragments
            chunks.append(section)
    return chunks


def infer_category(filename: str) -> str:
    """Infer knowledge category from filename."""
    name = filename.lower()
    if "brand" in name:
        return "brand"
    elif "polic" in name:
        return "policy"
    elif "faq" in name:
        return "faq"
    return "general"


def index_all():
    """Read all knowledge files, chunk them, and index into ChromaDB."""
    collection = get_collection()

    # Clear existing data for a clean re-index
    existing = collection.count()
    if existing > 0:
        all_ids = collection.get()["ids"]
        if all_ids:
            collection.delete(ids=all_ids)
        print(f"Cleared {existing} existing documents.")

    documents = []
    metadatas = []
    ids = []

    for filepath in sorted(KNOWLEDGE_DIR.glob("*.md")):
        print(f"Processing: {filepath.name}")
        text = filepath.read_text(encoding="utf-8")
        category = infer_category(filepath.name)
        chunks = split_markdown_sections(text)

        for i, chunk in enumerate(chunks):
            doc_id = f"{filepath.stem}_{i}"
            documents.append(chunk)
            metadatas.append({"category": category, "source": filepath.name})
            ids.append(doc_id)

    if not documents:
        print("No knowledge files found in", KNOWLEDGE_DIR)
        return

    # ChromaDB batch add
    collection.add(
        documents=documents,
        metadatas=metadatas,
        ids=ids,
    )

    print(f"Indexed {len(documents)} chunks from {len(list(KNOWLEDGE_DIR.glob('*.md')))} files.")


if __name__ == "__main__":
    index_all()
```

**Step 2: Run the indexer**

Run: `cd /Users/zhangjiabei/PycharmProjects/ForeverFurEver-Agent && python -m ff_agent.index_knowledge`
Expected: Output showing files processed and chunks indexed.

**Step 3: Verify search works**

Run: `python -c "from dotenv import load_dotenv; load_dotenv(); from ff_agent.knowledge import search_knowledge; results = search_knowledge('return policy'); print(results[0][:100] if results else 'empty')"`
Expected: Returns a chunk about return policy.

**Step 4: Commit**

```bash
git add ff_agent/index_knowledge.py data/
git commit -m "feat: add knowledge indexing script and initial ChromaDB data"
```

---

### Task 11: Integrate search_knowledge tool into the agent

**Files:**
- Modify: `ff_agent/tools.py` (add search_knowledge tool)
- Modify: `ff_agent/graph.py` (ALL_TOOLS now includes knowledge search)

**Step 1: Add search_knowledge to tools.py**

Append to the end of `ff_agent/tools.py`, before `ALL_TOOLS`:

```python
from ff_agent.knowledge import search_knowledge as _search_knowledge


@tool
def search_knowledge(query: str, category: str = "all") -> list[str]:
    """Search the store knowledge base for brand info, policies, and FAQ.

    Use this when a customer asks about store policies, shipping, returns,
    customization options, or general FAQ questions. Also use for brand
    information queries.

    Args:
        query: The search query describing what info is needed.
        category: Filter results by category. Options: 'brand', 'policy', 'faq', 'all'.
    """
    return _search_knowledge(query, category=category)
```

Update `ALL_TOOLS` to include it:

```python
ALL_TOOLS = [search_products, get_product_details, get_collection, search_knowledge]
```

**Step 2: Verify updated tools count**

Run: `python -c "from ff_agent.tools import ALL_TOOLS; print(len(ALL_TOOLS), 'tools:', [t.name for t in ALL_TOOLS])"`
Expected: `4 tools: ['search_products', 'get_product_details', 'get_collection', 'search_knowledge']`

**Step 3: Commit**

```bash
git add ff_agent/tools.py
git commit -m "feat: integrate search_knowledge tool with ChromaDB retrieval"
```

---

### Task 12: Test knowledge retrieval end-to-end

**Step 1: Start server and test a policy query**

Run: `cd /Users/zhangjiabei/PycharmProjects/ForeverFurEver-Agent && python -m uvicorn ff_agent.api_server:app --port 8000 &`

Wait 3 seconds, then:

Run: `curl -s -X POST http://127.0.0.1:8000/chat -H "Content-Type: application/json" -d '{"message": "What is your return policy for engraved items?"}' | python -m json.tool`

Expected: Response accurately states that engraved/personalized items are final sale, based on knowledge base retrieval.

**Step 2: Test FAQ query**

Run: `curl -s -X POST http://127.0.0.1:8000/chat -H "Content-Type: application/json" -d '{"message": "Is the TravelStar a traditional urn?"}' | python -m json.tool`

Expected: Response explains it's an emotional keepsake, not a traditional urn.

**Step 3: Kill server**

Run: `kill %1 || true`

---

## Phase 3: Frontend Upgrade

### Task 13: Rewrite chat.html

**Files:**
- Modify: `static/chat.html` (full rewrite)

**Step 1: Write the new chat.html with product cards, dynamic buttons, and typing indicator**

```html
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8" />
<meta name="viewport" content="width=device-width, initial-scale=1.0" />
<title>ForeverFurEver Agent</title>
<style>
* { box-sizing: border-box; margin: 0; padding: 0; }

body {
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
  background: #f5f5f5;
  color: #333;
}

#chat-box {
  width: 440px;
  max-width: 100vw;
  margin: 20px auto;
  background: #fff;
  border-radius: 16px;
  box-shadow: 0 4px 24px rgba(0,0,0,.08);
  display: flex;
  flex-direction: column;
  height: calc(100vh - 40px);
  max-height: 700px;
  overflow: hidden;
}

#chat-header {
  padding: 16px 20px;
  border-bottom: 1px solid #eee;
  font-weight: 600;
  font-size: 15px;
  color: #111;
}

#messages {
  flex: 1;
  overflow-y: auto;
  padding: 16px 20px;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.msg {
  max-width: 85%;
  padding: 10px 14px;
  border-radius: 12px;
  font-size: 14px;
  line-height: 1.5;
  word-wrap: break-word;
  white-space: pre-wrap;
}

.user {
  align-self: flex-end;
  background: #111;
  color: #fff;
  border-bottom-right-radius: 4px;
}

.ai {
  align-self: flex-start;
  background: #f0f0f0;
  color: #111;
  border-bottom-left-radius: 4px;
}

/* Typing indicator */
.typing {
  align-self: flex-start;
  padding: 10px 14px;
  background: #f0f0f0;
  border-radius: 12px;
  display: flex;
  gap: 4px;
}
.typing span {
  width: 6px; height: 6px;
  background: #999;
  border-radius: 50%;
  animation: bounce 1.2s infinite;
}
.typing span:nth-child(2) { animation-delay: 0.2s; }
.typing span:nth-child(3) { animation-delay: 0.4s; }
@keyframes bounce {
  0%, 80%, 100% { transform: translateY(0); }
  40% { transform: translateY(-6px); }
}

/* Product cards */
.product-cards {
  display: flex;
  gap: 10px;
  overflow-x: auto;
  padding: 8px 0;
  scroll-snap-type: x mandatory;
}
.product-cards::-webkit-scrollbar { height: 4px; }
.product-cards::-webkit-scrollbar-thumb { background: #ccc; border-radius: 2px; }

.product-card {
  min-width: 160px;
  max-width: 180px;
  border: 1px solid #e5e5e5;
  border-radius: 10px;
  overflow: hidden;
  flex-shrink: 0;
  scroll-snap-align: start;
  background: #fff;
}
.product-card img {
  width: 100%;
  height: 120px;
  object-fit: cover;
  background: #f5f5f5;
}
.product-card-body {
  padding: 8px 10px;
}
.product-card-title {
  font-size: 12px;
  font-weight: 600;
  line-height: 1.3;
  color: #111;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
.product-card-price {
  font-size: 13px;
  font-weight: 700;
  color: #111;
  margin-top: 4px;
}
.product-card-btn {
  display: block;
  width: 100%;
  padding: 6px;
  margin-top: 6px;
  border: 1px solid #111;
  border-radius: 6px;
  background: #fff;
  color: #111;
  font-size: 11px;
  font-weight: 600;
  cursor: pointer;
  text-align: center;
  text-decoration: none;
}
.product-card-btn:hover { background: #111; color: #fff; }

/* Actions / Quick replies */
#actions {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  padding: 0 20px 8px;
}

.quick-reply {
  padding: 8px 14px;
  border: 1px solid #ddd;
  border-radius: 20px;
  background: #fff;
  color: #333;
  font-size: 13px;
  cursor: pointer;
  transition: all 0.15s;
}
.quick-reply:hover { background: #111; color: #fff; border-color: #111; }

.url-btn {
  padding: 8px 14px;
  border: none;
  border-radius: 20px;
  background: #111;
  color: #fff;
  font-size: 13px;
  cursor: pointer;
  text-decoration: none;
}
.url-btn:hover { opacity: 0.85; }

/* Input area */
#input-area {
  display: flex;
  gap: 8px;
  padding: 12px 20px 16px;
  border-top: 1px solid #eee;
}

#input {
  flex: 1;
  padding: 10px 14px;
  border-radius: 10px;
  border: 1px solid #ddd;
  font-size: 14px;
  outline: none;
}
#input:focus { border-color: #111; }

#send {
  padding: 10px 18px;
  border-radius: 10px;
  border: none;
  background: #111;
  color: #fff;
  font-size: 14px;
  cursor: pointer;
  font-weight: 600;
}
#send:hover { opacity: 0.85; }

/* Animations */
.msg, .product-cards { animation: fadeIn 0.25s ease-out; }
@keyframes fadeIn {
  from { opacity: 0; transform: translateY(4px); }
  to { opacity: 1; transform: translateY(0); }
}

/* Responsive */
@media (max-width: 480px) {
  #chat-box { width: 100%; height: 100vh; max-height: none; margin: 0; border-radius: 0; }
}
</style>
</head>
<body>

<div id="chat-box">
  <div id="chat-header">ForeverFurEver</div>
  <div id="messages"></div>
  <div id="actions"></div>
  <div id="input-area">
    <input id="input" placeholder="Ask me anything..." />
    <button id="send">Send</button>
  </div>
</div>

<script>
// Use relative URL so it works both locally and on Render
const API_URL = window.location.origin + "/chat";

const messagesEl = document.getElementById("messages");
const actionsEl = document.getElementById("actions");
const inputEl = document.getElementById("input");
const sendBtn = document.getElementById("send");

// Generate a unique thread ID per browser session
let THREAD_ID = sessionStorage.getItem("ff_thread_id");
if (!THREAD_ID) {
  THREAD_ID = "t_" + Math.random().toString(36).slice(2, 10) + Date.now().toString(36);
  sessionStorage.setItem("ff_thread_id", THREAD_ID);
}

function addMessage(text, cls) {
  const div = document.createElement("div");
  div.className = "msg " + cls;
  div.textContent = text;
  messagesEl.appendChild(div);
  messagesEl.scrollTop = messagesEl.scrollHeight;
}

function showTyping() {
  const div = document.createElement("div");
  div.className = "typing";
  div.id = "typing-indicator";
  div.innerHTML = "<span></span><span></span><span></span>";
  messagesEl.appendChild(div);
  messagesEl.scrollTop = messagesEl.scrollHeight;
}

function hideTyping() {
  const el = document.getElementById("typing-indicator");
  if (el) el.remove();
}

function clearActions() {
  actionsEl.innerHTML = "";
}

function renderProducts(products) {
  if (!products || products.length === 0) return;

  const container = document.createElement("div");
  container.className = "product-cards";

  products.forEach(p => {
    const card = document.createElement("div");
    card.className = "product-card";

    const img = p.image_url
      ? `<img src="${p.image_url}" alt="${p.title}" />`
      : `<div style="width:100%;height:120px;background:#eee;display:flex;align-items:center;justify-content:center;color:#999;font-size:12px;">No image</div>`;

    const priceText = p.price ? "$" + parseFloat(p.price).toFixed(2) : "";

    card.innerHTML = `
      ${img}
      <div class="product-card-body">
        <div class="product-card-title">${p.title || "Product"}</div>
        <div class="product-card-price">${priceText}</div>
        <a class="product-card-btn" href="${p.url || "#"}" target="_blank">View Product</a>
      </div>
    `;
    container.appendChild(card);
  });

  messagesEl.appendChild(container);
  messagesEl.scrollTop = messagesEl.scrollHeight;
}

function renderActions(actions) {
  clearActions();
  if (!actions || actions.length === 0) return;

  actions.forEach(a => {
    if (a.type === "quick_reply") {
      const btn = document.createElement("button");
      btn.className = "quick-reply";
      btn.textContent = a.label || "Quick reply";
      btn.onclick = () => sendMessage(a.value || a.label);
      actionsEl.appendChild(btn);
    } else if (a.type === "open_url") {
      const link = document.createElement("a");
      link.className = "url-btn";
      link.textContent = a.label || "Open link";
      link.href = a.url || "#";
      link.target = "_blank";
      actionsEl.appendChild(link);
    }
  });
}

async function sendMessage(text) {
  text = (text || "").trim();
  if (!text) return;

  addMessage(text, "user");
  inputEl.value = "";
  clearActions();
  showTyping();

  try {
    const resp = await fetch(API_URL, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message: text, thread_id: THREAD_ID }),
    });
    const data = await resp.json();

    hideTyping();

    if (data.type === "error") {
      addMessage("Sorry, something went wrong. Please try again.", "ai");
      return;
    }

    if (data.content) {
      addMessage(data.content, "ai");
    }

    if (data.products && data.products.length > 0) {
      renderProducts(data.products);
    }

    if (data.actions && data.actions.length > 0) {
      renderActions(data.actions);
    }

    // Update thread_id if server assigned one
    if (data.thread_id) {
      THREAD_ID = data.thread_id;
      sessionStorage.setItem("ff_thread_id", THREAD_ID);
    }
  } catch (e) {
    hideTyping();
    addMessage("Network error. Please check your connection.", "ai");
  }
}

// Event listeners
sendBtn.onclick = () => sendMessage(inputEl.value);
inputEl.addEventListener("keydown", e => {
  if (e.key === "Enter") sendMessage(inputEl.value);
});

// Welcome message
addMessage("Hi! I'm here to help you find the perfect memorial for your beloved pet. Feel free to ask about our products, pricing, or policies.", "ai");
</script>
</body>
</html>
```

**Step 2: Verify the file renders**

Run: `cd /Users/zhangjiabei/PycharmProjects/ForeverFurEver-Agent && python -m uvicorn ff_agent.api_server:app --port 8000 &`

Open http://127.0.0.1:8000 in browser. Verify:
- Chat window renders with header, input, send button
- Welcome message appears
- Send a test message, verify typing indicator shows then response appears
- If products are returned, verify product cards render with images

Run: `kill %1 || true`

**Step 3: Commit**

```bash
git add static/chat.html
git commit -m "feat: redesign chat UI with product cards, dynamic actions, typing indicator"
```

---

## Phase 4: Integration, Tests, and Deployment

### Task 14: Update regression tests

**Files:**
- Modify: `scripts/regression_suite.py` (rewrite for new API)

**Step 1: Rewrite regression_suite.py**

```python
"""Regression test suite for ForeverFurEver Agent v1.0.

Tests the new Gemini-powered agent with tool calling.
Run: python scripts/regression_suite.py
"""

import sys
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from dotenv import load_dotenv
load_dotenv()

from langchain_core.messages import HumanMessage
from ff_agent.graph import build_graph

graph = build_graph()


TEST_CASES = [
    {
        "id": "product_budget",
        "message": "I want a pet memorial under $60.",
        "checks": {
            "has_content": True,
            "content_mentions_any": ["$", "product", "memorial", "recommend"],
        },
    },
    {
        "id": "policy_return",
        "message": "What's your return policy?",
        "checks": {
            "has_content": True,
            "content_mentions_any": ["return", "refund", "30 days", "day"],
        },
    },
    {
        "id": "customization",
        "message": "Can I engrave my dog's name on a product?",
        "checks": {
            "has_content": True,
            "content_mentions_any": ["engrav", "personal", "text", "name"],
        },
    },
    {
        "id": "chinese_query",
        "message": "我想买一个宠物纪念品，预算60美元以内",
        "checks": {
            "has_content": True,
        },
    },
    {
        "id": "product_detail",
        "message": "Tell me more about the Eternal Glow product.",
        "checks": {
            "has_content": True,
            "content_mentions_any": ["Eternal Glow", "eternal", "glow", "light"],
        },
    },
]


def extract_ai_content(state: dict) -> str:
    """Extract the final AI message content from state."""
    from langchain_core.messages import AIMessage
    for msg in reversed(state.get("messages", [])):
        if isinstance(msg, AIMessage) and not msg.tool_calls:
            return msg.content or ""
    return ""


def run_one(case: dict) -> dict:
    thread_id = f"test_{case['id']}"

    try:
        state = graph.invoke(
            {"messages": [HumanMessage(content=case["message"])]},
            config={"configurable": {"thread_id": thread_id}},
        )
    except Exception as e:
        return {"case_id": case["id"], "ok": False, "error": str(e), "content": ""}

    content = extract_ai_content(state)
    products = state.get("products", [])
    checks = case.get("checks", {})
    failures = []

    if checks.get("has_content") and not content.strip():
        failures.append("Expected non-empty content, got empty")

    if "content_mentions_any" in checks:
        keywords = checks["content_mentions_any"]
        content_lower = content.lower()
        if not any(kw.lower() in content_lower for kw in keywords):
            failures.append(f"Content doesn't mention any of {keywords}")

    return {
        "case_id": case["id"],
        "ok": len(failures) == 0,
        "failures": failures,
        "content": content[:200],
        "products_count": len(products),
    }


def main():
    reports = [run_one(c) for c in TEST_CASES]
    passed = sum(1 for r in reports if r["ok"])
    total = len(reports)

    print("\n" + "=" * 50)
    print(f"  Regression Suite: {passed}/{total} passed")
    print("=" * 50 + "\n")

    for r in reports:
        status = "PASS" if r["ok"] else "FAIL"
        print(f"  [{status}] {r['case_id']}")
        if not r["ok"]:
            for f in r.get("failures", []):
                print(f"    - {f}")
            if r.get("error"):
                print(f"    - Error: {r['error']}")
        print(f"    content: {r['content'][:100]}...")
        print(f"    products: {r.get('products_count', 0)}")
        print()

    sys.exit(0 if passed == total else 1)


if __name__ == "__main__":
    main()
```

**Step 2: Run the regression suite**

Run: `cd /Users/zhangjiabei/PycharmProjects/ForeverFurEver-Agent && python scripts/regression_suite.py`

Expected: All 5 tests pass. If any fail, investigate the specific failure and adjust (likely prompt tuning or tool description refinement).

**Step 3: Commit**

```bash
git add scripts/regression_suite.py
git commit -m "test: rewrite regression suite for new Gemini-powered agent"
```

---

### Task 15: Update .env and .gitignore

**Files:**
- Modify: `.env` (add GEMINI_API_KEY)
- Modify: `.gitignore` (add data/ directory)

**Step 1: Add GEMINI_API_KEY to .env**

Add to the `.env` file (DO NOT commit this):
```
GEMINI_API_KEY=your-gemini-api-key-here
```

Note: You can also use `GOOGLE_API_KEY` — the code checks both.

**Step 2: Update .gitignore**

Add these lines to `.gitignore`:
```
data/
*.db
```

This ensures the SQLite database and ChromaDB data directory are not committed.

**Step 3: Commit .gitignore only**

```bash
git add .gitignore
git commit -m "chore: ignore data directory and SQLite databases"
```

---

### Task 16: Final integration test and cleanup

**Step 1: Remove old unused code**

Verify these are no longer imported anywhere, then optionally keep `docs/01_store_knowledge.md` as reference:
- The old `URN_URL` / `KEEPSAKE_URL` constants in graph.py are gone (already removed in rewrite)
- `langchain-openai` / `openai` are removed from requirements

**Step 2: Full end-to-end test**

Run the full server:
```bash
cd /Users/zhangjiabei/PycharmProjects/ForeverFurEver-Agent
python -m ff_agent.index_knowledge  # re-index knowledge if needed
python -m uvicorn ff_agent.api_server:app --port 8000
```

Test manually in browser at http://127.0.0.1:8000:
1. "I want something under $60" → should get product recommendations with cards
2. "What's your return policy?" → should get accurate policy from knowledge base
3. "Can I engrave my cat's name?" → should explain customization options
4. "我想买纪念品" → should respond in Chinese
5. Multi-turn: "Show me urns" → "Tell me more about the first one" → should maintain context

**Step 3: Final commit**

```bash
git add -A
git commit -m "feat: complete v1.0 agent optimization - Gemini, ChromaDB, new UI"
```

---

## Summary of Files Changed

| File | Action | Phase |
|------|--------|-------|
| `requirements.txt` | Modify | 1 |
| `ff_agent/prompts.py` | Create | 1 |
| `ff_agent/shopify_storefront.py` | Rewrite | 1 |
| `ff_agent/tools.py` | Create | 1 |
| `ff_agent/graph.py` | Rewrite | 1 |
| `ff_agent/api_server.py` | Rewrite | 1 |
| `knowledge/brand.md` | Create | 2 |
| `knowledge/policies.md` | Create | 2 |
| `knowledge/faq.md` | Create | 2 |
| `ff_agent/knowledge.py` | Create | 2 |
| `ff_agent/index_knowledge.py` | Create | 2 |
| `static/chat.html` | Rewrite | 3 |
| `scripts/regression_suite.py` | Rewrite | 4 |
| `.gitignore` | Modify | 4 |
