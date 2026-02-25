"""FastAPI server for the ForeverFurEver agent."""

from __future__ import annotations

import json
import logging
import os
import threading
import time
import uuid
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from langchain_core.messages import AIMessage, HumanMessage
from langgraph.checkpoint.memory import MemorySaver
from pydantic import BaseModel

from ff_agent.graph import build_graph

load_dotenv()

app = FastAPI()

_default_origins = [
    "https://foreverfurever.org",
    "https://www.foreverfurever.org",
    "http://127.0.0.1:8000",
    "http://localhost:8000",
    "https://foreverfurever.myshopify.com",
    "https://admin.shopify.com",
]
# Allow adding extra origins via env var (comma-separated)
_extra = os.getenv("CORS_EXTRA_ORIGINS", "")
if _extra:
    _default_origins.extend(o.strip() for o in _extra.split(",") if o.strip())

app.add_middleware(
    CORSMiddleware,
    allow_origins=_default_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

PROJECT_ROOT = Path(__file__).resolve().parents[1]
STATIC_DIR = PROJECT_ROOT / "static"
DATA_DIR = PROJECT_ROOT / "data"

DATA_DIR.mkdir(exist_ok=True)

API_VERSION = "1.1.0"

# ---------- Rate limiting ----------

RATE_LIMIT_WINDOW = 60  # seconds
RATE_LIMIT_MAX = int(os.getenv("RATE_LIMIT_MAX", "15"))
_rate_limits: dict[str, list[float]] = defaultdict(list)


@app.middleware("http")
async def rate_limit_middleware(request: Request, call_next):
    if request.url.path in ("/chat", "/chat/stream"):
        client_ip = request.client.host if request.client else "unknown"
        now = time.time()
        _rate_limits[client_ip] = [
            t for t in _rate_limits[client_ip] if now - t < RATE_LIMIT_WINDOW
        ]
        if len(_rate_limits[client_ip]) >= RATE_LIMIT_MAX:
            return JSONResponse(
                status_code=429,
                content={"detail": "Too many requests. Please wait a moment."},
            )
        _rate_limits[client_ip].append(now)
    return await call_next(request)


# ---------- Static files ----------

@app.get("/")
def root():
    return FileResponse(STATIC_DIR / "chat.html")


@app.get("/admin")
def admin_page():
    return FileResponse(STATIC_DIR / "admin.html")


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

checkpointer = MemorySaver()
graph = build_graph(checkpointer=checkpointer)

# ---------- Conversation logging ----------

CONV_LOG = DATA_DIR / "conversations.jsonl"


def log_conversation(thread_id: str, user_msg: str, ai_response: str, products: list):
    entry = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "thread_id": thread_id,
        "user": user_msg,
        "ai": ai_response[:500],
        "products": [p.get("title", "") for p in products],
    }
    try:
        with open(CONV_LOG, "a") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except Exception:
        pass


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
        log_conversation(thread_id, req.message, response["content"], response["products"])
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


# ---------- SSE Streaming endpoint ----------

@app.post("/chat/stream")
async def chat_stream(req: ChatRequest):
    thread_id = req.thread_id or str(uuid.uuid4())

    async def event_generator():
        yield f"data: {json.dumps({'type': 'start', 'thread_id': thread_id})}\n\n"

        input_data = {
            "messages": [HumanMessage(content=req.message)],
            "thread_id": thread_id,
        }
        config = {"configurable": {"thread_id": thread_id}}

        full_content = ""
        products = []
        actions = []

        try:
            async for event in graph.astream_events(
                input_data, config=config, version="v2"
            ):
                kind = event.get("event", "")

                # Stream LLM tokens as they arrive
                if kind == "on_chat_model_stream":
                    chunk = event.get("data", {}).get("chunk")
                    if (
                        chunk
                        and hasattr(chunk, "content")
                        and chunk.content
                        and not getattr(chunk, "tool_call_chunks", None)
                    ):
                        full_content += chunk.content
                        yield f"data: {json.dumps({'type': 'token', 'text': chunk.content})}\n\n"

                # Capture products and actions from postprocess
                elif kind == "on_chain_end" and event.get("name") == "postprocess":
                    output = event.get("data", {}).get("output", {})
                    products = output.get("products", [])
                    actions = output.get("ui_actions", [])
                    if products:
                        yield f"data: {json.dumps({'type': 'products', 'products': products})}\n\n"
                    if actions:
                        yield f"data: {json.dumps({'type': 'actions', 'actions': actions})}\n\n"

        except Exception as e:
            logging.exception("Stream error")
            yield f"data: {json.dumps({'type': 'error', 'text': 'Sorry, something went wrong. Please try again.'})}\n\n"

        log_conversation(thread_id, req.message, full_content, products)
        yield f"data: {json.dumps({'type': 'done'})}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


# ---------- Feedback ----------

@app.post("/feedback")
def feedback(req: FeedbackRequest):
    entry = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "thread_id": req.thread_id,
        "rating": req.rating,
        "comment": req.comment,
    }
    logging.info(f"Feedback: {json.dumps(entry)}")
    try:
        with open(DATA_DIR / "feedback.jsonl", "a") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except Exception:
        pass
    return {"ok": True}


# ---------- Admin: Knowledge sync ----------

_sync_status = {"running": False, "last_result": None}


@app.post("/admin/sync-knowledge")
def sync_knowledge_endpoint(authorization: str = Header()):
    admin_token = os.getenv("ADMIN_TOKEN")
    if not admin_token:
        raise HTTPException(status_code=500, detail="ADMIN_TOKEN not configured")

    expected = f"Bearer {admin_token}"
    if authorization != expected:
        raise HTTPException(status_code=401, detail="Unauthorized")

    if _sync_status["running"]:
        return {"ok": True, "status": "already_running", "message": "同步正在进行中，请稍后查看结果"}

    def run_sync():
        from ff_agent.notion_sync import sync_knowledge as do_sync
        _sync_status["running"] = True
        try:
            results = do_sync()
            _sync_status["last_result"] = {
                "ok": True,
                "synced": results["synced"],
                "skipped": results["skipped"],
                "errors": results["errors"],
            }
        except Exception as e:
            logging.exception("Sync error")
            _sync_status["last_result"] = {"ok": False, "error": str(e)}
        finally:
            _sync_status["running"] = False

    threading.Thread(target=run_sync, daemon=True).start()
    return {"ok": True, "status": "started", "message": "同步已开始，请稍后查看结果"}


@app.get("/admin/sync-status")
def sync_status(authorization: str = Header()):
    admin_token = os.getenv("ADMIN_TOKEN")
    if not admin_token or authorization != f"Bearer {admin_token}":
        raise HTTPException(status_code=401, detail="Unauthorized")

    return {
        "running": _sync_status["running"],
        "last_result": _sync_status["last_result"],
    }
