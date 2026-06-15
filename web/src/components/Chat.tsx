import { useEffect, useRef, useState } from 'react'
import { motion } from 'motion/react'
import { ArrowUp, FlaskConical, ChevronRight, BookOpen, Check, Loader2 } from 'lucide-react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { cn } from '../lib'
import type { ChatMessage, DebateTranscript } from '../types'

const RATING_TONE: Record<string, string> = {
  Buy: 'text-up bg-up/12 ring-up/30',
  Overweight: 'text-up bg-up/12 ring-up/30',
  Hold: 'text-gold bg-gold/12 ring-gold/30',
  Underweight: 'text-down bg-down/12 ring-down/30',
  Sell: 'text-down bg-down/12 ring-down/30',
}

function Md({ children, report }: { children: string; report?: boolean }) {
  return (
    <div className={cn('prose-terminal', report && 'prose-report')}>
      <ReactMarkdown remarkPlugins={[remarkGfm]}>{children}</ReactMarkdown>
    </div>
  )
}

function Section({ title, body, open = false }: { title: string; body: string; open?: boolean }) {
  if (!body?.trim()) return null
  return (
    <details open={open} className="group border-t border-line">
      <summary className="flex cursor-pointer list-none items-center gap-2 py-2.5 transition-colors hover:text-ink">
        <ChevronRight size={13} className="text-gold transition-transform duration-200 group-open:rotate-90" />
        <span className="font-display text-[13px] italic text-muted group-open:text-ink">{title}</span>
      </summary>
      <div className="pb-3 pl-[21px] pr-1">
        <Md report>{body}</Md>
      </div>
    </details>
  )
}

function DebateReport({ t }: { t: DebateTranscript }) {
  const tone = RATING_TONE[t.rating] ?? RATING_TONE.Hold
  return (
    <div className="overflow-hidden rounded-2xl border border-gold/25 bg-panel/80">
      <div className="flex items-center justify-between gap-3 border-b border-line bg-panel-2/40 px-4 py-3">
        <div className="flex items-center gap-2">
          <FlaskConical size={14} className="text-gold" />
          <div>
            <div className="eyebrow">Research Brief</div>
            <div className="-mt-0.5 font-display text-[15px] font-semibold tracking-tight">{t.ticker}</div>
          </div>
        </div>
        <span className={cn('rounded-full px-3 py-1 font-mono text-[11px] font-semibold uppercase tracking-wide ring-1', tone)}>
          {t.rating}
        </span>
      </div>

      <div className="px-4 pt-3.5">
        <div className="eyebrow mb-1">Committee decision</div>
        <Md report>{t.final_decision}</Md>
      </div>

      <div className="mt-2 px-4 pb-1">
        <div className="eyebrow border-t border-line pt-2.5">The debate, in full</div>
        <Section title="Technical analyst" body={t.market_report} />
        <Section title="News & sentiment" body={t.news_report} />
        <Section title="Bull vs Bear — research debate" body={t.research_debate} />
        <Section title="Research manager's plan" body={t.investment_plan} />
        <Section title="Trader" body={t.trader_plan} />
        <Section title="Risk committee" body={t.risk_debate} />
      </div>
    </div>
  )
}

function Sources({ skills, onOpenSkill }: {
  skills: { name: string; title: string }[]
  onOpenSkill?: (name: string) => void
}) {
  return (
    <div className="mt-2 flex flex-wrap items-center gap-1.5">
      <span className="flex items-center gap-1 font-mono text-[10px] text-faint">
        <BookOpen size={11} /> Sources
      </span>
      {skills.map((s) => (
        <button
          key={s.name}
          onClick={() => onOpenSkill?.(s.name)}
          className="rounded-full border border-line bg-panel-2/50 px-2.5 py-0.5 text-[11px] text-muted transition-colors hover:border-gold/40 hover:text-gold"
        >
          {s.title}
        </button>
      ))}
    </div>
  )
}

function Bubble({ m, onOpenSkill }: { m: ChatMessage; onOpenSkill?: (name: string) => void }) {
  if (m.role === 'system') {
    return <div className="py-1 text-center font-mono text-[11px] text-faint">{m.text}</div>
  }
  const user = m.role === 'user'
  const isReport = !user && !!m.transcript
  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.3, ease: [0.16, 1, 0.3, 1] }}
      className={cn('flex gap-3', user && 'flex-row-reverse')}
    >
      <div className={cn(
        'mt-0.5 grid h-7 w-7 shrink-0 place-items-center rounded-full font-display text-[11px] font-semibold',
        user ? 'bg-panel-2 text-muted' : 'bg-gold/12 text-gold ring-1 ring-gold/25',
      )}>
        {user ? 'Y' : 'A'}
      </div>
      <div className={cn(isReport ? 'w-full max-w-[94%]' : 'max-w-[84%]')}>
        {isReport ? (
          <DebateReport t={m.transcript!} />
        ) : (
          <div className={cn(
            'rounded-2xl px-4 py-2.5 text-[14px] leading-relaxed',
            user ? 'bg-panel-2 text-ink' : 'border border-line bg-panel/70',
          )}>
            {user ? <span className="whitespace-pre-wrap">{m.text}</span> : <Md>{m.text}</Md>}
          </div>
        )}
        {!user && m.skills && m.skills.length > 0 && (
          <Sources skills={m.skills} onOpenSkill={onOpenSkill} />
        )}
        {m.provider && (
          <div className={cn('mt-1.5 font-mono text-[10px] text-faint', user && 'text-right')}>via {m.provider}</div>
        )}
      </div>
    </motion.div>
  )
}

type Debate = { ticker?: string; stages: Record<string, { label: string; status: string }> }
const DEBATE_STAGES: [string, string][] = [
  ['analysts', 'Analyst team'],
  ['research', 'Bull vs Bear debate'],
  ['plan', 'Research manager'],
  ['trader', 'Trader'],
  ['risk', 'Risk committee'],
  ['pm', 'Portfolio manager'],
]

function DebateProgress({ debate }: { debate: Debate }) {
  return (
    <div className="flex gap-3">
      <div className="mt-0.5 grid h-7 w-7 place-items-center rounded-full bg-gold/12 font-display text-[11px] font-semibold text-gold ring-1 ring-gold/25">A</div>
      <div className="w-full max-w-[94%] rounded-2xl border border-gold/25 bg-panel/70 px-4 py-3">
        <div className="eyebrow mb-2">Convening the committee{debate.ticker ? ` · ${debate.ticker}` : ''}</div>
        <div className="space-y-1.5">
          {DEBATE_STAGES.map(([key, name]) => {
            const st = debate.stages[key]
            const status = st?.status ?? 'pending'
            return (
              <div key={key} className={cn('flex items-center gap-2 text-[13px]',
                status === 'done' ? 'text-ink' : status === 'running' ? 'text-gold' : 'text-faint')}>
                <span className="grid w-4 place-items-center">
                  {status === 'done' ? <Check size={13} className="text-up" />
                    : status === 'running' ? <Loader2 size={12} className="animate-spin" />
                    : <span className="h-1 w-1 rounded-full bg-faint" />}
                </span>
                <span className="font-display">{st?.label || name}</span>
              </div>
            )
          })}
        </div>
      </div>
    </div>
  )
}

function Thinking({ deep }: { deep: boolean }) {
  return (
    <div className="flex gap-3">
      <div className="mt-0.5 grid h-7 w-7 place-items-center rounded-full bg-gold/12 font-display text-[11px] font-semibold text-gold ring-1 ring-gold/25">
        A
      </div>
      <div className="flex items-center gap-2.5 rounded-2xl border border-line bg-panel/70 px-4 py-3">
        <div className="flex items-center gap-1.5">
          {[0, 1, 2].map((i) => (
            <motion.span
              key={i}
              className="h-1.5 w-1.5 rounded-full bg-gold"
              animate={{ opacity: [0.25, 1, 0.25] }}
              transition={{ duration: 1, repeat: Infinity, delay: i * 0.18 }}
            />
          ))}
        </div>
        {deep && (
          <span className="font-mono text-[10px] text-faint">convening the committee — this takes a moment…</span>
        )}
      </div>
    </div>
  )
}

export function Chat({ messages, busy, onSend, onOpenSkill, debate }: {
  messages: ChatMessage[]
  busy: boolean
  onSend: (text: string, deep: boolean) => void
  onOpenSkill?: (name: string) => void
  debate?: Debate | null
}) {
  const [text, setText] = useState('')
  const [deep, setDeep] = useState(false)
  const listRef = useRef<HTMLDivElement>(null)
  const mounted = useRef(false)

  useEffect(() => {
    // Scroll the chat's OWN list to the latest message — not via scrollIntoView,
    // which would bubble up and drag the whole Terminal page down to the copilot.
    // Skip the very first mount so opening Terminal shows the top of the page.
    const el = listRef.current
    if (!el) return
    if (!mounted.current) { mounted.current = true; return }
    el.scrollTo({ top: el.scrollHeight, behavior: 'smooth' })
  }, [messages, busy])

  const submit = () => {
    const t = text.trim()
    if (!t || busy) return
    onSend(t, deep)
    setText('')
  }

  return (
    <div className="flex h-full flex-col overflow-hidden rounded-2xl border border-line bg-panel/50">
      <div className="flex items-center justify-between border-b border-line px-5 py-3.5">
        <div className="flex items-center gap-2.5">
          <div className="grid h-7 w-7 place-items-center rounded-full bg-gold/10 ring-1 ring-gold/25">
            <span className="font-display text-[13px] font-semibold text-gold">A</span>
          </div>
          <div>
            <div className="font-display text-[14px] font-medium">The Copilot</div>
            <div className="eyebrow">live market · remembers everything</div>
          </div>
        </div>
        {deep && (
          <span className="hidden items-center gap-1.5 rounded-full bg-gold/10 px-2.5 py-1 font-mono text-[10px] text-gold ring-1 ring-gold/20 sm:flex">
            <FlaskConical size={11} /> committee mode
          </span>
        )}
      </div>

      <div ref={listRef} className="flex-1 space-y-5 overflow-y-auto px-5 py-5">
        {messages.map((m, i) => <Bubble key={i} m={m} onOpenSkill={onOpenSkill} />)}
        {busy && (debate ? <DebateProgress debate={debate} /> : <Thinking deep={deep} />)}
      </div>

      <div className="border-t border-line p-3">
        <div className="flex items-end gap-2 rounded-xl border border-line bg-panel-2/40 p-2 transition-colors focus-within:border-gold/40">
          <textarea
            value={text}
            onChange={(e) => setText(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault()
                submit()
              }
            }}
            rows={1}
            placeholder="Ask the market, or “deep analysis of NVDA”…"
            className="max-h-32 flex-1 resize-none bg-transparent px-2 py-1.5 text-[14px] text-ink placeholder:text-faint focus:outline-none"
          />
          <button
            onClick={() => setDeep((d) => !d)}
            title="Deep analysis — convene the multi-agent committee"
            className={cn(
              'flex shrink-0 items-center gap-1.5 rounded-lg px-2.5 py-1.5 text-[11px] font-medium transition-colors',
              deep ? 'bg-gold/15 text-gold' : 'text-faint hover:text-muted',
            )}
          >
            <FlaskConical size={13} /> Deep
          </button>
          <button
            onClick={submit}
            disabled={busy || !text.trim()}
            aria-label="Send message"
            className="grid h-9 w-9 shrink-0 place-items-center rounded-lg bg-gold text-obsidian transition-transform hover:scale-105 active:scale-95 disabled:opacity-40"
          >
            <ArrowUp size={18} />
          </button>
        </div>
      </div>
    </div>
  )
}
