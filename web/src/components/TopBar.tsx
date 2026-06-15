import { motion } from 'motion/react'
import { BookOpen, RotateCcw } from 'lucide-react'
import type { Status } from '../types'
import { cn } from '../lib'

function Pill({ label, value, tone = 'muted', live = false }: {
  label: string; value: string; tone?: 'up' | 'gold' | 'muted'; live?: boolean
}) {
  const dot = tone === 'up' ? 'bg-up' : tone === 'gold' ? 'bg-gold' : 'bg-faint'
  return (
    <div className="flex items-center gap-2 rounded-lg border border-line bg-panel/60 px-3 py-1.5">
      <span className={cn('h-1.5 w-1.5 rounded-full', dot, live && 'live-dot')} />
      <span className="text-[10px] uppercase tracking-wider text-faint">{label}</span>
      <span className="font-mono text-[11px] text-ink/90">{value}</span>
    </div>
  )
}

export function TopBar({ status, marketOpen, onLearn, onReset }: {
  status: Status | null
  marketOpen: boolean | null
  onLearn: () => void
  onReset: () => void
}) {
  const brains = status
    ? Object.entries(status.providers).filter(([, v]) => v === true).map(([k]) => k)
    : []

  return (
    <motion.header
      initial={{ opacity: 0, y: -14 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.5, ease: [0.16, 1, 0.3, 1] }}
      className="flex flex-wrap items-center justify-between gap-4 border-b border-line px-6 py-3.5"
    >
      <div className="flex items-center gap-3">
        <div className="grid h-9 w-9 place-items-center rounded-xl bg-gold/10 ring-1 ring-gold/30">
          <span className="font-display text-lg leading-none text-gold">T</span>
        </div>
        <div className="leading-tight">
          <div className="font-display text-[1.05rem] tracking-tight">
            TRADING<span className="text-gold">//</span>LLM
          </div>
          <div className="-mt-0.5 text-[11px] text-faint">local market terminal · paper</div>
        </div>
      </div>

      <div className="flex flex-wrap items-center gap-2">
        <Pill label="market" value={marketOpen == null ? '—' : marketOpen ? 'OPEN' : 'CLOSED'}
              tone={marketOpen ? 'up' : 'muted'} live={!!marketOpen} />
        <Pill label="brain" value={brains[0] ?? '…'} tone="gold" />
        <Pill label="data" value={status ? status.data_sources.slice(0, 2).join(' · ') : '…'} />
        <button onClick={onReset}
          className="flex items-center gap-1.5 rounded-lg border border-line px-3 py-2 text-[12px] text-muted transition-colors hover:border-line-strong hover:text-ink">
          <RotateCcw size={13} /> reset
        </button>
        <button onClick={onLearn}
          className="flex items-center gap-1.5 rounded-lg bg-gold px-3.5 py-2 text-[12px] font-semibold text-obsidian transition-transform hover:scale-[1.03] active:scale-95">
          <BookOpen size={14} /> Learn
        </button>
      </div>
    </motion.header>
  )
}
