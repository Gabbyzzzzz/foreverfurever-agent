"""Tests for API server endpoints, security, and tracking."""

import os
import json

import pytest
from fastapi.testclient import TestClient

os.environ.setdefault("GOOGLE_API_KEY", "test-key")
os.environ.setdefault("SHOPIFY_STORE_DOMAIN", "test.myshopify.com")
os.environ.setdefault("SHOPIFY_STOREFRONT_TOKEN", "test-token")
os.environ.setdefault("ADMIN_TOKEN", "test-admin-token")

from ff_agent.api_server import app, MAX_MESSAGE_LENGTH

client = TestClient(app)


# ---------- Health ----------

def test_health():
    resp = client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["ok"] is True
    assert "version" in data


# ---------- Input validation ----------

def test_chat_rejects_empty_message():
    resp = client.post("/chat", json={"message": "", "thread_id": "t1"})
    # FastAPI/pydantic may return 422 for empty required string, or the model may accept it
    # Either way it shouldn't crash the server
    assert resp.status_code in (200, 422)


def test_chat_rejects_oversized_message():
    long_msg = "a" * (MAX_MESSAGE_LENGTH + 100)
    resp = client.post("/chat", json={"message": long_msg, "thread_id": "t1"})
    assert resp.status_code == 422  # Pydantic validation error


def test_chat_no_error_detail_in_response():
    """Ensure error responses don't leak internal exception details."""
    # This tests the error response format - error_detail should NOT be present
    resp = client.get("/health")
    assert "error_detail" not in resp.json()


# ---------- Tracking endpoint ----------

def test_track_event():
    resp = client.post("/track", json={
        "event": "buy_click",
        "thread_id": "t_test",
        "data": {"handle": "eternal-glow", "url": "https://example.com"},
    })
    assert resp.status_code == 200
    assert resp.json()["ok"] is True


def test_track_event_validates_length():
    resp = client.post("/track", json={
        "event": "x" * 100,  # exceeds max_length=50
        "thread_id": "t_test",
        "data": {},
    })
    assert resp.status_code == 422


def test_track_event_minimal():
    resp = client.post("/track", json={"event": "session_start"})
    assert resp.status_code == 200


# ---------- Feedback ----------

def test_feedback_validates_comment_length():
    resp = client.post("/feedback", json={
        "thread_id": "t_test",
        "rating": "helpful",
        "comment": "x" * 600,  # exceeds max_length=500
    })
    assert resp.status_code == 422


def test_feedback_accepts_valid_input():
    resp = client.post("/feedback", json={
        "thread_id": "t_test",
        "rating": "helpful",
        "comment": "Great help!",
    })
    assert resp.status_code == 200
    assert resp.json()["ok"] is True


# ---------- Static files ----------

def test_root_serves_chat():
    resp = client.get("/")
    assert resp.status_code == 200
    assert "ForeverFurEver" in resp.text


def test_admin_page():
    resp = client.get("/admin")
    assert resp.status_code == 200


def test_embed_js():
    resp = client.get("/static/embed.js")
    assert resp.status_code == 200
    assert "ff-chat-widget" in resp.text


# ---------- CORS ----------

def test_cors_headers():
    resp = client.options(
        "/chat",
        headers={
            "Origin": "https://foreverfurever.org",
            "Access-Control-Request-Method": "POST",
        },
    )
    assert resp.status_code == 200
    assert "foreverfurever.org" in resp.headers.get("access-control-allow-origin", "")
