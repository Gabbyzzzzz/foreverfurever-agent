"""In-memory knowledge retrieval for ForeverFurEver agent.

Loads markdown files from the knowledge/ directory at startup and provides
simple TF-IDF search. No external embedding API or vector database required.
"""

from __future__ import annotations

import math
import re
from collections import Counter
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
KNOWLEDGE_DIR = PROJECT_ROOT / "knowledge"

MAX_CHUNK_SIZE = 500

# In-memory store, loaded lazily on first search
_chunks: list[dict] = []


_STOP_WORDS = frozenset([
    "i", "me", "my", "we", "our", "you", "your", "it", "its", "the", "a", "an",
    "is", "am", "are", "was", "were", "be", "been", "being", "have", "has", "had",
    "do", "does", "did", "will", "would", "shall", "should", "may", "might",
    "can", "could", "to", "of", "in", "for", "on", "with", "at", "by", "from",
    "as", "into", "about", "that", "this", "these", "those", "and", "but", "or",
    "not", "no", "so", "if", "then", "than", "too", "very", "just", "also",
    "what", "how", "when", "where", "who", "which", "want", "need", "like",
    "please", "tell", "know", "get", "got", "some", "any",
])


def _tokenize(text: str) -> list[str]:
    """Lowercase and split on non-alphanumeric (supports CJK)."""
    return re.findall(r"[a-z0-9\u4e00-\u9fff]+", text.lower())


def _tokenize_query(text: str) -> list[str]:
    """Tokenize a search query, removing stop words."""
    return [t for t in _tokenize(text) if t not in _STOP_WORDS]


def _split_markdown_sections(text: str) -> list[str]:
    """Split markdown into sections by headers, then sub-split large ones."""
    sections = re.split(r"(?=^#{1,3} )", text, flags=re.MULTILINE)
    chunks: list[str] = []
    for section in sections:
        section = section.strip()
        if len(section) <= 20:
            continue
        if len(section) <= MAX_CHUNK_SIZE:
            chunks.append(section)
        else:
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


def _infer_category(filename: str) -> str:
    name = filename.lower()
    if "brand" in name:
        return "brand"
    elif "polic" in name or "care" in name:
        return "policy"
    elif "faq" in name:
        return "faq"
    return "general"


def _load_knowledge() -> None:
    """Load all markdown files from knowledge/ into memory."""
    global _chunks
    _chunks = []

    for filepath in sorted(KNOWLEDGE_DIR.glob("*.md")):
        text = filepath.read_text(encoding="utf-8")
        category = _infer_category(filepath.name)
        sections = _split_markdown_sections(text)
        for section in sections:
            _chunks.append({
                "text": section,
                "category": category,
                "source": filepath.name,
            })


def reload_knowledge() -> int:
    """Force reload knowledge from disk. Returns chunk count."""
    _load_knowledge()
    return len(_chunks)


def search_knowledge(query: str, category: str = "all", n_results: int = 3) -> list[str]:
    """Search the knowledge base and return relevant text chunks.

    Args:
        query: The search query.
        category: Filter by category ('brand', 'policy', 'faq', or 'all').
        n_results: Number of results to return.

    Returns:
        List of relevant text chunks.
    """
    # Lazy load on first call
    if not _chunks:
        _load_knowledge()

    if not _chunks:
        return ["Knowledge base is empty. No markdown files found in knowledge/ directory."]

    # Filter by category
    candidates = (
        _chunks if category == "all"
        else [c for c in _chunks if c["category"] == category]
    )

    if not candidates:
        return [f"No knowledge found for category: {category}"]

    query_tokens = _tokenize_query(query)
    if not query_tokens:
        return [c["text"] for c in candidates[:n_results]]

    # Compute TF-IDF scores
    n_docs = len(candidates)
    df: Counter = Counter()
    doc_token_sets: list[set[str]] = []

    for doc in candidates:
        tokens = set(_tokenize(doc["text"]))
        doc_token_sets.append(tokens)
        for token in tokens:
            df[token] += 1

    scored: list[tuple[float, dict]] = []
    query_set = set(query_tokens)

    for i, doc in enumerate(candidates):
        score = 0.0
        doc_text_lower = doc["text"].lower()
        for qt in query_set:
            if qt in doc_token_sets[i]:
                tf = doc_text_lower.count(qt)
                idf = math.log(n_docs / (1 + df.get(qt, 0)))
                score += tf * idf
        if score > 0:
            scored.append((score, doc))

    scored.sort(key=lambda x: -x[0])

    if not scored:
        # No keyword matches — return first chunks as fallback
        return [c["text"] for c in candidates[:n_results]]

    return [doc["text"] for _, doc in scored[:n_results]]
