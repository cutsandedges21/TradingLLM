"""Skill packs — a local finance knowledge base the copilot cites.

Each pack is a markdown file in ``learn/skills/`` with a small frontmatter block
(name/title/tags/level/summary). At question time, ``find_relevant`` does a
lightweight keyword/tag match (no vector DB — matches the project's YAGNI ethos),
the engine injects the top pack's gist into the LLM context, and the cited packs
are returned so the UI can show "📚 Sources".
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

SKILLS_DIR = Path(__file__).resolve().parent / "skills"

_STOPWORDS = {
    "the", "a", "an", "and", "or", "of", "to", "in", "on", "is", "it", "for",
    "what", "how", "why", "do", "does", "i", "my", "me", "you", "this", "that",
    "with", "about", "can", "should", "would", "are", "was", "be", "explain",
    "tell", "show", "whats", "right", "now", "today", "good", "bad", "vs",
}


@dataclass
class SkillPack:
    name: str
    title: str
    tags: list[str] = field(default_factory=list)
    level: str = "beginner"
    summary: str = ""
    body: str = ""

    def to_meta(self) -> dict:
        return {"name": self.name, "title": self.title, "tags": self.tags,
                "level": self.level, "summary": self.summary}


def _parse(path: Path) -> SkillPack | None:
    try:
        text = path.read_text(encoding="utf-8")
    except Exception:
        return None
    meta: dict = {}
    body = text
    if text.startswith("---"):
        parts = text.split("---", 2)
        if len(parts) == 3:
            for line in parts[1].strip().splitlines():
                if ":" in line:
                    k, _, v = line.partition(":")
                    meta[k.strip().lower()] = v.strip()
            body = parts[2].strip()
    name = meta.get("name", path.stem)
    tags = [t.strip().lower() for t in re.split(r"[,;]", meta.get("tags", "")) if t.strip()]
    return SkillPack(
        name=name, title=meta.get("title", name.replace("-", " ").title()),
        tags=tags, level=meta.get("level", "beginner"),
        summary=meta.get("summary", ""), body=body,
    )


@lru_cache(maxsize=1)
def load_all() -> tuple[SkillPack, ...]:
    if not SKILLS_DIR.exists():
        return ()
    packs = [p for f in sorted(SKILLS_DIR.glob("*.md")) if (p := _parse(f))]
    return tuple(packs)


def get(name: str) -> SkillPack | None:
    name = str(name).lower().strip()
    return next((p for p in load_all() if p.name == name), None)


def list_packs() -> list[dict]:
    return [p.to_meta() for p in load_all()]


def _tokens(text: str) -> set[str]:
    words = re.findall(r"[a-z]{2,}", text.lower())
    return {w for w in words if w not in _STOPWORDS and len(w) >= 3}


def find_relevant(query: str, k: int = 3, min_score: float = 2.0) -> list[SkillPack]:
    """Top-k packs by keyword/tag overlap with the query."""
    q = _tokens(query)
    if not q:
        return []
    scored: list[tuple[float, SkillPack]] = []
    for p in load_all():
        # whole tags can be multi-word ("price action"); match on their tokens too
        tag_tokens = set(p.tags) | {w for t in p.tags for w in _tokens(t)}
        title_tok = _tokens(p.title)
        summ_tok = _tokens(p.summary)
        name_tok = set(p.name.split("-"))
        score = 0.0
        for tok in q:
            if tok in tag_tokens:        # exact token match — no substring false-positives
                score += 3.0
            if tok in title_tok:
                score += 2.0
            if tok in summ_tok:
                score += 1.0
            if tok in name_tok:
                score += 0.5
        if score >= min_score:
            scored.append((score, p))
    scored.sort(key=lambda s: s[0], reverse=True)
    return [p for _, p in scored[:k]]


def context_snippet(packs: list[SkillPack], body_chars: int = 700) -> str:
    """Compact knowledge block injected into the LLM context."""
    if not packs:
        return ""
    lead = packs[0]
    excerpt = lead.body.strip()
    if len(excerpt) > body_chars:
        excerpt = excerpt[:body_chars].rsplit("\n", 1)[0] + " …"
    lines = [
        "[RELEVANT KNOWLEDGE — from the local skill library; use it and you may cite it]",
        f"## {lead.title}\n{excerpt}",
    ]
    if len(packs) > 1:
        also = "; ".join(f"{p.title} — {p.summary}" for p in packs[1:])
        lines.append(f"Also relevant: {also}")
    return "\n\n".join(lines)


def cited(packs: list[SkillPack]) -> list[dict]:
    return [{"name": p.name, "title": p.title} for p in packs]
