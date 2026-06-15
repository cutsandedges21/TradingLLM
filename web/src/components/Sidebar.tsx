import { FlaskConical, Landmark, Library, LineChart, Settings as SettingsIcon, Star, Terminal } from 'lucide-react'
import { cn } from '../lib'
import type { View } from '../types'

const ITEMS: { id: View; label: string; icon: typeof Terminal; idx: string }[] = [
  { id: 'terminal', label: 'Terminal', icon: Terminal, idx: '01' },
  { id: 'charts', label: 'Charts', icon: LineChart, idx: '02' },
  { id: 'studio', label: 'Studio', icon: FlaskConical, idx: '03' },
  { id: 'smartmoney', label: 'Smart$', icon: Landmark, idx: '04' },
  { id: 'watchlist', label: 'Watch', icon: Star, idx: '05' },
  { id: 'library', label: 'Library', icon: Library, idx: '06' },
  { id: 'settings', label: 'Settings', icon: SettingsIcon, idx: '07' },
]

export function Sidebar({ view, onNav }: { view: View; onNav: (v: View) => void }) {
  return (
    <nav
      className={cn(
        'z-30 flex shrink-0 items-center gap-1 border-line bg-panel/50 backdrop-blur',
        // mobile: bottom bar
        'order-last justify-around border-t px-2 py-1.5',
        // desktop: left rail
        'md:order-none md:h-full md:w-[84px] md:flex-col md:justify-start md:gap-2 md:border-r md:border-t-0 md:px-0 md:py-6',
      )}
    >
      {/* desktop monogram */}
      <div className="hidden md:mb-3 md:grid md:h-10 md:w-10 md:place-items-center md:self-center md:rounded-full md:border md:border-gold/30 md:bg-gold/5">
        <span className="font-display text-[15px] font-semibold text-gold">A</span>
      </div>

      {ITEMS.map((it) => {
        const active = view === it.id
        const Icon = it.icon
        return (
          <button
            key={it.id}
            onClick={() => onNav(it.id)}
            className={cn(
              'group relative flex flex-1 flex-col items-center gap-1 rounded-xl py-2 transition-colors md:w-[64px] md:flex-none md:self-center md:py-2.5',
              active ? 'text-gold' : 'text-faint hover:text-ink',
            )}
          >
            {active && (
              <span className="absolute left-0 top-1/2 hidden h-7 w-[2px] -translate-y-1/2 rounded-full bg-gold md:block" />
            )}
            <span className={cn(
              'grid h-9 w-9 place-items-center rounded-xl transition-colors',
              active ? 'bg-gold/12 ring-1 ring-gold/25' : 'group-hover:bg-panel-2/60',
            )}>
              <Icon size={18} />
            </span>
            <span className="font-mono text-[9px] uppercase tracking-[0.12em]">{it.label}</span>
          </button>
        )
      })}
    </nav>
  )
}
