import { useEffect, useMemo, useState } from 'react'
import { Activity, Building2, CalendarDays, ChevronRight, ExternalLink, Flame, FlaskConical, Landmark, Radar, RefreshCw, ShieldQuestion, Sparkles, Target, TrendingDown, TrendingUp, Users, Zap } from 'lucide-react'
import { api } from '../api'
import { cn } from '../lib'
import type { EdgeSignals, EventStudy, IdeasResponse, Proposal, Regime, ScanResult, ScanRow, SignalBundle, SmartSignal, TrackRecord } from '../types'

const REGIME_NICE: Record<string, { label: string; tone: 'up' | 'down' | 'gold' }> = {
  risk_on: { label: 'RISK-ON', tone: 'up' },
  neutral: { label: 'NEUTRAL', tone: 'gold' },
  risk_off: { label: 'RISK-OFF', tone: 'down' },
}

function usd(n: number): string {
  const a = Math.abs(n)
  if (a >= 1e9) return `$${(n / 1e9).toFixed(1)}B`
  if (a >= 1e6) return `$${(n / 1e6).toFixed(1)}M`
  if (a >= 1e3) return `$${(n / 1e3).toFixed(0)}K`
  return `$${n.toFixed(0)}`
}

function Metric({ label, value, sub }: { label: string; value: string; sub?: string }) {
  return (
    <div className="rounded-xl border border-line bg-panel-2/40 px-3 py-2.5">
      <div className="eyebrow">{label}</div>
      <div className="mt-0.5 font-mono text-[15px] text-ink">{value}</div>
      {sub && <div className="text-[10px] text-faint">{sub}</div>}
    </div>
  )
}

function RegimeCard({ regime, onRefresh }: { regime: Regime | null; onRefresh: () => void }) {
  const nice = regime ? REGIME_NICE[regime.label] : undefined
  const tone = nice?.tone ?? 'gold'
  const ring = tone === 'up' ? 'ring-up/30' : tone === 'down' ? 'ring-down/30' : 'ring-gold/30'
  const txt = tone === 'up' ? 'text-up' : tone === 'down' ? 'text-down' : 'text-gold'
  return (
    <div className={cn('rounded-2xl border border-line bg-panel/60 p-5 ring-1', ring)}>
      <div className="flex items-start justify-between gap-3">
        <div>
          <div className="eyebrow">Market Regime</div>
          <div className={cn('font-display text-[1.8rem] font-semibold leading-none', txt)}>
            {regime?.ok ? nice?.label ?? '—' : 'Computing…'}
          </div>
        </div>
        <button onClick={onRefresh} title="Recompute regime"
          className="flex items-center gap-1.5 rounded-full border border-line px-3 py-1.5 text-[11px] text-muted transition-colors hover:text-ink">
          <RefreshCw size={12} /> Refresh
        </button>
      </div>

      {regime?.ok && (
        <>
          <div className="mt-4 grid grid-cols-2 gap-2 sm:grid-cols-4">
            <Metric label="Trend" value={regime.trend} sub={`${regime.spy_vs_200dma_pct >= 0 ? '+' : ''}${regime.spy_vs_200dma_pct.toFixed(1)}% vs 200dma`} />
            <Metric label="Breadth" value={`${regime.breadth_pct.toFixed(0)}%`} sub="above 50dma" />
            <Metric label="Volatility" value={regime.vol} sub={`${regime.realized_vol_20d.toFixed(0)}% ann.`} />
            <Metric label="3-mo momentum" value={`${regime.momentum_3m_pct >= 0 ? '+' : ''}${regime.momentum_3m_pct.toFixed(1)}%`} sub="SPY" />
          </div>
          <p className="mt-3 text-[12px] leading-relaxed text-muted">
            <span className="text-faint">What this means:</span> a read on the market backdrop from
            price action — trend, how many stocks participate, volatility, and momentum. Smart-money
            signals mean different things in a risk-on advance than a risk-off correction.
            <span className="text-faint"> It is not a forecast.</span>
          </p>
        </>
      )}
    </div>
  )
}

const KIND_META: Record<string, { label: string; cls: string; icon: typeof Building2 }> = {
  insider_buy: { label: 'Insider buy', cls: 'border-up/40 bg-up/10 text-up', icon: TrendingUp },
  insider_sell: { label: 'Insider sell', cls: 'border-down/40 bg-down/10 text-down', icon: TrendingDown },
  inst_13f: { label: '13F holding', cls: 'border-gold/40 bg-gold/10 text-gold', icon: Building2 },
  congress: { label: 'Congress', cls: 'border-line-strong bg-panel-2 text-muted', icon: Landmark },
}

function SignalRow({ s }: { s: SmartSignal }) {
  const meta = KIND_META[s.kind] ?? KIND_META.congress
  const Icon = meta.icon
  return (
    <div className="flex items-center gap-3 border-b border-line/60 px-1 py-2.5 last:border-0">
      <span className={cn('flex shrink-0 items-center gap-1 rounded-full border px-2 py-0.5 font-mono text-[9px] uppercase tracking-wide', meta.cls)}>
        <Icon size={11} /> {meta.label}
      </span>
      <div className="min-w-0 flex-1">
        <div className="truncate text-[13px] text-ink">{s.detail || s.actor}</div>
        <div className="truncate text-[11px] text-faint">{s.actor} · {s.date || '—'} · <span className="italic">{s.lag_note}</span></div>
      </div>
      {s.size_usd > 0 && (
        <span className={cn('shrink-0 font-mono text-[12px]', s.direction > 0 ? 'text-up' : s.direction < 0 ? 'text-down' : 'text-muted')}>
          {usd(s.size_usd)}
        </span>
      )}
      {s.source_url && (
        <a href={s.source_url} target="_blank" rel="noreferrer" title="View filing"
          className="shrink-0 text-faint transition-colors hover:text-gold">
          <ExternalLink size={13} />
        </a>
      )}
    </div>
  )
}

function Chip({ icon: Icon, children, tone = 'muted' }: { icon: typeof Users; children: React.ReactNode; tone?: 'up' | 'down' | 'gold' | 'muted' }) {
  const cls = tone === 'up' ? 'text-up' : tone === 'down' ? 'text-down' : tone === 'gold' ? 'text-gold' : 'text-muted'
  return (
    <div className="flex items-center gap-1.5 rounded-lg border border-line bg-panel-2/40 px-2.5 py-1.5">
      <Icon size={13} className={cls} />
      <span className={cn('font-mono text-[12px]', cls)}>{children}</span>
    </div>
  )
}

function StudyCard({ symbol }: { symbol: string }) {
  const [kind, setKind] = useState<'insider_buy' | 'insider_sell'>('insider_buy')
  const [res, setRes] = useState<EventStudy | null>(null)
  const [loading, setLoading] = useState(false)

  // Reset when the symbol changes — a stale verdict for another ticker is misleading.
  useEffect(() => { setRes(null) }, [symbol])

  const run = async (k: 'insider_buy' | 'insider_sell') => {
    setKind(k); setLoading(true); setRes(null)
    try { setRes(await api.studySignal(symbol, k)) } catch { /* ignore */ } finally { setLoading(false) }
  }

  const verdictTone = (() => {
    if (!res?.ok || !res.horizons?.length) return 'muted'
    const row = res.horizons.find((r) => r.horizon === 60) ?? res.horizons[0]
    if (Math.abs(row.t_stat) < 1.5) return 'muted'
    return row.edge_pct > 0 ? 'up' : 'down'
  })()
  const vtxt = verdictTone === 'up' ? 'text-up' : verdictTone === 'down' ? 'text-down' : 'text-muted'

  return (
    <div className="rounded-2xl border border-line bg-panel/50 p-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-2">
          <FlaskConical size={15} className="text-gold" />
          <div>
            <span className="eyebrow">Signal backtest · event study</span>
            <div className="font-display text-[15px] italic text-muted">
              does this signal historically work for <span className="not-italic text-gold">{symbol}</span>?
            </div>
          </div>
        </div>
        <div className="flex items-center gap-1.5">
          <div className="flex rounded-lg border border-line p-0.5">
            {(['insider_buy', 'insider_sell'] as const).map((k) => (
              <button key={k} onClick={() => setKind(k)}
                className={cn('rounded-md px-2.5 py-1 font-mono text-[11px] transition-colors',
                  kind === k ? 'bg-gold/15 text-gold' : 'text-muted hover:text-ink')}>
                {k === 'insider_buy' ? 'Buys' : 'Sells'}
              </button>
            ))}
          </div>
          <button onClick={() => run(kind)} disabled={loading}
            className="rounded-lg bg-gold px-3 py-1.5 text-[12px] font-semibold text-obsidian disabled:opacity-50">
            {loading ? 'Running…' : 'Run study'}
          </button>
        </div>
      </div>

      {loading && (
        <div className="mt-4 text-center text-[12px] text-faint">
          Pulling ~5y of insider filings + prices and measuring forward returns…
        </div>
      )}

      {res && !loading && !res.ok && (
        <div className="mt-4 rounded-lg border border-line bg-panel-2/40 px-3 py-3 text-[12px] text-muted">
          {res.reason || 'Not enough data to run the study.'}
        </div>
      )}

      {res?.ok && !loading && res.horizons && (
        <div className="mt-4 space-y-3">
          <div className={cn('font-display text-[14px] leading-snug', vtxt)}>{res.verdict}</div>
          <div className="text-[11px] text-faint">
            {res.n_events} {kind === 'insider_buy' ? 'buy' : 'sell'} events · {res.window?.start} → {res.window?.end}
          </div>
          <div className="overflow-x-auto">
            <table className="w-full min-w-[460px] border-collapse text-[12px]">
              <thead>
                <tr className="text-faint">
                  {['Horizon', 'Return', 'Alpha vs SPY', 'Edge¹', 'Hit', 't-stat', 'OOS²'].map((h) => (
                    <th key={h} className="border-b border-line px-2 py-1.5 text-left font-mono text-[10px] uppercase tracking-wide">{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody className="font-mono">
                {res.horizons.map((r) => (
                  <tr key={r.horizon} className="border-b border-line/50">
                    <td className="px-2 py-1.5 text-ink">{r.horizon}d</td>
                    <td className={cn('px-2 py-1.5', r.mean_ret_pct >= 0 ? 'text-up' : 'text-down')}>{r.mean_ret_pct >= 0 ? '+' : ''}{r.mean_ret_pct}%</td>
                    <td className={cn('px-2 py-1.5', r.mean_alpha_pct >= 0 ? 'text-up' : 'text-down')}>{r.mean_alpha_pct >= 0 ? '+' : ''}{r.mean_alpha_pct}%</td>
                    <td className={cn('px-2 py-1.5 font-semibold', r.edge_pct >= 0 ? 'text-up' : 'text-down')}>{r.edge_pct >= 0 ? '+' : ''}{r.edge_pct}%</td>
                    <td className="px-2 py-1.5 text-muted">{r.hit_rate_pct}%</td>
                    <td className={cn('px-2 py-1.5', Math.abs(r.t_stat) >= 2 ? 'text-ink' : 'text-faint')}>{r.t_stat}</td>
                    <td className={cn('px-2 py-1.5', r.oos_alpha_pct >= 0 ? 'text-up/80' : 'text-down/80')}>{r.oos_alpha_pct >= 0 ? '+' : ''}{r.oos_alpha_pct}%</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <p className="text-[10px] leading-relaxed text-faint">
            ¹ <span className="text-muted">Edge</span> = event alpha − the stock's normal drift vs SPY (its unconditional baseline), so it isolates the signal's marginal information.
            ² <span className="text-muted">OOS</span> = alpha on the most recent 30% of events (did it hold up?).
            A |t-stat| under ~2 means the result is statistically indistinguishable from luck. <span className="text-muted">Past performance is not predictive.</span>
          </p>
        </div>
      )}
    </div>
  )
}

function dirTone(direction: string): 'up' | 'down' | 'gold' {
  return direction === 'bullish' ? 'up' : direction === 'bearish' ? 'down' : 'gold'
}

function ScanRowItem({ row, open, onToggle }: { row: ScanRow; open: boolean; onToggle: () => void }) {
  const tone = dirTone(row.direction)
  const bar = tone === 'up' ? 'bg-up' : tone === 'down' ? 'bg-down' : 'bg-gold'
  const txt = tone === 'up' ? 'text-up' : tone === 'down' ? 'text-down' : 'text-gold'
  return (
    <div className="border-b border-line/50 last:border-0">
      <button onClick={onToggle} className="flex w-full items-center gap-3 px-1 py-2.5 text-left">
        <ChevronRight size={13} className={cn('shrink-0 text-faint transition-transform', open && 'rotate-90')} />
        <span className="w-12 shrink-0 font-mono text-[13px] font-semibold text-ink">{row.symbol}</span>
        <div className="h-1.5 flex-1 rounded-full bg-panel-2">
          <span className={cn('block h-full rounded-full', bar)} style={{ width: `${row.score}%` }} />
        </div>
        <span className={cn('w-10 shrink-0 text-right font-mono text-[12px]', txt)}>{row.score}</span>
        <span className={cn('hidden w-16 shrink-0 text-right font-mono text-[10px] uppercase sm:inline', txt)}>{row.direction}</span>
      </button>
      {open && (
        <div className="ml-6 mb-2 space-y-1 rounded-lg border border-line bg-panel-2/30 px-3 py-2">
          {row.components.length === 0 && <div className="text-[11px] text-faint">No signal data available for this name.</div>}
          {row.components.map((c) => (
            <div key={c.name} className="flex items-center justify-between text-[11px]">
              <span className="text-muted">{c.label}</span>
              <span className={cn('font-mono', c.points >= 0 ? 'text-up' : 'text-down')}>
                {c.points >= 0 ? '+' : ''}{c.points} pts <span className="text-faint">(sig {c.signal >= 0 ? '+' : ''}{c.signal} · w{(c.weight * 100).toFixed(0)}%)</span>
              </span>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

function ScannerCard() {
  const [data, setData] = useState<ScanResult | null>(null)
  const [loading, setLoading] = useState(false)
  const [open, setOpen] = useState<string | null>(null)

  const scan = async () => {
    setLoading(true)
    try { setData(await api.scanner()) } catch { /* */ } finally { setLoading(false) }
  }

  return (
    <div className="rounded-2xl border border-line bg-panel/50 p-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-2">
          <Radar size={15} className="text-gold" />
          <div>
            <span className="eyebrow">Composite scanner · top setups</span>
            <div className="font-display text-[15px] italic text-muted">momentum + smart-money + edge signals, ranked &amp; explained</div>
          </div>
        </div>
        <button onClick={scan} disabled={loading}
          className="rounded-lg bg-gold px-3 py-1.5 text-[12px] font-semibold text-obsidian disabled:opacity-50">
          {loading ? 'Scanning…' : 'Run scanner'}
        </button>
      </div>

      {loading && <div className="mt-4 text-center text-[12px] text-faint">Blending signals across the universe (~30s)…</div>}

      {data && !loading && (
        <div className="mt-3">
          <div className="mb-2 flex items-center gap-2 text-[11px] text-faint">
            <span className="rounded-full bg-panel-2 px-2 py-0.5 font-mono uppercase">regime: {data.regime}</span>
            <span>· {data.scanned} names · click a row to see why</span>
          </div>
          <div>
            {data.results.map((r) => (
              <ScanRowItem key={r.symbol} row={r} open={open === r.symbol}
                onToggle={() => setOpen(open === r.symbol ? null : r.symbol)} />
            ))}
          </div>
          <p className="mt-2 px-1 text-[10px] text-faint">{data.note}</p>
        </div>
      )}
    </div>
  )
}

function IdeasCard({ onPropose }: { onPropose?: (p: Proposal) => void }) {
  const [data, setData] = useState<IdeasResponse | null>(null)
  const [loading, setLoading] = useState(false)
  const [scanned, setScanned] = useState(false)

  const scan = async () => {
    setLoading(true)
    try { setData(await api.signalIdeas()) } catch { /* ignore */ } finally { setLoading(false); setScanned(true) }
  }

  return (
    <div className="rounded-2xl border border-line bg-panel/50 p-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-2">
          <Zap size={15} className="text-gold" />
          <div>
            <span className="eyebrow">Actionable now · paper ideas</span>
            <div className="font-display text-[15px] italic text-muted">fresh insider-buying clusters worth a look</div>
          </div>
        </div>
        <button onClick={scan} disabled={loading}
          className="rounded-lg bg-gold px-3 py-1.5 text-[12px] font-semibold text-obsidian disabled:opacity-50">
          {loading ? 'Scanning…' : 'Scan for ideas'}
        </button>
      </div>

      {loading && (
        <div className="mt-4 text-center text-[12px] text-faint">Scanning insider filings across the universe…</div>
      )}

      {scanned && !loading && data && data.ideas.length === 0 && (
        <div className="mt-4 text-center text-[12px] text-faint">
          No fresh insider-buying clusters right now — that's normal. Insider <em>buys</em> are rare; check back later.
        </div>
      )}

      {data && data.ideas.length > 0 && !loading && (
        <div className="mt-3 space-y-2">
          {data.ideas.map((idea) => (
            <div key={idea.symbol} className="flex items-center gap-3 rounded-xl border border-line bg-panel-2/40 px-3 py-2.5">
              <span className="font-mono text-[13px] font-semibold text-ink">{idea.symbol}</span>
              <div className="min-w-0 flex-1">
                <div className="truncate text-[12px] text-muted">{idea.rationale}</div>
              </div>
              {onPropose && (
                <button onClick={() => onPropose(idea.proposal)}
                  className="shrink-0 rounded-lg border border-gold/40 bg-gold/10 px-2.5 py-1 text-[11px] font-semibold text-gold transition-colors hover:bg-gold/20">
                  Paper-trade ${idea.proposal.notional?.toLocaleString()}
                </button>
              )}
            </div>
          ))}
          <p className="px-1 text-[10px] text-faint">
            Candidates to <em>consider</em>, sized small, paper only — confirmed by you, never auto-executed. Public, lagged signal; not advice.
          </p>
        </div>
      )}
    </div>
  )
}

function TrackRecordCard() {
  const [tr, setTr] = useState<TrackRecord | null>(null)
  useEffect(() => { api.trackRecord().then(setTr).catch(() => {}) }, [])
  const groups = tr ? Object.entries(tr.by_group) : []
  const hasData = tr && tr.overall.n > 0

  return (
    <div className="rounded-2xl border border-line bg-panel/50 p-4">
      <div className="flex items-center gap-2">
        <Target size={15} className="text-gold" />
        <div>
          <span className="eyebrow">Track record · what your signal trades did</span>
          <div className="font-display text-[15px] italic text-muted">realized alpha vs SPY, 60 days after each call</div>
        </div>
      </div>

      {!hasData && (
        <div className="mt-3 text-[12px] text-faint">
          No matured signal trades yet{tr && tr.pending ? ` (${tr.pending} pending)` : ''}. Paper-trade an idea above; outcomes resolve after ~60 days and base rates appear here.
        </div>
      )}

      {hasData && tr && (
        <div className="mt-3 space-y-2">
          <div className="flex flex-wrap gap-2">
            <div className="rounded-lg border border-line bg-panel-2/40 px-3 py-1.5">
              <span className="font-mono text-[12px] text-ink">{tr.overall.wins}/{tr.overall.n} beat SPY ({tr.overall.win_rate_pct}%)</span>
            </div>
            <div className={cn('rounded-lg border border-line bg-panel-2/40 px-3 py-1.5 font-mono text-[12px]',
              tr.overall.avg_alpha_pct >= 0 ? 'text-up' : 'text-down')}>
              avg alpha {tr.overall.avg_alpha_pct >= 0 ? '+' : ''}{tr.overall.avg_alpha_pct}%
            </div>
            {tr.pending > 0 && <div className="rounded-lg border border-line bg-panel-2/40 px-3 py-1.5 font-mono text-[12px] text-faint">{tr.pending} pending</div>}
          </div>
          {groups.length > 0 && (
            <div className="space-y-1">
              {groups.map(([key, g]) => (
                <div key={key} className="flex items-center justify-between rounded-lg px-2 py-1 text-[11px]">
                  <span className="font-mono text-muted">{key.replace('|', ' · ')}</span>
                  <span className={cn('font-mono', g.avg_alpha_pct >= 0 ? 'text-up' : 'text-down')}>
                    {g.wins}/{g.n} · {g.avg_alpha_pct >= 0 ? '+' : ''}{g.avg_alpha_pct}%
                  </span>
                </div>
              ))}
            </div>
          )}
          {tr.overall.n < 10 && <p className="px-1 text-[10px] text-faint">Small, young sample — weak evidence so far.</p>}
        </div>
      )}
    </div>
  )
}

function MiniCard({ icon: Icon, title, children }:
  { icon: typeof Activity; title: string; children: React.ReactNode }) {
  return (
    <div className="rounded-xl border border-line bg-panel-2/40 p-3">
      <div className="mb-1.5 flex items-center gap-1.5 text-gold">
        <Icon size={13} />
        <span className="eyebrow">{title}</span>
      </div>
      {children}
    </div>
  )
}

function EdgeCard({ symbol }: { symbol: string }) {
  const [data, setData] = useState<EdgeSignals | null>(null)
  const [loading, setLoading] = useState(false)
  const [loaded, setLoaded] = useState(false)
  useEffect(() => { setData(null); setLoaded(false) }, [symbol])

  const load = async () => {
    setLoading(true)
    try { setData(await api.edgeSignals(symbol)) } catch { /* */ } finally { setLoading(false); setLoaded(true) }
  }

  const sea = data?.seasonality
  const si = data?.short_interest
  const of = data?.options_flow
  const pe = data?.pead
  const squeezeTone = (s?: number | null) => s == null ? 'text-muted' : s >= 60 ? 'text-down' : s >= 35 ? 'text-gold' : 'text-up'

  return (
    <div className="rounded-2xl border border-line bg-panel/50 p-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-2">
          <Sparkles size={15} className="text-gold" />
          <div>
            <span className="eyebrow">Under-crowded signals</span>
            <div className="font-display text-[15px] italic text-muted">
              options · short interest · earnings drift · seasonality for <span className="not-italic text-gold">{symbol}</span>
            </div>
          </div>
        </div>
        <button onClick={load} disabled={loading}
          className="rounded-lg bg-gold px-3 py-1.5 text-[12px] font-semibold text-obsidian disabled:opacity-50">
          {loading ? 'Loading…' : 'Load edge signals'}
        </button>
      </div>

      {loading && <div className="mt-4 text-center text-[12px] text-faint">Pulling options chains, short interest, earnings & seasonality…</div>}

      {data && !loading && (
        <div className="mt-3 grid gap-2.5 sm:grid-cols-2">
          {/* Options flow */}
          <MiniCard icon={Activity} title="Options flow">
            {of?.ok ? (
              <div className="space-y-1 text-[12px]">
                <div className="text-muted">Put/Call (vol): <span className="font-mono text-ink">{of.put_call_volume_ratio ?? '—'}</span>
                  {of.atm_iv_pct != null && <> · ATM IV <span className="font-mono text-ink">{of.atm_iv_pct}%</span></>}</div>
                <div className="text-faint">{of.sentiment}</div>
                {of.unusual && of.unusual.length > 0 && (
                  <div className="mt-1 space-y-0.5">
                    {of.unusual.slice(0, 3).map((u, i) => (
                      <div key={i} className="font-mono text-[11px] text-faint">
                        unusual {u.side} ${u.strike} · {u.volume.toLocaleString()} vol ({u.vol_oi_ratio}× OI)
                      </div>
                    ))}
                  </div>
                )}
              </div>
            ) : <div className="text-[12px] text-faint">{of?.reason || 'No options data.'}</div>}
          </MiniCard>

          {/* Short interest */}
          <MiniCard icon={Flame} title="Short interest / squeeze">
            {si?.ok ? (
              <div className="space-y-1 text-[12px]">
                <div className="text-muted">Short float: <span className="font-mono text-ink">{si.short_pct_float ?? '—'}%</span>
                  {si.days_to_cover != null && <> · {si.days_to_cover}d to cover</>}</div>
                <div className={cn('font-mono', squeezeTone(si.squeeze_score))}>
                  Squeeze score {si.squeeze_score ?? '—'}/100 · {si.label}
                </div>
                {si.change_pct != null && <div className="text-faint">SI {si.change_pct >= 0 ? '+' : ''}{si.change_pct}% vs prior month</div>}
              </div>
            ) : <div className="text-[12px] text-faint">{si?.reason || 'No short data.'}</div>}
          </MiniCard>

          {/* PEAD */}
          <MiniCard icon={TrendingUp} title="Post-earnings drift">
            {pe?.ok ? (
              <div className="space-y-1 text-[12px]">
                <div className={cn(pe.has_pead ? 'text-up' : 'text-muted')}>{pe.verdict}</div>
                {pe.last_earnings && (
                  <div className="text-faint font-mono text-[11px]">
                    last: {pe.last_earnings} · reacted {pe.last_reaction_pct! >= 0 ? '+' : ''}{pe.last_reaction_pct}%
                    {pe.last_drift_pct != null && <> → drifted {pe.last_drift_pct >= 0 ? '+' : ''}{pe.last_drift_pct}%</>}
                  </div>
                )}
              </div>
            ) : <div className="text-[12px] text-faint">{pe?.reason || 'No earnings data.'}</div>}
          </MiniCard>

          {/* Seasonality */}
          <MiniCard icon={CalendarDays} title="Seasonality">
            {sea?.ok ? (
              <div className="space-y-1 text-[12px]">
                {sea.current ? (
                  <div className="text-muted">{sea.current_month_name}: avg <span className={cn('font-mono', sea.current.avg_pct >= 0 ? 'text-up' : 'text-down')}>{sea.current.avg_pct >= 0 ? '+' : ''}{sea.current.avg_pct}%</span> · {sea.current.win_rate}% up ({sea.current.n}y)</div>
                ) : <div className="text-faint">No current-month stats.</div>}
                {sea.best_month && <div className="text-faint">best {sea.best_month.name} ({sea.best_month.avg_pct >= 0 ? '+' : ''}{sea.best_month.avg_pct}%) · worst {sea.worst_month?.name} ({sea.worst_month?.avg_pct}%)</div>}
                {sea.turn_of_month_edge_pct != null && <div className="text-faint">turn-of-month edge {sea.turn_of_month_edge_pct >= 0 ? '+' : ''}{sea.turn_of_month_edge_pct}%/day</div>}
              </div>
            ) : <div className="text-[12px] text-faint">{sea?.reason || 'No seasonality.'}</div>}
          </MiniCard>
        </div>
      )}

      {data && !loading && (
        <p className="mt-2 px-1 text-[10px] text-faint">
          Weak, lagged, low-capacity signals — context that can tilt odds, not a money machine. Options/short data is free &amp; delayed.
        </p>
      )}
      {!loaded && !loading && (
        <p className="mt-3 text-[11px] text-faint">Loads on demand (options chains are slow &amp; flaky on free data).</p>
      )}
    </div>
  )
}

export function SmartMoneyPage({ watchSymbols, regime: regimeProp, onPropose }:
  { watchSymbols: string[]; regime: Regime | null; onPropose?: (p: Proposal) => void }) {
  const [regime, setRegime] = useState<Regime | null>(regimeProp)
  const quick = useMemo(() => {
    const eq = watchSymbols.filter((s) => !s.includes('/') && !s.includes('=') && !s.endsWith('-USD'))
    const base = eq.length ? eq : ['AAPL', 'NVDA', 'MSFT', 'TSLA']
    return Array.from(new Set([...base, 'AAPL', 'NVDA'])).slice(0, 8)
  }, [watchSymbols])

  const [symbol, setSymbol] = useState(quick[0] ?? 'AAPL')
  const [input, setInput] = useState('')
  const [bundle, setBundle] = useState<SignalBundle | null>(null)
  const [loading, setLoading] = useState(false)

  useEffect(() => { setRegime(regimeProp) }, [regimeProp])
  useEffect(() => {
    let live = true
    setLoading(true)
    setBundle(null)
    api.signals(symbol).then((b) => { if (live) setBundle(b) }).catch(() => {}).finally(() => { if (live) setLoading(false) })
    return () => { live = false }
  }, [symbol])

  const refreshRegime = () => { api.regime().then(setRegime).catch(() => {}) }
  const submit = (e: React.FormEvent) => {
    e.preventDefault()
    const s = input.trim().toUpperCase()
    if (s) { setSymbol(s); setInput('') }
  }

  const congressUnavailable = bundle?.sources_unavailable?.includes('congress')

  return (
    <div className="h-full overflow-y-auto">
      <div className="mx-auto max-w-5xl space-y-4 p-4 md:p-6">
        <RegimeCard regime={regime} onRefresh={refreshRegime} />

        {/* composite multi-signal scanner — the synthesis headline */}
        <ScannerCard />

        {/* act & learn: fresh ideas + realized track record */}
        <div className="grid gap-4 lg:grid-cols-2">
          <IdeasCard onPropose={onPropose} />
          <TrackRecordCard />
        </div>

        {/* symbol picker */}
        <div className="rounded-2xl border border-line bg-panel/50 p-4">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <span className="eyebrow">Smart-money tracker</span>
              <div className="font-display text-[15px] italic text-muted">
                what insiders & institutions are doing in <span className="not-italic text-gold">{symbol}</span>
              </div>
            </div>
            <form onSubmit={submit} className="flex items-center gap-2">
              <input value={input} onChange={(e) => setInput(e.target.value)} placeholder="Ticker…"
                className="w-28 rounded-lg border border-line bg-panel-2/60 px-3 py-1.5 font-mono text-[13px] uppercase text-ink outline-none placeholder:text-faint focus:border-gold/40" />
              <button type="submit" className="rounded-lg bg-gold px-3 py-1.5 text-[12px] font-semibold text-obsidian">Go</button>
            </form>
          </div>
          <div className="mt-3 flex flex-wrap gap-1.5">
            {quick.map((s) => (
              <button key={s} onClick={() => setSymbol(s)}
                className={cn('rounded-full border px-3 py-1 font-mono text-[11px] transition-colors',
                  symbol === s ? 'border-gold/40 bg-gold/10 text-gold' : 'border-line text-muted hover:text-ink')}>
                {s}
              </button>
            ))}
          </div>
        </div>

        {/* aggregates */}
        {bundle && bundle.signals.length > 0 && (
          <div className="flex flex-wrap gap-2">
            <Chip icon={TrendingUp} tone={bundle.net_insider_usd_30d >= 0 ? 'up' : 'down'}>
              insiders {bundle.net_insider_usd_30d >= 0 ? '+' : '−'}{usd(Math.abs(bundle.net_insider_usd_30d))} / 30d
            </Chip>
            <Chip icon={TrendingUp} tone="muted">{bundle.insider_buys_30d} buys · {bundle.insider_sells_30d} sells (30d)</Chip>
            <Chip icon={Building2} tone="gold">{bundle.funds_holding} tracked fund{bundle.funds_holding !== 1 ? 's' : ''}</Chip>
            <Chip icon={Landmark} tone="muted">{bundle.congress_trades_90d} congress / 90d</Chip>
            {bundle.stale && <Chip icon={RefreshCw} tone="muted">cached</Chip>}
          </div>
        )}

        {/* event study — "does this signal work?" */}
        <StudyCard symbol={symbol} />

        {/* under-crowded edge signals (options / short interest / PEAD / seasonality) */}
        <EdgeCard symbol={symbol} />

        {/* signal list */}
        <div className="rounded-2xl border border-line bg-panel/40 p-4">
          {loading && (
            <div className="grid place-items-center py-12 text-center">
              <div className="font-display italic text-muted">Fetching SEC filings for {symbol}…</div>
              <div className="mt-1 text-[11px] text-faint">First lookup pulls from SEC EDGAR — a few seconds, then it's cached.</div>
            </div>
          )}
          {!loading && bundle && bundle.signals.length === 0 && (
            <div className="grid place-items-center py-12 text-center">
              <ShieldQuestion size={22} className="text-faint" />
              <div className="mt-2 font-display italic text-muted">No recent disclosures cached for {symbol}.</div>
              <div className="mt-1 text-[11px] text-faint">
                No Form 4 / 13F hits in the lookback window{congressUnavailable ? ', and the congress feed is currently unavailable' : ''}. Try a large-cap like AAPL or NVDA.
              </div>
            </div>
          )}
          {!loading && bundle && bundle.signals.length > 0 && (
            <div className="space-y-0">
              {bundle.signals.slice(0, 60).map((s, i) => <SignalRow key={i} s={s} />)}
            </div>
          )}
        </div>

        {/* honesty footer */}
        <p className="px-1 pb-2 text-[11px] leading-relaxed text-faint">
          These are <span className="text-muted">public, lagged disclosures</span> — Form 4 insider trades (~2-day lag),
          13F institutional holdings (~45-day lag, last quarter), and congressional trades (varies). Everyone can see them,
          so they're <span className="text-muted">information, not a guaranteed edge</span>. Use them as context, not as
          buy/sell instructions. {congressUnavailable && 'Congressional data source is currently unavailable (no free public API).'}
        </p>
      </div>
    </div>
  )
}
