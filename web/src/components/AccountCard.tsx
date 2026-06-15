import { motion } from 'motion/react'
import { TrendingUp, TrendingDown } from 'lucide-react'
import { AnimatedNumber } from './AnimatedNumber'
import { money, pct } from '../lib'
import { cn } from '../lib'
import type { Account } from '../types'

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <div className="eyebrow">{label}</div>
      <div className="mt-1 font-mono text-[13px] text-ink tnum">{value}</div>
    </div>
  )
}

export function AccountCard({ account }: { account: Account | null }) {
  const eq = account?.equity ?? 0
  const dpl = account?.day_pl ?? 0
  const up = dpl >= 0

  return (
    <motion.div
      initial={{ opacity: 0, y: 16 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.55, delay: 0.05, ease: [0.16, 1, 0.3, 1] }}
      className="relative shrink-0 overflow-hidden rounded-2xl border border-line bg-panel p-5"
    >
      <div
        className="absolute -right-12 -top-12 h-32 w-32 rounded-full"
        style={{ background: 'radial-gradient(circle, rgba(79,224,205,0.12), transparent 70%)' }}
      />
      <div className="flex items-center justify-between">
        <span className="eyebrow">Paper Equity</span>
        <span className="rounded-full bg-gold/10 px-2 py-0.5 font-mono text-[10px] text-gold ring-1 ring-gold/20">
          {account?.status ?? 'MOCK'}
        </span>
      </div>

      <div className="mt-2 font-display text-[2.8rem] font-semibold leading-none tracking-[-0.02em] tnum">
        <AnimatedNumber value={eq} format={(n) => money(n)} />
      </div>

      <div className={cn('mt-2.5 flex items-center gap-2 font-mono text-[13px] tnum', up ? 'text-up' : 'text-down')}>
        {up ? <TrendingUp size={15} /> : <TrendingDown size={15} />}
        <span>{money(Math.abs(dpl))}</span>
        <span className="opacity-70">({pct(account?.day_pl_pct)})</span>
        <span className="text-faint">today</span>
      </div>

      <div className="my-4 rule" />

      <div className="grid grid-cols-2 gap-4">
        <Stat label="Cash" value={money(account?.cash)} />
        <Stat label="Buying Power" value={money(account?.buying_power)} />
      </div>
    </motion.div>
  )
}
