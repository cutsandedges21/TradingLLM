import { useEffect, useState } from 'react'
import { Check, Plus, RotateCcw, Smartphone, X } from 'lucide-react'
import { api, getApiKey, setApiKey } from '../api'
import { money } from '../lib'
import type { Account, SettingsView } from '../types'

function Section({ title, desc, children }: { title: string; desc?: string; children: React.ReactNode }) {
  return (
    <div className="rounded-2xl border border-line bg-panel p-5">
      <div className="mb-4">
        <div className="font-display text-lg">{title}</div>
        {desc && <div className="text-[12px] leading-relaxed text-faint">{desc}</div>}
      </div>
      {children}
    </div>
  )
}

export function SettingsPage({ account, onChanged }: { account: Account | null; onChanged: () => void }) {
  const [settings, setSettings] = useState<SettingsView | null>(null)
  const [cash, setCash] = useState('100000')
  const [wl, setWl] = useState<string[]>([])
  const [newSym, setNewSym] = useState('')
  const [saved, setSaved] = useState('')
  const [apiKey, setApiKeyState] = useState(getApiKey())
  const isRemote = typeof window !== 'undefined'
    && !['localhost', '127.0.0.1', '::1', ''].includes(window.location.hostname)

  useEffect(() => {
    api.getSettings().then((s) => {
      setSettings(s)
      setCash(String(s.mock_starting_cash))
      setWl(s.watchlist)
    }).catch(() => {})
  }, [])

  const flash = (m: string) => { setSaved(m); setTimeout(() => setSaved(''), 2200) }
  const addSym = () => {
    const s = newSym.trim().toUpperCase()
    if (s && !wl.includes(s)) setWl([...wl, s])
    setNewSym('')
  }
  const saveCash = async () => {
    const n = parseFloat(cash)
    if (!isNaN(n)) { await api.saveSettings({ mock_starting_cash: n }); flash('Starting balance saved') }
  }
  const saveWatchlist = async () => { await api.saveSettings({ watchlist: wl }); flash('Watchlist saved'); onChanged() }
  const resetAccount = async () => {
    const n = parseFloat(cash)
    await api.reset(isNaN(n) ? undefined : n)
    flash('Account reset')
    onChanged()
  }
  const resetLabel = `Reset to ${money(parseFloat(cash) || 0, 0)}`
  const saveKey = () => { setApiKey(apiKey); flash('Access key saved — reconnecting'); setTimeout(() => window.location.reload(), 700) }

  return (
    <div className="h-full overflow-y-auto p-4 md:p-8">
      <div className="mx-auto max-w-3xl space-y-5">
        <div>
          <div className="font-display text-2xl">Settings</div>
          <div className="text-[12px] text-faint">configure your paper account and watchlist</div>
        </div>

        <Section title="Remote access (phone)"
          desc="Reaching this from your phone? The server requires the access key you set in config/settings.json (api_auth_key). Paste it here once — it's stored only in this browser and sent with every request. On the desktop (localhost) you don't need it.">
          <div className="flex flex-wrap items-end gap-3">
            <div className="flex items-center gap-2 text-[12px]">
              <Smartphone size={15} className={isRemote ? 'text-gold' : 'text-faint'} />
              <span className={isRemote ? 'text-gold' : 'text-faint'}>
                {isRemote ? 'remote device' : 'localhost (key optional)'}
              </span>
            </div>
            <div className="flex-1">
              <div className="mb-1 text-[10px] uppercase tracking-wider text-faint">Access key</div>
              <input value={apiKey} onChange={(e) => setApiKeyState(e.target.value)} type="password"
                placeholder="paste api_auth_key" autoComplete="off"
                className="w-full min-w-[200px] rounded-lg border border-line bg-panel-2/50 px-3 py-2 font-mono text-sm text-ink placeholder:text-faint focus:border-line-strong focus:outline-none" />
            </div>
            <button onClick={saveKey}
              className="flex items-center gap-1.5 rounded-lg bg-gold px-3.5 py-2 text-sm font-semibold text-obsidian transition-transform hover:scale-[1.02] active:scale-95">
              <Check size={14} /> Save &amp; reconnect
            </button>
          </div>
        </Section>

        <Section title="Paper account" desc="Set your simulated starting balance. Resetting clears positions and restores cash to this amount.">
          <div className="flex flex-wrap items-end gap-4">
            <div>
              <div className="mb-1 text-[10px] uppercase tracking-wider text-faint">Current equity</div>
              <div className="font-mono text-lg text-ink tnum">{money(account?.equity)}</div>
            </div>
            <div>
              <div className="mb-1 text-[10px] uppercase tracking-wider text-faint">Starting balance ($)</div>
              <input value={cash} onChange={(e) => setCash(e.target.value)} inputMode="decimal"
                className="w-40 rounded-lg border border-line bg-panel-2/50 px-3 py-2 font-mono text-sm text-ink focus:border-line-strong focus:outline-none" />
            </div>
            <button onClick={saveCash}
              className="rounded-lg border border-line px-3.5 py-2 text-sm text-muted transition-colors hover:text-ink">
              Save
            </button>
            <button onClick={resetAccount}
              className="flex items-center gap-1.5 rounded-lg bg-gold px-3.5 py-2 text-sm font-semibold text-obsidian transition-transform hover:scale-[1.02] active:scale-95">
              <RotateCcw size={14} /> {resetLabel}
            </button>
          </div>
        </Section>

        <Section title="Watchlist" desc="Symbols shown on the Terminal and given to the assistant. Use a ticker (AAPL), crypto (BTC/USD), or futures (ES=F).">
          <div className="flex flex-wrap gap-2">
            {wl.map((s) => (
              <span key={s} className="flex items-center gap-1.5 rounded-lg border border-line bg-panel-2/60 px-2.5 py-1.5 font-mono text-[13px]">
                {s}
                <button onClick={() => setWl(wl.filter((x) => x !== s))} className="text-faint transition-colors hover:text-down">
                  <X size={13} />
                </button>
              </span>
            ))}
            {wl.length === 0 && <span className="text-[13px] text-faint">No symbols — add some below.</span>}
          </div>
          <div className="mt-4 flex flex-wrap gap-2">
            <input value={newSym} onChange={(e) => setNewSym(e.target.value)}
              onKeyDown={(e) => { if (e.key === 'Enter') addSym() }} placeholder="Add symbol…"
              className="w-44 rounded-lg border border-line bg-panel-2/50 px-3 py-2 font-mono text-sm text-ink placeholder:text-faint focus:border-line-strong focus:outline-none" />
            <button onClick={addSym}
              className="flex items-center gap-1.5 rounded-lg border border-line px-3 py-2 text-sm text-muted transition-colors hover:text-ink">
              <Plus size={14} /> Add
            </button>
            <button onClick={saveWatchlist}
              className="flex items-center gap-1.5 rounded-lg bg-gold px-3.5 py-2 text-sm font-semibold text-obsidian transition-transform hover:scale-[1.02] active:scale-95">
              <Check size={14} /> Save watchlist
            </button>
          </div>
        </Section>

        <div className="flex items-center justify-between px-1">
          {settings && <div className="text-[11px] text-faint">data sources: {settings.data_source_order.join(' → ')}</div>}
          {saved && <div className="font-mono text-[12px] text-up">✓ {saved}</div>}
        </div>
      </div>
    </div>
  )
}
