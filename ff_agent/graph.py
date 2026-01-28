# ff_agent/graph.py
import json
import re
from typing import TypedDict, Dict, Any, List, Literal, Optional

from langgraph.graph import StateGraph, END
from langchain_openai import ChatOpenAI
from langgraph.checkpoint.memory import MemorySaver

from ff_agent.shopify_storefront import search_products

# =========================
# 固定商品 URL（当前只有两个产品时最实用）
# =========================
URN_URL = "https://foreverfurever.org/products/travelstar-companion-portable-pet-urn-for-travel-hand-engraved-memorial-for-ashes-personalized-keepsake-for-dogs-cats"
KEEPSAKE_URL = "https://foreverfurever.org/products/personalized-pet-night-light-custom-relief-night-light-v2-0"

# =========================
# 1) Graph State
# =========================
class GraphState(TypedDict):
    user_message: str
    intent: Literal["product", "policy", "customization", "other"]
    answer: str
    needs_clarification: bool
    clarification_question: str
    profile: Dict[str, Any]

    # Debug / Observability
    products_debug: List[Dict[str, Any]]
    tool_error: Optional[str]

    # Frontend actions
    actions: List[Dict[str, Any]]


# =========================
# 2) Router：识别意图
# =========================
def route_intent(state: GraphState) -> GraphState:
    msg_raw = state["user_message"]
    msg_lower = msg_raw.lower()

    # English routing
    if any(k in msg_lower for k in ["shipping", "return", "refund", "policy", "exchange", "warranty"]):
        state["intent"] = "policy"
    elif any(k in msg_lower for k in ["custom", "personal", "engrave", "engraving", "text", "wording", "message"]):
        state["intent"] = "customization"
    elif any(k in msg_lower for k in ["price", "size", "material", "order", "product", "box", "recommend", "suggest", "gift"]):
        state["intent"] = "product"
    else:
        # Chinese lightweight routing
        if any(k in msg_raw for k in ["运费", "退换", "退款", "政策", "质保"]):
            state["intent"] = "policy"
        elif any(k in msg_raw for k in ["定制", "刻字", "文字", "个性化"]):
            state["intent"] = "customization"
        elif any(k in msg_raw for k in ["推荐", "送人", "礼物", "价格", "尺寸", "材质", "下单", "产品", "盒子"]):
            state["intent"] = "product"
        else:
            state["intent"] = "other"

    state.setdefault("profile", {})
    # Always init these to avoid missing fields downstream
    state.setdefault("products_debug", [])
    state.setdefault("tool_error", None)
    state.setdefault("actions", [])
    state.setdefault("answer", "")
    state.setdefault("needs_clarification", False)
    state.setdefault("clarification_question", "")

    return state


# =========================
# 3) Extract profile
# =========================
def extract_profile(state: GraphState) -> GraphState:
    state.setdefault("profile", {})
    msg = state["user_message"]
    profile = state["profile"]

    # ---------- ✅ 规则兜底：先稳定抽 budget ----------
    import re
    m = re.search(r"(under|below|less than)\s*\$?\s*(\d+(\.\d+)?)", msg.lower())
    if m and not profile.get("budget"):
        profile["budget"] = f"under ${m.group(2)}"

    m2 = re.search(r"\$\s*(\d+(\.\d+)?)", msg)
    if m2 and not profile.get("budget"):
        profile["budget"] = f"${m2.group(1)}"

    m3 = re.search(r"\b(\d+(\.\d+)?)\b", msg)
    if ("budget" in msg.lower() or "under" in msg.lower() or "below" in msg.lower()) and m3 and not profile.get("budget"):
        profile["budget"] = f"under ${m3.group(1)}"

    # ---------- 原来的 LLM 抽取（保留） ----------
    llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)

    prompt = (
        "Extract shopping preferences from the user's message.\n"
        "Return ONLY valid JSON with these keys (use null if unknown):\n"
        "{"
        "\"budget\": null, "
        "\"occasion\": null, "
        "\"style\": null, "
        "\"deadline\": null, "
        "\"engraving_language\": null, "
        "\"engraving_text\": null"
        "}\n\n"
        f"User message:\n{msg}"
    )

    resp = llm.invoke(prompt).content

    try:
        extracted = json.loads(resp)
        for k, v in extracted.items():
            if v is not None and v != "":
                profile[k] = v
    except Exception:
        pass

    state["profile"] = profile
    return state

def apply_choice(state: GraphState) -> GraphState:
    msg = (state.get("user_message") or "").strip().lower()
    state.setdefault("profile", {})

    # 只处理我们自己的按钮指令
    if msg.startswith("#choice:occasion="):
        val = msg.replace("#choice:occasion=", "").strip()
        if val in ["gift", "self", "other"]:
            state["profile"]["occasion"] = val

        # ✅ 可选：把 user_message 清空，避免 LLM 把这串当成自然语言
        state["user_message"] = ""

    return state
# =========================
# Helpers: budget parsing + filtering
# =========================
def parse_budget_usd(budget_value: Any) -> Optional[float]:
    """Parse 'under $60' / '$60' / '60' / 'below 60' into 60.0"""
    if not budget_value:
        return None
    s = str(budget_value).lower().strip()
    m = re.search(r"(\d+(\.\d+)?)", s)
    if not m:
        return None
    try:
        return float(m.group(1))
    except Exception:
        return None


def _price_amount(p: Dict[str, Any]) -> Optional[float]:
    """p['price'] like '47.00 USD'"""
    try:
        return float(str(p.get("price", "")).split()[0])
    except Exception:
        return None


def filter_products_by_budget(
    products: List[Dict[str, Any]],
    max_usd: Optional[float]
) -> tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """Return (within_budget, over_budget)"""
    if not max_usd:
        return products, []

    ok: List[Dict[str, Any]] = []
    over: List[Dict[str, Any]] = []
    for p in products:
        amt = _price_amount(p)
        if amt is None:
            ok.append(p)  # keep unknown price rather than dropping
        elif amt <= max_usd:
            ok.append(p)
        else:
            over.append(p)
    return ok, over


# =========================
# 4) 是否需要追问（轻量规则）
# =========================
def needs_clarification(state: GraphState) -> GraphState:
    msg = state["user_message"].strip()
    intent = state["intent"]
    profile = state.get("profile", {})

    state["needs_clarification"] = False
    state["clarification_question"] = ""

    if intent in ["product", "other"]:
        # ✅ 4.2 主线：如果只有预算，没有用途（occasion），强制走导购分流
        if profile.get("budget") and not profile.get("occasion"):
            state["needs_clarification"] = True
            return state

        has_key_info = any(profile.get(k) for k in ["budget", "style", "occasion", "deadline"])
        if len(msg) < 25 and not has_key_info:
            state["needs_clarification"] = True

    if intent == "customization":
        # Keep it conservative: needs at least one of these to proceed
        if not profile.get("engraving_language") or not profile.get("engraving_text"):
            state["needs_clarification"] = True

    if intent == "policy" and len(msg) < 15:
        state["needs_clarification"] = True

    return state


# =========================
# 5) Clarify Node
# =========================
def clarify_node(state: GraphState, system_prompt: str) -> GraphState:
    user_msg = state["user_message"]
    profile = state.get("profile", {}) or {}

    # 简单判断语言：用户包含中文就用中文追问
    is_cn = any('\u4e00' <= ch <= '\u9fff' for ch in user_msg)

    # ✅ 4.2：导购分流（Gift vs Personal keepsake）
    # 条件：用户提到了预算，但 profile 里还没有 occasion
    if profile.get("budget") and not profile.get("occasion"):
        state["needs_clarification"] = True

        if is_cn:
            state["clarification_question"] = "这是送礼（Gift）还是给自己留作纪念（Personal keepsake）呢？"
            state["actions"] = [
                {"type": "reply", "label": "🎁 送礼 Gift", "value": "It's a gift."},
                {"type": "reply", "label": "🐾 自用纪念 Personal keepsake", "value": "For myself / personal keepsake."},
            ]
        else:
            state["clarification_question"] = "Is this for a gift, or for your own keepsake?"
            state["actions"] = [
                {"type": "reply", "label": "🎁 Gift", "value": "It's a gift."},
                {"type": "reply", "label": "🐾 Personal keepsake", "value": "For myself / personal keepsake."},
            ]

        state["answer"] = ""
        return state

    # ---------------------------
    # 原来的 LLM 追问（保留兜底）
    # ---------------------------
    llm = ChatOpenAI(model="gpt-4o-mini", temperature=0.3)

    intent = state["intent"]
    prompt = (
        f"{system_prompt}\n\n"
        "Task: Ask concise clarification question(s) only.\n"
        "Rules:\n"
        "- Ask at most 2 questions.\n"
        "- Keep it short and friendly.\n"
        "- If user is Chinese, ask in Chinese.\n"
        "- Do NOT answer the user yet.\n"
        "- Ask ONLY for missing critical info based on the profile.\n\n"
        f"Known user profile (may be incomplete): {profile}\n"
        f"User intent: {intent}\n"
        f"User message: {user_msg}\n\n"
        "Output ONLY the question(s)."
    )

    resp = llm.invoke(prompt)
    state["clarification_question"] = resp.content
    state["answer"] = ""
    state["actions"] = [
        {"type": "set_profile", "label": "🎁 Gift", "patch": {"occasion": "gift"}},
        {"type": "set_profile", "label": "🐾 Personal keepsake", "patch": {"occasion": "self"}},
    ]

    return state

# =========================
# 6) Answer Node
# =========================
def answer_node(state: GraphState, system_prompt: str) -> GraphState:
    llm = ChatOpenAI(model="gpt-4o-mini", temperature=0.4)

    intent = state["intent"]
    user_msg = state["user_message"]
    profile = state.get("profile", {})

    # --- Step 1: keyword strategy ---
    products: List[Dict[str, Any]] = []
    state["tool_error"] = None

    # We only call Shopify for these intents
    if intent in ["product", "other", "customization"]:
        text = (user_msg + " " + json.dumps(profile, ensure_ascii=False)).lower()

        if any(k in text for k in ["ash", "ashes", "urn", "memorial", "tribute"]):
            search_kw = "memorial"
        elif any(k in text for k in ["engrave", "engraving", "custom", "personal", "personalize", "text", "message"]):
            search_kw = "personalized"
        else:
            # no clear category => use empty query => fallback latest
            search_kw = ""

        try:
            products = search_products(search_kw, first=12 if search_kw == "" else 6)
        except Exception as e:
            products = []
            state["tool_error"] = str(e)

    # --- Step 2: budget filtering ---
    max_budget = parse_budget_usd(profile.get("budget"))
    products_in_budget, products_over_budget = filter_products_by_budget(products, max_budget)

    # If user has a budget but budget list empty, do another safe fallback query
    if max_budget and len(products_in_budget) == 0:
        try:
            products_fallback = search_products("", first=12)
            products_in_budget, products_over_budget = filter_products_by_budget(products_fallback, max_budget)
            products = products_fallback
        except Exception as e:
            # keep original products empty, record error
            state["tool_error"] = state["tool_error"] or str(e)

    # LLM sees: within budget first, plus at most 1 over-budget alternative
    products_for_llm = (products_in_budget[:3] + products_over_budget[:1]) if (products_in_budget or products_over_budget) else []
    state["products_debug"] = products_for_llm

    # --- Step 3: prompt ---
    prompt = (
        f"{system_prompt}\n\n"
        f"User intent: {intent}\n"
        f"User message: {user_msg}\n"
        f"Known user profile: {profile}\n\n"
        f"Shopify products (ground truth, budget-filtered): {products_for_llm}\n"
        f"User budget parsed (USD): {max_budget}\n\n"
        "STRICT RULES (must follow):\n"
        "1) If Shopify products list is NOT empty, recommend ONLY from that list.\n"
        "   - Use exact titles/prices/links from the list.\n"
        "2) If user provided a budget, prioritize items within budget.\n"
        "   - If none are within budget, say so and show at most 1 closest alternative above budget.\n"
        "3) If user is vague (e.g., only says 'under $60' without saying what they want), ask ONE short clarifying question:\n"
        "   - Example: 'Are you looking for a pet urn for ashes, or a memorial keepsake like a night light?'\n"
        "   - Still provide 1 best budget-friendly suggestion if available.\n"
        "4) Keep the answer short and clean formatting:\n"
        "   - No markdown headings like '###'\n"
        "   - Prefer 2–4 bullet points max\n"
        "5) Never invent product names, prices, or availability.\n\n"
        "Respond accordingly."
    )

    resp = llm.invoke(prompt)
    state["answer"] = resp.content

    # --- Step 4: actions (3.9.5) ---
    if state.get("actions"):
        return state
    actions: List[Dict[str, Any]] = []
    content_lc = (state.get("answer") or "").lower()
    user_lc = (user_msg or "").lower()

    # detect binary choice either from model output or user message
    needs_choice = (
        ("are you looking for" in content_lc and ("urn" in content_lc or "keepsake" in content_lc or "night light" in content_lc))
        or ("urn" in content_lc and "night light" in content_lc)
        or ("urn" in content_lc and "keepsake" in content_lc)
        or ("urn" in user_lc or "ashes" in user_lc) and ("under $" in user_lc or "budget" in user_lc or "cheap" in user_lc)
    )

    if needs_choice:
        actions.append({"type": "open_product", "label": "Choose: Urn (engraving)", "url": URN_URL})
        actions.append({"type": "open_product", "label": "Choose: Keepsake (night light)", "url": KEEPSAKE_URL})
    else:
        # up to 2 product links from debug list
        for p in (state.get("products_debug") or [])[:2]:
            url = p.get("url")
            title = p.get("title") or "Product"
            if url:
                actions.append({
                    "type": "open_product",
                    "label": f"View: {title}"[:40],
                    "url": url
                })

    actions.append({
        "type": "open_collection",
        "label": "Browse all products",
        "url": "https://foreverfurever.org/collections/all"
    })

    state["actions"] = actions
    return state


# =========================
# 7) Build Graph
# =========================
def build_graph(system_prompt: str):
    g = StateGraph(GraphState)

    g.add_node("router", route_intent)
    g.add_node("extract_profile", extract_profile)
    g.add_node("check_clarify", needs_clarification)
    g.add_node("clarify", lambda s: clarify_node(s, system_prompt))
    g.add_node("answer", lambda s: answer_node(s, system_prompt))
    g.add_node("apply_choice", apply_choice)

    g.set_entry_point("router")
    g.add_edge("router", "apply_choice")
    g.add_edge("apply_choice", "extract_profile")
    g.add_edge("extract_profile", "check_clarify")

    def route_after_check(state: GraphState):
        return "clarify" if state.get("needs_clarification") else "answer"

    g.add_conditional_edges(
        "check_clarify",
        route_after_check,
        {"clarify": "clarify", "answer": "answer"},
    )

    g.add_edge("clarify", END)
    g.add_edge("answer", END)

    checkpointer = MemorySaver()
    return g.compile(checkpointer=checkpointer)
