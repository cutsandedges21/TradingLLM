import { useEffect, useState } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { api } from '../api'
import { cn } from '../lib'
import type { SkillMeta, SkillPack } from '../types'

export function LibraryPage({ initial }: { initial?: string | null }) {
  const [packs, setPacks] = useState<SkillMeta[]>([])
  const [selected, setSelected] = useState<SkillPack | null>(null)

  useEffect(() => { api.skills().then(setPacks).catch(() => {}) }, [])

  const open = async (name: string) => {
    try { setSelected(await api.skill(name)) } catch { /* ignore */ }
  }
  useEffect(() => { if (initial) open(initial) }, [initial])

  return (
    <div className="h-full overflow-y-auto lg:overflow-hidden">
      <div className="grid gap-4 p-4 lg:h-full lg:grid-cols-[minmax(300px,400px)_1fr]">
        {/* index */}
        <div className="min-h-0 rounded-2xl border border-line bg-panel/50 p-3 lg:overflow-y-auto">
          <div className="px-1 pb-2.5">
            <span className="eyebrow">Knowledge Library</span>
            <div className="font-display text-[15px] italic text-muted">{packs.length} topics the copilot cites</div>
          </div>
          <div className="space-y-1.5">
            {packs.map((p) => (
              <button
                key={p.name}
                onClick={() => open(p.name)}
                className={cn(
                  'w-full rounded-xl border px-3 py-2.5 text-left transition-colors',
                  selected?.name === p.name ? 'border-gold/40 bg-gold/8' : 'border-line hover:bg-panel-2/50',
                )}
              >
                <div className="flex items-center justify-between gap-2">
                  <span className="font-display text-[14px] font-medium">{p.title}</span>
                  <span className="rounded-full bg-panel-2 px-2 py-0.5 font-mono text-[9px] uppercase tracking-wide text-faint">
                    {p.level}
                  </span>
                </div>
                <div className="mt-0.5 text-[12px] leading-snug text-muted">{p.summary}</div>
              </button>
            ))}
          </div>
        </div>

        {/* reader */}
        <div className="min-h-[50vh] rounded-2xl border border-line bg-panel/40 lg:min-h-0 lg:overflow-y-auto">
          {selected ? (
            <div className="prose-terminal px-6 py-6 md:px-9">
              <div className="eyebrow mb-1">{selected.level} · {selected.tags.slice(0, 4).join(' · ')}</div>
              <ReactMarkdown remarkPlugins={[remarkGfm]}>{selected.body}</ReactMarkdown>
            </div>
          ) : (
            <div className="grid h-full place-items-center px-6 py-16 text-center">
              <div>
                <div className="font-display text-lg italic text-muted">Pick a topic to read.</div>
                <div className="mt-1.5 text-[12px] text-faint">
                  The copilot pulls from these whenever you ask a question — turn on Beginner mode for extra hand-holding.
                </div>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
