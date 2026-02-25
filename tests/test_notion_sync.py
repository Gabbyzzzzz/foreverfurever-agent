"""Tests for Notion sync module."""

from ff_agent.notion_sync import blocks_to_markdown, _make_filename


def test_paragraph_block():
    blocks = [
        {
            "type": "paragraph",
            "paragraph": {
                "rich_text": [{"plain_text": "Hello world"}]
            },
        }
    ]
    assert blocks_to_markdown(blocks) == "Hello world"


def test_heading_blocks():
    blocks = [
        {
            "type": "heading_1",
            "heading_1": {"rich_text": [{"plain_text": "Title"}]},
        },
        {
            "type": "heading_2",
            "heading_2": {"rich_text": [{"plain_text": "Subtitle"}]},
        },
        {
            "type": "heading_3",
            "heading_3": {"rich_text": [{"plain_text": "Section"}]},
        },
    ]
    result = blocks_to_markdown(blocks)
    assert "# Title" in result
    assert "## Subtitle" in result
    assert "### Section" in result


def test_bulleted_list():
    blocks = [
        {
            "type": "bulleted_list_item",
            "bulleted_list_item": {
                "rich_text": [{"plain_text": "Item one"}]
            },
        },
        {
            "type": "bulleted_list_item",
            "bulleted_list_item": {
                "rich_text": [{"plain_text": "Item two"}]
            },
        },
    ]
    result = blocks_to_markdown(blocks)
    assert "- Item one" in result
    assert "- Item two" in result


def test_numbered_list():
    blocks = [
        {
            "type": "numbered_list_item",
            "numbered_list_item": {
                "rich_text": [{"plain_text": "First"}]
            },
        },
        {
            "type": "numbered_list_item",
            "numbered_list_item": {
                "rich_text": [{"plain_text": "Second"}]
            },
        },
    ]
    result = blocks_to_markdown(blocks)
    assert "1. First" in result
    assert "2. Second" in result


def test_divider():
    blocks = [
        {"type": "paragraph", "paragraph": {"rich_text": [{"plain_text": "Above"}]}},
        {"type": "divider", "divider": {}},
        {"type": "paragraph", "paragraph": {"rich_text": [{"plain_text": "Below"}]}},
    ]
    result = blocks_to_markdown(blocks)
    assert "---" in result


def test_bold_and_italic_rich_text():
    blocks = [
        {
            "type": "paragraph",
            "paragraph": {
                "rich_text": [
                    {"plain_text": "normal "},
                    {"plain_text": "bold", "annotations": {"bold": True, "italic": False}},
                    {"plain_text": " and "},
                    {"plain_text": "italic", "annotations": {"bold": False, "italic": True}},
                ]
            },
        }
    ]
    result = blocks_to_markdown(blocks)
    assert "**bold**" in result
    assert "*italic*" in result


def test_empty_blocks():
    assert blocks_to_markdown([]) == ""


def test_unknown_block_type_skipped():
    blocks = [
        {"type": "table_of_contents", "table_of_contents": {}},
        {"type": "paragraph", "paragraph": {"rich_text": [{"plain_text": "Visible"}]}},
    ]
    result = blocks_to_markdown(blocks)
    assert "Visible" in result


# --- Filename generation tests ---

def test_make_filename_product():
    assert _make_filename("TravelStar Companion", "product") == "ProductKnowledge\u2013TravelStar Companion.md"


def test_make_filename_brand():
    assert _make_filename("About ForeverFurEver", "brand") == "BrandStory\u2013AboutForeverFurEver.md"


def test_make_filename_product_eternal_glow():
    assert _make_filename("Eternal Glow \u2013 Product Overview", "product") == "ProductKnowledge\u2013Eternal Glow.md"


def test_make_filename_product_travelstar():
    assert _make_filename("TravelStar Companion \u2013 Product Overview", "product") == "ProductKnowledge\u2013TravelStar Companion.md"


def test_make_filename_faq():
    assert _make_filename("FAQ", "faq") == "FAQ.md"


def test_make_filename_care():
    assert _make_filename("How to Use & Care", "care") == "HowtoUse&Care.md"


# --- API endpoint tests ---

from fastapi.testclient import TestClient


def test_sync_endpoint_rejects_no_auth():
    from ff_agent.api_server import app
    client = TestClient(app)
    resp = client.post("/admin/sync-knowledge")
    assert resp.status_code == 422  # missing header


def test_sync_endpoint_rejects_bad_token(monkeypatch):
    monkeypatch.setenv("ADMIN_TOKEN", "real-secret")
    from ff_agent.api_server import app
    client = TestClient(app)
    resp = client.post(
        "/admin/sync-knowledge",
        headers={"Authorization": "Bearer wrong-token"},
    )
    assert resp.status_code == 401


def test_sync_endpoint_returns_started(monkeypatch):
    monkeypatch.setenv("ADMIN_TOKEN", "test-secret")
    from ff_agent import api_server
    # Reset sync status
    api_server._sync_status["running"] = False
    api_server._sync_status["last_result"] = None
    client = TestClient(api_server.app)
    resp = client.post(
        "/admin/sync-knowledge",
        headers={"Authorization": "Bearer test-secret"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] in ("started", "already_running")
    # Clean up: wait briefly for thread to start
    import time
    time.sleep(0.5)
    api_server._sync_status["running"] = False


def test_sync_status_endpoint(monkeypatch):
    monkeypatch.setenv("ADMIN_TOKEN", "test-secret")
    from ff_agent import api_server
    api_server._sync_status["running"] = False
    api_server._sync_status["last_result"] = {"ok": True, "synced": ["FAQ.md"], "skipped": [], "errors": []}
    client = TestClient(api_server.app)
    resp = client.get(
        "/admin/sync-status",
        headers={"Authorization": "Bearer test-secret"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["running"] is False
    assert data["last_result"]["ok"] is True


def test_sync_status_rejects_bad_token(monkeypatch):
    monkeypatch.setenv("ADMIN_TOKEN", "test-secret")
    from ff_agent.api_server import app
    client = TestClient(app)
    resp = client.get(
        "/admin/sync-status",
        headers={"Authorization": "Bearer wrong"},
    )
    assert resp.status_code == 401
