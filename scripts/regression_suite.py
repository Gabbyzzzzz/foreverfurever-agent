import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import json
from typing import Dict, Any, List
from ff_agent.graph import build_graph


# ====== 1) 和 api_server.py 保持一致的 system_prompt 生成方式 ======
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
KNOWLEDGE_PATH = PROJECT_ROOT / "docs" / "01_store_knowledge.md"

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

graph = build_graph(system_prompt)


# ====== 2) 一组固定测试问题（你后续可随时加） ======
TEST_CASES: List[Dict[str, Any]] = [
    {
        "id": "budget_only",
        "thread_id": "t_budget_only",
        "message": "I want something under $60.",
        "checks": {
            "must_have_fields": ["type", "intent", "content", "profile", "products_debug"],
            "must_not_invent_when_products_present": True,
        }
    },
    {
        "id": "urn_budget",
        "thread_id": "t_urn_budget",
        "message": "I need a pet urn for ashes under $60.",
        "checks": {
            "must_have_fields": ["type", "intent", "content", "products_debug","actions"],
            "must_not_invent_when_products_present": True,
            "must_have_urn_keepsake_actions": True
        }
    },
    {
        "id": "gift_budget",
        "thread_id": "t_gift_budget",
        "message": "I’m buying a gift under $60.",
        "checks": {
            "must_have_fields": ["type", "intent", "content", "profile", "products_debug"],
            "must_not_invent_when_products_present": True,
        }
    },
    {
        "id": "policy_short",
        "thread_id": "t_policy_short",
        "message": "What’s your return policy?",
        "checks": {
            "must_have_fields": ["type", "intent", "content"],
        }
    },
    {
        "id": "cn_budget",
        "thread_id": "t_cn_budget",
        "message": "我想买一个60刀以内的纪念品",
        "checks": {
            "must_have_fields": ["type", "intent", "content", "profile", "products_debug"],
        }
    },
]


# ====== 3) 通用断言工具 ======
def fail(msg: str) -> Dict[str, Any]:
    return {"ok": False, "reason": msg}

def ok() -> Dict[str, Any]:
    return {"ok": True, "reason": ""}

def assert_has_fields(resp: Dict[str, Any], fields: List[str]) -> Dict[str, Any]:
    missing = [f for f in fields if f not in resp]
    if missing:
        return fail(f"Missing fields: {missing}")
    return ok()

def extract_titles_from_debug(resp: Dict[str, Any]) -> List[str]:
    items = resp.get("products_debug") or []
    titles = []
    for it in items:
        t = it.get("title")
        if t:
            titles.append(t)
    return titles

def assert_no_invented_products(resp: Dict[str, Any]) -> Dict[str, Any]:
    """
    如果 products_debug 非空，则 content 中不应该出现 debug 列表之外的商品标题（粗略检查）。
    这是个“保守检查”：我们只检查是否提到了 debug 里完全不存在的 title 片段。
    """
    debug_titles = extract_titles_from_debug(resp)
    if not debug_titles:
        return ok()

    content = (resp.get("content") or "").lower()

    # 只要 content 提到了某个 debug title 的关键片段，就算通过。
    # 若 content 完全没提任何 debug title，也不一定失败（可能在追问），这里不强制。
    mentions_any = any(t.lower()[:20] in content for t in debug_titles if len(t) >= 20)
    if mentions_any:
        return ok()

    # 如果是 answer 且 debug 非空，但一个 debug title 都没提到，通常意味着模型可能在乱说
    if resp.get("type") == "answer":
        return fail("products_debug is non-empty, but content doesn't mention any debug product title (possible mismatch).")

    return ok()

def assert_has_urn_vs_keepsake_actions(resp: Dict[str, Any]) -> Dict[str, Any]:
    actions = resp.get("actions") or []
    labels = " ".join((a.get("label","") for a in actions)).lower()
    has_urn = "choose: urn" in labels
    has_keep = "choose: keepsake" in labels
    if has_urn and has_keep:
        return ok()
    return fail("Expected quick-choice actions for Urn vs Keepsake, but not found.")

# ====== 4) 运行并打印报告 ======
def run_one(case: Dict[str, Any]) -> Dict[str, Any]:
    thread_id = case["thread_id"]
    msg = case["message"]

    state = graph.invoke(
        {"user_message": msg},
        config={"configurable": {"thread_id": thread_id}}
    )

    # 模拟 api_server.py 的返回格式（你可以按需扩展）
    if state.get("needs_clarification"):
        resp = {
            "type": "clarify",
            "intent": state.get("intent", "other"),
            "content": state.get("clarification_question", ""),
            "profile": state.get("profile", {}),
            "products_debug": state.get("products_debug", []),
            "tool_error": state.get("tool_error"),
            "actions": state.get("actions", []),
        }
    else:
        resp = {
            "type": "answer",
            "intent": state.get("intent", "other"),
            "content": state.get("answer", ""),
            "profile": state.get("profile", {}),
            "products_debug": state.get("products_debug", []),
            "tool_error": state.get("tool_error"),
            "actions": state.get("actions", []),
        }

    # checks
    checks = case.get("checks", {})
    results = []

    if "must_have_fields" in checks:
        results.append(assert_has_fields(resp, checks["must_have_fields"]))

    if checks.get("must_not_invent_when_products_present"):
        results.append(assert_no_invented_products(resp))
    if checks.get("must_have_urn_keepsake_actions"):
        results.append(assert_has_urn_vs_keepsake_actions(resp))

    ok_all = all(r["ok"] for r in results)
    return {"case_id": case["id"], "ok": ok_all, "resp": resp, "checks": results}

def main():
    reports = [run_one(c) for c in TEST_CASES]
    passed = sum(1 for r in reports if r["ok"])
    total = len(reports)

    print("\n================ Regression Suite ================\n")
    print(f"Passed: {passed}/{total}\n")

    for r in reports:
        status = "✅ PASS" if r["ok"] else "❌ FAIL"
        print(f"{status}  {r['case_id']}")
        if not r["ok"]:
            for chk in r["checks"]:
                if not chk["ok"]:
                    print(f"  - {chk['reason']}")
        # 简短打印关键信息
        print(f"  type={r['resp'].get('type')} intent={r['resp'].get('intent')}")
        print(f"  content_snippet={json.dumps((r['resp'].get('content') or '')[:120])}")
        print(f"  products_debug_count={len(r['resp'].get('products_debug') or [])}")
        print()

    # 如果你想失败就退出非0（方便 CI），打开下面两行
    # import sys
    # sys.exit(0 if passed == total else 1)

if __name__ == "__main__":
    main()
