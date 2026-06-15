import { motion } from 'motion/react'
import { money, num, pct } from '../lib'
import { cn } from '../lib'
import type { Position } from '../types'

export function Positions({ positions }: { positions: Position[] }) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 16 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.55, delay: 0.18, ease: [0.16, 1, 0.3, 1] }}
      className="flex min-h-[240px] flex-1 flex-col rounded-2xl border border-line bg-panel p-4 lg:min-h-0"
    >
      <div className="mb-3 flex shrink-0 items-center justify-between px-1">
        <span className="eyebrow">Open Positions</span>
        <span className="font-mono text-[11px] text-faint">{positions.length}</span>
      </div>

      <div className="-mr-1 min-h-0 flex-1 overflow-y-auto pr-1">
        {positions.length === 0 ? (
          <div className="px-1 py-8 text-center">
            <div className="font-display text-[15px] italic text-muted">No open positions yet.</div>
            <div className="mt-1.5 text-[12px] text-faint">Ask the copilot for a setup — or run a deep analysis.</div>
          </div>
        ) : (
          <div className="space-y-px">
            {positions.map((p) => {
              const up = p.unrealized_pl >= 0
              return (
                <div key={p.symbol}
                  className="flex items-center justify-between rounded-lg px-2.5 py-2 transition-colors hover:bg-panel-2/60">
                  <div>
                    <div className="flex items-center gap-1.5">
                      <span className="font-mono text-[13px] text-ink">{p.symbol}</span>
                      <span className={cn('rounded px-1 py-0.5 font-mono text-[9px] font-semibold',
                        p.side === 'short' ? 'bg-down/15 text-down' : 'bg-up/15 text-up')}>
                        {(p.side ?? 'long').toUpperCase()}
                      </span>
                    </div>
                    <div className="font-mono text-[11px] text-faint tnum">
                      {num(Math.abs(p.qty), Math.abs(p.qty) < 1 ? 4 : 0)} @ {money(p.avg_entry)}
                    </div>
                  </div>
                  <div className="text-right">
                    <div className="font-mono text-[13px] text-ink tnum">{money(p.market_value)}</div>
                    <div className={cn('font-mono text-[11px] tnum', up ? 'text-up' : 'text-down')}>
                      {up ? '+' : ''}{money(p.unrealized_pl)} ({pct(p.unrealized_plpc)})
                    </div>
                  </div>
                </div>
              )
            })}
          </div>
        )}
      </div>
    </motion.div>
  )
}
