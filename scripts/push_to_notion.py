"""One-time script: push existing knowledge/*.md content to Notion pages."""

import os
import re
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

from notion_client import Client

c = Client(auth=os.getenv("NOTION_TOKEN"))
db = c.databases.retrieve(database_id=os.getenv("NOTION_DATABASE_ID"))
ds_id = db["data_sources"][0]["id"]
resp = c.data_sources.query(data_source_id=ds_id)

KNOWLEDGE_DIR = Path(__file__).resolve().parents[1] / "knowledge"

# Map Notion title -> local filename
TITLE_TO_FILE = {
    "Eternal Glow – Product Overview": "ProductKnowledge\u2013Eternal Glow.md",
    "TravelStar Companion – Product Overview": "ProductKnowledge\u2013TravelStar Companion.md",
    "About ForeverFurEver": "BrandStory\u2013AboutForeverFurEver.md",
    "FAQ": "FAQ.md",
    "How to Use & Care": "HowtoUse&Care.md",
}


def md_to_notion_blocks(md_text):
    """Convert markdown text to Notion block objects."""
    blocks = []
    lines = md_text.split("\n")
    for line in lines:
        stripped = line.strip()

        if not stripped:
            continue

        if stripped == "---":
            blocks.append({"object": "block", "type": "divider", "divider": {}})
        elif stripped.startswith("### "):
            text = stripped[4:]
            blocks.append({
                "object": "block", "type": "heading_3",
                "heading_3": {"rich_text": [{"type": "text", "text": {"content": text}}]},
            })
        elif stripped.startswith("## "):
            text = stripped[3:]
            blocks.append({
                "object": "block", "type": "heading_2",
                "heading_2": {"rich_text": [{"type": "text", "text": {"content": text}}]},
            })
        elif stripped.startswith("# "):
            text = stripped[2:]
            blocks.append({
                "object": "block", "type": "heading_1",
                "heading_1": {"rich_text": [{"type": "text", "text": {"content": text}}]},
            })
        elif stripped.startswith(("- ", "\u2022 ", "* ")):
            text = stripped[2:]
            blocks.append({
                "object": "block", "type": "bulleted_list_item",
                "bulleted_list_item": {"rich_text": [{"type": "text", "text": {"content": text}}]},
            })
        elif re.match(r"^\d+\.", stripped):
            text = re.sub(r"^\d+\.\s*", "", stripped)
            blocks.append({
                "object": "block", "type": "numbered_list_item",
                "numbered_list_item": {"rich_text": [{"type": "text", "text": {"content": text}}]},
            })
        elif stripped.startswith("> "):
            text = stripped[2:]
            blocks.append({
                "object": "block", "type": "quote",
                "quote": {"rich_text": [{"type": "text", "text": {"content": text}}]},
            })
        else:
            # Plain paragraph - handle **bold**
            rich_text = []
            parts = re.split(r"(\*\*[^*]+\*\*)", stripped)
            for part in parts:
                if part.startswith("**") and part.endswith("**"):
                    rich_text.append({
                        "type": "text",
                        "text": {"content": part[2:-2]},
                        "annotations": {"bold": True},
                    })
                elif part:
                    rich_text.append({"type": "text", "text": {"content": part}})
            if rich_text:
                blocks.append({
                    "object": "block", "type": "paragraph",
                    "paragraph": {"rich_text": rich_text},
                })

    return blocks


for page in resp["results"]:
    title = "".join(t["plain_text"] for t in page["properties"]["Title"]["title"])
    page_id = page["id"]
    filename = TITLE_TO_FILE.get(title)

    if not filename:
        print(f"SKIP: No mapping for '{title}'")
        continue

    filepath = KNOWLEDGE_DIR / filename
    if not filepath.exists():
        print(f"SKIP: File not found: {filepath}")
        continue

    md_content = filepath.read_text(encoding="utf-8")
    blocks = md_to_notion_blocks(md_content)

    # Notion API allows max 100 blocks per append
    for chunk_start in range(0, len(blocks), 100):
        chunk = blocks[chunk_start : chunk_start + 100]
        c.blocks.children.append(block_id=page_id, children=chunk)

    print(f"OK: {title} <- {filename} ({len(blocks)} blocks)")

print("\nDone! All knowledge content pushed to Notion.")
