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


# Filename prefix mapping to match existing knowledge file naming
_CATEGORY_PREFIX = {
    "brand": "BrandStory\u2013",
    "product": "ProductKnowledge\u2013",
    "faq": "",
    "care": "",
}

# Known filenames that don't follow the simple prefix+title pattern
_KNOWN_FILENAMES = {
    ("FAQ", "faq"): "FAQ.md",
    ("How to Use & Care", "care"): "HowtoUse&Care.md",
    ("About ForeverFurEver", "brand"): "BrandStory\u2013AboutForeverFurEver.md",
    ("Eternal Glow \u2013 Product Overview", "product"): "ProductKnowledge\u2013Eternal Glow.md",
    ("TravelStar Companion \u2013 Product Overview", "product"): "ProductKnowledge\u2013TravelStar Companion.md",
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

    # Get data_source_id from the database (notion-client v3 API)
    db = notion.databases.retrieve(database_id=database_id)
    data_sources = db.get("data_sources", [])
    if not data_sources:
        raise RuntimeError(f"No data sources found for database {database_id}")
    data_source_id = data_sources[0]["id"]

    # Query pages with Status = Published
    response = notion.data_sources.query(
        data_source_id=data_source_id,
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
    logger.info(
        f"Sync complete: {len(results['synced'])} synced, "
        f"{len(results['skipped'])} skipped, {len(results['errors'])} errors"
    )

    return results
