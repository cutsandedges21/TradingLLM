import { useEffect, useState, type ReactNode } from 'react'
import {
  ResponsiveContainer, LineChart, Line, XAxis, YAxis, Tooltip, CartesianGrid,
} from 'recharts'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { FlaskConical, BarChart3, Trophy, Loader2, Wand2, ShieldAlert, Bell, Plus, Trash2, Play } from 'lucide-react'
import { api } from '../api'
import { cn } from '../lib'
import type {
  StrategyMeta, BacktestRun, OptimizeRun, FactorBench, CoachData, ShadowData,
  StrategyResult, EquityPoint, RiskDashboard, RiskSize,
  AlertRule, AlertFields, AlertEval, RuleBacktest, AlertCondition, Proposal,
} from '../types'

type Tab = 'backtest' | 'builder' | 'factors' | 'risk' | 'alerts' | 'coach'
const PERIODS = ['6mo', '1y', '2y', '5y']

function EquityChart({ data }: { data: EquityPoint[] }) {
  return (
    <div className="rounded-2xl border border-line bg-panel/40 p-3">
      <div className="eyebrow mb-2 px-1">Equity curve · strategy vs buy &amp; hold</div>
      <ResponsiveContainer width="100%" height={260}>
        <LineChart data={data} margin={{ top: 6, right: 12, bottom: 0, left: 4 }}>
          <CartesianGrid stroke="rgba(220,228,245,0.06)" vertical={false} />
          <XAxis dataKey="date" tick={{ fontSize: 10, fill: '#5b6478' }} minTickGap={48} />
          <YAxis tick={{ fontSize: 10, fill: '#5b6478' }} width={52}
            domain={['auto', 'auto']} tickFormatter={(v) => `$${(v / 1000).toFixed(1)}k`} />
          <Tooltip contentStyle={{ background: '#0d1018', border: '1px solid rgba(220,228,245,0.15)', borderRadius: 10, fontSize: 12 }}
            labelStyle={{ color: '#9aa3b6' }} formatter={(v: number) => `$${v.toLocaleString()}`} />
          <Line type="monotone" dataKey="equity" stroke="#4fe0cd" strokeWidth={2} dot={false} name="Strategy" />
          <Line type="monotone" dataKey="benchmark" stroke="#5b6478" strokeWidth={1.5} dot={false} strokeDasharray="4 3" name="Buy & Hold" />
        </LineChart>
      </ResponsiveContainer>
    </div>
  )
}

function Md({ children }: { children: string }) {
  return <div className="prose-terminal"><ReactMarkdown remarkPlugins={[remarkGfm]}>{children}</ReactMarkdown></div>
}

function Metric({ label, value, tone }: { label: string; value: string; tone?: 'up' | 'down' }) {
  return (
    <div className="rounded-xl border border-line bg-panel-2/40 px-3.5 py-2.5">
      <div className="eyebrow">{label}</div>
      <div className={cn('mt-0.5 font-mono text-[15px] tnum',
        tone === 'up' ? 'text-up' : tone === 'down' ? 'text-down' : 'text-ink')}>{value}</div>
    </div>
  )
}

function Spinner({ label }: { label: string }) {
  return (
    <div className="flex items-center gap-2 py-8 text-muted">
      <Loader2 size={16} className="animate-spin text-gold" />
      <span className="font-display text-[14px] italic">{label}</span>
    </div>
  )
}

function Explainer({ title, children }: { title: string; children: ReactNode }) {
  return (
    <div className="rounded-xl border border-line bg-panel-2/30 px-4 py-3 text-[13px] leading-relaxed text-muted">
      <div className="eyebrow mb-1">{title}</div>
      {children}
    </div>
  )
}

// ───────────────────────── Backtest ─────────────────────────
function BacktestTab() {
  const [strats, setStrats] = useState<StrategyMeta[]>([])
  const [symbol, setSymbol] = useState('AAPL')
  const [strategy, setStrategy] = useState('sma_cross')
  const [period, setPeriod] = useState('2y')
  const [run, setRun] = useState<BacktestRun | null>(null)
  const [opt, setOpt] = useState<OptimizeRun | null>(null)
  const [busy, setBusy] = useState<'' | 'run' | 'opt'>('')

  useEffect(() => { api.strategies().then(setStrats).catch(() => {}) }, [])

  const doRun = async () => {
    setBusy('run'); setOpt(null)
    try { setRun(await api.runBacktest({ symbol, strategy, period })) } catch { /* */ } finally { setBusy('') }
  }
  const doOpt = async () => {
    setBusy('opt')
    try { setOpt(await api.runOptimize({ symbol, strategy, period, metric: 'sharpe' })) } catch { /* */ } finally { setBusy('') }
  }

  const m = run?.metrics
  return (
    <div className="space-y-4">
      <Explainer title="What is a backtest?">
        A <strong className="text-ink">backtest</strong> runs a trading rule over past price data to see how it
        <em> would</em> have performed — the cheapest way to pressure-test an idea before risking real money.
        Compare the strategy line to <strong className="text-ink">buy &amp; hold</strong> (beating "do nothing" is the bar),
        watch the <strong className="text-ink">max drawdown</strong> (the worst drop you'd have had to stomach), and beware
        <strong className="text-ink"> overfitting</strong> — a rule tuned to look perfect on history often falls apart live.
        Hit <em>Optimize</em> to sweep a strategy's parameters and see that trap first-hand.
      </Explainer>
      <div className="flex flex-wrap items-end gap-2 rounded-2xl border border-line bg-panel/50 p-3">
        <label className="flex flex-col gap-1">
          <span className="eyebrow">Symbol</span>
          <input value={symbol} onChange={(e) => setSymbol(e.target.value.toUpperCase())}
            className="w-28 rounded-lg border border-line bg-panel-2/50 px-3 py-1.5 font-mono text-[13px] text-ink focus:border-gold/40 focus:outline-none" />
        </label>
        <label className="flex flex-col gap-1">
          <span className="eyebrow">Strategy</span>
          <select value={strategy} onChange={(e) => setStrategy(e.target.value)}
            className="rounded-lg border border-line bg-panel-2/50 px-3 py-1.5 text-[13px] text-ink focus:border-gold/40 focus:outline-none">
            {strats.map((s) => <option key={s.name} value={s.name}>{s.label}</option>)}
          </select>
        </label>
        <label className="flex flex-col gap-1">
          <span className="eyebrow">Period</span>
          <select value={period} onChange={(e) => setPeriod(e.target.value)}
            className="rounded-lg border border-line bg-panel-2/50 px-3 py-1.5 text-[13px] text-ink focus:border-gold/40 focus:outline-none">
            {PERIODS.map((p) => <option key={p} value={p}>{p}</option>)}
          </select>
        </label>
        <button onClick={doRun} disabled={!!busy}
          className="rounded-lg bg-gold px-4 py-2 text-[13px] font-semibold text-obsidian transition-transform hover:scale-[1.03] active:scale-95 disabled:opacity-50">
          Run backtest
        </button>
        <button onClick={doOpt} disabled={!!busy}
          className="rounded-lg border border-gold/40 px-4 py-2 text-[13px] font-medium text-gold transition-colors hover:bg-gold/10 disabled:opacity-50">
          Optimize
        </button>
      </div>

      {busy === 'run' && <Spinner label="Running backtest…" />}
      {busy === 'opt' && <Spinner label="Sweeping parameters…" />}

      {run && !busy && (run.ok ? (
        <div className="space-y-4">
          <div className="grid grid-cols-2 gap-2.5 sm:grid-cols-3 lg:grid-cols-6">
            <Metric label="Return" value={`${(m!.total_return_pct).toFixed(1)}%`} tone={m!.total_return_pct >= 0 ? 'up' : 'down'} />
            <Metric label="Buy & Hold" value={`${(m!.buy_hold_return_pct).toFixed(1)}%`} />
            <Metric label="Max DD" value={`${(m!.max_drawdown_pct).toFixed(1)}%`} tone="down" />
            <Metric label="Sharpe" value={(m!.sharpe).toFixed(2)} />
            <Metric label="Trades" value={`${m!.n_trades}`} />
            <Metric label="Win rate" value={`${(m!.win_rate_pct).toFixed(0)}%`} />
          </div>
          <div className="rounded-2xl border border-line bg-panel/40 p-3">
            <div className="eyebrow mb-2 px-1">Equity curve · strategy vs buy &amp; hold</div>
            <ResponsiveContainer width="100%" height={260}>
              <LineChart data={run.equity_curve} margin={{ top: 6, right: 12, bottom: 0, left: 4 }}>
                <CartesianGrid stroke="rgba(220,228,245,0.06)" vertical={false} />
                <XAxis dataKey="date" tick={{ fontSize: 10, fill: '#5b6478' }} minTickGap={48} />
                <YAxis tick={{ fontSize: 10, fill: '#5b6478' }} width={52}
                  domain={['auto', 'auto']} tickFormatter={(v) => `$${(v / 1000).toFixed(1)}k`} />
                <Tooltip contentStyle={{ background: '#0d1018', border: '1px solid rgba(220,228,245,0.15)', borderRadius: 10, fontSize: 12 }}
                  labelStyle={{ color: '#9aa3b6' }} formatter={(v: number) => `$${v.toLocaleString()}`} />
                <Line type="monotone" dataKey="equity" stroke="#4fe0cd" strokeWidth={2} dot={false} name="Strategy" />
                <Line type="monotone" dataKey="benchmark" stroke="#5b6478" strokeWidth={1.5} dot={false} strokeDasharray="4 3" name="Buy & Hold" />
              </LineChart>
            </ResponsiveContainer>
          </div>
          <Md>{run.explanation}</Md>
        </div>
      ) : <div className="rounded-xl border border-down/30 bg-down/5 px-4 py-3 text-[13px] text-down">{run.error}</div>)}

      {opt && !busy && (
        <div className="rounded-2xl border border-gold/25 bg-panel/40 p-4">
          {opt.ok ? <Md>{opt.explanation}</Md>
            : <div className="text-[13px] text-down">{opt.error}</div>}
        </div>
      )}
    </div>
  )
}

// ───────────────────────── Factors ─────────────────────────
function bar(ic: number) {
  const w = Math.min(100, Math.abs(ic) * 1200)
  return (
    <div className="flex items-center gap-2">
      <span className="w-14 text-right font-mono text-[12px] tnum">{ic >= 0 ? '+' : ''}{ic.toFixed(4)}</span>
      <span className="h-1.5 flex-1 rounded-full bg-panel-2">
        <span className={cn('block h-full rounded-full', ic >= 0 ? 'bg-up' : 'bg-down')} style={{ width: `${w}%` }} />
      </span>
    </div>
  )
}

function FactorsTab() {
  const [data, setData] = useState<FactorBench | null>(null)
  const [busy, setBusy] = useState(false)

  const scan = async () => {
    setBusy(true)
    try { setData(await api.factorsBench({ period: '2y', horizon: 5 })) } catch { /* */ } finally { setBusy(false) }
  }

  return (
    <div className="space-y-4">
      <Explainer title="What is the factor zoo?">
        A <strong className="text-ink">factor</strong> (or <em>alpha</em>) ranks the whole universe every day by some
        signal — momentum, reversal, volatility, a Kakushadze formula — betting the ranking predicts the next few days'
        returns. The <strong className="text-ink">IC</strong> (information coefficient) measures whether it actually does:
        around <strong className="text-ink">±0.03</strong> with a steady <strong className="text-ink">IR</strong> is a
        genuine (if small) edge; near zero is noise; a <em>negative</em> IC isn't useless — it's a <em>reversal</em>
        signal (rank it the other way). Real edges are tiny and unstable, which is exactly the lesson.
      </Explainer>
      <div className="flex items-center justify-between rounded-2xl border border-line bg-panel/50 p-3">
        <div>
          <div className="eyebrow">Factor Zoo</div>
          <div className="font-display text-[14px] italic text-muted">IC/IR scan over a liquid large-cap universe</div>
        </div>
        <button onClick={scan} disabled={busy}
          className="rounded-lg bg-gold px-4 py-2 text-[13px] font-semibold text-obsidian transition-transform hover:scale-[1.03] active:scale-95 disabled:opacity-50">
          Run scan
        </button>
      </div>
      {busy && <Spinner label="Scoring factors (IC/IR over real data)…" />}
      {data && !busy && (data.ok ? (
        <div className="overflow-x-auto rounded-2xl border border-line bg-panel/40">
          <table className="w-full min-w-[640px] text-[13px]">
            <thead>
              <tr className="border-b border-line text-left">
                {['Factor', 'Type', 'IC mean', 'IR', 'IC>0', 'Top−Bot', 'Read'].map((h) => (
                  <th key={h} className="px-3 py-2 font-mono text-[10px] uppercase tracking-wide text-faint">{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {data.results.map((r) => (
                <tr key={r.name} className="border-b border-line/60 last:border-0">
                  <td className="px-3 py-2 font-display">{r.label}</td>
                  <td className="px-3 py-2 font-mono text-[11px] text-faint">{r.category}</td>
                  <td className="px-3 py-2" style={{ minWidth: 160 }}>{bar(r.ic_mean)}</td>
                  <td className="px-3 py-2 font-mono tnum">{r.ir >= 0 ? '+' : ''}{r.ir.toFixed(2)}</td>
                  <td className="px-3 py-2 font-mono tnum text-muted">{r.ic_positive_pct.toFixed(0)}%</td>
                  <td className={cn('px-3 py-2 font-mono tnum', r.spread_pct >= 0 ? 'text-up' : 'text-down')}>
                    {r.spread_pct >= 0 ? '+' : ''}{r.spread_pct.toFixed(2)}%
                  </td>
                  <td className="px-3 py-2 text-[11px] text-muted">{r.strength}/{r.direction}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : <div className="rounded-xl border border-down/30 bg-down/5 px-4 py-3 text-[13px] text-down">{data.error}</div>)}
    </div>
  )
}

// ───────────────────────── Risk ─────────────────────────
function pctText(v: number | undefined): string {
  return v == null ? '—' : `${(v * 100).toFixed(v < 0.1 ? 1 : 0)}%`
}

function RiskTab() {
  const [dash, setDash] = useState<RiskDashboard | null>(null)
  const [busy, setBusy] = useState(true)
  useEffect(() => { api.riskDashboard().then(setDash).catch(() => {}).finally(() => setBusy(false)) }, [])

  const [symbol, setSymbol] = useState('AAPL')
  const [entry, setEntry] = useState('')
  const [stop, setStop] = useState('')
  const [riskPct, setRiskPct] = useState('1')
  const [size, setSize] = useState<RiskSize | null>(null)
  const [sizing, setSizing] = useState(false)
  const calc = async () => {
    setSizing(true)
    try {
      setSize(await api.riskSize({
        symbol, entry: entry ? +entry : null, stop: stop ? +stop : null,
        risk_pct: riskPct ? +riskPct / 100 : null, method: stop ? 'fixed' : 'atr',
      }))
    } catch { /* */ } finally { setSizing(false) }
  }

  const ruinTone = (v: number) => v > 0.25 ? 'down' : v > 0.05 ? 'gold' : 'up'

  return (
    <div className="space-y-4">
      <Explainer title="Why risk management is the real edge">
        You can't control whether a trade wins — you <em>can</em> control how much you lose when it doesn't.
        Sizing every trade to risk a small, <strong className="text-ink">fixed fraction</strong> of equity is what lets
        you survive a losing streak long enough for your edge to show up. <strong className="text-ink">Kelly</strong>
        suggests a mathematically optimal fraction from your win rate &amp; payoff; smart traders use a <em>quarter</em> of it.
        Watch <strong className="text-ink">risk-of-ruin</strong>: oversize, and a 50% drawdown becomes almost certain
        regardless of how good your picks are.
      </Explainer>

      {busy && <Spinner label="Reading your account &amp; stats…" />}

      {dash && !busy && (
        <>
          <div className="grid grid-cols-2 gap-2.5 sm:grid-cols-4">
            <Metric label="Equity" value={`$${(dash.equity / 1000).toFixed(1)}k`} />
            <Metric label="Open risk (heat)" value={`${dash.heat.open_risk_pct}%`}
              tone={dash.heat.open_risk_pct > dash.rules.max_portfolio_heat_pct * 100 ? 'down' : undefined} />
            <Metric label="Gross exposure" value={`${dash.heat.gross_pct}%`} />
            <Metric label="Positions" value={`${dash.heat.n_positions}`} />
          </div>

          {dash.stats ? (
            <div className="grid gap-4 lg:grid-cols-2">
              <div className="rounded-2xl border border-line bg-panel/50 p-5">
                <div className="eyebrow mb-2">Your edge (from {dash.n_trips} closed trades)</div>
                <div className="grid grid-cols-3 gap-2.5">
                  <Metric label="Win rate" value={`${(dash.stats.win_rate * 100).toFixed(0)}%`} />
                  <Metric label="Payoff" value={`${dash.stats.payoff.toFixed(2)}×`} />
                  <Metric label="Expectancy" value={`${dash.stats.expectancy_r >= 0 ? '+' : ''}${dash.stats.expectancy_r}R`}
                    tone={dash.stats.expectancy_r >= 0 ? 'up' : 'down'} />
                </div>
                <div className="mt-3 flex flex-wrap gap-2 text-[12px]">
                  <span className="rounded-lg border border-line bg-panel-2/40 px-3 py-1.5 font-mono">
                    Full Kelly: {pctText(dash.kelly)}
                  </span>
                  <span className="rounded-lg border border-gold/40 bg-gold/10 px-3 py-1.5 font-mono text-gold">
                    Suggested (¼-Kelly): {pctText(dash.suggested_risk_pct)} / trade
                  </span>
                </div>
              </div>

              <div className="rounded-2xl border border-line bg-panel/50 p-5">
                <div className="eyebrow mb-3">Risk-of-ruin · chance of a −50% drawdown</div>
                {dash.ruin && (
                  <div className="space-y-2.5">
                    {([
                      [`At your current ${pctText(dash.rules.account_risk_pct)} risk`, dash.ruin.at_current],
                      [`At suggested ${pctText(dash.suggested_risk_pct)}`, dash.ruin.at_suggested],
                      ['At a reckless 5%', dash.ruin.at_5pct],
                    ] as [string, number][]).map(([label, v]) => (
                      <div key={label}>
                        <div className="flex items-center justify-between text-[12px]">
                          <span className="text-muted">{label}</span>
                          <span className={cn('font-mono tnum',
                            ruinTone(v) === 'down' ? 'text-down' : ruinTone(v) === 'gold' ? 'text-gold' : 'text-up')}>
                            {(v * 100).toFixed(0)}%
                          </span>
                        </div>
                        <div className="mt-1 h-1.5 rounded-full bg-panel-2">
                          <span className={cn('block h-full rounded-full',
                            ruinTone(v) === 'down' ? 'bg-down' : ruinTone(v) === 'gold' ? 'bg-gold' : 'bg-up')}
                            style={{ width: `${Math.max(2, v * 100)}%` }} />
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </div>
          ) : (
            <div className="rounded-xl border border-line bg-panel-2/30 px-4 py-3 text-[13px] text-muted">{dash.note}</div>
          )}
        </>
      )}

      {/* position-size calculator */}
      <div className="rounded-2xl border border-line bg-panel/50 p-4">
        <div className="eyebrow mb-2">Position-size calculator</div>
        <div className="flex flex-wrap items-end gap-2">
          <label className="flex flex-col gap-1">
            <span className="eyebrow">Symbol</span>
            <input value={symbol} onChange={(e) => setSymbol(e.target.value.toUpperCase())}
              className="w-24 rounded-lg border border-line bg-panel-2/50 px-3 py-1.5 font-mono text-[13px] text-ink focus:border-gold/40 focus:outline-none" />
          </label>
          <label className="flex flex-col gap-1">
            <span className="eyebrow">Entry (blank=live)</span>
            <input value={entry} onChange={(e) => setEntry(e.target.value)} placeholder="auto"
              className="w-24 rounded-lg border border-line bg-panel-2/50 px-3 py-1.5 font-mono text-[13px] text-ink focus:border-gold/40 focus:outline-none" />
          </label>
          <label className="flex flex-col gap-1">
            <span className="eyebrow">Stop (blank=2·ATR)</span>
            <input value={stop} onChange={(e) => setStop(e.target.value)} placeholder="auto"
              className="w-28 rounded-lg border border-line bg-panel-2/50 px-3 py-1.5 font-mono text-[13px] text-ink focus:border-gold/40 focus:outline-none" />
          </label>
          <label className="flex flex-col gap-1">
            <span className="eyebrow">Risk %</span>
            <input value={riskPct} onChange={(e) => setRiskPct(e.target.value)}
              className="w-16 rounded-lg border border-line bg-panel-2/50 px-3 py-1.5 font-mono text-[13px] text-ink focus:border-gold/40 focus:outline-none" />
          </label>
          <button onClick={calc} disabled={sizing}
            className="rounded-lg bg-gold px-4 py-2 text-[13px] font-semibold text-obsidian transition-transform hover:scale-[1.03] active:scale-95 disabled:opacity-50">
            {sizing ? 'Sizing…' : 'Size it'}
          </button>
        </div>
        {size && !sizing && (
          size.shares > 0 ? (
            <div className="mt-3 grid grid-cols-2 gap-2.5 sm:grid-cols-4">
              <Metric label="Shares" value={`${size.shares}`} />
              <Metric label="Notional" value={`$${size.notional.toLocaleString()}`} />
              <Metric label="Risk $" value={`$${size.risk_dollars.toLocaleString()}`} tone="down" />
              <Metric label="% of equity" value={`${size.pct_of_equity}%`} />
              <div className="col-span-2 sm:col-span-4 text-[11px] text-faint">
                Entry ${size.entry} · stop ${size.stop} ({size.method === 'atr' ? '2·ATR' : 'manual'}) · risking {pctText(size.risk_pct)} of equity.
              </div>
            </div>
          ) : (
            <div className="mt-3 rounded-lg border border-line bg-panel-2/40 px-3 py-2 text-[12px] text-muted">{size.note}</div>
          )
        )}
      </div>
    </div>
  )
}

// ───────────────────────── Alerts / Automation ─────────────────────────
const BLANK_RULE: AlertRule = {
  name: '', conditions: [{ field: 'rsi', op: '<=', value: 35 }], scope: 'universe',
  symbols: [], action: 'buy', hold_days: 20, risk_pct: 0.01, enabled: true,
}

function condText(c: AlertCondition): string {
  return `${c.field} ${c.op} ${c.value}`
}

function BacktestResult({ res }: { res: RuleBacktest }) {
  if (!res.ok) {
    return (
      <div className="mt-2 rounded-lg border border-line bg-panel-2/40 px-3 py-2 text-[11px] text-muted">
        {res.reason}
        {res.skipped_forward_only && res.skipped_forward_only.length > 0 &&
          <span className="text-faint"> (forward-only: {res.skipped_forward_only.join(', ')})</span>}
      </div>
    )
  }
  const row = res.horizons?.[0]
  return (
    <div className="mt-2 rounded-lg border border-line bg-panel-2/40 px-3 py-2 text-[11px]">
      <div className="font-display text-[12px] text-ink">{res.verdict}</div>
      {row && (
        <div className="mt-1 font-mono text-faint">
          {res.symbol} · {res.n_entries} entries · {row.horizon}d: edge
          <span className={cn(row.edge_pct >= 0 ? 'text-up' : 'text-down')}> {row.edge_pct >= 0 ? '+' : ''}{row.edge_pct}%</span>
          {' '}· t={row.t_stat} · hit {row.hit_rate_pct}% · OOS {row.oos_alpha_pct >= 0 ? '+' : ''}{row.oos_alpha_pct}%
        </div>
      )}
      {res.skipped_forward_only && res.skipped_forward_only.length > 0 &&
        <div className="mt-0.5 text-[10px] text-faint">forward-only (not backtested): {res.skipped_forward_only.join(', ')}</div>}
    </div>
  )
}

function AlertsTab({ onPropose }: { onPropose?: (p: Proposal) => void }) {
  const [rules, setRules] = useState<AlertRule[]>([])
  const [fields, setFields] = useState<AlertFields | null>(null)
  const [evalRes, setEvalRes] = useState<AlertEval | null>(null)
  const [checking, setChecking] = useState(false)
  const [bt, setBt] = useState<Record<string, RuleBacktest>>({})
  const [btSym, setBtSym] = useState<Record<string, string>>({})
  const [draft, setDraft] = useState<AlertRule>({ ...BLANK_RULE })
  const [saving, setSaving] = useState(false)

  const refresh = () => api.alertRules().then(setRules).catch(() => {})
  useEffect(() => { refresh(); api.alertFields().then(setFields).catch(() => {}) }, [])

  const check = async () => { setChecking(true); try { setEvalRes(await api.evaluateAlerts()) } catch { /* */ } finally { setChecking(false) } }
  const toggle = async (r: AlertRule) => { await api.saveAlertRule({ ...r, enabled: !r.enabled }).catch(() => {}); refresh() }
  const del = async (id?: string) => { if (id) { await api.deleteAlertRule(id).catch(() => {}); refresh() } }
  const runBt = async (r: AlertRule) => {
    const res = await api.backtestRule(r, r.id ? btSym[r.id] : undefined).catch(() => null)
    if (res && r.id) setBt((b) => ({ ...b, [r.id!]: res }))
  }
  const save = async () => {
    if (!draft.name.trim() || draft.conditions.length === 0) return
    setSaving(true)
    try { await api.saveAlertRule(draft); setDraft({ ...BLANK_RULE, conditions: [{ field: 'rsi', op: '<=', value: 35 }] }); refresh() }
    catch { /* */ } finally { setSaving(false) }
  }

  const setCond = (i: number, patch: Partial<AlertCondition>) =>
    setDraft((d) => ({ ...d, conditions: d.conditions.map((c, j) => j === i ? { ...c, ...patch } : c) }))
  const addCond = () => setDraft((d) => ({ ...d, conditions: [...d.conditions, { field: 'composite', op: '>=', value: 60 }] }))
  const rmCond = (i: number) => setDraft((d) => ({ ...d, conditions: d.conditions.filter((_, j) => j !== i) }))

  const fieldKeys = fields ? Object.keys(fields.fields) : []

  return (
    <div className="space-y-4">
      <Explainer title="From signals to a system">
        A rule is a set of conditions that must <em>all</em> hold. Turn good ideas into a
        <strong className="text-ink"> checklist the machine watches for you</strong> — removing the emotion of
        deciding in the moment. <strong className="text-ink">Walk-forward backtest</strong> the price-based part to see if
        it ever worked (in/out-of-sample); the smart-money conditions can't be backtested (no point-in-time history),
        so those are tracked forward by the learning loop. Fired alerts come <strong className="text-ink">pre-sized by your
        risk rules</strong> — you still confirm every one.
      </Explainer>

      {/* Check now */}
      <div className="flex items-center justify-between rounded-2xl border border-line bg-panel/50 p-3">
        <div>
          <div className="eyebrow">Monitor</div>
          <div className="font-display text-[14px] italic text-muted">evaluate enabled rules against live data</div>
        </div>
        <button onClick={check} disabled={checking}
          className="rounded-lg bg-gold px-4 py-2 text-[13px] font-semibold text-obsidian disabled:opacity-50">
          {checking ? 'Checking…' : 'Check now'}
        </button>
      </div>

      {checking && <Spinner label="Evaluating rules across the universe…" />}
      {evalRes && !checking && (
        evalRes.alerts.length === 0 ? (
          <div className="rounded-xl border border-line bg-panel-2/30 px-4 py-3 text-[13px] text-muted">
            No rules fired right now. {evalRes.note}
          </div>
        ) : (
          <div className="space-y-2">
            {evalRes.alerts.map((a, i) => (
              <div key={i} className="flex items-center gap-3 rounded-xl border border-gold/25 bg-gold/5 px-3 py-2.5">
                <Bell size={14} className="text-gold" />
                <div className="min-w-0 flex-1">
                  <div className="text-[13px] text-ink"><span className="font-mono font-semibold">{a.symbol}</span> · {a.rule_name}</div>
                  <div className="truncate text-[11px] text-faint">{a.matched.map(condText).join(' · ')}</div>
                </div>
                {onPropose && (
                  <button onClick={() => onPropose(a.proposal)}
                    className="shrink-0 rounded-lg border border-gold/40 bg-gold/10 px-2.5 py-1 text-[11px] font-semibold text-gold hover:bg-gold/20">
                    Paper-trade ${a.proposal.notional?.toLocaleString()}
                  </button>
                )}
              </div>
            ))}
          </div>
        )
      )}

      {/* Rules list */}
      <div className="space-y-2">
        <div className="eyebrow px-1">Your rules</div>
        {rules.map((r) => (
          <div key={r.id} className="rounded-xl border border-line bg-panel/50 p-3">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <div className="flex items-center gap-2">
                <button onClick={() => toggle(r)} title="Enable/disable"
                  className={cn('h-5 w-9 rounded-full p-0.5 transition-colors', r.enabled ? 'bg-gold/80' : 'bg-panel-2')}>
                  <span className={cn('block h-4 w-4 rounded-full bg-obsidian transition-transform', r.enabled && 'translate-x-4')} />
                </button>
                <span className="font-display text-[14px]">{r.name}</span>
                <span className="font-mono text-[10px] text-faint">{r.hold_days}d · {(r.risk_pct * 100).toFixed(1)}% risk</span>
              </div>
              <div className="flex items-center gap-1.5">
                <input value={r.id ? (btSym[r.id] ?? '') : ''} placeholder="symbol"
                  onChange={(e) => r.id && setBtSym((m) => ({ ...m, [r.id!]: e.target.value.toUpperCase() }))}
                  className="w-20 rounded-lg border border-line bg-panel-2/50 px-2 py-1 font-mono text-[11px] text-ink focus:border-gold/40 focus:outline-none" />
                <button onClick={() => runBt(r)} title="Walk-forward backtest"
                  className="flex items-center gap-1 rounded-lg border border-line px-2 py-1 text-[11px] text-muted hover:text-ink">
                  <Play size={11} /> Backtest
                </button>
                <button onClick={() => del(r.id)} title="Delete" className="text-faint hover:text-down"><Trash2 size={14} /></button>
              </div>
            </div>
            <div className="mt-1.5 flex flex-wrap gap-1.5">
              {r.conditions.map((c, i) => (
                <span key={i} className="rounded-md border border-line bg-panel-2/40 px-2 py-0.5 font-mono text-[10px] text-muted">{condText(c)}</span>
              ))}
            </div>
            {r.id && bt[r.id] && <BacktestResult res={bt[r.id]} />}
          </div>
        ))}
      </div>

      {/* Add rule */}
      <div className="rounded-2xl border border-line bg-panel/50 p-3">
        <div className="eyebrow mb-2">New rule</div>
        <input value={draft.name} onChange={(e) => setDraft({ ...draft, name: e.target.value })}
          placeholder="Rule name (e.g. Oversold dip in uptrend)"
          className="mb-2 w-full rounded-lg border border-line bg-panel-2/50 px-3 py-1.5 text-[13px] text-ink placeholder:text-faint focus:border-gold/40 focus:outline-none" />
        <div className="space-y-1.5">
          {draft.conditions.map((c, i) => {
            const meta = fields?.fields[c.field]
            return (
              <div key={i} className="flex items-center gap-1.5">
                <select value={c.field} onChange={(e) => setCond(i, { field: e.target.value, value: fields?.fields[e.target.value]?.type === 'cat' ? (fields.fields[e.target.value].choices?.[0] ?? '') : 0 })}
                  className="rounded-lg border border-line bg-panel-2/50 px-2 py-1 text-[12px] text-ink focus:border-gold/40 focus:outline-none">
                  {fieldKeys.map((k) => <option key={k} value={k}>{fields!.fields[k].label}{!fields!.fields[k].pit ? ' ⚡' : ''}</option>)}
                </select>
                <select value={c.op} onChange={(e) => setCond(i, { op: e.target.value })}
                  className="rounded-lg border border-line bg-panel-2/50 px-2 py-1 font-mono text-[12px] text-ink focus:border-gold/40 focus:outline-none">
                  {(meta?.type === 'cat' ? ['=='] : (fields?.ops ?? ['>=', '<=', '>', '<', '=='])).map((o) => <option key={o} value={o}>{o}</option>)}
                </select>
                {meta?.type === 'cat' ? (
                  <select value={String(c.value)} onChange={(e) => setCond(i, { value: e.target.value })}
                    className="rounded-lg border border-line bg-panel-2/50 px-2 py-1 text-[12px] text-ink focus:border-gold/40 focus:outline-none">
                    {(meta.choices ?? []).map((ch) => <option key={ch} value={ch}>{ch}</option>)}
                  </select>
                ) : (
                  <input value={String(c.value)} onChange={(e) => setCond(i, { value: e.target.value === '' ? '' : Number(e.target.value) })}
                    type="number" className="w-24 rounded-lg border border-line bg-panel-2/50 px-2 py-1 font-mono text-[12px] text-ink focus:border-gold/40 focus:outline-none" />
                )}
                <button onClick={() => rmCond(i)} className="text-faint hover:text-down"><Trash2 size={13} /></button>
              </div>
            )
          })}
        </div>
        <div className="mt-2 flex flex-wrap items-center gap-2">
          <button onClick={addCond} className="flex items-center gap-1 rounded-lg border border-line px-2 py-1 text-[11px] text-muted hover:text-ink"><Plus size={12} /> Condition</button>
          <label className="flex items-center gap-1 text-[11px] text-faint">hold
            <input type="number" value={draft.hold_days} onChange={(e) => setDraft({ ...draft, hold_days: Number(e.target.value) })}
              className="w-14 rounded border border-line bg-panel-2/50 px-1.5 py-0.5 font-mono text-ink focus:outline-none" />d</label>
          <label className="flex items-center gap-1 text-[11px] text-faint">risk
            <input type="number" step="0.1" value={(draft.risk_pct * 100)} onChange={(e) => setDraft({ ...draft, risk_pct: Number(e.target.value) / 100 })}
              className="w-14 rounded border border-line bg-panel-2/50 px-1.5 py-0.5 font-mono text-ink focus:outline-none" />%</label>
          <button onClick={save} disabled={saving || !draft.name.trim()}
            className="ml-auto rounded-lg bg-gold px-4 py-1.5 text-[12px] font-semibold text-obsidian disabled:opacity-50">
            {saving ? 'Saving…' : 'Save rule'}
          </button>
        </div>
        <div className="mt-1.5 text-[10px] text-faint">⚡ = smart-money field (live-only; can't be walk-forward backtested)</div>
      </div>
    </div>
  )
}

// ───────────────────────── Coach ─────────────────────────
const GRADE_COLOR: Record<string, string> = {
  A: 'text-up', B: 'text-up', C: 'text-gold', D: 'text-down', F: 'text-down', '—': 'text-faint',
}

function CoachTab() {
  const [coach, setCoach] = useState<CoachData | null>(null)
  const [shadow, setShadow] = useState<ShadowData | null>(null)
  const [busy, setBusy] = useState(true)

  useEffect(() => {
    Promise.all([api.coach().catch(() => null), api.shadow().catch(() => null)])
      .then(([c, s]) => { setCoach(c); setShadow(s) }).finally(() => setBusy(false))
  }, [])

  if (busy) return <Spinner label="Grading your trading…" />
  const sc = coach?.coach.scorecard
  const chs = coach?.coach.challenges ?? []

  return (
    <div className="grid gap-4 lg:grid-cols-2">
      <div className="space-y-4">
        <div className="rounded-2xl border border-line bg-panel/50 p-5">
          <div className="eyebrow mb-2">Discipline scorecard</div>
          {sc?.ok ? (
            <>
              <div className="flex items-baseline gap-3">
                <span className={cn('font-display text-[3.2rem] font-semibold leading-none', GRADE_COLOR[sc.grade] ?? 'text-ink')}>{sc.grade}</span>
                <span className="font-mono text-[15px] text-muted tnum">{sc.score}/100</span>
                <span className="text-[11px] text-faint">· {sc.n_trips} trades</span>
              </div>
              <div className="mt-4 space-y-2.5">
                {sc.components.map((c: any) => (
                  <div key={c.name}>
                    <div className="flex items-center justify-between text-[12px]">
                      <span className="text-muted">{c.name}</span>
                      <span className="font-mono text-faint tnum">{c.score}</span>
                    </div>
                    <div className="mt-1 h-1.5 rounded-full bg-panel-2">
                      <span className="block h-full rounded-full bg-gold" style={{ width: `${c.score}%` }} />
                    </div>
                    <div className="mt-0.5 text-[11px] text-faint">{c.note}</div>
                  </div>
                ))}
              </div>
            </>
          ) : <div className="font-display text-[14px] italic text-muted">{sc?.message ?? 'No trades graded yet.'}</div>}
        </div>

        <div className="rounded-2xl border border-line bg-panel/50 p-5">
          <div className="eyebrow mb-2.5">Challenges</div>
          <div className="space-y-1.5">
            {chs.map((c: any) => (
              <div key={c.id} className="flex items-start gap-2.5">
                <span className="mt-0.5">{c.done ? '✅' : '⬜'}</span>
                <div className="flex-1">
                  <div className="flex items-center justify-between gap-2">
                    <span className="font-display text-[13px] font-medium">{c.title}</span>
                    <span className="font-mono text-[10px] text-faint">{c.status}</span>
                  </div>
                  <div className="text-[11px] text-faint">{c.desc}</div>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>

      <div className="rounded-2xl border border-line bg-panel/40 p-5">
        {shadow ? <Md>{shadow.reply}</Md> : <div className="text-faint">No review available.</div>}
      </div>
    </div>
  )
}

// ───────────────────────── Builder ─────────────────────────
function BuilderTab() {
  const [desc, setDesc] = useState('')
  const [symbol, setSymbol] = useState('SPY')
  const [period, setPeriod] = useState('2y')
  const [res, setRes] = useState<StrategyResult | null>(null)
  const [busy, setBusy] = useState(false)

  const gen = async () => {
    if (!desc.trim()) return
    setBusy(true)
    try { setRes(await api.generateStrategy({ description: desc, symbol, period })) }
    catch { /* */ } finally { setBusy(false) }
  }

  const m = res?.metrics
  return (
    <div className="space-y-4">
      <Explainer title="What is the strategy builder?">
        Describe a trading idea in plain English — <em>"buy when RSI dips below 30 while price is above the
        200-day average, sell when RSI tops 65"</em> — and the copilot turns it into a precise rule set,
        backtests it on real data, and exports it as <strong className="text-ink">TradingView Pine Script</strong>
        you can paste straight onto a chart. No coding required; the same honest backtest caveats apply.
      </Explainer>
      <div className="space-y-2 rounded-2xl border border-line bg-panel/50 p-3">
        <textarea value={desc} onChange={(e) => setDesc(e.target.value)}
          placeholder="e.g. Go long when the 20-day EMA crosses above the 50-day EMA, exit when it crosses back below."
          className="h-24 w-full resize-none rounded-lg border border-line bg-panel-2/50 px-3 py-2 text-[13px] text-ink placeholder:text-faint focus:border-gold/40 focus:outline-none" />
        <div className="flex flex-wrap items-end gap-2">
          <label className="flex flex-col gap-1">
            <span className="eyebrow">Symbol</span>
            <input value={symbol} onChange={(e) => setSymbol(e.target.value.toUpperCase())}
              className="w-28 rounded-lg border border-line bg-panel-2/50 px-3 py-1.5 font-mono text-[13px] text-ink focus:border-gold/40 focus:outline-none" />
          </label>
          <label className="flex flex-col gap-1">
            <span className="eyebrow">Period</span>
            <select value={period} onChange={(e) => setPeriod(e.target.value)}
              className="rounded-lg border border-line bg-panel-2/50 px-3 py-1.5 text-[13px] text-ink focus:border-gold/40 focus:outline-none">
              {PERIODS.map((p) => <option key={p} value={p}>{p}</option>)}
            </select>
          </label>
          <button onClick={gen} disabled={busy || !desc.trim()}
            className="flex items-center gap-1.5 rounded-lg bg-gold px-4 py-2 text-[13px] font-semibold text-obsidian transition-transform hover:scale-[1.03] active:scale-95 disabled:opacity-50">
            <Wand2 size={15} /> Generate &amp; backtest
          </button>
        </div>
      </div>

      {busy && <Spinner label="Designing &amp; backtesting your strategy…" />}
      {res && !busy && (res.ok ? (
        <div className="space-y-4">
          <div className="grid grid-cols-2 gap-2.5 sm:grid-cols-3 lg:grid-cols-6">
            <Metric label="Return" value={`${(m!.total_return_pct).toFixed(1)}%`} tone={m!.total_return_pct >= 0 ? 'up' : 'down'} />
            <Metric label="Buy & Hold" value={`${(m!.buy_hold_return_pct).toFixed(1)}%`} />
            <Metric label="Max DD" value={`${(m!.max_drawdown_pct).toFixed(1)}%`} tone="down" />
            <Metric label="Sharpe" value={(m!.sharpe).toFixed(2)} />
            <Metric label="Trades" value={`${m!.n_trades}`} />
            <Metric label="Win rate" value={`${(m!.win_rate_pct).toFixed(0)}%`} />
          </div>
          {res.equity_curve && res.equity_curve.length > 0 && <EquityChart data={res.equity_curve} />}
          <Md>{res.explanation ?? ''}</Md>
        </div>
      ) : <div className="rounded-xl border border-down/30 bg-down/5 px-4 py-3 text-[13px] text-down">{res.error}</div>)}
    </div>
  )
}

export function StudioPage({ onPropose }: { onPropose?: (p: Proposal) => void }) {
  const [tab, setTab] = useState<Tab>('backtest')
  const tabs: { id: Tab; label: string; icon: typeof FlaskConical }[] = [
    { id: 'backtest', label: 'Backtest', icon: BarChart3 },
    { id: 'builder', label: 'Builder', icon: Wand2 },
    { id: 'factors', label: 'Factor Zoo', icon: FlaskConical },
    { id: 'risk', label: 'Risk', icon: ShieldAlert },
    { id: 'alerts', label: 'Alerts', icon: Bell },
    { id: 'coach', label: 'Coach', icon: Trophy },
  ]
  return (
    <div className="h-full overflow-y-auto">
      <div className="mx-auto max-w-5xl p-4">
        <div className="mb-4 flex gap-1 overflow-x-auto rounded-xl border border-line bg-panel/40 p-1
                        [-ms-overflow-style:none] [scrollbar-width:none] [&::-webkit-scrollbar]:hidden">
          {tabs.map((t) => {
            const Icon = t.icon
            return (
              <button key={t.id} onClick={() => setTab(t.id)}
                className={cn('flex shrink-0 items-center justify-center gap-2 whitespace-nowrap rounded-lg px-3 py-2 text-[13px] transition-colors sm:flex-1',
                  tab === t.id ? 'bg-gold/12 text-gold' : 'text-muted hover:text-ink')}>
                <Icon size={15} /> {t.label}
              </button>
            )
          })}
        </div>
        {tab === 'backtest' && <BacktestTab />}
        {tab === 'builder' && <BuilderTab />}
        {tab === 'factors' && <FactorsTab />}
        {tab === 'risk' && <RiskTab />}
        {tab === 'alerts' && <AlertsTab onPropose={onPropose} />}
        {tab === 'coach' && <CoachTab />}
      </div>
    </div>
  )
}
