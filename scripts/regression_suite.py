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

from langchain_core.messages import HumanMessage, AIMessage
from ff_agent.graph import build_graph

graph = build_graph()


TEST_CASES = [
    {
        "id": "product_budget",
        "message": "I want a pet memorial under $60.",
        "checks": {
            "has_content": True,
            "content_mentions_any": ["$", "product", "memorial", "recommend", "Eternal", "Glow"],
        },
    },
    {
        "id": "policy_return",
        "message": "What's your return policy?",
        "checks": {
            "has_content": True,
            "content_mentions_any": ["return", "refund", "30 days", "day", "policy"],
        },
    },
    {
        "id": "customization",
        "message": "Can I engrave my dog's name on a product?",
        "checks": {
            "has_content": True,
            "content_mentions_any": ["engrav", "personal", "text", "name", "custom"],
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
            "content_mentions_any": ["Eternal Glow", "eternal", "glow", "light", "night"],
        },
    },
]


def extract_ai_content(state: dict) -> str:
    """Extract the final AI message content from state."""
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
        return {"case_id": case["id"], "ok": False, "failures": [f"Exception: {e}"], "content": "", "products_count": 0}

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
        print(f"    content: {r['content'][:100]}...")
        print(f"    products: {r.get('products_count', 0)}")
        print()

    sys.exit(0 if passed == total else 1)


if __name__ == "__main__":
    main()
