# Notion Knowledge Sync Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Sync knowledge base content from a Notion Database to the agent's `knowledge/` directory and ChromaDB index via a manual API trigger.

**Architecture:** A new `ff_agent/notion_sync.py` module handles all Notion API interaction: querying published pages, converting Notion blocks to markdown, writing files, and updating the "Last Synced" field. A new admin endpoint in `api_server.py` exposes this as `POST /admin/sync-knowledge` with Bearer token auth.

**Tech Stack:** Python, notion-client SDK, FastAPI, ChromaDB (existing)

---

### Task 1: Add dependency and environment variables

**Files:**
- Modify: `requirements.txt`
- Modify: `.env`
- Modify: `.env` (add template comments)

**Step 1: Add notion-client to requirements.txt**

Add `notion-client` as the last line in `requirements.txt`:

```
notion-client
```

**Step 2: Add environment variables to .env**

Append to `.env`:

```
NOTION_TOKEN=<user fills in their ntn_ secret>
NOTION_DATABASE_ID=8253d66706364524b6ce88a42038fad9
ADMIN_TOKEN=<user picks a strong random string>
```

**Step 3: Install dependencies**

Run: `pip install notion-client`

**Step 4: Commit**

```bash
git add requirements.txt
git commit -m "chore: add notion-client dependency"
```

> Note: Do NOT commit `.env` — it contains secrets.

---

### Task 2: Create notion_sync.py — Notion block-to-markdown converter

**Files:**
- Create: `ff_agent/notion_sync.py`
- Create: `tests/test_notion_sync.py`

**Step 1: Create tests directory and test file with block converter tests**

```python
# tests/test_notion_sync.py
"""Tests for Notion sync module."""

from ff_agent.notion_sync import blocks_to_markdown


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
                    {"plain_text": "bold", "annotations": {"bold": True, "italic": False, "strikethrough": False, "underline": False, "code": False}},
                    {"plain_text": " and "},
                    {"plain_text": "italic", "annotations": {"bold": False, "italic": True, "strikethrough": False, "underline": False, "code": False}},
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
```

**Step 2: Run tests to verify they fail**

Run: `pytest tests/test_notion_sync.py -v`
Expected: FAIL — `notion_sync` module does not exist yet

**Step 3: Create `ff_agent/notion_sync.py` with blocks_to_markdown**

```python
"""Notion knowledge base sync for ForeverFurEver agent."""

from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parents[1]
KNOWLEDGE_DIR = PROJECT_ROOT / "knowledge"


def _rich_text_to_markdown(rich_texts: list[dict]) -> str:
    """Convert Notion rich_text array to markdown string."""
    parts = []
    for rt in rich_texts:
        text = rt.get("plain_text", "")
        ann = rt.get("annotations", {})
        if ann.get("bold"):
            text = f"**{text}**"
        if ann.get("italic"):
            text = f"*{text}*"
        if ann.get("code"):
            text = f"`{text}`"
        parts.append(text)
    return "".join(parts)


def blocks_to_markdown(blocks: list[dict]) -> str:
    """Convert a list of Notion blocks to a markdown string."""
    lines: list[str] = []
    numbered_counter = 0

    for block in blocks:
        block_type = block.get("type", "")

        if block_type == "paragraph":
            text = _rich_text_to_markdown(block["paragraph"].get("rich_text", []))
            lines.append(text)
            numbered_counter = 0

        elif block_type == "heading_1":
            text = _rich_text_to_markdown(block["heading_1"].get("rich_text", []))
            lines.append(f"# {text}")
            numbered_counter = 0

        elif block_type == "heading_2":
            text = _rich_text_to_markdown(block["heading_2"].get("rich_text", []))
            lines.append(f"## {text}")
            numbered_counter = 0

        elif block_type == "heading_3":
            text = _rich_text_to_markdown(block["heading_3"].get("rich_text", []))
            lines.append(f"### {text}")
            numbered_counter = 0

        elif block_type == "bulleted_list_item":
            text = _rich_text_to_markdown(block["bulleted_list_item"].get("rich_text", []))
            lines.append(f"- {text}")
            numbered_counter = 0

        elif block_type == "numbered_list_item":
            numbered_counter += 1
            text = _rich_text_to_markdown(block["numbered_list_item"].get("rich_text", []))
            lines.append(f"{numbered_counter}. {text}")

        elif block_type == "divider":
            lines.append("---")
            numbered_counter = 0

        elif block_type == "quote":
            text = _rich_text_to_markdown(block["quote"].get("rich_text", []))
            lines.append(f"> {text}")
            numbered_counter = 0

        else:
            numbered_counter = 0

    return "\n\n".join(lines).strip()
```

**Step 4: Run tests to verify they pass**

Run: `pytest tests/test_notion_sync.py -v`
Expected: All 8 tests PASS

**Step 5: Commit**

```bash
git add ff_agent/notion_sync.py tests/test_notion_sync.py
git commit -m "feat: add Notion block-to-markdown converter with tests"
```

---

### Task 3: Add sync_knowledge() function

**Files:**
- Modify: `ff_agent/notion_sync.py`
- Modify: `tests/test_notion_sync.py`

**Step 1: Add test for filename generation helper**

Append to `tests/test_notion_sync.py`:

```python
from ff_agent.notion_sync import _make_filename


def test_make_filename_product():
    assert _make_filename("TravelStar Companion", "product") == "ProductKnowledge–TravelStar Companion.md"


def test_make_filename_brand():
    assert _make_filename("About ForeverFurEver", "brand") == "BrandStory–About ForeverFurEver.md"


def test_make_filename_faq():
    assert _make_filename("FAQ", "faq") == "FAQ.md"


def test_make_filename_care():
    assert _make_filename("How to Use & Care", "care") == "HowtoUse&Care.md"
```

**Step 2: Run tests to verify new tests fail**

Run: `pytest tests/test_notion_sync.py -v -k "make_filename"`
Expected: FAIL — `_make_filename` not defined

**Step 3: Add _make_filename and sync_knowledge to notion_sync.py**

Add these after `blocks_to_markdown` in `ff_agent/notion_sync.py`:

```python
# Filename prefix mapping to match existing knowledge file naming
_CATEGORY_PREFIX = {
    "brand": "BrandStory–",
    "product": "ProductKnowledge–",
    "faq": "",
    "care": "",
}

# Known filenames that don't follow the prefix pattern
_KNOWN_FILENAMES = {
    ("FAQ", "faq"): "FAQ.md",
    ("How to Use & Care", "care"): "HowtoUse&Care.md",
}


def _make_filename(title: str, category: str) -> str:
    """Generate a knowledge markdown filename from title and category."""
    key = (title, category)
    if key in _KNOWN_FILENAMES:
        return _KNOWN_FILENAMES[key]
    prefix = _CATEGORY_PREFIX.get(category, "")
    return f"{prefix}{title}.md"


def sync_knowledge() -> dict:
    """Pull published pages from Notion and sync to knowledge/ directory.

    Returns dict with keys: synced, skipped, errors.
    """
    from notion_client import Client

    from ff_agent.index_knowledge import index_all

    token = os.getenv("NOTION_TOKEN")
    database_id = os.getenv("NOTION_DATABASE_ID")

    if not token or not database_id:
        raise RuntimeError("NOTION_TOKEN and NOTION_DATABASE_ID must be set")

    notion = Client(auth=token)

    # Query pages with Status = Published
    response = notion.databases.query(
        database_id=database_id,
        filter={"property": "Status", "select": {"equals": "Published"}},
    )

    results = {"synced": [], "skipped": [], "errors": []}

    for page in response.get("results", []):
        page_id = page["id"]
        try:
            # Extract title
            title_prop = page["properties"].get("Title", {})
            title_parts = title_prop.get("title", [])
            title = "".join(t.get("plain_text", "") for t in title_parts).strip()

            if not title:
                results["skipped"].append(page_id)
                continue

            # Extract category
            cat_prop = page["properties"].get("Category", {})
            category = (cat_prop.get("select") or {}).get("name", "general").lower()

            # Fetch page blocks (content)
            blocks_response = notion.blocks.children.list(block_id=page_id)
            blocks = blocks_response.get("results", [])

            # Convert to markdown
            markdown = blocks_to_markdown(blocks)
            if not markdown.strip():
                results["skipped"].append(title)
                continue

            # Write to knowledge directory
            filename = _make_filename(title, category)
            filepath = KNOWLEDGE_DIR / filename
            filepath.write_text(markdown, encoding="utf-8")

            # Update Last Synced in Notion
            now_iso = datetime.now(timezone.utc).isoformat()
            notion.pages.update(
                page_id=page_id,
                properties={"Last Synced": {"date": {"start": now_iso}}},
            )

            results["synced"].append(title)
            logger.info(f"Synced: {title} -> {filename}")

        except Exception as e:
            logger.exception(f"Error syncing page {page_id}")
            results["errors"].append({"page_id": page_id, "error": str(e)})

    # Re-index ChromaDB
    index_all()
    logger.info(f"Sync complete: {len(results['synced'])} synced, {len(results['skipped'])} skipped, {len(results['errors'])} errors")

    return results
```

**Step 4: Run all tests**

Run: `pytest tests/test_notion_sync.py -v`
Expected: All 12 tests PASS

**Step 5: Commit**

```bash
git add ff_agent/notion_sync.py tests/test_notion_sync.py
git commit -m "feat: add sync_knowledge function with Notion API integration"
```

---

### Task 4: Add admin sync endpoint to api_server.py

**Files:**
- Modify: `ff_agent/api_server.py:1-5` (add imports)
- Modify: `ff_agent/api_server.py:140-143` (add endpoint after /feedback)

**Step 1: Add import and auth helper at top of api_server.py**

After existing imports (line 17), add:

```python
from fastapi import FastAPI, Header, HTTPException
```

Replace the existing `from fastapi import FastAPI` line.

**Step 2: Add the /admin/sync-knowledge endpoint**

Append after the `/feedback` endpoint (after line 143):

```python

@app.post("/admin/sync-knowledge")
def sync_knowledge(authorization: str = Header()):
    admin_token = os.getenv("ADMIN_TOKEN")
    if not admin_token:
        raise HTTPException(status_code=500, detail="ADMIN_TOKEN not configured")

    expected = f"Bearer {admin_token}"
    if authorization != expected:
        raise HTTPException(status_code=401, detail="Unauthorized")

    from ff_agent.notion_sync import sync_knowledge as do_sync

    try:
        results = do_sync()
        return {
            "ok": True,
            "synced": results["synced"],
            "skipped": results["skipped"],
            "errors": results["errors"],
        }
    except Exception as e:
        logging.exception("Sync error")
        raise HTTPException(status_code=500, detail=str(e))
```

**Step 3: Add endpoint test**

Append to `tests/test_notion_sync.py`:

```python
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
```

**Step 4: Run all tests**

Run: `pytest tests/test_notion_sync.py -v`
Expected: All 14 tests PASS

**Step 5: Commit**

```bash
git add ff_agent/api_server.py tests/test_notion_sync.py
git commit -m "feat: add POST /admin/sync-knowledge endpoint with Bearer auth"
```

---

### Task 5: End-to-end verification

**Step 1: Verify env variables are set**

Run: `grep -c "NOTION_TOKEN\|NOTION_DATABASE_ID\|ADMIN_TOKEN" .env`
Expected: 3

**Step 2: Start the server locally**

Run: `python start.py &`
Wait for "Uvicorn running" message.

**Step 3: Test the sync endpoint**

Run (substitute your actual ADMIN_TOKEN):
```bash
curl -X POST http://localhost:8000/admin/sync-knowledge \
  -H "Authorization: Bearer <YOUR_ADMIN_TOKEN>"
```

Expected: JSON with `"ok": true`, `"synced"` list containing your 5 knowledge entries.

**Step 4: Verify knowledge files were updated**

Run: `ls -la knowledge/`
Expected: Files show recent modification timestamps.

**Step 5: Verify ChromaDB was re-indexed**

Run: `python -c "from ff_agent.knowledge import get_collection; print(get_collection().count())"`
Expected: Non-zero count (similar to before sync).

**Step 6: Stop server and commit any remaining changes**

```bash
kill %1
git add -A
git commit -m "docs: add notion knowledge sync implementation plan"
```

---

## Summary

| Task | Description | Files |
|------|-------------|-------|
| 1 | Dependencies + env vars | requirements.txt, .env |
| 2 | Block-to-markdown converter | ff_agent/notion_sync.py, tests/test_notion_sync.py |
| 3 | sync_knowledge() function | ff_agent/notion_sync.py, tests/test_notion_sync.py |
| 4 | Admin API endpoint | ff_agent/api_server.py, tests/test_notion_sync.py |
| 5 | End-to-end verification | — |
