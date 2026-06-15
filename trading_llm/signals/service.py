"""SignalService — orchestrates regime + smart-money sources with disk caching.

Design rules (inherited from the project):
- **Fail-soft:** any source that errors yields empty data + a stale/unavailable flag,
  never an exception. The snapshot/chat must never break because SEC is slow.
- **Non-blocking snapshot:** the snapshot reads cache only (``allow_fetch=False``);
  network refreshes happen on a background warm thread at startup and on the
  explicit API endpoints, never inside the chat hot path.
- **Atomic cache:** all writes go through ``core.paths.save_json``.
"""
from __future__ import annotations

import threading
import time
from datetime import datetime

from trading_llm.core import paths
from trading_llm.signals import edgar, congress as congress_mod, eventstudy
from trading_llm.signals.models import Regime, Signal, SignalBundle
from trading_llm.signals.regime import detect_regime

_CACHE_DIR = paths.MEMORY_DIR / "signals_cache"
_REGIME_TTL = 3600          # 1h
_INSIDER_TTL_DEFAULT = 12 * 3600
_INDEX_TTL = 24 * 3600      # 13F (quarterly) + congress indexes


def _default_cfg() -> dict:
    return {
        "enabled": True,
        "sec_user_agent": "TradingLLM research example@example.com",
        "cache_ttl_hours": 12,
        "sources": {"insiders": True, "institutional_13f": True, "congress": True},
        "famous_filers": [{"cik": "0001067983", "name": "Berkshire Hathaway"}],
        "congress_sources": None,  # None -> module defaults
    }


class SignalService:
    def __init__(self, data, settings: dict | None = None, warm: bool = True):
        self.data = data
        cfg = {**_default_cfg(), **((settings or {}).get("signals") or {})}
        self.cfg = cfg
        self.enabled = bool(cfg.get("enabled", True))
        self.ua = cfg.get("sec_user_agent") or _default_cfg()["sec_user_agent"]
        self.sources = {**_default_cfg()["sources"], **(cfg.get("sources") or {})}
        self.filers = cfg.get("famous_filers") or []
        self.congress_sources = cfg.get("congress_sources")
        self.insider_ttl = int(float(cfg.get("cache_ttl_hours", 12)) * 3600) or _INSIDER_TTL_DEFAULT
        self._regime: Regime | None = None
        self._regime_ts = 0.0
        self._lock = threading.RLock()
        if warm and self.enabled:
            threading.Thread(target=self._warm, daemon=True).start()

    # ---------------- cache plumbing ----------------
    @staticmethod
    def _path(name: str):
        return _CACHE_DIR / f"{name}.json"

    def _read(self, name: str, ttl: int) -> tuple[object, bool, bool]:
        """Return (data, fresh, exists)."""
        blob = paths.load_json(self._path(name), None)
        if not isinstance(blob, dict) or "ts" not in blob:
            return None, False, False
        fresh = (time.time() - float(blob["ts"])) < ttl
        return blob.get("data"), fresh, True

    def _write(self, name: str, data) -> None:
        try:
            paths.save_json(self._path(name), {"ts": time.time(), "data": data})
        except Exception:
            pass

    # ---------------- regime ----------------
    def regime(self, force: bool = False) -> Regime:
        with self._lock:
            if not force and self._regime and (time.time() - self._regime_ts) < _REGIME_TTL:
                return self._regime
        r = Regime(ok=False)
        try:
            r = detect_regime(self.data)
        except Exception:
            r = Regime(ok=False, summary="Regime unavailable.",
                       as_of=datetime.now().strftime("%Y-%m-%d"))
        with self._lock:
            if r.ok:
                self._regime, self._regime_ts = r, time.time()
                self._write("regime", r.to_dict())
        return r

    def cached_regime(self) -> Regime:
        """Non-blocking: in-memory → disk → ok=False. Never computes."""
        with self._lock:
            if self._regime:
                return self._regime
        data, _fresh, exists = self._read("regime", _REGIME_TTL)
        if exists and isinstance(data, dict):
            r = Regime(**{k: data.get(k) for k in Regime().__dict__ if k in data})
            with self._lock:
                self._regime = r
            return r
        return Regime(ok=False)

    # ---------------- 13F holdings index ----------------
    def _holdings_index(self, allow_fetch: bool) -> dict:
        data, fresh, exists = self._read("holdings_13f", _INDEX_TTL)
        if exists and (fresh or not allow_fetch):
            return data or {}
        if not allow_fetch or not self.sources.get("institutional_13f") or not self.filers:
            return (data or {}) if exists else {}
        try:
            idx = edgar.build_holdings_index(self.filers, self.ua)
            self._write("holdings_13f", idx)
            return idx
        except Exception:
            return (data or {}) if exists else {}

    # ---------------- congress index ----------------
    def _congress_index(self, allow_fetch: bool) -> dict:
        data, fresh, exists = self._read("congress", _INDEX_TTL)
        if exists and (fresh or not allow_fetch):
            return data or {"index": {}, "available": False}
        if not allow_fetch or not self.sources.get("congress"):
            return (data or {"index": {}, "available": False}) if exists else {"index": {}, "available": False}
        try:
            res = congress_mod.fetch_congress_index(self.ua, self.congress_sources)
            # store signals as dicts
            serial = {"available": res["available"],
                      "index": {k: [s.to_dict() for s in v] for k, v in res["index"].items()}}
            self._write("congress", serial)
            return serial
        except Exception:
            return (data or {"index": {}, "available": False}) if exists else {"index": {}, "available": False}

    # ---------------- insiders (per symbol) ----------------
    def _insiders(self, symbol: str, allow_fetch: bool) -> tuple[list[Signal], bool]:
        """Return (signals, stale)."""
        name = f"insider_{symbol.upper()}"
        data, fresh, exists = self._read(name, self.insider_ttl)
        if exists and (fresh or not allow_fetch):
            sigs = [Signal.from_dict(d) for d in (data or [])]
            return sigs, (not fresh)
        if not allow_fetch or not self.sources.get("insiders"):
            return ([Signal.from_dict(d) for d in (data or [])] if exists else []), exists
        try:
            sigs = edgar.fetch_insider_signals(symbol, self.ua)
            self._write(name, [s.to_dict() for s in sigs])
            return sigs, False
        except Exception:
            return ([Signal.from_dict(d) for d in (data or [])] if exists else []), exists

    # ---------------- public bundle ----------------
    def signals_for(self, symbol: str, allow_fetch: bool = True) -> SignalBundle:
        symbol = (symbol or "").upper()
        if not self.enabled or not symbol:
            return SignalBundle.build(symbol, [])
        all_sigs: list[Signal] = []
        stale = False
        unavailable: list[str] = []

        sigs, s_stale = self._insiders(symbol, allow_fetch)
        all_sigs.extend(sigs)
        stale = stale or s_stale

        idx = self._holdings_index(allow_fetch)
        f_sigs, funds = edgar.signals_from_holdings(
            symbol, idx, datetime.now().strftime("%Y-%m-%d"))
        all_sigs.extend(f_sigs)

        cong = self._congress_index(allow_fetch)
        for d in (cong.get("index") or {}).get(symbol, []):
            all_sigs.append(Signal.from_dict(d))
        if self.sources.get("congress") and not cong.get("available"):
            unavailable.append("congress")

        return SignalBundle.build(symbol, all_sigs, funds_holding=funds,
                                  stale=stale, sources_unavailable=unavailable)

    def cached_bundle(self, symbol: str) -> SignalBundle:
        """Non-blocking bundle for the snapshot (cache only)."""
        return self.signals_for(symbol, allow_fetch=False)

    # ---------------- event study (Phase B) ----------------
    def _ohlc_series(self, symbol: str, period: str = "5y"):
        """(dates, closes) from daily OHLC — for the event study. Fail-soft → ([], [])."""
        from datetime import datetime
        dates, closes = [], []
        try:
            candles = self.data.get_ohlc(symbol, period, "1d")
        except Exception:
            return [], []
        for c in candles or []:
            try:
                d = datetime.strptime(str(c.get("time"))[:10], "%Y-%m-%d").date()
            except Exception:
                continue
            dates.append(d)
            closes.append(float(c["close"]))
        return dates, closes

    def _insider_history(self, symbol: str, allow_fetch: bool = True) -> list[Signal]:
        """Multi-year insider events for the study (cached separately, longer window)."""
        name = f"insider_hist_{symbol.upper()}"
        data, fresh, exists = self._read(name, _INDEX_TTL)
        if exists and (fresh or not allow_fetch):
            return [Signal.from_dict(d) for d in (data or [])]
        if not allow_fetch or not self.sources.get("insiders"):
            return [Signal.from_dict(d) for d in (data or [])] if exists else []
        try:
            sigs = edgar.fetch_insider_signals(symbol, self.ua, lookback_days=1825, max_filings=400)
            self._write(name, [s.to_dict() for s in sigs])
            return sigs
        except Exception:
            return [Signal.from_dict(d) for d in (data or [])] if exists else []

    def study_signal(self, symbol: str, kind: str = "insider_buy",
                     horizons=eventstudy.DEFAULT_HORIZONS) -> dict:
        """Event study: does ``kind`` historically precede out-performance for ``symbol``?"""
        symbol = (symbol or "").upper()
        if not self.enabled or not symbol:
            return {"ok": False, "reason": "Signals are disabled."}
        if kind not in ("insider_buy", "insider_sell"):
            return {"ok": False, "reason": f"Event study supports insider buys/sells, not '{kind}'."}
        sigs = [s for s in self._insider_history(symbol) if s.kind == kind]
        events = [{"date": s.date} for s in sigs if s.date]
        sd, sc = self._ohlc_series(symbol)
        bd, bc = self._ohlc_series("SPY")
        if not sd or not bd:
            return {"ok": False, "symbol": symbol, "kind": kind,
                    "n_events": len(events), "reason": "Price history unavailable right now."}
        res = eventstudy.event_study(events, sd, sc, bd, bc, horizons)
        res["symbol"] = symbol
        res["kind"] = kind
        res["explain"] = eventstudy.explain(res)
        return res

    # ---------------- background warm ----------------
    def _warm(self) -> None:
        try:
            self.regime(force=True)
        except Exception:
            pass
        try:
            self._holdings_index(allow_fetch=True)
        except Exception:
            pass
        try:
            self._congress_index(allow_fetch=True)
        except Exception:
            pass
