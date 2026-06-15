type Props = {
  data: number[]
  up?: boolean
  width?: number
  height?: number
  strokeWidth?: number
}

export function Sparkline({ data, up = true, width = 132, height = 38, strokeWidth = 1.5 }: Props) {
  if (!data || data.length < 2) return <svg width={width} height={height} />
  const min = Math.min(...data)
  const max = Math.max(...data)
  const range = max - min || 1
  const x = (i: number) => (i / (data.length - 1)) * width
  const y = (d: number) => height - 2 - ((d - min) / range) * (height - 4)
  const line = data.map((d, i) => `${i ? 'L' : 'M'}${x(i).toFixed(1)} ${y(d).toFixed(1)}`).join(' ')
  const area = `${line} L${width.toFixed(1)} ${height} L0 ${height} Z`
  const color = up ? 'var(--color-up)' : 'var(--color-down)'
  const id = `sg-${Math.round(min * 1000)}-${data.length}-${up ? 'u' : 'd'}`

  return (
    <svg width={width} height={height} className="overflow-visible">
      <defs>
        <linearGradient id={id} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor={color} stopOpacity="0.3" />
          <stop offset="100%" stopColor={color} stopOpacity="0" />
        </linearGradient>
      </defs>
      <path d={area} fill={`url(#${id})`} />
      <path
        d={line}
        fill="none"
        stroke={color}
        strokeWidth={strokeWidth}
        strokeLinejoin="round"
        strokeLinecap="round"
      />
    </svg>
  )
}
