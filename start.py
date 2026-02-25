"""Startup script: launch the API server with optional Notion auto-sync.

Knowledge is loaded into memory on first search — no external database
or embedding API needed at startup.
"""

import os
import subprocess
import sys
import threading

from dotenv import load_dotenv

load_dotenv()


def start_auto_sync():
    """Start background thread for periodic Notion sync (if configured).

    Set SYNC_INTERVAL_HOURS env var to enable (e.g., "6" for every 6 hours).
    """
    interval_hours = int(os.getenv("SYNC_INTERVAL_HOURS", "0"))
    if interval_hours <= 0:
        return

    import time

    def sync_loop():
        while True:
            time.sleep(interval_hours * 3600)
            try:
                from ff_agent.notion_sync import sync_knowledge
                sync_knowledge()
                print("[auto-sync] Completed successfully")
            except Exception as e:
                print(f"[auto-sync] Failed: {e}")

    thread = threading.Thread(target=sync_loop, daemon=True)
    thread.start()
    print(f"[auto-sync] Enabled: every {interval_hours} hours")


def main():
    # Step 1: Pre-load knowledge into memory
    print("=== Loading knowledge base ===")
    from ff_agent.knowledge import reload_knowledge

    count = reload_knowledge()
    print(f"=== Loaded {count} knowledge chunks ===\n")

    # Step 2: Start optional auto-sync
    start_auto_sync()

    # Step 3: Start the FastAPI server
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
