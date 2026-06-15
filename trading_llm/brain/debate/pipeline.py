"""DebateEngine — orchestrates the multi-agent pipeline into one decision.

Flow (mirrors TradingAgents, grounded on our live data + driven by our providers):

    Technical Analyst  ┐
    News Analyst       ┘→ Bull ⇄ Bear (N rounds) → Research Manager (plan + rating)
                           → Trader (proposal)
                           → Aggressive ⇄ Conservative ⇄ Neutral (N rounds)
                           → Portfolio Manager (FINAL decision + rating, sees past lessons)

Quick model drives analysts/debators; the deep model drives the two managers.
Each step is a single ``llm.invoke`` and the whole transcript is captured so the
UI can show it as a teaching artifact.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from trading_llm.brain.debate import agents
from trading_llm.brain.debate.signal import parse_rating


@dataclass
class DebateResult:
    ticker: str
    market_report: str = ""
    news_report: str = ""
    smart_money_report: str = ""
    research_debate: str = ""
    investment_plan: str = ""
    trader_plan: str = ""
    risk_debate: str = ""
    final_decision: str = ""
    rating: str = "Hold"
    transcript: dict = field(default_factory=dict)

    def to_markdown(self) -> str:
        """Readable transcript for the chat bubble (the teaching artifact)."""
        return (
            f"### 🧠 Multi-agent deep analysis — {self.ticker}\n\n"
            f"**Committee decision: {self.rating}**\n\n"
            f"{self.final_decision}\n\n"
            "<hr/>\n\n"
            "#### 📈 Technical analyst\n"
            f"{self.market_report}\n\n"
            "#### 📰 News & sentiment analyst\n"
            f"{self.news_report}\n\n"
            + (f"#### 🏛️ Smart-money & regime analyst\n{self.smart_money_report}\n\n"
               if self.smart_money_report else "")
            + "#### 🟢 Bull vs 🔴 Bear — research debate\n"
            f"{self.research_debate}\n\n"
            "#### 🧭 Research manager's plan\n"
            f"{self.investment_plan}\n\n"
            "#### 💼 Trader\n"
            f"{self.trader_plan}\n\n"
            "#### ⚖️ Risk committee (aggressive · conservative · neutral)\n"
            f"{self.risk_debate}"
        )


class DebateEngine:
    """Runs the multi-agent debate using ProviderRouter LangChain models."""

    def __init__(self, router, settings: dict | None = None):
        self.router = router
        debate_cfg = (settings or {}).get("debate", {})
        self.research_rounds = int(debate_cfg.get("research_rounds", 1))
        self.risk_rounds = int(debate_cfg.get("risk_rounds", 1))
        self._available: bool | None = None

    def available(self) -> bool:
        """True when a LangChain model can be built (provider + langchain present)."""
        if self._available is None:
            try:
                self.router.get_llm("quick")
                self._available = True
            except Exception:
                self._available = False
        return self._available

    def run(self, ticker: str, technical_context: str,
            news_context: str, past_context: str = "", progress=None,
            signals_context: str = "") -> DebateResult:
        def emit(stage, label, status):
            if progress:
                try:
                    progress(stage=stage, label=label, status=status)
                except Exception:
                    pass

        quick = self.router.get_llm("quick")
        deep = self.router.get_llm("deep")
        res = DebateResult(ticker=ticker)

        # 1) Analysts (grounded on our data)
        emit("analysts", "Technical analyst", "running")
        res.market_report = agents.run_market_analyst(quick, ticker, technical_context)
        emit("analysts", "News & sentiment analyst", "running")
        res.news_report = agents.run_news_analyst(quick, ticker, news_context)
        if signals_context.strip():
            emit("analysts", "Smart-money & regime analyst", "running")
            try:
                res.smart_money_report = agents.run_smart_money_analyst(quick, ticker, signals_context)
            except Exception:
                res.smart_money_report = ""
        emit("analysts", "Analysts", "done")

        # 2) Bull/Bear research debate
        emit("research", "Bull vs Bear debate", "running")
        history = ""
        last_bull = last_bear = ""
        for _ in range(max(1, self.research_rounds)):
            last_bull = agents.run_bull(quick, ticker, res.market_report,
                                        res.news_report, history, last_bear, res.smart_money_report)
            history += f"\n\nBull Analyst: {last_bull}"
            last_bear = agents.run_bear(quick, ticker, res.market_report,
                                        res.news_report, history, last_bull, res.smart_money_report)
            history += f"\n\nBear Analyst: {last_bear}"
        res.research_debate = history.strip()
        emit("research", "Bull vs Bear debate", "done")

        # 3) Research manager -> investment plan (deep model; fall back to quick on error)
        emit("plan", "Research manager", "running")
        try:
            res.investment_plan = agents.run_research_manager(deep, ticker, res.research_debate)
        except Exception:
            res.investment_plan = agents.run_research_manager(quick, ticker, res.research_debate)
        emit("plan", "Research manager", "done")

        # 4) Trader -> concrete proposal
        emit("trader", "Trader", "running")
        res.trader_plan = agents.run_trader(quick, ticker, res.investment_plan)
        emit("trader", "Trader", "done")

        # 5) Risk committee debate
        emit("risk", "Risk committee", "running")
        rhistory = ""
        agg = con = neu = ""
        for _ in range(max(1, self.risk_rounds)):
            agg = agents.run_aggressive(quick, res.market_report, res.news_report,
                                        res.trader_plan, rhistory, con, neu)
            rhistory += f"\n\nAggressive Analyst: {agg}"
            con = agents.run_conservative(quick, res.market_report, res.news_report,
                                          res.trader_plan, rhistory, agg, neu)
            rhistory += f"\n\nConservative Analyst: {con}"
            neu = agents.run_neutral(quick, res.market_report, res.news_report,
                                     res.trader_plan, rhistory, agg, con)
            rhistory += f"\n\nNeutral Analyst: {neu}"
        res.risk_debate = rhistory.strip()
        emit("risk", "Risk committee", "done")

        # 6) Portfolio manager -> final decision (deep model; fall back to quick on error)
        emit("pm", "Portfolio manager", "running")
        try:
            res.final_decision = agents.run_portfolio_manager(
                deep, ticker, res.investment_plan, res.trader_plan, res.risk_debate,
                past_context, res.smart_money_report)
        except Exception:
            res.final_decision = agents.run_portfolio_manager(
                quick, ticker, res.investment_plan, res.trader_plan, res.risk_debate,
                past_context, res.smart_money_report)
        res.rating = parse_rating(res.final_decision)
        emit("pm", "Portfolio manager", "done")

        res.transcript = {
            "ticker": ticker,
            "market_report": res.market_report,
            "news_report": res.news_report,
            "smart_money_report": res.smart_money_report,
            "research_debate": res.research_debate,
            "investment_plan": res.investment_plan,
            "trader_plan": res.trader_plan,
            "risk_debate": res.risk_debate,
            "final_decision": res.final_decision,
            "rating": res.rating,
        }
        return res
