"""TradingEngine — the core that the UI talks to.

Responsibilities:
- assemble context (live market snapshot + paper account + profile + journal)
- call the brain (provider router) and return the reply
- parse any ```trade proposal and enforce risk gates before placing (paper) orders
- grow persistent memory (profile + journal) so it 'learns' over time

Data comes from the MarketData layer (Finnhub/yfinance/Alpaca). Trading runs
through the local mock PaperBroker by default (no brokerage account required).

Phase 0 keeps the original single-brain ``ask()`` flow. Phase 1 plugs the
multi-agent debate in at the ``_reason()`` seam without changing this surface.
"""
from __future__ import annotations

import json
import re
import threading

from datetime import datetime

from trading_llm.core import config as app_config
from trading_llm.core.paths import LEARN_PATH
from trading_llm.brain.providers import ProviderRouter
from trading_llm.brain.prompts import (
    SYSTEM_PROMPT, BEGINNER_ADDENDUM, MEMORY_EXTRACT_SYSTEM, memory_extract_prompt,
    STRATEGY_GEN_SYSTEM, strategy_gen_prompt,
)
from trading_llm.learn import skills
from trading_llm.brain.debate import DebateEngine, rating_to_proposal
from trading_llm.brain import reflection
from trading_llm.backtest import (
    backtest as run_backtest, explain as explain_backtest, list_strategies,
    optimize as run_optimize, explain_optimize,
    run_custom, validate_strategy, to_pine,
)
from trading_llm.factors import (
    bench as run_factor_bench, explain as explain_factors, DEFAULT_UNIVERSE, clean_universe,
)
from trading_llm import shadow
from trading_llm import gamify
from trading_llm.risk import sizing as risk_sizing
from trading_llm.shadow import diagnostics as shadow_diag
from trading_llm import edge as edge_signals_pkg
from trading_llm import scanner as composite_scanner
from trading_llm.alerts import rules as alert_rules, store as alert_store, walkforward as alert_wf
from trading_llm.market.data import MarketData, is_crypto
from trading_llm.broker.paper_broker import PaperBroker
from trading_llm.broker import safety
from trading_llm.market import snapshot, indicators
from trading_llm.signals import SignalService, signal_format, learning as signal_learning
from trading_llm.memory import profile as profile_mem
from trading_llm.memory import journal
from trading_llm.memory import decision_log
from trading_llm.memory import notes as notes_mem
from trading_llm.memory import goals as goals_mem

_BACKTEST_EXTRACT_SYSTEM = "Return ONLY valid JSON. No markdown, no commentary."

_TRADE_BLOCK = re.compile(r"```trade\s*(\{.*?\})\s*```", re.DOTALL)
_DEEP_TRIGGERS = ("deep analysis", "deep dive", "thorough", "in detail", "detailed analysis")

_STOPWORDS = {
    "I", "A", "AN", "THE", "AND", "OR", "IF", "IS", "IT", "AT", "ON", "IN", "TO", "OF",
    "DO", "MY", "ME", "WE", "BE", "SO", "US", "AM", "PM", "OK", "NO", "GO", "UP",
    "USD", "USA", "ETF", "ETFS", "RSI", "MACD", "SMA", "EMA", "CEO", "CFO", "IPO",
    "AI", "LLM", "API", "EPS", "PE", "YOY", "ATH", "FYI", "TLDR", "FAQ", "HODL",
    "BUY", "SELL", "LONG", "SHORT", "CALL", "PUT", "Q", "EOD", "YTD", "MTD",
}
_CRYPTO_ALIASES = {
    "BTC": "BTC/USD", "ETH": "ETH/USD", "SOL": "SOL/USD",
    "DOGE": "DOGE/USD", "AVAX": "AVAX/USD", "LTC": "LTC/USD",
}


class TradingEngine:
    def __init__(self):
        self.settings = app_config.load_settings()
        self.keys = app_config.load_keys()
        self.brain = ProviderRouter(self.settings, self.keys)
        self.debate = DebateEngine(self.brain, self.settings)
        self.data = MarketData(self.settings, self.keys)
        # Smart-money signals + market regime (warms caches in the background).
        self.signals = SignalService(self.data, self.settings)

        starting_cash = self.settings.get("mock_starting_cash", 100000)
        self.broker = PaperBroker(starting_cash)
        self.trading_mode = "mock paper ($%s)" % f"{int(starting_cash):,}"

        self.history: list[dict] = []
        self.watchlist = self.settings.get("watchlist", [])
        self.timeframe = self.settings.get("default_timeframe", "1Day")
        self.lookback = self.settings.get("bars_lookback", 120)
        self._ask_count = 0
        self.brain_mode = "local" if self.brain.order[:1] == ["ollama"] else "cloud"
        self.beginner = bool(self.settings.get("beginner_mode", False))
        # Serializes account/history mutations so concurrent requests (multiple tabs)
        # can't interleave and corrupt the mock account or chat history.
        self._trade_lock = threading.RLock()

    # ---------- status ----------
    def status(self) -> dict:
        nxt = self.data.next_market_open()
        return {
            "providers": self.brain.providers_status(),
            "data_sources": self.data.sources(),
            "trading": self.trading_mode,
            "market_open": self.data.market_open(),
            "next_open": self.data.next_open_label(),
            "next_open_ts": nxt.timestamp() if nxt else None,
            "brain_mode": self.brain_mode,
            "beginner_mode": self.beginner,
            "live": {"enabled": bool(self.settings.get("live_trading", {}).get("enabled")),
                     "halted": safety.is_halted()},
        }

    # ---------- smart-money signals + regime (Phase A) ----------
    def regime_view(self) -> dict:
        """Current market regime (triggers a compute if the cache is cold)."""
        try:
            return signal_format.regime_to_dict(self.signals.regime())
        except Exception as exc:  # noqa: BLE001
            return {"ok": False, "summary": f"unavailable: {exc}"}

    def signals_view(self, symbol: str) -> dict:
        """Smart-money signals for a symbol (fetches + caches on demand)."""
        try:
            return signal_format.bundle_to_dict(self.signals.signals_for(symbol))
        except Exception as exc:  # noqa: BLE001
            return {"symbol": (symbol or "").upper(), "signals": [],
                    "sources_unavailable": ["error"], "error": str(exc)}

    def signal_study(self, symbol: str, kind: str = "insider_buy") -> dict:
        """Event study (Phase B): did this signal historically precede out-performance?"""
        try:
            return self.signals.study_signal(symbol, kind)
        except Exception as exc:  # noqa: BLE001
            return {"ok": False, "symbol": (symbol or "").upper(), "kind": kind, "reason": str(exc)}

    # ---------- act on signals + learn (Phase C) ----------
    def _regime_label(self) -> str:
        try:
            r = self.signals.cached_regime()
            return r.label if r and r.ok else "unknown"
        except Exception:
            return "unknown"

    def signal_ideas(self, limit: int = 8, scan_cap: int = 15) -> dict:
        """Scan for fresh actionable longs — net insider buying over 30d. Each idea
        carries a ready paper-trade proposal (small size, user confirms). Honest:
        candidates to consider, never auto-traded."""
        try:
            signal_learning.resolve_pending()  # lazy, best-effort
        except Exception:
            pass
        regime_label = self._regime_label()
        max_pos = self.settings.get("risk", {}).get("max_position_usd", 2000)
        notional = round(max_pos * 0.25)
        universe = clean_universe(list(self.watchlist) + DEFAULT_UNIVERSE)[:scan_cap]
        ideas: list[dict] = []
        for sym in universe:
            try:
                b = self.signals.signals_for(sym)  # fetch+cache (bounded by scan_cap)
            except Exception:
                continue
            if b.insider_buys_30d >= 1 and b.net_insider_usd_30d > 0:
                score = b.net_insider_usd_30d * (1.25 if regime_label == "risk_on" else 1.0)
                ideas.append({
                    "symbol": sym, "side": "buy", "score": round(score),
                    "net_insider_30d": b.net_insider_usd_30d, "buys_30d": b.insider_buys_30d,
                    "funds_holding": b.funds_holding, "regime": regime_label,
                    "rationale": (f"Fresh insider buying: net +${b.net_insider_usd_30d/1e6:.1f}M over 30d "
                                  f"({b.insider_buys_30d} buy{'s' if b.insider_buys_30d != 1 else ''}); "
                                  f"regime {regime_label}. Public, lagged signal — paper idea, not advice."),
                    "proposal": {
                        "action": "buy", "symbol": sym, "notional": notional,
                        "order_type": "market", "source": "signal_idea", "signal_kind": "insider_buy",
                        "rationale": f"Signal idea: fresh insider buying in {sym} ({regime_label} regime).",
                    },
                })
        ideas.sort(key=lambda x: x["score"], reverse=True)
        return {"regime": regime_label, "notional_each": notional, "ideas": ideas[:limit]}

    def signal_track_record(self) -> dict:
        """Resolve any matured signal trades, then return base rates (Phase C learning)."""
        try:
            signal_learning.resolve_pending()
        except Exception:
            pass
        try:
            return signal_learning.view()
        except Exception as exc:  # noqa: BLE001
            return {"overall": {"n": 0}, "by_group": {}, "pending": 0, "total": 0, "error": str(exc)}

    # ---------- risk & position sizing (Phase D1) ----------
    def _trader_stats(self) -> tuple[float | None, float | None, int]:
        """Empirical (win_rate, payoff, n_trips) from closed round-trips — feeds Kelly/RoR."""
        try:
            prof = shadow_diag.analyze(shadow.load_round_trips())
            if prof.get("ok"):
                return (prof.get("win_rate_pct") or 0) / 100.0, prof.get("payoff_ratio"), prof.get("n_trips", 0)
        except Exception:
            pass
        return None, None, 0

    def risk_dashboard(self) -> dict:
        acct = self.account() or {}
        equity = acct.get("equity") or 0.0
        rcfg = self.settings.get("risk", {})
        stop_pct = float(rcfg.get("default_stop_pct", risk_sizing.DEFAULT_STOP_PCT))
        heat = risk_sizing.portfolio_heat(self.positions(), equity, stop_pct=stop_pct)
        cur_risk = float(rcfg.get("account_risk_pct", risk_sizing.DEFAULT_ACCOUNT_RISK_PCT))
        out = {
            "equity": equity, "heat": heat,
            "rules": {
                "account_risk_pct": cur_risk,
                "max_portfolio_heat_pct": float(rcfg.get("max_portfolio_heat_pct",
                                                         risk_sizing.DEFAULT_MAX_HEAT_PCT)),
                "max_position_usd": rcfg.get("max_position_usd", 2000),
                "default_stop_pct": stop_pct,
            },
        }
        wr, payoff, n = self._trader_stats()
        out["n_trips"] = n
        if wr is not None and payoff:
            sugg = risk_sizing.suggested_risk_pct(wr, payoff)
            out["stats"] = {"win_rate": round(wr, 3), "payoff": payoff,
                            "expectancy_r": round(risk_sizing.expectancy(wr, payoff), 3)}
            out["kelly"] = round(risk_sizing.kelly_fraction(wr, payoff), 4)
            out["suggested_risk_pct"] = sugg
            out["ruin"] = {
                "at_current": risk_sizing.risk_of_ruin(wr, payoff, cur_risk),
                "at_suggested": risk_sizing.risk_of_ruin(wr, payoff, sugg or cur_risk),
                "at_5pct": risk_sizing.risk_of_ruin(wr, payoff, 0.05),
            }
        else:
            out["stats"] = None
            out["note"] = ("Close some paper round-trips and I'll compute Kelly + risk-of-ruin "
                           "from YOUR win rate and payoff.")
        return out

    def position_size(self, symbol: str, entry=None, stop=None, risk_pct=None,
                      method: str = "fixed") -> dict:
        acct = self.account() or {}
        equity = acct.get("equity") or 0.0
        rcfg = self.settings.get("risk", {})
        rp = float(risk_pct) if risk_pct else float(rcfg.get("account_risk_pct",
                                                            risk_sizing.DEFAULT_ACCOUNT_RISK_PCT))
        try:
            entry = float(entry) if entry else (self.data.get_price(symbol) or 0.0)
        except Exception:
            entry = self.data.get_price(symbol) or 0.0
        try:
            stop = float(stop) if stop not in (None, "") else None
        except Exception:
            stop = None
        if stop is None and method == "atr" and entry:
            candles = self.data.get_ohlc(symbol, "6mo", "1d")
            atr = risk_sizing.atr_from_bars([c["high"] for c in candles], [c["low"] for c in candles],
                                            [c["close"] for c in candles], 14)
            if atr:
                stop = round(entry - 2 * atr, 2)  # 2-ATR stop for a long
        if stop is None and entry:
            stop = round(entry * (1 - float(rcfg.get("default_stop_pct",
                                                     risk_sizing.DEFAULT_STOP_PCT))), 2)
        size = risk_sizing.fixed_fractional_size(equity, rp, entry, float(stop or 0))
        size.update({"symbol": (symbol or "").upper(), "entry": round(entry, 2),
                     "stop": round(float(stop or 0), 2), "risk_pct": rp, "method": method,
                     "ruin_at_risk_pct": risk_sizing.risk_of_ruin(0.5, 1.5, rp)})
        return size

    def risk_check(self, proposal: dict) -> dict:
        acct = self.account() or {}
        return risk_sizing.pretrade_check(
            proposal, acct.get("equity") or 0.0, acct.get("buying_power") or 0.0,
            self.positions(), self.settings.get("risk", {}), journal.trades_today())

    # ---------- under-crowded "edge" signals (Phase D2) ----------
    def edge_signals(self, symbol: str) -> dict:
        """Options flow + short interest + PEAD + seasonality for a symbol. Fail-soft per source."""
        symbol = (symbol or "").upper()
        out: dict = {"symbol": symbol}
        try:
            candles = self.data.get_ohlc(symbol, "10y", "1d", 3000)  # full history (default limit caps at 400)
            dates = [datetime.strptime(str(c["time"])[:10], "%Y-%m-%d").date() for c in candles]
            closes = [float(c["close"]) for c in candles]
            out["seasonality"] = edge_signals_pkg.seasonality.analyze(dates, closes)
        except Exception as exc:  # noqa: BLE001
            out["seasonality"] = {"ok": False, "reason": str(exc)}
        try:
            out["short_interest"] = edge_signals_pkg.short_interest.fetch(symbol)
        except Exception as exc:  # noqa: BLE001
            out["short_interest"] = {"ok": False, "reason": str(exc)}
        try:
            out["options_flow"] = edge_signals_pkg.options_flow.fetch(symbol, self.data.get_price(symbol))
        except Exception as exc:  # noqa: BLE001
            out["options_flow"] = {"ok": False, "reason": str(exc)}
        try:
            out["pead"] = edge_signals_pkg.pead.analyze(symbol, self.data)
        except Exception as exc:  # noqa: BLE001
            out["pead"] = {"ok": False, "reason": str(exc)}
        return out

    # ---------- composite multi-signal scanner (Phase D3) ----------
    def _scan_symbol_raw(self, sym: str) -> dict:
        """Gather the fast-ish per-symbol components for the composite score. Fail-soft."""
        raw: dict = {}
        try:
            ind = snapshot.symbol_indicators(self.data, sym, self.timeframe, self.lookback)
            raw["trend"] = ind.get("trend")
            raw["rsi"] = ind.get("rsi")
            raw["momentum"] = ind.get("momentum")
            p, s50 = ind.get("price"), ind.get("sma50")
            if p and s50:
                raw["price_vs_sma50_pct"] = round((p / s50 - 1) * 100, 2)
        except Exception:
            pass
        try:
            b = self.signals.signals_for(sym)
            raw["net_insider_30d"] = b.net_insider_usd_30d
            raw["funds_holding"] = b.funds_holding
        except Exception:
            pass
        try:
            candles = self.data.get_ohlc(sym, "10y", "1d", 3000)
            dts = [datetime.strptime(str(c["time"])[:10], "%Y-%m-%d").date() for c in candles]
            cls = [float(c["close"]) for c in candles]
            sea = edge_signals_pkg.seasonality.analyze(dts, cls)
            if sea.get("ok") and sea.get("current"):
                raw["seasonality_month_pct"] = sea["current"]["avg_pct"]
        except Exception:
            pass
        try:
            si = edge_signals_pkg.short_interest.fetch(sym)
            if si.get("ok"):
                raw["squeeze_score"] = si.get("squeeze_score")
        except Exception:
            pass
        return raw

    def scan_universe(self, scan_cap: int = 10, limit: int = 12) -> dict:
        """Rank the universe by the composite score, gated by market regime."""
        regime = self._regime_label()
        universe = clean_universe(list(self.watchlist) + DEFAULT_UNIVERSE)[:scan_cap]
        rows = []
        for sym in universe:
            raw = self._scan_symbol_raw(sym)
            sc = composite_scanner.score_symbol(raw)
            sc["symbol"] = sym
            sc["readings"] = {
                "net_insider_30d": raw.get("net_insider_30d"),
                "funds_holding": raw.get("funds_holding"),
                "seasonality_month_pct": raw.get("seasonality_month_pct"),
                "squeeze_score": raw.get("squeeze_score"),
                "trend": raw.get("trend"),
            }
            rows.append(sc)
        rows.sort(key=lambda r: r["score"], reverse=True)
        note = ("⚠️ Regime is RISK-OFF — discount bullish scores and size down."
                if regime == "risk_off"
                else "A transparent blend of individually-weak signals — a ranking to research, not a guarantee.")
        return {"regime": regime, "scanned": len(rows), "results": rows[:limit], "note": note}

    # ---------- automation: alert rules (Phase D4) ----------
    def alert_fields(self) -> dict:
        return {"fields": alert_rules.FIELDS, "ops": list(alert_rules.OPS)}

    def list_alert_rules(self) -> list:
        return alert_store.list_rules()

    def save_alert_rule(self, rule: dict) -> dict:
        return alert_store.save_rule(rule)

    def delete_alert_rule(self, rid: str) -> dict:
        return {"ok": alert_store.delete_rule(rid)}

    def _alert_features(self, sym: str, regime: str) -> dict:
        """Current per-symbol feature vector for rule evaluation. Fail-soft."""
        raw = self._scan_symbol_raw(sym)
        f: dict = {
            "regime": regime,
            "rsi": raw.get("rsi"),
            "trend": raw.get("trend"),
            "macd": {"bullish": "bullish", "bearish": "bearish"}.get(raw.get("momentum"), "flat"),
            "net_insider_30d": raw.get("net_insider_30d"),
            "funds_holding": raw.get("funds_holding"),
            "seasonality_month_pct": raw.get("seasonality_month_pct"),
            "squeeze_score": raw.get("squeeze_score"),
        }
        try:
            f["composite"] = composite_scanner.score_symbol(raw)["score"]
        except Exception:
            pass
        try:
            bars = self.data.get_bars(sym, "1Day", 220)
            if len(bars) >= 200:
                s200 = sum(bars[-200:]) / 200
                f["price_vs_sma200_pct"] = round((bars[-1] / s200 - 1) * 100, 2)
        except Exception:
            pass
        try:
            f["insider_buys_30d"] = self.signals.cached_bundle(sym).insider_buys_30d
        except Exception:
            pass
        return f

    def evaluate_alerts(self, scan_cap: int = 15) -> dict:
        """Evaluate enabled rules against current data; return fired alerts + sized proposals."""
        regime = self._regime_label()
        rules = [r for r in alert_store.list_rules() if r.get("enabled")]
        if not rules:
            return {"regime": regime, "alerts": [], "scanned": 0,
                    "note": "No enabled rules. Toggle one on (or create one) to start monitoring."}
        universe = clean_universe(list(self.watchlist) + DEFAULT_UNIVERSE)[:scan_cap]
        needed: set = set()
        for r in rules:
            if r.get("scope") == "symbols" and r.get("symbols"):
                needed |= {s.upper() for s in r["symbols"]}
            else:
                needed |= set(universe)
        feats = {}
        for s in needed:
            try:
                feats[s] = self._alert_features(s, regime)
            except Exception:
                feats[s] = {}
        max_pos = self.settings.get("risk", {}).get("max_position_usd", 2000)
        alerts = []
        for r in rules:
            syms = ([s.upper() for s in r["symbols"]] if r.get("scope") == "symbols" and r.get("symbols")
                    else universe)
            for s in syms:
                f = feats.get(s, {})
                if alert_rules.evaluate_conditions(r.get("conditions", []), f):
                    size = self.position_size(s, risk_pct=r.get("risk_pct", 0.01), method="atr")
                    notional = min(size.get("notional") or 0, max_pos) or round(max_pos * 0.25)
                    alerts.append({
                        "rule_id": r.get("id"), "rule_name": r.get("name"), "symbol": s,
                        "matched": alert_rules.matched_conditions(r.get("conditions", []), f),
                        "proposal": {"action": r.get("action", "buy"), "symbol": s,
                                     "notional": round(notional), "order_type": "market",
                                     "source": "signal_idea", "signal_kind": "alert",
                                     "rationale": f"Alert '{r.get('name')}' fired on {s} ({regime} regime)."},
                    })
        return {"regime": regime, "alerts": alerts, "scanned": len(needed),
                "note": "Mechanical triggers — confirm each; sized by your risk rules."}

    def backtest_rule(self, rule: dict, symbol: str | None = None) -> dict:
        sym = (symbol or (rule.get("symbols") or ["SPY"])[0] or "SPY").upper()
        try:
            candles = self.data.get_ohlc(sym, "5y", "1d", 2000)
            dates = [datetime.strptime(str(c["time"])[:10], "%Y-%m-%d").date() for c in candles]
            closes = [float(c["close"]) for c in candles]
            spy = self.data.get_ohlc("SPY", "5y", "1d", 2000)
            sd = [datetime.strptime(str(c["time"])[:10], "%Y-%m-%d").date() for c in spy]
            sc = [float(c["close"]) for c in spy]
        except Exception as exc:  # noqa: BLE001
            return {"ok": False, "reason": f"Price history unavailable: {exc}"}
        res = alert_wf.backtest(rule, dates, closes, sd, sc)
        res["symbol"] = sym
        return res

    def set_beginner_mode(self, on: bool) -> dict:
        self.beginner = bool(on)
        self.settings["beginner_mode"] = self.beginner
        app_config.save_settings(self.settings)
        return {"beginner_mode": self.beginner}

    def _system_prompt(self) -> str:
        return SYSTEM_PROMPT + ("\n\n" + BEGINNER_ADDENDUM if self.beginner else "")

    # ---------- skill library passthroughs (Phase 4) ----------
    def list_skills(self) -> list[dict]:
        return skills.list_packs()

    def get_skill(self, name: str) -> dict | None:
        pack = skills.get(name)
        if not pack:
            return None
        return {**pack.to_meta(), "body": pack.body}

    def set_brain_mode(self, mode: str) -> dict:
        if mode == "local":
            self.brain.order = ["ollama", "gemini", "openrouter"]
        else:
            mode = "cloud"
            self.brain.order = ["gemini", "openrouter", "ollama"]
        self.brain_mode = mode
        self.settings.setdefault("llm", {})["provider_order"] = self.brain.order
        app_config.save_settings(self.settings)
        return {"brain_mode": mode}

    # ---------- symbol detection ----------
    def _symbols_for(self, text: str) -> list[str]:
        ordered = list(self.watchlist)
        wl_upper = {s.upper() for s in self.watchlist}
        extras: list[str] = []

        for raw in re.findall(r"\$?\b([A-Za-z]{1,5})\b", text):
            tok = raw.upper()
            if tok in _CRYPTO_ALIASES:
                tok = _CRYPTO_ALIASES[tok]
            if tok in wl_upper or tok in {e.upper() for e in extras}:
                continue
            if tok in _STOPWORDS:
                continue
            looks_like_ticker = (f"${raw}" in text) or (raw.isupper() and len(raw) >= 2)
            if looks_like_ticker:
                extras.append(tok)
            if len(extras) >= 4:
                break
        return ordered + extras

    def _wants_deep(self, text: str) -> bool:
        low = text.lower()
        return any(t in low for t in _DEEP_TRIGGERS)

    # ---------- focus ticker + grounded contexts for the debate ----------
    def _focus_ticker(self, text: str, symbols: list[str]) -> str | None:
        """The single ticker a deep analysis is about: first explicitly mentioned,
        else the first watchlist symbol."""
        for raw in re.findall(r"\$?\b([A-Za-z]{1,5})\b", text):
            tok = raw.upper()
            if tok in _CRYPTO_ALIASES:
                return _CRYPTO_ALIASES[tok]
            if tok in _STOPWORDS:
                continue
            if (f"${raw}" in text) or (raw.isupper() and len(raw) >= 2):
                return tok
        if symbols:
            return symbols[0]
        return self.watchlist[0] if self.watchlist else None

    def _technical_context(self, ticker: str) -> str:
        ind = snapshot.symbol_indicators(self.data, ticker, self.timeframe, self.lookback)
        if ind.get("price") is None:
            return f"Ticker: {ticker}\n(No price/indicator data is available right now.)"
        lines = [f"Ticker: {ticker}",
                 f"Timeframe: {self.timeframe} (last {self.lookback} bars)",
                 indicators.summary_line(ticker, ind)]
        for key, label in (("price", "Price"), ("change_pct", "Day change %"),
                           ("rsi", "RSI(14)"), ("rsi_label", "RSI zone"),
                           ("sma20", "SMA20"), ("sma50", "SMA50"),
                           ("trend", "Trend"), ("macd_hist", "MACD histogram"),
                           ("momentum", "MACD momentum")):
            val = ind.get(key)
            if val is not None:
                lines.append(f"  {label}: {val}")
        return "\n".join(lines)

    def _news_context(self, symbols: list[str]) -> str:
        news = self.data.get_news(symbols, limit=6)
        if not news:
            return ""
        return "\n".join(f"- {n['headline']} ({n['created_at']})" for n in news)

    def _signals_context(self, ticker: str) -> str:
        """Smart-money + regime context for the copilot (cache-only, non-blocking).
        Honest framing baked in: these are public, lagged signals, not a buy/sell call."""
        try:
            reg = signal_format.regime_summary(self.signals.cached_regime())
            tag = signal_format.signals_summary(self.signals.cached_bundle(ticker))
        except Exception:
            return ""
        lines: list[str] = []
        if reg:
            lines.append(reg)
        if tag:
            lines.append(f"Smart money on {ticker.upper()}: {tag}")
        if not lines:
            return ""
        lines.append("(Public, lagged disclosures — context only, not a recommendation.)")
        return "[SMART-MONEY & REGIME]\n" + "\n".join(lines)

    def _debate_signals_context(self, ticker: str) -> str:
        """Rich smart-money + regime + track-record context for the committee's
        Smart-Money Analyst (Phase C). Fetch allowed here — the debate is already slow."""
        parts: list[str] = []
        try:
            reg = signal_format.regime_summary(self.signals.regime())
            if reg:
                parts.append(reg)
        except Exception:
            pass
        try:
            bundle = self.signals.signals_for(ticker)
            tag = signal_format.signals_summary(bundle)
            if tag:
                parts.append(f"Smart money on {ticker.upper()}: {tag}")
            for s in bundle.signals[:6]:
                parts.append(f"  - {s.detail} ({s.date}, {s.lag_note})")
            if "congress" in bundle.sources_unavailable:
                parts.append("  (Congressional data unavailable.)")
        except Exception:
            pass
        try:
            tr = signal_learning.track_record_context()
            if tr:
                parts.append(tr)
        except Exception:
            pass
        return "\n".join(parts)

    # ---------- deep multi-agent analysis ----------
    def _run_debate(self, ticker: str, progress=None) -> dict:
        # Learn from past decisions on this ticker (best-effort), then inject lessons.
        try:
            reflection.resolve_pending(self.brain, ticker)
        except Exception:
            pass
        past_context = decision_log.get_past_context(ticker)

        technical_context = self._technical_context(ticker)
        news_context = self._news_context([ticker])
        signals_context = self._debate_signals_context(ticker)

        result = self.debate.run(ticker, technical_context, news_context, past_context,
                                 progress=progress, signals_context=signals_context)

        # Persist the decision so a future run can reflect on its realized outcome.
        decision_log.store_decision(
            ticker, datetime.now().strftime("%Y-%m-%d"), result.final_decision)

        max_pos = self.settings.get("risk", {}).get("max_position_usd", 2000)
        proposal = rating_to_proposal(
            result.rating, ticker, max_pos,
            rationale=f"{result.rating} — multi-agent committee decision.")
        return {
            "reply": result.to_markdown(),
            "provider": "multi-agent debate",
            "proposal": proposal,
            "transcript": result.transcript,
        }

    # ---------- backtesting (Phase 2) ----------
    def _wants_backtest(self, text: str) -> bool:
        low = text.lower()
        return "backtest" in low or "back-test" in low or "back test" in low

    def _backtest_spec(self, user_text: str) -> dict:
        """Ask the model to turn a free-text request into a backtest spec (JSON)."""
        names = ", ".join(s["name"] for s in list_strategies())
        prompt = (
            "Extract a backtest spec from the user's request as JSON with keys:\n"
            '  "symbol": ticker (e.g. "AAPL", "BTC/USD") — REQUIRED\n'
            f'  "strategy": one of [{names}] (default "sma_cross")\n'
            '  "params": object of overrides like {"fast":20,"slow":50} (optional)\n'
            '  "period": one of 1mo,3mo,6mo,1y,2y,5y,10y,max (default "2y")\n'
            '  "interval": "1d" or "1wk" (default "1d")\n'
            'Map phrases like "20/50 moving average crossover" to strategy "sma_cross" '
            'with params {"fast":20,"slow":50}; "MACD" -> "macd"; "RSI dip/mean reversion" '
            '-> "rsi_reversion". Return ONLY JSON.\n\n'
            f"Request: {user_text}\n\nJSON:"
        )
        return self.brain.chat_json(_BACKTEST_EXTRACT_SYSTEM, prompt)

    def _run_backtest_nl(self, user_text: str) -> dict | None:
        spec = self._backtest_spec(user_text)
        symbol = str(spec.get("symbol", "")).upper().strip()
        if not symbol:
            return None  # couldn't pin a ticker -> let normal chat handle it
        if symbol in _CRYPTO_ALIASES:
            symbol = _CRYPTO_ALIASES[symbol]
        result = run_backtest(
            symbol=symbol,
            strategy=spec.get("strategy", "sma_cross"),
            params=spec.get("params") if isinstance(spec.get("params"), dict) else None,
            period=str(spec.get("period", "2y")),
            interval=str(spec.get("interval", "1d")),
        )
        reply = explain_backtest(result)
        if result.ok:
            journal.add_entry("backtest", symbol=symbol, strategy=result.strategy_name,
                              content=f"{result.strategy_label} {result.params} -> "
                                      f"{result.metrics.get('total_return_pct')}% vs "
                                      f"{result.metrics.get('buy_hold_return_pct')}% B&H")
        return {
            "reply": reply, "provider": "backtest", "proposal": None,
            "backtest": {
                "ok": result.ok, "symbol": result.symbol, "strategy": result.strategy_label,
                "metrics": result.metrics, "equity_curve": result.equity_curve,
                "trades": result.trades[-10:],
            },
        }

    def backtest_spec(self, spec: dict) -> dict:
        """Direct programmatic backtest (for the API / future UI)."""
        result = run_backtest(
            symbol=str(spec.get("symbol", "")), strategy=str(spec.get("strategy", "sma_cross")),
            params=spec.get("params") if isinstance(spec.get("params"), dict) else None,
            period=str(spec.get("period", "2y")), interval=str(spec.get("interval", "1d")),
        )
        return {
            "ok": result.ok, "symbol": result.symbol, "strategy": result.strategy_label,
            "params": result.params, "error": result.error, "metrics": result.metrics,
            "equity_curve": result.equity_curve, "trades": result.trades,
            "explanation": explain_backtest(result),
        }

    # ---------- memory & goals commands (Phase 10) ----------
    def _memory_command(self, text: str) -> dict | None:
        """Deterministic remember/recall + goal commands (no LLM)."""
        low = text.lower().strip()
        _Q_WORDS = {"when", "if", "how", "why", "what", "who", "where", "whether", "do", "does", "did"}
        for p in ("remember that ", "remember: ", "remember:", "remember ", "note that ",
                  "note: ", "note:", "make a note that ", "make a note: ", "make a note "):
            if low.startswith(p):
                fact = text.strip()[len(p):].strip()
                if not fact:
                    return {"reply": "What should I remember? Try: *remember I prefer swing trades*.",
                            "provider": "memory", "proposal": None}
                # Don't hijack questions like "remember when AAPL crashed?" — let chat answer.
                first = fact.lower().split()[0] if fact.split() else ""
                if first in _Q_WORDS or fact.rstrip().endswith("?"):
                    return None
                note = notes_mem.add(fact)
                return {"reply": f"📌 Noted — I'll remember that: *{note['text']}*",
                        "provider": "memory", "proposal": None}
        if any(p in low for p in ("what do you remember", "what do you know about me", "recall my",
                                  "show my notes", "list my notes", "my notes")):
            results = notes_mem.search(text, 8) or notes_mem.recent(8)
            if not results:
                return {"reply": "I don't have any saved notes yet. Say *remember …* to save one.",
                        "provider": "memory", "proposal": None}
            body = "\n".join(f"- {n['text']}" for n in results)
            return {"reply": f"Here's what I remember:\n{body}", "provider": "memory", "proposal": None}
        for p in ("set a goal to ", "set a goal: ", "set a goal ", "new goal: ", "new goal ",
                  "my goal is to ", "my goal is ", "goal: "):
            if low.startswith(p):
                title = text.strip()[len(p):].strip()
                if not title:
                    return {"reply": "What's the goal? Try: *set a goal to decide on NVDA this month*.",
                            "provider": "goals", "proposal": None}
                g = goals_mem.add(title)
                return {"reply": f"🎯 Goal set: *{g['title']}*. I'll keep it in mind across our chats.",
                        "provider": "goals", "proposal": None}
        if any(p in low for p in ("my goals", "list goals", "list my goals", "show goals",
                                  "show my goals", "what are my goals", "active goals")):
            gs = goals_mem.active()
            if not gs:
                return {"reply": "No active goals yet. Say *set a goal to …* to start one.",
                        "provider": "goals", "proposal": None}
            body = "\n".join(f"- {g['title']}" for g in gs)
            return {"reply": f"🎯 Your active goals:\n{body}", "provider": "goals", "proposal": None}
        if any(p in low for p in ("complete goal", "complete my goal", "mark goal", "goal done",
                                  "finished my goal", "completed my goal", "mark my goal done")):
            ok = goals_mem.complete()
            return {"reply": "✅ Marked your most recent goal complete — nice work." if ok
                    else "You don't have an active goal to complete.",
                    "provider": "goals", "proposal": None}
        return None

    # ---------- strategy generation (Phase 9) ----------
    def _wants_strategy_gen(self, text: str) -> bool:
        low = text.lower()
        return any(p in low for p in (
            "create a strategy", "build a strategy", "design a strategy", "make a strategy",
            "generate a strategy", "write a strategy", "build me a strategy", "custom strategy",
            "strategy that", "strategy where", "strategy: buy", "pine script"))

    def generate_strategy(self, description: str, symbol: str | None = None,
                          period: str | None = None) -> dict:
        """NL -> rule-DSL spec (via LLM) -> compiled backtest + Pine Script."""
        data = self.brain.chat_json(STRATEGY_GEN_SYSTEM, strategy_gen_prompt(description))
        if not data or "entry" not in data or "exit" not in data:
            return {"ok": False, "error": "Couldn't turn that into a strategy. Try naming the "
                                          "indicator(s), a buy condition, and a sell condition."}
        sym = (symbol or data.get("symbol") or "SPY").upper()
        per = period or data.get("period") or "2y"
        spec = {"name": data.get("name", "Custom strategy"),
                "entry": data["entry"], "exit": data["exit"]}
        ok, err = validate_strategy(spec)
        if not ok:
            return {"ok": False, "error": err, "spec": spec}
        return run_custom(spec, sym, per)

    def custom_backtest(self, spec: dict, symbol: str = "SPY", period: str = "2y") -> dict:
        return run_custom(spec, symbol, period)

    def strategy_pine(self, spec: dict) -> dict:
        ok, err = validate_strategy(spec)
        if not ok:
            return {"ok": False, "error": err}
        return {"ok": True, "pine": to_pine(spec)}

    def _run_strategy_gen_nl(self, user_text: str) -> dict:
        result = self.generate_strategy(user_text)
        if not result.get("ok"):
            return {"reply": f"⚠️ {result.get('error', 'Strategy generation failed.')}",
                    "provider": "strategy builder", "proposal": None}
        if result.get("ok"):
            journal.add_entry("strategy", symbol=result["symbol"],
                              content=f"Generated '{result['name']}': "
                                      f"{result['metrics'].get('total_return_pct')}% vs "
                                      f"{result['metrics'].get('buy_hold_return_pct')}% B&H")
        return {"reply": result["explanation"], "provider": "strategy builder", "proposal": None,
                "strategy": {"ok": True, "symbol": result["symbol"], "name": result["name"],
                             "spec": result["spec"], "metrics": result["metrics"],
                             "equity_curve": result["equity_curve"], "pine": result["pine"]}}

    # ---------- hyperparameter optimization (Phase 7) ----------
    def _wants_optimize(self, text: str) -> bool:
        low = text.lower()
        return any(p in low for p in ("optimize", "hyperopt", "best parameter", "best setting",
                                      "tune ", "best params"))

    def _run_optimize_nl(self, user_text: str) -> dict | None:
        spec = self._backtest_spec(user_text)
        symbol = str(spec.get("symbol", "")).upper().strip()
        if not symbol:
            return None
        if symbol in _CRYPTO_ALIASES:
            symbol = _CRYPTO_ALIASES[symbol]
        result = run_optimize(symbol=symbol, strategy=spec.get("strategy", "sma_cross"),
                              period=str(spec.get("period", "2y")),
                              interval=str(spec.get("interval", "1d")),
                              metric=str(spec.get("metric", "sharpe")))
        return {"reply": explain_optimize(result), "provider": "optimization", "proposal": None,
                "optimize": {"ok": result.ok, "symbol": result.symbol,
                             "strategy": result.strategy_label, "metric": result.metric,
                             "best_params": result.best_params, "results": result.results[:12],
                             "train_metric": result.train_metric, "oos_metric": result.oos_metric,
                             "overfit": result.overfit}}

    def optimize_spec(self, spec: dict) -> dict:
        result = run_optimize(
            symbol=str(spec.get("symbol", "")), strategy=str(spec.get("strategy", "sma_cross")),
            period=str(spec.get("period", "2y")), interval=str(spec.get("interval", "1d")),
            metric=str(spec.get("metric", "sharpe")))
        return {"ok": result.ok, "error": result.error, "symbol": result.symbol,
                "strategy": result.strategy_label, "metric": result.metric,
                "best_params": result.best_params, "default_params": result.default_params,
                "n_combos": result.n_combos, "results": result.results,
                "train_metric": result.train_metric, "oos_metric": result.oos_metric,
                "overfit": result.overfit, "explanation": explain_optimize(result)}

    # ---------- factor zoo / IC bench (Phase 3) ----------
    def _wants_factors(self, text: str) -> bool:
        low = text.lower()
        if "backtest" in low:
            return False  # backtest path owns that intent
        if "factor" in low or "alpha zoo" in low or "alpha scan" in low or "factor scan" in low:
            return True
        return "alpha" in low and any(w in low for w in ("which", "best", "work", "scan", "zoo"))

    def _factor_universe(self) -> list[str]:
        """Default large-cap basket plus any plain-equity watchlist names (crypto +
        futures filtered out so the cross-section stays apples-to-apples)."""
        return clean_universe(DEFAULT_UNIVERSE + list(self.watchlist))

    def _run_factor_scan(self, period: str = "2y", horizon: int = 5) -> dict:
        result = run_factor_bench(universe=self._factor_universe(), period=period, horizon=horizon)
        reply = explain_factors(result)
        if result.ok and result.results:
            best = next((r for r in result.results if r.get("ok")), {})
            journal.add_entry("factor_scan",
                              content=f"{result.n_symbols} names, {period}: best={best.get('label')} "
                                      f"IC={best.get('ic_mean')} IR={best.get('ir')}")
        return {
            "reply": reply, "provider": "factor scan", "proposal": None,
            "factors": {
                "ok": result.ok, "n_symbols": result.n_symbols, "horizon": result.horizon,
                "results": [r for r in result.results if r.get("ok")][:12],
            },
        }

    # ---------- shadow account + gamification (Phase 5) ----------
    def _wants_review(self, text: str) -> bool:
        low = text.lower()
        return any(p in low for p in (
            "review my trad", "analyze my trad", "shadow account", "my biases",
            "my trading behavior", "review my journal", "review my trades"))

    def _wants_coach(self, text: str) -> bool:
        low = text.lower()
        return any(p in low for p in (
            "scorecard", "score my", "grade my", "how am i doing", "my score",
            "challenge", "coach", "rate my trading"))

    def shadow_review(self, csv_text: str | None = None) -> dict:
        result = shadow.review(csv_text)
        return {"reply": result["report"], "provider": "trade review", "proposal": None,
                "shadow": {"ok": result["ok"], "n_trips": result["n_trips"],
                           "profile": result["profile"]}}

    def coach(self) -> dict:
        trips = shadow.load_round_trips()
        account = self.account()
        max_pos = self.settings.get("risk", {}).get("max_position_usd", 2000)
        reply = gamify.coach_report(account, trips, max_pos)
        return {"reply": reply, "provider": "coach", "proposal": None,
                "coach": {
                    "scorecard": gamify.scorecard(account, trips, max_pos),
                    "challenges": gamify.challenges(account, trips, max_pos),
                }}

    def factor_bench(self, spec: dict) -> dict:
        """Direct programmatic factor bench (for the API / future UI)."""
        universe = spec.get("universe") or self._factor_universe()
        result = run_factor_bench(
            universe=[str(s).upper() for s in universe],
            period=str(spec.get("period", "2y")), horizon=int(spec.get("horizon", 5)),
            factor_names=spec.get("factors"),
        )
        return {
            "ok": result.ok, "error": result.error, "universe": result.universe,
            "n_symbols": result.n_symbols, "n_days": result.n_days, "horizon": result.horizon,
            "results": result.results, "explanation": explain_factors(result),
        }

    # ---------- main entry ----------
    def ask(self, user_text: str, deep: bool = False) -> dict:
        deep = deep or self._wants_deep(user_text)
        symbols = self._symbols_for(user_text)
        transcript = None

        # Memory / goal commands (deterministic, no LLM).
        mc = self._memory_command(user_text)
        if mc is not None:
            self._finish_exchange(user_text, mc["reply"])
            return mc

        # Strategy-builder intent -> generate a custom strategy from the description.
        if self._wants_strategy_gen(user_text):
            try:
                out = self._run_strategy_gen_nl(user_text)
                self._finish_exchange(user_text, out["reply"])
                return out
            except Exception as exc:
                print(f"[engine] strategy gen failed, falling back: {exc}")

        # Optimize intent -> sweep strategy params (checked before plain backtest).
        if self._wants_optimize(user_text):
            try:
                out = self._run_optimize_nl(user_text)
                if out is not None:
                    self._finish_exchange(user_text, out["reply"])
                    return out
            except Exception as exc:
                print(f"[engine] optimize failed, falling back: {exc}")

        # Backtest intent -> run a real backtest and explain it (educational).
        if self._wants_backtest(user_text):
            try:
                out = self._run_backtest_nl(user_text)
                if out is not None:
                    self._finish_exchange(user_text, out["reply"])
                    return out
            except Exception as exc:
                print(f"[engine] backtest failed, falling back: {exc}")

        # Factor-zoo intent -> scan the alphas by IC/IR and explain (educational).
        if self._wants_factors(user_text):
            try:
                out = self._run_factor_scan()
                self._finish_exchange(user_text, out["reply"])
                return out
            except Exception as exc:
                print(f"[engine] factor scan failed, falling back: {exc}")

        # Coach intent -> scorecard + challenges (deterministic, no LLM).
        if self._wants_coach(user_text):
            try:
                out = self.coach()
                self._finish_exchange(user_text, out["reply"])
                return out
            except Exception as exc:
                print(f"[engine] coach failed, falling back: {exc}")

        # Trade-review intent -> shadow account behavior diagnostics.
        if self._wants_review(user_text):
            try:
                out = self.shadow_review()
                self._finish_exchange(user_text, out["reply"])
                return out
            except Exception as exc:
                print(f"[engine] shadow review failed, falling back: {exc}")

        # Deep analysis -> multi-agent debate (when LangChain + a provider are available).
        if deep and self.debate.available():
            ticker = self._focus_ticker(user_text, symbols)
            if ticker:
                try:
                    out = self._run_debate(ticker)
                    reply, provider = out["reply"], out["provider"]
                    proposal = out["proposal"]
                    transcript = out["transcript"]
                    self._finish_exchange(user_text, reply)
                    result = {"reply": reply, "provider": provider, "proposal": proposal,
                              "transcript": transcript, "analysis_kind": "debate"}
                    return result
                except Exception as exc:
                    # Fall through to the standard single-brain path on any failure.
                    print(f"[engine] debate failed, falling back: {exc}")

        # Standard single-brain path (with live context + cited knowledge).
        market_ctx = snapshot.build_snapshot(self.data, symbols, self.timeframe, self.lookback,
                                             signal_service=self.signals)
        account_ctx = snapshot.account_and_positions_text(self.broker, self.data)
        profile_ctx = profile_mem.format_profile_for_prompt()
        journal_ctx = journal.format_for_prompt(12)
        goals_ctx = goals_mem.format_for_prompt()
        notes_ctx = notes_mem.format_for_prompt(user_text)
        relevant = skills.find_relevant(user_text)
        skill_ctx = skills.context_snippet(relevant)
        now = datetime.now().strftime("%A, %B %d, %Y — %I:%M %p")

        focus = self._focus_ticker(user_text, symbols)
        signals_ctx = self._signals_context(focus) if focus else ""

        context = f"[NOW] {now}\n\n{market_ctx}\n\n{account_ctx}"
        if signals_ctx:
            context += "\n\n" + signals_ctx
        if profile_ctx:
            context += "\n\n" + profile_ctx
        if goals_ctx:
            context += "\n\n" + goals_ctx
        if notes_ctx:
            context += "\n\n" + notes_ctx
        if journal_ctx:
            context += "\n\n" + journal_ctx
        if skill_ctx:
            context += "\n\n" + skill_ctx

        user_msg = f"{context}\n\n[USER QUESTION]\n{user_text}"
        messages = self.history[-6:] + [{"role": "user", "content": user_msg}]

        reply, provider = self.brain.chat(self._system_prompt(), messages, deep=deep)
        proposal = self._parse_trade(reply)
        self._finish_exchange(user_text, reply)
        result = {"reply": reply, "provider": provider, "proposal": proposal}
        if relevant:
            result["skills"] = skills.cited(relevant)
        return result

    def _finish_exchange(self, user_text: str, reply: str) -> None:
        """Shared post-processing: rolling history, journal, throttled memory extraction."""
        with self._trade_lock:
            self.history.append({"role": "user", "content": user_text})
            self.history.append({"role": "assistant", "content": reply})
            self.history = self.history[-12:]

        journal.add_entry("chat", content=f"Q: {user_text[:160]} | A: {reply[:220]}")

        # Throttle memory extraction (an extra LLM call) to ~1 in 3 messages so it
        # doesn't burn the free-tier rate limit twice as fast.
        self._ask_count += 1
        if len(user_text.strip()) >= 12 and self._ask_count % 3 == 0:
            threading.Thread(target=self._extract_memory,
                             args=(user_text, reply), daemon=True).start()

    # ---------- streaming deep analysis (Phase 10) ----------
    def stream_chat(self, user_text: str, deep: bool, emit) -> None:
        """Drive a chat turn, emitting progress events. Deep requests stream the
        multi-agent committee stage-by-stage; everything else emits one result."""
        deep = deep or self._wants_deep(user_text)
        if deep and self.debate.available() and not self._memory_command(user_text):
            ticker = self._focus_ticker(user_text, self._symbols_for(user_text))
            if ticker:
                try:
                    emit({"type": "start", "ticker": ticker})
                    out = self._run_debate(ticker, progress=lambda **e: emit({"type": "stage", **e}))
                    self._finish_exchange(user_text, out["reply"])
                    proposal = out.get("proposal")
                    if proposal:
                        proposal["est_cost"] = self.estimate_cost(proposal)
                    emit({"type": "result", "reply": out["reply"], "provider": out["provider"],
                          "proposal": proposal, "transcript": out.get("transcript")})
                    return
                except Exception as exc:  # noqa: BLE001
                    emit({"type": "stage", "stage": "error",
                          "label": f"debate failed: {exc}", "status": "failed"})
                    res = self.ask(user_text, deep=False)
                    if res.get("proposal"):
                        res["proposal"]["est_cost"] = self.estimate_cost(res["proposal"])
                    emit({"type": "result", **res})
                    return
        res = self.ask(user_text, deep=deep)
        if res.get("proposal"):
            res["proposal"]["est_cost"] = self.estimate_cost(res["proposal"])
        emit({"type": "result", **res})

    # ---------- agent mode (Phase 8): LLM decides which tools to call ----------
    def agent_ask(self, user_text: str) -> dict:
        """Answer via the agentic tool-calling loop, falling back to the standard
        keyword-routed chat when no LangChain provider (tool calling) is available."""
        from trading_llm.agentic import build_registry, AgentLoop
        if getattr(self, "_agent_loop", None) is None:
            self._agent_loop = AgentLoop(self.brain, build_registry(self))
        loop = self._agent_loop
        if not loop.available():
            return self.ask(user_text)
        try:
            out = loop.run(user_text, self._system_prompt())
        except Exception as exc:  # noqa: BLE001
            print(f"[engine] agent loop failed, falling back: {exc}")
            return self.ask(user_text)
        reply = out["reply"]
        self._finish_exchange(user_text, reply)
        return {"reply": reply, "provider": "agent", "proposal": self._parse_trade(reply),
                "tools_used": out.get("tools_used", [])}

    # ---------- trade proposal parsing ----------
    def _parse_trade(self, reply: str) -> dict | None:
        m = _TRADE_BLOCK.search(reply)
        if not m:
            return None
        try:
            data = json.loads(m.group(1))
        except Exception:
            return None
        action = str(data.get("action", "")).lower()
        symbol = str(data.get("symbol", "")).upper().strip()
        if action not in ("buy", "sell") or not symbol:
            return None
        if symbol in _CRYPTO_ALIASES:
            symbol = _CRYPTO_ALIASES[symbol]
        return {
            "action": action,
            "symbol": symbol,
            "qty": data.get("qty"),
            "notional": data.get("notional"),
            "order_type": str(data.get("order_type", "market")).lower(),
            "limit_price": data.get("limit_price"),
            "rationale": str(data.get("rationale", ""))[:200],
        }

    def estimate_cost(self, proposal: dict) -> float | None:
        if proposal.get("notional"):
            try:
                return float(proposal["notional"])
            except Exception:
                return None
        qty = proposal.get("qty")
        if not qty:
            return None
        price = proposal.get("limit_price") or self.data.get_price(proposal["symbol"])
        try:
            return float(qty) * float(price) if price else None
        except Exception:
            return None

    # ---------- placing a (paper) trade, after user confirmation ----------
    def place_trade(self, proposal: dict) -> dict:
        with self._trade_lock:
            return self._place_trade_locked(proposal)

    def _place_trade_locked(self, proposal: dict) -> dict:
        # Opt-in real (Alpaca PAPER) routing, behind the committed mandate + guard.
        mandate = self.settings.get("live_trading", safety.DEFAULT_MANDATE)
        if mandate.get("enabled"):
            return self._place_live(proposal, mandate)

        risk = self.settings.get("risk", {})
        max_trades = risk.get("max_trades_per_day", 10)
        if journal.trades_today() >= max_trades:
            return {"error": f"Daily paper-trade limit reached ({max_trades}). Adjust in settings.json."}

        est = self.estimate_cost(proposal)
        max_pos = risk.get("max_position_usd", 2000)
        if est and est > max_pos:
            return {"error": (f"Order is ~${est:,.0f}, above your max_position_usd "
                              f"of ${max_pos:,.0f}. Lower the size or raise the limit in settings.json.")}

        execu = self.settings.get("execution", {})
        res = self.broker.place_order(
            symbol=proposal["symbol"], side=proposal["action"],
            qty=proposal.get("qty"), notional=proposal.get("notional"),
            price_fn=self.data.get_price,
            order_type=proposal.get("order_type", "market"),
            limit_price=proposal.get("limit_price"),
            slippage_bps=execu.get("slippage_bps", 0.0),
            fee_bps=execu.get("fee_bps", 0.0),
        )
        if "error" in res:
            journal.add_entry("trade", symbol=proposal["symbol"], side=proposal["action"],
                              qty=proposal.get("qty"), status="rejected",
                              rationale=proposal.get("rationale", ""), error=res["error"])
            return res

        journal.add_entry("trade", symbol=res["symbol"], side=res["side"],
                          qty=res.get("qty"), price=res.get("filled_avg_price"),
                          order_id=res.get("id"), status=res.get("status"),
                          rationale=proposal.get("rationale", ""))

        # Tag signal-driven paper trades so the learning loop can attribute outcomes.
        if proposal.get("source") == "signal_idea":
            try:
                signal_learning.record(
                    res["symbol"], proposal.get("signal_kind", "insider_buy"),
                    self._regime_label(), side=res["side"],
                    note=proposal.get("rationale", "")[:200])
            except Exception:
                pass
        return res

    # ---------- opt-in live (Alpaca paper) trading (Phase 11) ----------
    def _alpaca(self):
        if getattr(self, "_alpaca_client", None) is None:
            try:
                from trading_llm.market.alpaca_client import AlpacaClient
                self._alpaca_client = AlpacaClient(
                    self.keys.get("alpaca_paper_key", ""),
                    self.keys.get("alpaca_paper_secret", ""), paper=True)
            except Exception:
                self._alpaca_client = None
        return self._alpaca_client

    def _place_live(self, proposal: dict, mandate: dict) -> dict:
        """Route an order to Alpaca PAPER, fail-closed through the safety guard."""
        est = self.estimate_cost(proposal)
        ok, reason = safety.check_order(proposal, est, journal.trades_today(), mandate)
        if not ok:
            safety.audit("blocked", {"symbol": proposal.get("symbol"),
                                     "action": proposal.get("action"), "reason": reason})
            return {"error": reason}

        client = self._alpaca()
        if client is None or not getattr(client, "has_keys", False):
            reason = ("Live trading is enabled but no Alpaca paper keys are set "
                      "(add alpaca_paper_key/secret to config/api_keys.json), or alpaca-py isn't installed.")
            safety.audit("blocked", {"symbol": proposal.get("symbol"), "reason": reason})
            return {"error": reason}

        res = client.place_order(
            symbol=proposal["symbol"], side=proposal["action"],
            qty=proposal.get("qty"), notional=proposal.get("notional"),
            order_type=proposal.get("order_type", "market"),
            limit_price=proposal.get("limit_price"))
        if "error" in res:
            safety.audit("error", {"symbol": proposal.get("symbol"), "error": res["error"]})
            journal.add_entry("trade", symbol=proposal["symbol"], side=proposal["action"],
                              qty=proposal.get("qty"), status="error",
                              rationale=proposal.get("rationale", ""), error=res["error"],
                              venue="alpaca_paper")
            return res

        safety.audit("placed", {"symbol": res.get("symbol"), "side": res.get("side"),
                                "qty": res.get("qty"), "id": res.get("id")})
        journal.add_entry("trade", symbol=res.get("symbol"), side=res.get("side"),
                          qty=res.get("qty"), price=res.get("filled_avg_price"),
                          order_id=res.get("id"), status=res.get("status"),
                          rationale=proposal.get("rationale", ""), venue="alpaca_paper")
        return res

    def get_mandate(self) -> dict:
        return self.settings.get("live_trading", dict(safety.DEFAULT_MANDATE))

    def set_mandate(self, patch: dict) -> dict:
        m = dict(self.get_mandate())
        for k in ("enabled", "max_order_usd", "max_trades_per_day", "allowed_symbols"):
            if k in patch and patch[k] is not None:
                m[k] = patch[k]
        self.settings["live_trading"] = m
        app_config.save_settings(self.settings)
        return m

    def set_halt(self, on: bool) -> dict:
        if on:
            safety.halt()
        else:
            safety.resume()
        return self.live_status()

    def live_status(self) -> dict:
        m = self.get_mandate()
        return {
            "enabled": bool(m.get("enabled")),
            "halted": safety.is_halted(),
            "has_alpaca_keys": bool(self.keys.get("alpaca_paper_key") and self.keys.get("alpaca_paper_secret")),
            "mandate": m,
            "audit": safety.audit_log(25),
        }

    # ---------- memory extraction (background) ----------
    def _extract_memory(self, user_text: str, reply: str) -> None:
        try:
            data = self.brain.chat_json(MEMORY_EXTRACT_SYSTEM,
                                        memory_extract_prompt(user_text, reply))
            if data:
                profile_mem.update_profile(data)
        except Exception:
            pass

    # ---------- data passthroughs for the UI ----------
    def watchlist_rows(self) -> list[dict]:
        return snapshot.watchlist_quotes(self.data, self.watchlist, self.timeframe, self.lookback)

    def account(self) -> dict | None:
        return self.broker.get_account(self.data.get_price)

    def positions(self) -> list[dict]:
        return self.broker.get_positions(self.data.get_price)

    def quotes(self, symbols: list[str]) -> list[dict]:
        """Lightweight live prices (+ day change) for fast polling."""
        out = []
        for s in symbols:
            price = self.data.get_price(s)
            bars = self.data.get_bars(s, self.timeframe, self.lookback)
            prev = bars[-2] if len(bars) >= 2 else (bars[-1] if bars else None)
            chg = round((price / prev - 1) * 100, 2) if price and prev else None
            out.append({"symbol": s, "price": price, "change_pct": chg})
        return out

    def get_settings(self) -> dict:
        return {
            "watchlist": self.watchlist,
            "mock_starting_cash": self.settings.get("mock_starting_cash", 100000),
            "data_source_order": self.settings.get("data_source_order", []),
            "default_timeframe": self.timeframe,
        }

    def update_settings(self, patch: dict) -> dict:
        if not isinstance(patch, dict):
            return self.get_settings()
        wl = patch.get("watchlist")
        if isinstance(wl, list):
            cleaned: list[str] = []
            for s in wl:
                sym = str(s).strip().upper()
                if sym and sym not in cleaned:
                    cleaned.append(sym)
            self.watchlist = cleaned
            self.settings["watchlist"] = cleaned
        if "mock_starting_cash" in patch:
            try:
                self.settings["mock_starting_cash"] = float(patch["mock_starting_cash"])
            except Exception:
                pass
        app_config.save_settings(self.settings)
        return self.get_settings()

    def reset_account(self, cash: float | None = None) -> dict | None:
        self.broker.reset(cash)
        return self.account()

    def learn_text(self) -> str:
        try:
            return LEARN_PATH.read_text(encoding="utf-8")
        except Exception:
            return "LEARN_TO_TRADE.md not found."
