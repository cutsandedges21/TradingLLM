import { useEffect, useRef } from 'react'
import { AccountCard } from '../components/AccountCard'
import { Positions } from '../components/Positions'
import { Chat } from '../components/Chat'
import type { Account, ChatMessage, Position } from '../types'

export function TerminalPage({ messages, busy, onSend, account, positions, onOpenSkill, debate }: {
  messages: ChatMessage[]
  busy: boolean
  onSend: (text: string, deep: boolean) => void
  account: Account | null
  positions: Position[]
  onOpenSkill?: (name: string) => void
  debate?: { ticker?: string; stages: Record<string, { label: string; status: string }> } | null
}) {
  // Show the top of the page (account/positions) when Terminal opens, not the chat bottom.
  const topRef = useRef<HTMLDivElement>(null)
  useEffect(() => { topRef.current?.scrollTo({ top: 0 }) }, [])

  return (
    <div ref={topRef} className="h-full overflow-y-auto lg:overflow-hidden">
      <div className="grid gap-4 p-4 lg:h-full lg:grid-cols-[1fr_clamp(340px,30vw,420px)]">
        <div className="order-2 h-[68vh] min-h-0 lg:order-1 lg:h-full">
          <Chat messages={messages} busy={busy} onSend={onSend} onOpenSkill={onOpenSkill} debate={debate} />
        </div>
        <div className="order-1 flex min-h-0 flex-col gap-4 lg:order-2 lg:overflow-hidden">
          <AccountCard account={account} />
          <Positions positions={positions} />
        </div>
      </div>
    </div>
  )
}
