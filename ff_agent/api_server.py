from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from pathlib import Path
from dotenv import load_dotenv
from fastapi.responses import FileResponse

from ff_agent.graph import build_graph

# ------------------------
# 基础初始化
# ------------------------

load_dotenv()

app = FastAPI()

PROJECT_ROOT = Path(__file__).resolve().parents[1]
STATIC_DIR = PROJECT_ROOT / "static"
DOCS_DIR = PROJECT_ROOT / "docs"

API_VERSION = "0.4.0"

# ------------------------
# 静态页面（前端聊天）
# ------------------------
@app.get("/")
def root():
    return FileResponse("static/chat.html")

app.mount(
    "/static",
    StaticFiles(directory=STATIC_DIR),
    name="static"
)

# ------------------------
# 数据结构
# ------------------------

class ChatRequest(BaseModel):
    message: str
    thread_id: str = "default"

# ------------------------
# 加载知识 + 构建 Agent
# ------------------------

KNOWLEDGE_PATH = DOCS_DIR / "01_store_knowledge.md"

def load_store_knowledge() -> str:
    if KNOWLEDGE_PATH.exists():
        return KNOWLEDGE_PATH.read_text(encoding="utf-8")
    return ""

def build_system_prompt(store_knowledge: str) -> str:
    return (
        "You are a compassionate assistant for an English-first pet memorial store (ForeverFurEver).\n"
        "Default to English unless user writes in Chinese.\n"
        "Personalization is TEXT-ONLY.\n\n"
        f"{store_knowledge}"
    )

store_knowledge = load_store_knowledge()
system_prompt = build_system_prompt(store_knowledge)

# ✅ 只初始化一次 Graph（很重要）
graph = build_graph(system_prompt)

# ------------------------
# 统一返回结构
# ------------------------

def make_response(result: dict, resp_type: str) -> dict:
    return {
        "type": resp_type,
        "intent": result.get("intent", "other"),
        "content": (
            result.get("answer", "")
            if resp_type == "answer"
            else result.get("clarification_question", "")
        ),
        "profile": result.get("profile", {}) or {},
        "actions": result.get("actions", []) or [],
        "products_debug": result.get("products_debug", []) or [],
        "tool_error": result.get("tool_error", None),
        "version": API_VERSION,
    }

# ------------------------
# Health check
# ------------------------

@app.get("/health")
def health():
    return {"ok": True, "version": API_VERSION}

# ------------------------
# Chat API（唯一入口）
# ------------------------

@app.post("/chat")
def chat(req: ChatRequest):
    try:
        result = graph.invoke(
            {"user_message": req.message},
            config={"configurable": {"thread_id": req.thread_id}}
        )

        if result.get("needs_clarification"):
            return make_response(result, "clarify")

        return make_response(result, "answer")

    except Exception as e:
        return {
            "type": "error",
            "intent": "other",
            "content": "Server error. Please try again.",
            "profile": {},
            "actions": [],
            "products_debug": [],
            "tool_error": str(e),
            "version": API_VERSION,
        }
