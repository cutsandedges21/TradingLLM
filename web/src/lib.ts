import { clsx, type ClassValue } from 'clsx'

export const cn = (...a: ClassValue[]) => clsx(a)

export const money = (n?: number | null, dp = 2) =>
  n == null
    ? '—'
    : n.toLocaleString('en-US', {
        style: 'currency',
        currency: 'USD',
        minimumFractionDigits: dp,
        maximumFractionDigits: dp,
      })

export const pct = (n?: number | null) =>
  n == null ? '—' : `${n >= 0 ? '+' : ''}${n.toFixed(2)}%`

export const num = (n?: number | null, dp = 2) =>
  n == null
    ? '—'
    : n.toLocaleString('en-US', { minimumFractionDigits: dp, maximumFractionDigits: dp })
