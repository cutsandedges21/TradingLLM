import { Watchlist } from '../components/Watchlist'
import type { WatchRow } from '../types'

export function WatchlistPage({ rows, flash, onPick }: {
  rows: WatchRow[]
  flash: Record<string, 'up' | 'down'>
  onPick: (s: string) => void
}) {
  return (
    <div className="h-full overflow-y-auto p-4 md:p-8">
      <div className="mx-auto max-w-3xl">
        <Watchlist rows={rows} flash={flash} onPick={onPick} />
        <p className="mt-3 px-1 text-[11px] text-faint">
          Click a symbol to open its chart. Edit which symbols appear in <span className="text-muted">Settings</span>.
        </p>
      </div>
    </div>
  )
}
