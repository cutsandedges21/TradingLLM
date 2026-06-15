import { useEffect, useRef, useState } from 'react'
import { api } from '../api'
import type { Quote } from '../types'

/**
 * Polls /api/quotes for the given symbols and reports per-symbol price flashes
 * (up/down) whenever a price changes — this is what makes the watchlist/account
 * visibly tick in real time.
 */
export function useLiveQuotes(symbols: string[], intervalMs = 4000, enabled = true) {
  const [quotes, setQuotes] = useState<Record<string, Quote>>({})
  const [flash, setFlash] = useState<Record<string, 'up' | 'down'>>({})
  const prev = useRef<Record<string, number>>({})
  const key = symbols.join(',')

  useEffect(() => {
    if (!enabled || !symbols.length) return
    let stopped = false

    const tick = async () => {
      try {
        const qs = await api.quotes(symbols)
        if (stopped) return
        const map: Record<string, Quote> = {}
        const fl: Record<string, 'up' | 'down'> = {}
        for (const q of qs) {
          map[q.symbol] = q
          const p = prev.current[q.symbol]
          if (q.price != null && p != null && q.price !== p) {
            fl[q.symbol] = q.price > p ? 'up' : 'down'
          }
          if (q.price != null) prev.current[q.symbol] = q.price
        }
        setQuotes(map)
        if (Object.keys(fl).length) {
          setFlash(fl)
          setTimeout(() => { if (!stopped) setFlash({}) }, 700)
        }
      } catch {
        /* ignore transient errors */
      }
    }

    tick()
    const id = setInterval(tick, intervalMs)
    return () => { stopped = true; clearInterval(id) }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key, intervalMs, enabled])

  return { quotes, flash }
}
