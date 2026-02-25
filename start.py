"""Startup script: index knowledge base, then launch the API server.

Render's free tier has an ephemeral filesystem, so ChromaDB data is lost
on every deploy/restart. This script re-indexes knowledge before starting
the server to ensure the knowledge base is always available.
"""

import os
import subprocess
import sys

from dotenv import load_dotenv

load_dotenv()


def main():
    # Step 1: Index knowledge into ChromaDB
    print("=== Indexing knowledge base ===")
    from ff_agent.index_knowledge import index_all

    index_all()
    print("=== Knowledge indexing complete ===\n")

    # Step 2: Start the FastAPI server
    port = os.getenv("PORT", "8000")
    print(f"=== Starting server on port {port} ===")
    subprocess.run(
        [
            sys.executable,
            "-m",
            "uvicorn",
            "ff_agent.api_server:app",
            "--host",
            "0.0.0.0",
            "--port",
            port,
        ],
        check=True,
    )


if __name__ == "__main__":
    main()
