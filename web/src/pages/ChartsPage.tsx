import { useEffect, useMemo, useState } from 'react'
import { motion } from 'motion/react'
import { Check, Minus, MousePointer2, Slash, Trash2 } from 'lucide-react'
import { ProChart, type ChartType, type DrawMode, type Legend, type Overlays } from '../components/ProChart'
import { useLiveQuotes } from '../hooks/useLiveQuotes'
import { api } from '../api'
import { money, num, pct } from '../lib'
import { cn } from '../lib'
import type { Account, Candle } from '../types'

const CATEGORIES: Record<string, string[]> = {
  Stocks: ['AAPL', 'NVDA', 'TSLA', 'MSFT', 'AMZN', 'GOOGL', 'META'],
  ETFs: ['SPY', 'QQQ', 'DIA', 'IWM', 'VTI'],
  Crypto: ['BTC-USD', 'ETH-USD', 'SOL-USD', 'DOGE-USD'],
  Futures: ['ES=F', 'NQ=F', 'YM=F', 'CL=F', 'GC=F', 'SI=F'],
  Indices: ['^GSPC', '^IXIC', '^DJI', '^VIX'],
}
const SUBMINUTE: Record<string, number> = { '5s': 5, '30s': 30 }
const TFS = ['5s', '30s', '1m', '5m', '15m', '1H', '1D', '1W']
const TYPES: { id: ChartType; label: string }[] = [
  { id: 'candles', label: 'Candles' }, { id: 'heikin', label: 'HA' }, { id: 'line', label: 'Line' }, { id: 'area', label: 'Area' },
]
const OVERLAY_KEYS: { id: keyof Overlays; label: string; color: string }[] = [
  { id: 'sma20', label: 'MA20', color: '#f2b24c' }, { id: 'sma50', label: 'MA50', color: '#7fb0ff' },
  { id: 'ema20', label: 'EMA20', color: '#d7c4ff' }, { id: 'boll', label: 'BB', color: '#8a8a93' },
]

export function ChartsPage({ account, watchSymbols, onTraded, initialSymbol }: {
  account: Account | null; watchSymbols: string[]; onTraded: () => void; initialSymbol?: string | null
}) {
  const [cat, setCat] = useState('Stocks')
  const [symbol, setSymbol] = useState('AAPL')
  const [tf, setTf] = useState('1D')
  const [chartType, setChartType] = useState<ChartType>('candles')
  const [overlays, setOverlays] = useState<Overlays>({ sma20: true, sma50: false, ema20: false, boll: false })
  const [subs, setSubs] = useState({ rsi: false, macd: false })
  const [drawMode, setDrawMode] = useState<DrawMode>('none')
  const [clearKey, setClearKey] = useState(0)
  const [candles, setCandles] = useState<Candle[]>([])
  const [liveCandles, setLiveCandles] = useState<Candle[]>([])
  const [source, setSource] = useState('')
  const [useLiveBuild, setUseLiveBuild] = useState(false)
  const [custom, setCustom] = useState('')
  const [loading, setLoading] = useState(false)
  const [legend, setLegend] = useState<Legend>(null)

  // compact trade ticket
  const [tSide, setTSide] = useState<'buy' | 'sell'>('buy')
  const [tQty, setTQty] = useState('1')
  const [tBusy, setTBusy] = useState(false)
  const [tMsg, setTMsg] = useState<{ ok: boolean; text: string } | null>(null)

  const isSub = tf in SUBMINUTE
  const cryptoSym = cat === 'Crypto' || /[-/]USD$/i.test(symbol)
  const visibleTFs = cryptoSym ? TFS : TFS.filter((t) => !(t in SUBMINUTE))
  const railSyms = useMemo(() => Array.from(new Set([symbol, ...watchSymbols])), [symbol, watchSymbols])

  useEffect(() => { if (initialSymbol) setSymbol(initialSymbol) }, [initialSymbol])

  useEffect(() => { if (!cryptoSym && tf in SUBMINUTE) setTf('1D') }, [cryptoSym, tf])

  useEffect(() => {
    let stop = false
    const load = async () => {
      setLoading(true)
      try {
        const r = await api.candles(symbol, tf)
        if (stop) return
        if (r.candles.length) { setCandles(r.candles); setSource(r.source || 'yfinance'); setUseLiveBuild(false) }
        else { setCandles([]); setSource(r.source || ''); setUseLiveBuild(tf in SUBMINUTE) }
      } catch { if (!stop) { setCandles([]); setUseLiveBuild(tf in SUBMINUTE) } } finally { if (!stop) setLoading(false) }
    }
    load()
    const id = setInterval(load, isSub ? 7000 : 20000)
    return () => { stop = true; clearInterval(id) }
  }, [symbol, tf, isSub])

  useEffect(() => {
    if (!useLiveBuild) return
    const interval = SUBMINUTE[tf]; const buf: Candle[] = []; setLiveCandles([]); let stop = false
    const tick = async () => {
      try {
        const r = await api.tick(symbol); if (r.price == null) return
        const bucket = Math.floor(Date.now() / 1000 / interval) * interval
        const last = buf[buf.length - 1]
        if (!last || (last.time as number) !== bucket) { buf.push({ time: bucket, open: r.price, high: r.price, low: r.price, close: r.price, volume: 0 }); if (buf.length > 400) buf.shift() }
        else { last.high = Math.max(last.high, r.price); last.low = Math.min(last.low, r.price); last.close = r.price }
        if (!stop) setLiveCandles([...buf])
      } catch { /* ignore */ }
    }
    tick(); const id = setInterval(tick, 1200)
    return () => { stop = true; clearInterval(id) }
  }, [symbol, tf, useLiveBuild])

  const { quotes } = useLiveQuotes(railSyms, 3500, !useLiveBuild)

  const data = useLiveBuild ? liveCandles : candles
  const live = useLiveBuild
    ? (liveCandles.length ? liveCandles[liveCandles.length - 1].close : null)
    : (quotes[symbol]?.price ?? (candles.length ? candles[candles.length - 1].close : null))
  const chg = useLiveBuild ? null : (quotes[symbol]?.change_pct ?? null)
  const up = (chg ?? 0) >= 0
  const last = data.length ? data[data.length - 1] : null
  const leg = legend ?? (last ? { o: last.open, h: last.high, l: last.low, c: last.close, v: last.volume } : null)
  const estCost = live ? parseFloat(tQty || '0') * live : null

  const pickCat = (c: string) => { setCat(c); setSymbol(CATEGORIES[c][0]) }
  const submitCustom = () => { const s = custom.trim().toUpperCase(); if (s) { setSymbol(s); setCustom('') } }
  const toggleOverlay = (k: keyof Overlays) => setOverlays((o) => ({ ...o, [k]: !o[k] }))

  const placeTrade = async () => {
    setTBusy(true); setTMsg(null)
    try {
      const res = (await api.trade({ action: tSide, symbol, order_type: 'market', qty: parseFloat(tQty), rationale: 'chart trade' } as never)) as Record<string, any>
      if (res.error) setTMsg({ ok: false, text: res.error })
      else setTMsg({ ok: true, text: `${res.status} ${String(res.side).toUpperCase()} ${res.qty} ${res.symbol}` })
      onTraded()
    } catch (e) { setTMsg({ ok: false, text: (e as Error).message }) } finally { setTBusy(false) }
  }

  return (
    <div className="flex h-full flex-col gap-3 overflow-y-auto p-4 lg:overflow-hidden">
      {/* header */}
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div className="flex items-end gap-5">
          <div>
            <div className="font-display text-3xl tracking-tight">{symbol}</div>
            <div className="text-[11px] text-faint">{cat} · {useLiveBuild ? 'live tick · no history' : source || 'yfinance'}</div>
          </div>
          <div className="pb-1">
            <div className={cn('font-mono text-2xl tnum', up ? 'text-up' : 'text-down')}>{live != null ? money(live) : '—'}</div>
            <div className={cn('font-mono text-xs tnum', useLiveBuild ? 'text-gold' : up ? 'text-up' : 'text-down')}>
              {useLiveBuild ? `⚡ live · ${tf}` : chg != null ? `${pct(chg)} today` : '—'}
            </div>
          </div>
        </div>
        <div className="flex flex-wrap gap-1 rounded-xl border border-line bg-panel p-1">
          {visibleTFs.map((t) => {
            const sub = t in SUBMINUTE
            return <button key={t} onClick={() => setTf(t)}
              className={cn('rounded-lg px-2.5 py-1.5 font-mono text-xs transition-colors', tf === t ? 'bg-gold text-obsidian' : sub ? 'text-gold/80 hover:text-gold' : 'text-faint hover:text-ink')}>{sub ? '⚡' : ''}{t}</button>
          })}
        </div>
      </div>

      {/* toolbar */}
      <div className="flex flex-wrap items-center gap-2">
        <div className="flex gap-1 rounded-lg border border-line bg-panel p-1">
          {TYPES.map((t) => <button key={t.id} onClick={() => setChartType(t.id)}
            className={cn('rounded-md px-2.5 py-1 text-xs transition-colors', chartType === t.id ? 'bg-panel-2 text-ink ring-1 ring-line-strong' : 'text-faint hover:text-ink')}>{t.label}</button>)}
        </div>
        <div className="flex flex-wrap gap-1.5">
          {OVERLAY_KEYS.map((o) => <button key={o.id} onClick={() => toggleOverlay(o.id)}
            className={cn('flex items-center gap-1.5 rounded-md border px-2 py-1 text-[11px] transition-colors', overlays[o.id] ? 'border-line-strong text-ink' : 'border-line text-faint hover:text-muted')}>
            <span className="h-2 w-2 rounded-full" style={{ background: overlays[o.id] ? o.color : 'transparent', boxShadow: `inset 0 0 0 1px ${o.color}` }} />{o.label}</button>)}
        </div>
        <span className="hidden h-4 w-px bg-line sm:block" />
        <div className="flex gap-1.5">
          {(['rsi', 'macd'] as const).map((k) => <button key={k} onClick={() => setSubs((s) => ({ ...s, [k]: !s[k] }))}
            className={cn('rounded-md border px-2 py-1 text-[11px] uppercase transition-colors', subs[k] ? 'border-gold/40 bg-gold/10 text-gold' : 'border-line text-faint hover:text-muted')}>{k}</button>)}
        </div>
        <span className="hidden h-4 w-px bg-line sm:block" />
        <div className="flex gap-1">
          {([['none', MousePointer2], ['hline', Minus], ['trend', Slash]] as const).map(([m, Icon]) => (
            <button key={m} onClick={() => setDrawMode(m)} title={m === 'none' ? 'cursor' : m === 'hline' ? 'horizontal line' : 'trendline'}
              className={cn('grid h-7 w-7 place-items-center rounded-md border transition-colors',
                drawMode === m ? 'border-gold/40 bg-gold/10 text-gold' : 'border-line text-faint hover:text-ink')}>
              <Icon size={14} />
            </button>
          ))}
          <button onClick={() => setClearKey((k) => k + 1)} title="clear drawings"
            className="grid h-7 w-7 place-items-center rounded-md border border-line text-faint transition-colors hover:text-down">
            <Trash2 size={14} />
          </button>
        </div>
        <span className="hidden h-4 w-px bg-line md:block" />
        {Object.keys(CATEGORIES).map((c) => <button key={c} onClick={() => pickCat(c)}
          className={cn('rounded-md px-2 py-1 text-[11px] font-medium transition-colors', cat === c ? 'bg-panel-2 text-ink ring-1 ring-line-strong' : 'text-faint hover:text-muted')}>{c}</button>)}
        <input value={custom} onChange={(e) => setCustom(e.target.value)} onKeyDown={(e) => { if (e.key === 'Enter') submitCustom() }}
          placeholder="symbol…" className="w-24 rounded-md border border-line bg-panel-2/50 px-2 py-1 font-mono text-[11px] text-ink placeholder:text-faint focus:border-line-strong focus:outline-none" />
      </div>

      {/* chart-first row: rail | chart | trade ticket */}
      <div className="flex min-h-[56vh] flex-1 gap-3 lg:min-h-0">
        {/* watchlist rail */}
        <div className="hidden w-40 shrink-0 flex-col overflow-y-auto rounded-2xl border border-line bg-panel p-2 lg:flex">
          <div className="px-1 pb-1.5 text-[10px] uppercase tracking-wider text-faint">Watchlist</div>
          {railSyms.map((s) => {
            const q = quotes[s]; const u = (q?.change_pct ?? 0) >= 0
            return <button key={s} onClick={() => setSymbol(s)}
              className={cn('flex items-center justify-between gap-2 rounded-lg px-2 py-1.5 text-left transition-colors', symbol === s ? 'bg-gold/10 ring-1 ring-gold/20' : 'hover:bg-panel-2/60')}>
              <span className={cn('font-mono text-[12px]', symbol === s ? 'text-gold' : 'text-ink')}>{s}</span>
              <span className={cn('font-mono text-[10px] tnum', u ? 'text-up' : 'text-down')}>{q?.change_pct != null ? pct(q.change_pct) : '—'}</span>
            </button>
          })}
        </div>

        {/* chart */}
        <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.4 }}
          className="relative min-h-0 flex-1 rounded-2xl border border-line bg-panel p-3">
          {leg && (
            <div className="pointer-events-none absolute left-5 top-4 z-10 flex flex-wrap gap-3 font-mono text-[11px]">
              {(['o', 'h', 'l', 'c'] as const).map((k) => <span key={k}><span className="text-faint">{k.toUpperCase()}</span> <span className={leg.c >= leg.o ? 'text-up' : 'text-down'}>{num(leg[k])}</span></span>)}
              <span><span className="text-faint">V</span> <span className="text-muted">{num(leg.v, 0)}</span></span>
            </div>
          )}
          {!useLiveBuild && loading && <div className="absolute right-5 top-4 z-10 font-mono text-[11px] text-faint">loading…</div>}
          {data.length > 0 ? (
            <ProChart candles={data} livePrice={useLiveBuild ? null : live} secondsVisible={isSub}
              fitKey={`${symbol}-${tf}-${chartType}`} chartType={chartType} overlays={overlays} rsi={subs.rsi} macd={subs.macd}
              drawMode={drawMode} clearKey={clearKey} onLegend={setLegend} />
          ) : (
            <div className="grid h-full place-items-center text-center text-faint">
              {useLiveBuild ? <div><div className="font-mono text-sm text-gold">⚡ building {tf} candles live…</div><div className="mt-1 text-[12px]">No free history at this resolution for {symbol}.</div></div>
                : loading ? 'Loading…' : `No data for ${symbol}.`}
            </div>
          )}
        </motion.div>

        {/* trade ticket */}
        <div className="hidden w-56 shrink-0 flex-col gap-2.5 rounded-2xl border border-line bg-panel p-3 lg:flex">
          <div className="text-[10px] uppercase tracking-wider text-faint">Trade {symbol}</div>
          <div className="font-mono text-lg text-ink tnum">{live != null ? money(live) : '—'}</div>
          <div className="flex gap-2 rounded-lg border border-line bg-panel-2/40 p-1">
            <button onClick={() => setTSide('buy')} className={cn('flex-1 rounded-md py-1.5 text-xs font-semibold transition-colors', tSide === 'buy' ? 'bg-up text-obsidian' : 'text-faint hover:text-ink')}>BUY</button>
            <button onClick={() => setTSide('sell')} className={cn('flex-1 rounded-md py-1.5 text-xs font-semibold transition-colors', tSide === 'sell' ? 'bg-down text-obsidian' : 'text-faint hover:text-ink')}>SELL</button>
          </div>
          <div>
            <div className="mb-1 text-[10px] uppercase tracking-wider text-faint">Quantity</div>
            <input value={tQty} onChange={(e) => setTQty(e.target.value)} inputMode="decimal"
              className="w-full rounded-lg border border-line bg-panel-2/50 px-2.5 py-1.5 font-mono text-sm text-ink focus:border-line-strong focus:outline-none" />
          </div>
          <div className="flex justify-between text-[11px]"><span className="text-faint">Est. {tSide === 'buy' ? 'cost' : 'proceeds'}</span><span className="font-mono text-gold tnum">{estCost != null ? money(estCost) : '—'}</span></div>
          <div className="flex justify-between text-[11px]"><span className="text-faint">Buying power</span><span className="font-mono text-muted tnum">{money(account?.buying_power)}</span></div>
          <button onClick={placeTrade} disabled={tBusy}
            className={cn('flex items-center justify-center gap-1.5 rounded-lg py-2 text-sm font-bold text-obsidian transition-transform hover:scale-[1.02] active:scale-95 disabled:opacity-60', tSide === 'buy' ? 'bg-up' : 'bg-down')}>
            {tBusy ? '…' : <><Check size={14} /> {tSide === 'buy' ? 'Buy' : 'Sell'}</>}
          </button>
          {tMsg && <div className={cn('rounded-md border px-2 py-1.5 text-[11px]', tMsg.ok ? 'border-up/30 bg-up/10 text-up' : 'border-down/30 bg-down/10 text-down')}>{tMsg.ok ? '✓ ' : '✕ '}{tMsg.text}</div>}
          <div className="mt-auto text-[10px] text-faint">Simulated — fills at live price.</div>
        </div>
      </div>
    </div>
  )
}
