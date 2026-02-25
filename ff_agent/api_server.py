"""FastAPI server for the ForeverFurEver agent."""

from __future__ import annotations

import logging
import sqlite3
import uuid
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from langchain_core.messages import AIMessage, HumanMessage
from langgraph.checkpoint.sqlite import SqliteSaver
from pydantic import BaseModel

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

_conn = sqlite3.connect(DB_PATH, check_same_thread=False)
checkpointer = SqliteSaver(conn=_conn)
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
        logging.exception("Chat error")
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
    logging.info(f"Feedback: thread={req.thread_id} rating={req.rating} comment={req.comment}")
    return {"ok": True}
