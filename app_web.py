"""Launch the Trading LLM web app: start the API server and open the browser.

    python app_web.py

Serves the built React UI + API. By default it listens on your whole network
(0.0.0.0) so you can open it from your phone on the same Wi-Fi; remote devices
must send your API key (set ``api_auth_key`` in config/settings.json or the
TRADING_LLM_API_KEY env var). Localhost is always allowed without a key.

Override the bind host/port with TRADING_LLM_HOST / TRADING_LLM_PORT.
This is a thin launcher; all app code lives in the ``trading_llm`` package.
"""
from __future__ import annotations

import os
import socket
import sys
import threading
import time
import webbrowser

# Make the project root importable regardless of the current working directory.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

HOST = os.environ.get("TRADING_LLM_HOST", "0.0.0.0")
# Honor a host-injected port (Render/Railway/Heroku set $PORT) so GitHub-connected
# deploys "just work"; fall back to our own var, then 8000 for local use.
PORT = int(os.environ.get("TRADING_LLM_PORT") or os.environ.get("PORT") or "8000")


def _lan_ip() -> str | None:
    """Best-effort primary LAN IP (the address your phone would use)."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return None


def _open_browser():
    time.sleep(1.8)
    webbrowser.open(f"http://127.0.0.1:{PORT}")


def main():
    import uvicorn
    from trading_llm.core.paths import WEB_DIST
    from trading_llm.core.config import api_auth_key

    if not (WEB_DIST / "index.html").exists():
        print("[Trading LLM] The web UI isn't built yet. Run:\n"
              "    cd web && npm install && npm run build\n"
              "…then run this again.")

    print(f"[Trading LLM] Local   -> http://127.0.0.1:{PORT}")
    if HOST == "0.0.0.0":
        ip = _lan_ip()
        if ip:
            print(f"[Trading LLM] Phone   -> http://{ip}:{PORT}   (same Wi-Fi)")
        if not api_auth_key():
            print("[Trading LLM] NOTE: remote devices (your phone) are blocked until you set an API key.\n"
                  '              Add  "api_auth_key": "<choose-a-secret>"  to config/settings.json,\n'
                  "              then enter that same key in the app's Settings on your phone.")
        else:
            print("[Trading LLM] Remote access is key-protected. Enter your api_auth_key in Settings on the phone.")
    print("[Trading LLM] (press Ctrl+C to stop)")

    if not os.environ.get("TRADING_LLM_NO_BROWSER"):   # set this on a server/container
        threading.Thread(target=_open_browser, daemon=True).start()
    uvicorn.run("trading_llm.server:app", host=HOST, port=PORT, log_level="warning")


if __name__ == "__main__":
    main()
