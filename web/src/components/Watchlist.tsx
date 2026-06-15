import { useEffect, useState } from 'react'
import { motion } from 'motion/react'
import { ArrowUpRight, ArrowDownRight, Minus } from 'lucide-react'
import { Sparkline } from './Sparkline'
import { api } from '../api'
import { money, pct } from '../lib'
import { cn } from '../lib'
import type { WatchRow } from '../types'

function rsiTone(rsi: number | null) {
  if (rsi == null) return 'text-faint'
  if (rsi >= 70) return 'text-down'
  if (rsi <= 30) return 'text-up'
  return 'text-muted'
}

function TrendIcon({ trend }: { trend: string | null }) {
  if (trend === 'up') return <ArrowUpRight size={14} className="text-up" />
  if (trend === 'down') return <ArrowDownRight size={14} className="text-down" />
  return <Minus size={14} className="text-faint" />
}

export function Watchlist({ rows, onPick, flash }: {
  rows: WatchRow[]
  onPick?: (s: string) => void
  flash?: Record<string, 'up' | 'down'>
}) {
  const [spark, setSpark] = useState<Record<string, number[]>>({})
  const symbolsKey = rows.map((r) => r.symbol).join(',')

  useEffect(() => {
    let cancelled = false
    ;(async () => {
      for (const r of rows) {
        if (spark[r.symbol]) continue
        try {
          const b = await api.bars(r.symbol)
          if (!cancelled) setSpark((s) => ({ ...s, [r.symbol]: b.closes.slice(-40) }))
        } catch {
          /* ignore */
        }
      }
    })()
    return () => {
      cancelled = true
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [symbolsKey])

  return (
    <motion.div
      initial={{ opacity: 0, y: 16 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.55, delay: 0.11, ease: [0.16, 1, 0.3, 1] }}
      className="shrink-0 rounded-2xl border border-line bg-panel p-4"
    >
      <div className="mb-2 flex items-center justify-between px-1">
        <span className="eyebrow">Watchlist</span>
        <span className="font-mono text-[10px] text-faint">RSI · trend</span>
      </div>

      <div className="space-y-0.5">
        {rows.map((r) => {
          const up = (r.change_pct ?? 0) >= 0
          const fl = flash?.[r.symbol]
          return (
            <button
              key={r.symbol}
              onClick={() => onPick?.(r.symbol)}
              className={cn(
                'group flex w-full items-center gap-3 rounded-xl px-2.5 py-2 text-left transition-colors duration-500',
                fl === 'up' ? 'bg-up/10' : fl === 'down' ? 'bg-down/10' : 'hover:bg-panel-2/70',
              )}
            >
              <div className="w-16 shrink-0">
                <div className="font-mono text-[13px] text-ink">{r.symbol}</div>
                <div className="flex items-center gap-1">
                  <TrendIcon trend={r.trend} />
                  <span className={cn('font-mono text-[10px]', rsiTone(r.rsi))}>
                    {r.rsi != null ? r.rsi.toFixed(0) : '—'}
                  </span>
                </div>
              </div>

              <div className="flex-1 opacity-90">
                <Sparkline data={spark[r.symbol] ?? []} up={up} width={120} height={32} />
              </div>

              <div className="w-24 shrink-0 text-right">
                <div className="font-mono text-[13px] text-ink tnum">
                  {r.price != null ? money(r.price) : '—'}
                </div>
                <div className={cn('font-mono text-[11px] tnum', up ? 'text-up' : 'text-down')}>
                  {r.change_pct != null ? pct(r.change_pct) : '—'}
                </div>
              </div>
            </button>
          )
        })}
      </div>
    </motion.div>
  )
}
