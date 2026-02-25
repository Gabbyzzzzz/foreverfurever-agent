"""Index knowledge files into ChromaDB for retrieval.

Usage: python -m ff_agent.index_knowledge
"""

from __future__ import annotations

import re
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

from ff_agent.knowledge import get_collection, KNOWLEDGE_DIR


MAX_CHUNK_SIZE = 500


def split_markdown_sections(text: str) -> list[str]:
    """Split markdown into sections by headers, then sub-split large sections by paragraphs."""
    sections = re.split(r"(?=^#{1,3} )", text, flags=re.MULTILINE)
    chunks = []
    for section in sections:
        section = section.strip()
        if len(section) <= 20:
            continue
        if len(section) <= MAX_CHUNK_SIZE:
            chunks.append(section)
        else:
            # Split large sections by double newline (paragraphs)
            paragraphs = section.split("\n\n")
            current = ""
            for para in paragraphs:
                if current and len(current) + len(para) + 2 > MAX_CHUNK_SIZE:
                    chunks.append(current)
                    current = para
                else:
                    current = current + "\n\n" + para if current else para
            if current and len(current) > 20:
                chunks.append(current)
    return chunks


def infer_category(filename: str) -> str:
    """Infer knowledge category from filename."""
    name = filename.lower()
    if "brand" in name:
        return "brand"
    elif "polic" in name:
        return "policy"
    elif "faq" in name:
        return "faq"
    return "general"


def index_all():
    """Read all knowledge files, chunk them, and index into ChromaDB."""
    collection = get_collection()

    # Clear existing data for a clean re-index
    existing = collection.count()
    if existing > 0:
        all_ids = collection.get()["ids"]
        if all_ids:
            collection.delete(ids=all_ids)
        print(f"Cleared {existing} existing documents.")

    documents = []
    metadatas = []
    ids = []

    for filepath in sorted(KNOWLEDGE_DIR.glob("*.md")):
        print(f"Processing: {filepath.name}")
        text = filepath.read_text(encoding="utf-8")
        category = infer_category(filepath.name)
        chunks = split_markdown_sections(text)

        for i, chunk in enumerate(chunks):
            doc_id = f"{filepath.stem}_{i}"
            documents.append(chunk)
            metadatas.append({"category": category, "source": filepath.name})
            ids.append(doc_id)

    if not documents:
        print("No knowledge files found in", KNOWLEDGE_DIR)
        return

    # ChromaDB batch add
    collection.add(
        documents=documents,
        metadatas=metadatas,
        ids=ids,
    )

    print(f"Indexed {len(documents)} chunks from {len(list(KNOWLEDGE_DIR.glob('*.md')))} files.")


if __name__ == "__main__":
    index_all()
