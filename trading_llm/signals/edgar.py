"""SEC EDGAR client — Form 4 (insider) + 13F (institutional) signals.

Free + official. SEC fair-access rules require a descriptive ``User-Agent`` and
keeping request rates modest; every fetch sends the configured UA, uses a short
timeout, and backs off once on 429/503. The *parsing* functions
(``parse_form4`` / ``parse_13f``) are pure and take an XML string, so tests feed
saved fixtures with no network.

Discovery uses the official submissions feed (``data.sec.gov/submissions``), which
for an issuer CIK includes its insiders' Form 4 filings, plus ``company_tickers.json``
for ticker→CIK resolution.
"""
from __future__ import annotations

import time
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta

from trading_llm.signals.models import (
    Signal, INSIDER_BUY, INSIDER_SELL, INST_13F,
)

SUBMISSIONS_URL = "https://data.sec.gov/submissions/CIK{cik:010d}.json"
TICKERS_URL = "https://www.sec.gov/files/company_tickers.json"
ARCHIVE_BASE = "https://www.sec.gov/Archives/edgar/data/{cik}/{accnd}/"

INSIDER_LAG = "~2-day lag"
INST_LAG = "~45-day lag (last quarter)"

_TRANSIENT = {429, 503, 502, 504}


# --------------------------------------------------------------------------- #
# HTTP (urllib — always available; no optional dependency)
# --------------------------------------------------------------------------- #
def _get(url: str, ua: str, timeout: int = 12, retries: int = 1) -> bytes | None:
    last_status = None
    for attempt in range(retries + 1):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": ua,
                                                       "Accept-Encoding": "gzip, deflate"})
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                data = resp.read()
                enc = resp.headers.get("Content-Encoding", "")
                if "gzip" in enc:
                    import gzip
                    data = gzip.decompress(data)
                return data
        except urllib.error.HTTPError as exc:  # type: ignore[attr-defined]
            last_status = exc.code
            if exc.code in _TRANSIENT and attempt < retries:
                time.sleep(1.5 * (attempt + 1))
                continue
            return None
        except Exception:
            if attempt < retries:
                time.sleep(1.0)
                continue
            return None
    return None


def _get_text(url: str, ua: str, **kw) -> str | None:
    b = _get(url, ua, **kw)
    return b.decode("utf-8", "replace") if b is not None else None


def _get_json(url: str, ua: str, **kw):
    import json
    b = _get(url, ua, **kw)
    if b is None:
        return None
    try:
        return json.loads(b.decode("utf-8", "replace"))
    except Exception:
        return None


# --------------------------------------------------------------------------- #
# XML helpers (namespace-agnostic — 13F filers vary in prefixing)
# --------------------------------------------------------------------------- #
def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1] if "}" in tag else tag


def _first(elem, name: str):
    """First *descendant* (not self) whose local tag matches ``name``."""
    if elem is None:
        return None
    for node in elem.iter():
        if node is elem:
            continue
        if _local(node.tag) == name:
            return node
    return None


def _find(elem, *names: str):
    """Walk a local-name path: each name descends into the previous match.
    With one name, returns the first matching descendant."""
    cur = elem
    for n in names:
        cur = _first(cur, n)
        if cur is None:
            return None
    return cur


def _text(elem, *names: str) -> str:
    """Text at a local-name path. With no names, returns ``elem``'s own text."""
    node = _find(elem, *names) if names else elem
    return (node.text or "").strip() if node is not None and node.text else ""


def _to_float(s: str) -> float:
    try:
        return float(str(s).replace(",", "").strip())
    except Exception:
        return 0.0


# --------------------------------------------------------------------------- #
# ticker <-> CIK and issuer-name index (cached in-process)
# --------------------------------------------------------------------------- #
_tickers_cache: dict | None = None


def _normalize_name(name: str) -> str:
    """Collapse an issuer name to an alnum key for fuzzy 13F-name → ticker matching."""
    up = "".join(ch for ch in str(name).upper() if ch.isalnum())
    for suf in ("INCORPORATED", "CORPORATION", "COMPANY", "HOLDINGS", "HOLDING",
                "GROUP", "INC", "CORP", "CO", "LTD", "PLC", "LLC", "COM", "CLA", "CLB", "CLC"):
        if up.endswith(suf) and len(up) > len(suf) + 2:
            up = up[: -len(suf)]
    return up


def load_ticker_maps(ua: str) -> dict:
    """Return {'by_ticker': {TICKER: cik}, 'by_name': {normname: TICKER}}. Cached."""
    global _tickers_cache
    if _tickers_cache is not None:
        return _tickers_cache
    raw = _get_json(TICKERS_URL, ua)
    by_ticker: dict[str, int] = {}
    by_name: dict[str, str] = {}
    if isinstance(raw, dict):
        for row in raw.values():
            try:
                tkr = str(row["ticker"]).upper()
                cik = int(row["cik_str"])
                title = str(row.get("title", ""))
            except Exception:
                continue
            by_ticker.setdefault(tkr, cik)
            key = _normalize_name(title)
            if key:
                by_name.setdefault(key, tkr)
    _tickers_cache = {"by_ticker": by_ticker, "by_name": by_name}
    return _tickers_cache


def ticker_to_cik(symbol: str, ua: str) -> int | None:
    return load_ticker_maps(ua)["by_ticker"].get(str(symbol).upper())


# --------------------------------------------------------------------------- #
# Form 4 — insider transactions
# --------------------------------------------------------------------------- #
def _owner_label(root) -> str:
    name = _text(root, "rptOwnerName") or "Insider"
    # Title casing from the relationship block.
    rel = _find(root, "reportingOwnerRelationship")
    roles = []
    if rel is not None:
        if _text(rel, "isDirector").lower() in ("1", "true"):
            roles.append("Director")
        if _text(rel, "isOfficer").lower() in ("1", "true"):
            roles.append(_text(rel, "officerTitle") or "Officer")
        if _text(rel, "isTenPercentOwner").lower() in ("1", "true"):
            roles.append("10% owner")
    nice = " ".join(w.capitalize() for w in name.replace(",", " ").split())
    return f"{nice} ({', '.join(roles)})" if roles else nice


def parse_form4(xml_text: str, *, as_of: str = "", source_url: str = "") -> list[Signal]:
    """Parse a Form 4 ownership XML into open-market buy/sell Signals (codes P/S)."""
    try:
        root = ET.fromstring(xml_text)
    except Exception:
        return []
    if _text(root, "documentType") not in ("4", ""):
        # Some filings omit/rename; still try, but skip clearly-wrong docs.
        pass
    symbol = (_text(root, "issuerTradingSymbol") or "").upper()
    date = _text(root, "periodOfReport")
    owner = _owner_label(root)
    out: list[Signal] = []
    for node in root.iter():
        if _local(node.tag) != "nonDerivativeTransaction":
            continue
        code = _text(node, "transactionCode").upper()
        if code not in ("P", "S"):  # only open-market purchases/sales
            continue
        shares = _to_float(_text(node, "transactionShares", "value")
                           or _text(_find(node, "transactionShares"), "value"))
        price = _to_float(_text(_find(node, "transactionPricePerShare"), "value"))
        tdate = _text(_find(node, "transactionDate"), "value") or date
        kind = INSIDER_BUY if code == "P" else INSIDER_SELL
        direction = 1 if code == "P" else -1
        sec = _text(_find(node, "securityTitle"), "value") or "shares"
        out.append(Signal(
            kind=kind, symbol=symbol, date=tdate, actor=owner, direction=direction,
            size_usd=shares * price, source_url=source_url, as_of=as_of,
            lag_note=INSIDER_LAG,
            detail=f"{'Bought' if direction > 0 else 'Sold'} {shares:,.0f} {sec} "
                   f"@ ${price:,.2f}",
        ))
    return out


def fetch_insider_signals(symbol: str, ua: str, *, lookback_days: int = 120,
                          max_filings: int = 15, as_of: str | None = None) -> list[Signal]:
    """Discover + parse recent Form 4 filings for a ticker. Fail-soft → []."""
    as_of = as_of or datetime.now().strftime("%Y-%m-%d")
    cik = ticker_to_cik(symbol, ua)
    if cik is None:
        return []
    sub = _get_json(SUBMISSIONS_URL.format(cik=cik), ua)
    if not isinstance(sub, dict):
        return []
    recent = (sub.get("filings") or {}).get("recent") or {}
    forms = recent.get("form") or []
    accs = recent.get("accessionNumber") or []
    docs = recent.get("primaryDocument") or []
    dates = recent.get("filingDate") or []
    cutoff = (datetime.now() - timedelta(days=lookback_days)).strftime("%Y-%m-%d")
    out: list[Signal] = []
    seen = 0
    for i, form in enumerate(forms):
        if form != "4":
            continue
        if i < len(dates) and dates[i] < cutoff:
            break  # recent[] is newest-first; older than lookback → stop
        if seen >= max_filings:
            break
        seen += 1
        try:
            accnd = accs[i].replace("-", "")
            doc = docs[i].split("/")[-1] or "form4.xml"  # raw XML lives at folder root
            base = ARCHIVE_BASE.format(cik=cik, accnd=accnd)
            url = base + doc
            xml = _get_text(url, ua)
            if xml:
                out.extend(parse_form4(xml, as_of=as_of, source_url=url))
        except Exception:
            continue
    return out


# --------------------------------------------------------------------------- #
# 13F — institutional holdings (curated filers)
# --------------------------------------------------------------------------- #
def parse_13f(xml_text: str) -> list[dict]:
    """Parse a 13F information table XML into holdings dicts.
    Returns [{name, cusip, value_usd, shares}], fail-soft → []."""
    try:
        root = ET.fromstring(xml_text)
    except Exception:
        return []
    out: list[dict] = []
    for node in root.iter():
        if _local(node.tag) != "infoTable":
            continue
        name = _text(_find(node, "nameOfIssuer")) or _text(node, "nameOfIssuer")
        cusip = _text(node, "cusip")
        value = _to_float(_text(node, "value"))
        shares = _to_float(_text(node, "sshPrnamt"))
        if name:
            out.append({"name": name, "cusip": cusip, "value_usd": value, "shares": shares})
    return out


def latest_13f_url(cik: int, ua: str) -> tuple[str | None, str | None]:
    """Return (info_table_xml_url, report_date) for a filer's most recent 13F-HR."""
    sub = _get_json(SUBMISSIONS_URL.format(cik=cik), ua)
    if not isinstance(sub, dict):
        return None, None
    recent = (sub.get("filings") or {}).get("recent") or {}
    forms = recent.get("form") or []
    accs = recent.get("accessionNumber") or []
    rpts = recent.get("reportDate") or []
    for i, form in enumerate(forms):
        if form != "13F-HR":
            continue
        accnd = accs[i].replace("-", "")
        base = ARCHIVE_BASE.format(cik=cik, accnd=accnd)
        # The info table is the .xml that isn't primary_doc.xml. List the folder.
        idx = _get_text(base, ua)
        if not idx:
            return None, (rpts[i] if i < len(rpts) else None)
        import re
        for fname in re.findall(r'href="[^"]*?/([^"/]+\.xml)"', idx):
            if "primary_doc" in fname.lower():
                continue
            return base + fname, (rpts[i] if i < len(rpts) else None)
        return None, (rpts[i] if i < len(rpts) else None)
    return None, None


def fetch_filer_holdings(cik: int, filer_name: str, ua: str) -> dict:
    """Return {'report_date', 'url', 'holdings': [..]} for a filer's latest 13F. Fail-soft."""
    url, report_date = latest_13f_url(cik, ua)
    if not url:
        return {"report_date": report_date, "url": "", "holdings": []}
    xml = _get_text(url, ua)
    holdings = parse_13f(xml) if xml else []
    return {"report_date": report_date, "url": url, "holdings": holdings}


def build_holdings_index(filers: list[dict], ua: str) -> dict:
    """Build {TICKER: [{filer, value_usd, report_date, url}]} across curated filers.

    Maps each holding's issuer name → ticker via the SEC company_tickers title index
    (unmapped names are skipped rather than guessed).
    """
    by_name = load_ticker_maps(ua)["by_name"]
    index: dict[str, list[dict]] = {}
    for f in filers:
        try:
            cik = int(str(f.get("cik")).lstrip("0") or "0")
        except Exception:
            continue
        name = f.get("name") or f"CIK {cik}"
        data = fetch_filer_holdings(cik, name, ua)
        # A 13F can list the same issuer many times (split across sub-managers).
        # Aggregate to ONE position per filer per ticker so funds_holding counts
        # distinct filers, not rows, and the value is the filer's total stake.
        per_ticker: dict[str, float] = {}
        for h in data.get("holdings", []):
            tkr = by_name.get(_normalize_name(h["name"]))
            if not tkr:
                continue
            per_ticker[tkr] = per_ticker.get(tkr, 0.0) + float(h.get("value_usd") or 0.0)
        for tkr, val in per_ticker.items():
            index.setdefault(tkr, []).append({
                "filer": name, "value_usd": val,
                "report_date": data.get("report_date") or "", "url": data.get("url", ""),
            })
    return index


def signals_from_holdings(symbol: str, index: dict, as_of: str) -> tuple[list[Signal], int]:
    """Turn the holdings index into INST_13F Signals for one symbol + a fund count."""
    rows = index.get(str(symbol).upper(), [])
    out = [
        Signal(kind=INST_13F, symbol=symbol.upper(), date=r.get("report_date", ""),
               actor=r["filer"], direction=1, size_usd=float(r.get("value_usd", 0.0)),
               detail=f"{r['filer']} holds ${float(r.get('value_usd', 0.0))/1e6:,.0f}M "
                      f"(as of {r.get('report_date', '?')})",
               source_url=r.get("url", ""), as_of=as_of, lag_note=INST_LAG)
        for r in rows
    ]
    return out, len(rows)
