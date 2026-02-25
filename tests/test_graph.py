"""Tests for graph postprocess logic."""

import json

from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from ff_agent.graph import postprocess


def _make_state(ai_content, tool_products=None, user_messages=None, viewed_handles=None):
    """Build a minimal GraphState dict for testing postprocess."""
    messages = []

    if user_messages:
        for text in user_messages:
            messages.append(HumanMessage(content=text))

    if tool_products:
        messages.append(ToolMessage(
            content=json.dumps(tool_products),
            tool_call_id="test-call",
        ))

    messages.append(AIMessage(content=ai_content))

    return {
        "messages": messages,
        "viewed_handles": viewed_handles or [],
    }


# ---------- No quick reply buttons ----------

def test_no_quick_reply_buttons():
    """Quick reply buttons (gift/budget) were removed."""
    state = _make_state(
        "Is this a gift for someone or for yourself? What's your budget?",
        user_messages=["I want a memorial"],
    )
    result = postprocess(state)
    labels = [a["label"] for a in result["ui_actions"]]
    assert "It's a gift" not in labels
    assert "For myself" not in labels
    assert "Under $50" not in labels
    assert "Under $100" not in labels


# ---------- Product deduplication ----------

def test_products_extracted_from_tool_messages():
    products = [
        {"title": "Eternal Glow", "handle": "eternal-glow", "price": "49.99"},
        {"title": "TravelStar", "handle": "travelstar", "price": "39.99"},
    ]
    state = _make_state("Here are our products:", tool_products=products)
    result = postprocess(state)
    assert len(result["products"]) == 2


def test_previously_viewed_products_filtered():
    products = [
        {"title": "Eternal Glow", "handle": "eternal-glow"},
        {"title": "TravelStar", "handle": "travelstar"},
    ]
    state = _make_state(
        "Here are our products:",
        tool_products=products,
        viewed_handles=["eternal-glow"],
    )
    result = postprocess(state)
    assert len(result["products"]) == 1
    assert result["products"][0]["handle"] == "travelstar"


def test_all_viewed_shows_nothing():
    products = [
        {"title": "Eternal Glow", "handle": "eternal-glow"},
        {"title": "TravelStar", "handle": "travelstar"},
    ]
    state = _make_state(
        "Here are our products:",
        tool_products=products,
        viewed_handles=["eternal-glow", "travelstar"],
    )
    result = postprocess(state)
    assert len(result["products"]) == 0


def test_browse_all_button_only_with_products():
    state = _make_state("I can help with that!")
    result = postprocess(state)
    urls = [a.get("url", "") for a in result["ui_actions"]]
    assert "https://foreverfurever.org/collections/all" not in urls


# ---------- Escalation ----------

def test_escalation_button_on_support_mention():
    state = _make_state(
        "I'd recommend reaching out to support@foreverfurever.org for that.",
        user_messages=["I want a refund"],
    )
    result = postprocess(state)
    labels = [a["label"] for a in result["ui_actions"]]
    assert "Email Support" in labels


def test_no_escalation_on_normal_response():
    state = _make_state(
        "Here's what I found for you!",
        user_messages=["Show me products"],
    )
    result = postprocess(state)
    labels = [a["label"] for a in result["ui_actions"]]
    assert "Email Support" not in labels


# ---------- Edge cases ----------

def test_empty_messages():
    state = {"messages": [], "viewed_handles": []}
    result = postprocess(state)
    assert result["products"] == []
    assert result["ui_actions"] == []


def test_no_ai_message():
    state = {
        "messages": [HumanMessage(content="hello")],
        "viewed_handles": [],
    }
    result = postprocess(state)
    assert result["products"] == []
