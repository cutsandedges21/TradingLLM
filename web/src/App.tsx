import { lazy, Suspense, useCallback, useEffect, useMemo, useState } from 'react'
import { Background } from './components/Background'
import { Sidebar } from './components/Sidebar'
import { Header } from './components/Header'
import { TradeModal } from './components/TradeModal'
import { LearnPanel } from './components/LearnPanel'
import { TerminalPage } from './pages/TerminalPage'
import { WatchlistPage } from './pages/WatchlistPage'
import { SettingsPage } from './pages/SettingsPage'

// Heavy, route-only pages (recharts / lightweight-charts) are code-split so they
// don't bloat the initial bundle — loaded on demand when you open them.
const ChartsPage = lazy(() => import('./pages/ChartsPage').then((m) => ({ default: m.ChartsPage })))
const StudioPage = lazy(() => import('./pages/StudioPage').then((m) => ({ default: m.StudioPage })))
const LibraryPage = lazy(() => import('./pages/LibraryPage').then((m) => ({ default: m.LibraryPage })))
const SmartMoneyPage = lazy(() => import('./pages/SmartMoneyPage').then((m) => ({ default: m.SmartMoneyPage })))
import { useLiveQuotes } from './hooks/useLiveQuotes'
import { api, authHeaders } from './api'
import type { Account, ChatMessage, Position, Proposal, Regime, Status, View, WatchRow } from './types'

const TRADE_RE = /```trade[\s\S]*?```/g

const INTRO: ChatMessage = {
  role: 'assistant',
  ts: Date.now(),
  text:
    "I'm your local trading copilot. I read **live market data**, remember our history, and can place **paper trades** (simulated) after you confirm.\n\n" +
    'Try: *“How does NVDA look today?”*, *“Explain RSI simply”*, or *“Set up a small paper buy of SPY, about $200.”*\n\n' +
    'New here? Tap **Learn** for a from-zero guide, or open **Charts** for live candlesticks.',
}

const TITLES: Record<View, { t: string; s: string }> = {
  terminal: { t: 'Terminal', s: 'live market · paper trading' },
  charts: { t: 'Charts', s: 'live candlesticks · trade from chart' },
  studio: { t: 'Studio', s: 'backtest · factors · coach' },
  smartmoney: { t: 'Smart Money', s: 'regime · insiders · institutions' },
  watchlist: { t: 'Watchlist', s: 'your live symbols' },
  library: { t: 'Library', s: 'learn to trade · cited knowledge' },
  settings: { t: 'Settings', s: 'account & watchlist' },
}

export default function App() {
  const [view, setView] = useState<View>('terminal')
  const [status, setStatus] = useState<Status | null>(null)
  const [marketOpen, setMarketOpen] = useState<boolean | null>(null)
  const [account, setAccount] = useState<Account | null>(null)
  const [positions, setPositions] = useState<Position[]>([])
  const [watch, setWatch] = useState<WatchRow[]>([])
  const [messages, setMessages] = useState<ChatMessage[]>([INTRO])
  const [busy, setBusy] = useState(false)
  const [proposal, setProposal] = useState<Proposal | null>(null)
  const [tradeBusy, setTradeBusy] = useState(false)
  const [learnOpen, setLearnOpen] = useState(false)
  const [chartSymbol, setChartSymbol] = useState<string | null>(null)
  const [librarySkill, setLibrarySkill] = useState<string | null>(null)
  const [debate, setDebate] = useState<{ ticker?: string; stages: Record<string, { label: string; status: string }> } | null>(null)
  const [regime, setRegime] = useState<Regime | null>(null)

  const watchSymbols = useMemo(() => watch.map((r) => r.symbol), [watch])
  // Pause the watchlist live-poll when off the Terminal, freeing the rate budget
  // for the live tick chart on the Charts page.
  const { quotes, flash } = useLiveQuotes(watchSymbols, 4000, view === 'terminal' || view === 'watchlist')
  const liveWatch = useMemo(
    () => watch.map((r) => {
      const q = quotes[r.symbol]
      return q ? { ...r, price: q.price ?? r.price, change_pct: q.change_pct ?? r.change_pct } : r
    }),
    [watch, quotes],
  )

  const refreshAccount = useCallback(async () => {
    try {
      const [a, p] = await Promise.all([api.account(), api.positions()])
      setAccount(a)
      setPositions(p)
    } catch { /* ignore */ }
  }, [])

  const refreshWatch = useCallback(async () => {
    try { setWatch(await api.watchlist()) } catch { /* ignore */ }
  }, [])

  useEffect(() => {
    const loadStatus = () => api.status().then((s) => { setStatus(s); setMarketOpen(s.market_open ?? null) }).catch(() => {})
    const loadRegime = () => api.regime().then((r) => { if (r?.ok) setRegime(r) }).catch(() => {})
    loadStatus()
    loadRegime()
    refreshAccount()
    refreshWatch()
    const id = setInterval(loadStatus, 60000)  // keep market state + countdown fresh
    const rid = setInterval(loadRegime, 300000)  // regime is slow-moving (server caches ~1h)
    return () => { clearInterval(id); clearInterval(rid) }
  }, [refreshAccount, refreshWatch])

  useEffect(() => {
    const id = setInterval(refreshAccount, 5000)
    return () => clearInterval(id)
  }, [refreshAccount])

  useEffect(() => {
    const id = setInterval(refreshWatch, 20000)
    return () => clearInterval(id)
  }, [refreshWatch])

  const push = (m: ChatMessage) => setMessages((cur) => [...cur, m])

  const handleEvent = (ev: any) => {
    if (ev.type === 'start') {
      setDebate({ ticker: ev.ticker, stages: {} })
    } else if (ev.type === 'stage') {
      setDebate((d) => ({ ticker: d?.ticker, stages: { ...(d?.stages || {}), [ev.stage]: { label: ev.label, status: ev.status } } }))
    } else if (ev.type === 'result') {
      const clean = (ev.reply || '').replace(TRADE_RE, '').trim()
      push({ role: 'assistant', text: clean || ev.reply, provider: ev.provider, ts: Date.now(), transcript: ev.transcript, skills: ev.skills })
      if (ev.proposal) setProposal(ev.proposal)
      refreshAccount()
    } else if (ev.type === 'error') {
      push({ role: 'system', text: '⚠️ ' + ev.error, ts: Date.now() })
    }
  }

  const streamChat = async (text: string) => {
    const res = await fetch('/api/chat/stream', {
      method: 'POST', headers: { 'Content-Type': 'application/json', ...authHeaders() },
      body: JSON.stringify({ message: text, deep: true }),
    })
    if (!res.body) throw new Error('streaming not supported')
    const reader = res.body.getReader()
    const dec = new TextDecoder()
    let buf = ''
    for (;;) {
      const { done, value } = await reader.read()
      if (done) break
      buf += dec.decode(value, { stream: true })
      let i: number
      while ((i = buf.indexOf('\n\n')) >= 0) {
        const line = buf.slice(0, i).trim()
        buf = buf.slice(i + 2)
        if (line.startsWith('data:')) {
          try { handleEvent(JSON.parse(line.slice(5).trim())) } catch { /* ignore partial */ }
        }
      }
    }
  }

  const onSend = async (text: string, deep: boolean) => {
    setView('terminal')
    push({ role: 'user', text, ts: Date.now() })
    setBusy(true)
    try {
      if (deep) {
        await streamChat(text)
      } else {
        const res = await api.chat(text, deep)
        const clean = res.reply.replace(TRADE_RE, '').trim()
        push({ role: 'assistant', text: clean || res.reply, provider: res.provider, ts: Date.now(), transcript: res.transcript, skills: res.skills })
        if (res.proposal) setProposal(res.proposal)
        refreshAccount()
      }
    } catch (e) {
      push({ role: 'system', text: '⚠️ ' + (e as Error).message, ts: Date.now() })
    } finally {
      setBusy(false)
      setDebate(null)
    }
  }

  const confirmTrade = async () => {
    if (!proposal) return
    setTradeBusy(true)
    try {
      const res = (await api.trade(proposal)) as Record<string, any>
      if (res.error) {
        push({ role: 'system', text: '❌ ' + res.error, ts: Date.now() })
      } else {
        push({
          role: 'system',
          text: `✅ ${res.status} ${String(res.side).toUpperCase()} ${res.qty} ${res.symbol} @ ${res.filled_avg_price}`,
          ts: Date.now(),
        })
      }
      refreshAccount()
    } catch (e) {
      push({ role: 'system', text: '❌ ' + (e as Error).message, ts: Date.now() })
    } finally {
      setTradeBusy(false)
      setProposal(null)
    }
  }

  const onSettingsChanged = () => { refreshWatch(); refreshAccount() }

  const toggleBrain = async () => {
    const next = status?.brain_mode === 'local' ? 'cloud' : 'local'
    try {
      await api.setBrainMode(next)
      const s = await api.status()
      setStatus(s)
      setMarketOpen(s.market_open ?? null)
    } catch { /* ignore */ }
  }

  const toggleBeginner = async () => {
    try {
      await api.setBeginner(!status?.beginner_mode)
      setStatus(await api.status())
    } catch { /* ignore */ }
  }

  const openSkill = (name: string) => { setLibrarySkill(name); setView('library') }

  const title = TITLES[view]

  return (
    <div className="grain engrave relative flex h-screen w-screen flex-col overflow-hidden md:flex-row">
      <Background />
      <Sidebar view={view} onNav={setView} />

      <div className="flex min-h-0 min-w-0 flex-1 flex-col overflow-hidden">
        <Header title={title.t} subtitle={title.s} status={status} marketOpen={marketOpen}
          regime={regime} onRegime={() => setView('smartmoney')}
          onLearn={() => setLearnOpen(true)} onToggleBrain={toggleBrain} onToggleBeginner={toggleBeginner} />
        <div className="min-h-0 flex-1 overflow-hidden">
          <Suspense fallback={<div className="grid h-full place-items-center font-display italic text-faint">Loading…</div>}>
            {view === 'terminal' && (
              <TerminalPage messages={messages} busy={busy} onSend={onSend} account={account}
                positions={positions} onOpenSkill={openSkill} debate={debate} />
            )}
            {view === 'charts' && (
              <ChartsPage account={account} watchSymbols={watchSymbols} onTraded={refreshAccount} initialSymbol={chartSymbol} />
            )}
            {view === 'watchlist' && (
              <WatchlistPage rows={liveWatch} flash={flash} onPick={(s) => { setChartSymbol(s); setView('charts') }} />
            )}
            {view === 'studio' && <StudioPage onPropose={setProposal} />}
            {view === 'smartmoney' && <SmartMoneyPage watchSymbols={watchSymbols} regime={regime} onPropose={setProposal} />}
            {view === 'library' && <LibraryPage initial={librarySkill} />}
            {view === 'settings' && <SettingsPage account={account} onChanged={onSettingsChanged} />}
          </Suspense>
        </div>
      </div>

      <TradeModal proposal={proposal} busy={tradeBusy} onConfirm={confirmTrade} onCancel={() => setProposal(null)} />
      <LearnPanel open={learnOpen} onClose={() => setLearnOpen(false)} />
    </div>
  )
}
