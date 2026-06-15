"""Canonical filesystem paths + tiny JSON helpers for Trading LLM v2.

All persistent state lives at the **repository root** (not inside the package),
so the app behaves identically no matter where it is launched from and the
"memory never leaves your machine" guarantee holds — it is just files on disk.

Layout (rooted at BASE_DIR = repo root):
    config/          settings.json + api_keys.json
    memory/          profile.json + journal.json + paper_account.json + decision_log.json
    web/dist/        built React UI
    LEARN_TO_TRADE.md
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path
from typing import Any

# trading_llm/core/paths.py -> parents[1] = trading_llm/ (package), parents[2] = repo root.
PACKAGE_DIR = Path(__file__).resolve().parents[1]


def base_dir() -> Path:
    """Repo root. Works as a script and when frozen into an .exe later."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return PACKAGE_DIR.parent


BASE_DIR = base_dir()
CONFIG_DIR = BASE_DIR / "config"
MEMORY_DIR = BASE_DIR / "memory"
WEB_DIST = BASE_DIR / "web" / "dist"
LEARN_PATH = BASE_DIR / "LEARN_TO_TRADE.md"


def load_json(path: Path, default: Any) -> Any:
    """Read JSON; never let a missing/corrupt file crash the app."""
    try:
        p = Path(path)
        if not p.exists():
            return default
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception as exc:  # corrupt file should never crash the app
        print(f"[paths] load_json failed for {path}: {exc}")
        return default


def save_json(path: Path, data: Any) -> None:
    """Atomic write: serialize to a temp file in the same dir, then replace.

    A crash (or OneDrive sync grabbing the file) mid-write can't leave a half-written,
    corrupt JSON — the original stays intact until the atomic ``os.replace``.
    """
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(data, indent=2, ensure_ascii=False)
    fd, tmp = tempfile.mkstemp(dir=str(p.parent), prefix=f".{p.name}.", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(text)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, p)  # atomic on the same filesystem
    except Exception:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        # last-resort direct write so we never silently lose the update
        p.write_text(text, encoding="utf-8")
