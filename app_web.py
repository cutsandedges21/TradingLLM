"""Launch the Trading LLM web app: start the API server and open the browser.

    python app_web.py

Serves the built React UI + API at http://127.0.0.1:8000. If the frontend isn't
built yet, it tells you how (cd web && npm run build).

This is a thin launcher; all app code lives in the ``trading_llm`` package.
"""
from __future__ import annotations

import os
import sys
import threading
import time
import webbrowser

# Make the project root importable regardless of the current working directory.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

URL = "http://127.0.0.1:8000"


def _open_browser():
    time.sleep(1.8)
    webbrowser.open(URL)


def main():
    import uvicorn
    from trading_llm.core.paths import WEB_DIST

    if not (WEB_DIST / "index.html").exists():
        print("[Trading LLM] The web UI isn't built yet. Run:\n"
              "    cd web && npm install && npm run build\n"
              "…then run this again.")

    threading.Thread(target=_open_browser, daemon=True).start()
    print(f"[Trading LLM] Web UI -> {URL}   (press Ctrl+C to stop)")
    uvicorn.run("trading_llm.server:app", host="127.0.0.1", port=8000, log_level="warning")


if __name__ == "__main__":
    main()
