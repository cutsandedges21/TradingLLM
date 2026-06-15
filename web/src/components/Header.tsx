import { useEffect, useState } from 'react'
import { BookOpen, Cloud, Cpu, GraduationCap } from 'lucide-react'
import { cn } from '../lib'
import type { Regime, Status } from '../types'

const REGIME_LABEL: Record<string, string> = {
  risk_on: 'RISK-ON', neutral: 'NEUTRAL', risk_off: 'RISK-OFF',
}

function RegimeChip({ regime, onClick }: { regime: Regime; onClick: () => void }) {
  const tone = regime.label === 'risk_on' ? 'up' : regime.label === 'risk_off' ? 'down' : 'gold'
  const dot = tone === 'up' ? 'bg-up' : tone === 'down' ? 'bg-down' : 'bg-gold'
  const txt = tone === 'up' ? 'text-up' : tone === 'down' ? 'text-down' : 'text-gold'
  return (
    <button onClick={onClick} title={regime.summary || 'Market regime'}
      className="flex items-center gap-1.5 border-l border-line pl-3">
      <span className={cn('h-1.5 w-1.5 rounded-full', dot)} />
      <span className="eyebrow hidden sm:inline">regime</span>
      <span className={cn('font-mono text-[11px]', txt)}>{REGIME_LABEL[regime.label] ?? '…'}</span>
    </button>
  )
}

function Pill({ label, value, tone = 'muted', live = false }: {
  label: string; value: string; tone?: 'up' | 'gold' | 'muted'; live?: boolean
}) {
  const dot = tone === 'up' ? 'bg-up' : tone === 'gold' ? 'bg-gold' : 'bg-faint'
  return (
    <div className="flex items-center gap-2 border-l border-line pl-3">
      <span className={cn('h-1.5 w-1.5 rounded-full', dot, live && 'live-dot')} />
      <span className="eyebrow hidden sm:inline">{label}</span>
      <span className="font-mono text-[11px] text-ink/90">{value}</span>
    </div>
  )
}

export function Header({ title, subtitle, status, marketOpen, regime, onRegime, onLearn, onToggleBrain, onToggleBeginner }: {
  title: string
  subtitle?: string
  status: Status | null
  marketOpen: boolean | null
  regime?: Regime | null
  onRegime?: () => void
  onLearn: () => void
  onToggleBrain: () => void
  onToggleBeginner: () => void
}) {
  const beginner = !!status?.beginner_mode
  const brains = status
    ? Object.entries(status.providers).filter(([, v]) => v === true).map(([k]) => k)
    : []

  const [now, setNow] = useState(Date.now())
  useEffect(() => {
    const id = setInterval(() => setNow(Date.now()), 30000)
    return () => clearInterval(id)
  }, [])
  const countdown = (() => {
    const ts = status?.next_open_ts
    if (!ts || marketOpen) return null
    const diff = ts * 1000 - now
    if (diff <= 0) return null
    const mins = Math.floor(diff / 60000)
    const h = Math.floor(mins / 60)
    const m = mins % 60
    return h > 0 ? `in ${h}h ${m}m` : `in ${m}m`
  })()

  return (
    <header className="flex flex-wrap items-center justify-between gap-3 border-b border-line bg-panel/40 px-4 py-3 backdrop-blur-sm md:px-7">
      {/* masthead */}
      <div className="flex items-baseline gap-3">
        <div className="leading-none">
          <div className="font-display text-[1.45rem] font-semibold tracking-[-0.02em] text-ink">
            Atlas<span className="text-gold">.</span>
          </div>
        </div>
        <div className="hidden h-7 w-px bg-line-strong sm:block" />
        <div className="hidden leading-tight sm:block">
          <div className="eyebrow">{title}</div>
          <div className="-mt-0.5 font-display text-[13px] italic text-muted">{subtitle}</div>
        </div>
      </div>

      <div className="flex flex-wrap items-center gap-x-3 gap-y-2">
        <div className="flex items-center gap-2">
          <span className={cn('h-1.5 w-1.5 rounded-full', marketOpen ? 'bg-up live-dot' : 'bg-faint')} />
          <span className="eyebrow hidden sm:inline">market</span>
          <span className="font-mono text-[11px] text-ink/90">{marketOpen == null ? '—' : marketOpen ? 'OPEN' : 'CLOSED'}</span>
          {marketOpen === false && status?.next_open && (
            <span className="font-mono text-[10px] text-faint">
              · {status.next_open.replace('opens ', '')}{countdown ? ` · ${countdown}` : ''}
            </span>
          )}
        </div>
        {regime?.ok && <RegimeChip regime={regime} onClick={onRegime ?? (() => {})} />}
        <Pill label="brain" value={brains[0] ?? '…'} tone="gold" />
        <Pill label="data" value={status ? status.data_sources.slice(0, 2).join(' · ') : '…'} />
        {status?.brain_mode && (
          <button onClick={onToggleBrain} title="Toggle cloud (fast) / local (private) brain"
            className={cn('ml-1 flex items-center gap-1.5 rounded-full border px-3 py-1.5 text-[11px] transition-colors',
              status.brain_mode === 'local' ? 'border-gold/40 bg-gold/10 text-gold' : 'border-line text-muted hover:text-ink')}>
            {status.brain_mode === 'local' ? <Cpu size={13} /> : <Cloud size={13} />}
            {status.brain_mode === 'local' ? 'Local' : 'Cloud'}
          </button>
        )}
        <button onClick={onToggleBeginner} title="Beginner mode — the copilot explains everything and defines every term"
          className={cn('flex items-center gap-1.5 rounded-full border px-3 py-1.5 text-[11px] transition-colors',
            beginner ? 'border-gold/40 bg-gold/10 text-gold' : 'border-line text-muted hover:text-ink')}>
          <GraduationCap size={13} /> Beginner
        </button>
        <button onClick={onLearn}
          className="flex items-center gap-1.5 rounded-full bg-gold px-4 py-1.5 text-[12px] font-semibold text-obsidian transition-transform hover:scale-[1.03] active:scale-95">
          <BookOpen size={14} /> Learn
        </button>
      </div>
    </header>
  )
}
