"""ChromaDB-based knowledge retrieval for ForeverFurEver agent."""

from __future__ import annotations

import os
from pathlib import Path

import chromadb
from chromadb.utils.embedding_functions import GoogleGenerativeAiEmbeddingFunction

PROJECT_ROOT = Path(__file__).resolve().parents[1]
CHROMA_DIR = str(PROJECT_ROOT / "data" / "chroma")
KNOWLEDGE_DIR = PROJECT_ROOT / "knowledge"


def get_embedding_function():
    """Create Gemini embedding function for ChromaDB."""
    api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    if not api_key:
        raise RuntimeError("Missing GEMINI_API_KEY or GOOGLE_API_KEY in environment")

    # Force REST transport to avoid gRPC "503 Illegal metadata" on Render
    import google.generativeai as genai
    genai.configure(api_key=api_key, transport="rest")

    return GoogleGenerativeAiEmbeddingFunction(
        api_key=api_key,
        model_name="models/gemini-embedding-001",
    )


def get_collection():
    """Get or create the knowledge ChromaDB collection."""
    client = chromadb.PersistentClient(path=CHROMA_DIR)
    embedding_fn = get_embedding_function()
    return client.get_or_create_collection(
        name="store_knowledge",
        embedding_function=embedding_fn,
    )


def search_knowledge(query: str, category: str = "all", n_results: int = 3) -> list[str]:
    """Search the knowledge base and return relevant text chunks.

    Args:
        query: The search query.
        category: Filter by category ('brand', 'policy', 'faq', or 'all').
        n_results: Number of results to return.

    Returns:
        List of relevant text chunks.
    """
    collection = get_collection()

    if collection.count() == 0:
        return ["Knowledge base is empty. Please run: python -m ff_agent.index_knowledge"]

    where_filter = None
    if category != "all":
        where_filter = {"category": category}

    results = collection.query(
        query_texts=[query],
        n_results=n_results,
        where=where_filter,
    )

    documents = results.get("documents", [[]])[0]
    return documents
