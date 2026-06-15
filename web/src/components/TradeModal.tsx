import { useEffect, useState } from 'react'
import { motion, AnimatePresence } from 'motion/react'
import { AlertTriangle, Check, CircleCheck, X } from 'lucide-react'
import { api } from '../api'
import { money } from '../lib'
import { cn } from '../lib'
import type { Proposal, RiskCheck } from '../types'

function Row({ label, value, accent }: { label: string; value: string; accent?: boolean }) {
  return (
    <div className="flex items-center justify-between gap-4">
      <span className="text-[12px] text-faint">{label}</span>
      <span className={cn('text-right font-mono text-[13px]', accent ? 'text-gold' : 'text-ink')}>{value}</span>
    </div>
  )
}

function RiskPanel({ check }: { check: RiskCheck | null }) {
  if (!check) return null
  const tone = check.verdict === 'fail' ? 'down' : check.verdict === 'warn' ? 'gold' : 'up'
  const txt = tone === 'down' ? 'text-down' : tone === 'gold' ? 'text-gold' : 'text-up'
  const border = tone === 'down' ? 'border-down/40' : tone === 'gold' ? 'border-gold/40' : 'border-up/30'
  const Icon = check.verdict === 'pass' ? CircleCheck : AlertTriangle
  const dot = (s: string) => s === 'fail' ? 'text-down' : s === 'warn' ? 'text-gold' : 'text-up'
  const glyph = (s: string) => s === 'fail' ? '✗' : s === 'warn' ? '!' : '✓'
  return (
    <div className={cn('mt-4 rounded-lg border bg-panel-2/40 px-3 py-2.5', border)}>
      <div className={cn('flex items-center gap-1.5 text-[12px] font-semibold', txt)}>
        <Icon size={13} /> {check.headline}
      </div>
      <div className="mt-2 space-y-1">
        {check.checks.map((c) => (
          <div key={c.name} className="flex items-start gap-2 text-[11px]">
            <span className={cn('mt-px font-mono font-bold', dot(c.status))}>{glyph(c.status)}</span>
            <span className="text-faint"><span className="text-muted">{c.name}:</span> {c.detail}</span>
          </div>
        ))}
      </div>
    </div>
  )
}

export function TradeModal({ proposal, busy, onConfirm, onCancel }: {
  proposal: Proposal | null
  busy: boolean
  onConfirm: () => void
  onCancel: () => void
}) {
  const buy = proposal?.action === 'buy'
  const size =
    proposal?.qty != null ? `${proposal.qty} unit(s)`
    : proposal?.notional != null ? `${money(proposal.notional)} notional`
    : '—'

  // Pre-trade risk check — runs the proposal through the survival rules before you confirm.
  const [check, setCheck] = useState<RiskCheck | null>(null)
  useEffect(() => {
    setCheck(null)
    if (!proposal) return
    let live = true
    api.riskCheck(proposal).then((r) => { if (live) setCheck(r) }).catch(() => {})
    return () => { live = false }
  }, [proposal])

  return (
    <AnimatePresence>
      {proposal && (
        <motion.div
          className="fixed inset-0 z-40 grid place-items-center p-4"
          initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
        >
          <div className="absolute inset-0 bg-obsidian/70 backdrop-blur-sm" onClick={busy ? undefined : onCancel} />
          <motion.div
            initial={{ scale: 0.94, y: 16, opacity: 0 }}
            animate={{ scale: 1, y: 0, opacity: 1 }}
            exit={{ scale: 0.96, opacity: 0 }}
            transition={{ duration: 0.32, ease: [0.16, 1, 0.3, 1] }}
            className="relative w-full max-w-md overflow-hidden rounded-2xl border border-line-strong bg-panel p-6 shadow-2xl"
          >
            <div className={cn('absolute inset-x-0 top-0 h-1 opacity-80', buy ? 'bg-up' : 'bg-down')} />
            <div className="flex items-start justify-between">
              <div>
                <div className="text-[11px] uppercase tracking-[0.2em] text-faint">Confirm paper trade</div>
                <div className="mt-1.5 flex items-center gap-2">
                  <span className={cn('rounded-md px-2 py-0.5 font-display text-sm', buy ? 'bg-up/15 text-up' : 'bg-down/15 text-down')}>
                    {proposal.action.toUpperCase()}
                  </span>
                  <span className="font-display text-2xl tracking-tight">{proposal.symbol}</span>
                </div>
              </div>
              <button onClick={onCancel} aria-label="Close" className="text-faint transition-colors hover:text-ink">
                <X size={18} />
              </button>
            </div>

            <div className="mt-5 space-y-2.5">
              <Row label="Size" value={size} />
              {proposal.est_cost != null && <Row label="Est. cost" value={money(proposal.est_cost)} accent />}
              <Row
                label="Order type"
                value={proposal.order_type + (proposal.limit_price ? ` @ ${money(proposal.limit_price)}` : '')}
              />
              {proposal.rationale && <Row label="Reason" value={proposal.rationale} />}
            </div>

            <RiskPanel check={check} />

            <div className="mt-4 rounded-lg border border-line bg-panel-2/60 px-3 py-2 text-[11px] leading-relaxed text-muted">
              Simulated money — this records a paper position on your laptop. Nothing real is bought.
            </div>

            <div className="mt-5 flex gap-3">
              <button
                onClick={onCancel}
                disabled={busy}
                className="flex-1 rounded-xl border border-line py-2.5 text-sm text-muted transition-colors hover:text-ink disabled:opacity-50"
              >
                Cancel
              </button>
              <button
                onClick={onConfirm}
                disabled={busy}
                className={cn(
                  'flex flex-1 items-center justify-center gap-2 rounded-xl py-2.5 text-sm font-semibold text-obsidian transition-transform hover:scale-[1.02] active:scale-95 disabled:opacity-60',
                  buy ? 'bg-up' : 'bg-down',
                )}
              >
                {busy ? 'Placing…' : (<><Check size={16} /> Confirm {proposal.action}</>)}
              </button>
            </div>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  )
}
