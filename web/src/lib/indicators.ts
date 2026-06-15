import type { Candle } from '../types'

export type LinePoint = { time: Candle['time']; value: number }

export function smaArr(v: number[], n: number): (number | null)[] {
  const out: (number | null)[] = Array(v.length).fill(null)
  let sum = 0
  for (let i = 0; i < v.length; i++) {
    sum += v[i]
    if (i >= n) sum -= v[i - n]
    if (i >= n - 1) out[i] = sum / n
  }
  return out
}

export function emaArr(v: number[], n: number): (number | null)[] {
  const out: (number | null)[] = Array(v.length).fill(null)
  if (!v.length) return out
  const k = 2 / (n + 1)
  let prev = v[0]
  for (let i = 0; i < v.length; i++) {
    prev = i === 0 ? v[0] : v[i] * k + prev * (1 - k)
    if (i >= n - 1) out[i] = prev
  }
  return out
}

export function rsiArr(c: number[], n = 14): (number | null)[] {
  const out: (number | null)[] = Array(c.length).fill(null)
  if (c.length < n + 1) return out
  let gain = 0
  let loss = 0
  for (let i = 1; i <= n; i++) {
    const d = c[i] - c[i - 1]
    if (d >= 0) gain += d
    else loss -= d
  }
  let ag = gain / n
  let al = loss / n
  out[n] = al === 0 ? 100 : 100 - 100 / (1 + ag / al)
  for (let i = n + 1; i < c.length; i++) {
    const d = c[i] - c[i - 1]
    ag = (ag * (n - 1) + (d > 0 ? d : 0)) / n
    al = (al * (n - 1) + (d < 0 ? -d : 0)) / n
    out[i] = al === 0 ? 100 : 100 - 100 / (1 + ag / al)
  }
  return out
}

export function macdArr(c: number[], fast = 12, slow = 26, signal = 9) {
  const ef = emaArr(c, fast)
  const es = emaArr(c, slow)
  const macd = c.map((_, i) => (ef[i] != null && es[i] != null ? (ef[i] as number) - (es[i] as number) : null))
  const macdVals = macd.map((x) => (x == null ? 0 : x))
  const sigRaw = emaArr(macdVals, signal)
  const sig = sigRaw.map((x, i) => (macd[i] == null ? null : x))
  const hist = c.map((_, i) => (macd[i] != null && sig[i] != null ? (macd[i] as number) - (sig[i] as number) : null))
  return { macd, signal: sig, hist }
}

export function bollArr(c: number[], n = 20, k = 2) {
  const mid = smaArr(c, n)
  const upper: (number | null)[] = Array(c.length).fill(null)
  const lower: (number | null)[] = Array(c.length).fill(null)
  for (let i = n - 1; i < c.length; i++) {
    const m = mid[i] as number
    let sum = 0
    for (let j = i - n + 1; j <= i; j++) sum += (c[j] - m) ** 2
    const sd = Math.sqrt(sum / n)
    upper[i] = m + k * sd
    lower[i] = m - k * sd
  }
  return { upper, mid, lower }
}

/** Convert a parallel indicator array into lightweight-charts line data (skips nulls). */
export function toLine(candles: Candle[], arr: (number | null)[]): LinePoint[] {
  const out: LinePoint[] = []
  for (let i = 0; i < candles.length; i++) {
    if (arr[i] != null) out.push({ time: candles[i].time, value: arr[i] as number })
  }
  return out
}

/** Heikin-Ashi transform of OHLC candles. */
export function heikinAshi(candles: Candle[]): Candle[] {
  const out: Candle[] = []
  for (let i = 0; i < candles.length; i++) {
    const c = candles[i]
    const close = (c.open + c.high + c.low + c.close) / 4
    const open = i === 0 ? (c.open + c.close) / 2 : (out[i - 1].open + out[i - 1].close) / 2
    out.push({
      time: c.time,
      open,
      close,
      high: Math.max(c.high, open, close),
      low: Math.min(c.low, open, close),
      volume: c.volume,
    })
  }
  return out
}
