import { useEffect, useRef } from 'react'
import {
  createChart, ColorType, CrosshairMode, LineStyle,
  type IChartApi, type ISeriesApi, type Time, type CandlestickData, type LineData,
} from 'lightweight-charts'
import type { Candle } from '../types'
import { smaArr, emaArr, bollArr, rsiArr, macdArr, toLine, heikinAshi } from '../lib/indicators'

export type ChartType = 'candles' | 'line' | 'area' | 'heikin'
export type Overlays = { sma20: boolean; sma50: boolean; ema20: boolean; boll: boolean }
export type Legend = { o: number; h: number; l: number; c: number; v: number } | null

const COLORS = { sma20: '#f2b24c', sma50: '#7fb0ff', ema20: '#d7c4ff', band: 'rgba(138,138,147,0.5)', mid: '#8a8a93' }

const SUB_OPTS = {
  layout: { background: { type: ColorType.Solid, color: 'transparent' }, textColor: '#8a8a93', fontFamily: "'JetBrains Mono', monospace", fontSize: 10 },
  grid: { vertLines: { color: 'rgba(255,255,255,0.03)' }, horzLines: { color: 'rgba(255,255,255,0.03)' } },
  rightPriceScale: { borderColor: 'rgba(255,255,255,0.08)' },
  timeScale: { visible: false, borderColor: 'rgba(255,255,255,0.08)' },
  crosshair: { mode: CrosshairMode.Normal },
}

export type DrawMode = 'none' | 'hline' | 'trend'

export function ProChart({
  candles, livePrice, secondsVisible = false, fitKey = '',
  chartType = 'candles', overlays, rsi = false, macd = false, onLegend,
  drawMode = 'none', clearKey = 0,
}: {
  candles: Candle[]; livePrice?: number | null; secondsVisible?: boolean; fitKey?: string
  chartType?: ChartType; overlays: Overlays; rsi?: boolean; macd?: boolean; onLegend?: (l: Legend) => void
  drawMode?: DrawMode; clearKey?: number
}) {
  const outer = useRef<HTMLDivElement>(null)
  const mainWrap = useRef<HTMLDivElement>(null)
  const rsiWrap = useRef<HTMLDivElement>(null)
  const macdWrap = useRef<HTMLDivElement>(null)

  const chartRef = useRef<IChartApi | null>(null)
  const priceRef = useRef<ISeriesApi<'Candlestick' | 'Line' | 'Area'> | null>(null)
  const volRef = useRef<ISeriesApi<'Histogram'> | null>(null)
  const linesRef = useRef<Record<string, ISeriesApi<'Line'>>>({})
  const rsiChartRef = useRef<IChartApi | null>(null)
  const rsiSerRef = useRef<ISeriesApi<'Line'> | null>(null)
  const macdChartRef = useRef<IChartApi | null>(null)
  const macdHistRef = useRef<ISeriesApi<'Histogram'> | null>(null)
  const macdLineRef = useRef<ISeriesApi<'Line'> | null>(null)
  const macdSigRef = useRef<ISeriesApi<'Line'> | null>(null)

  const candlesRef = useRef<Map<Candle['time'], Candle>>(new Map())
  const latest = useRef<Candle[]>(candles); latest.current = candles
  const lastRef = useRef<Candle | null>(null)
  const fitKeyRef = useRef('')
  const onLegendRef = useRef(onLegend); onLegendRef.current = onLegend
  const syncing = useRef(false)
  const drawModeRef = useRef<DrawMode>(drawMode); drawModeRef.current = drawMode
  const priceLinesRef = useRef<ReturnType<ISeriesApi<'Candlestick'>['createPriceLine']>[]>([])
  const trendsRef = useRef<ISeriesApi<'Line'>[]>([])
  const pendingTrend = useRef<{ time: Candle['time']; price: number } | null>(null)

  const allCharts = () => [chartRef.current, rsiChartRef.current, macdChartRef.current].filter(Boolean) as IChartApi[]
  const syncFrom = (src: IChartApi) => (range: unknown) => {
    if (!range || syncing.current) return
    syncing.current = true
    for (const c of allCharts()) if (c !== src) c.timeScale().setVisibleLogicalRange(range as never)
    syncing.current = false
  }
  const resizeAll = () => {
    const pairs: [HTMLDivElement | null, IChartApi | null][] = [
      [mainWrap.current, chartRef.current], [rsiWrap.current, rsiChartRef.current], [macdWrap.current, macdChartRef.current],
    ]
    for (const [w, c] of pairs) if (w && c) c.applyOptions({ width: w.clientWidth, height: w.clientHeight })
  }

  const pushRsi = () => {
    if (!rsiSerRef.current) return
    rsiSerRef.current.setData(toLine(latest.current, rsiArr(latest.current.map((c) => c.close))) as LineData[])
  }
  const pushMacd = () => {
    if (!macdHistRef.current || !macdLineRef.current || !macdSigRef.current) return
    const m = macdArr(latest.current.map((c) => c.close))
    macdHistRef.current.setData(latest.current.map((c, i) => m.hist[i] == null ? null : {
      time: c.time as Time, value: m.hist[i] as number,
      color: (m.hist[i] as number) >= 0 ? 'rgba(61,220,151,0.5)' : 'rgba(255,107,107,0.5)',
    }).filter(Boolean) as never[])
    macdLineRef.current.setData(toLine(latest.current, m.macd) as LineData[])
    macdSigRef.current.setData(toLine(latest.current, m.signal) as LineData[])
  }

  // ---- main chart ----
  useEffect(() => {
    if (!mainWrap.current) return
    const chart = createChart(mainWrap.current, {
      layout: { background: { type: ColorType.Solid, color: 'transparent' }, textColor: '#9b9ba5', fontFamily: "'JetBrains Mono', monospace", fontSize: 11 },
      grid: { vertLines: { color: 'rgba(255,255,255,0.035)' }, horzLines: { color: 'rgba(255,255,255,0.035)' } },
      rightPriceScale: { borderColor: 'rgba(255,255,255,0.08)' },
      timeScale: { borderColor: 'rgba(255,255,255,0.08)', timeVisible: true, secondsVisible },
      crosshair: { mode: CrosshairMode.Normal, vertLine: { color: 'rgba(242,178,76,0.4)', labelBackgroundColor: '#b9852f' }, horzLine: { color: 'rgba(242,178,76,0.4)', labelBackgroundColor: '#b9852f' } },
      width: mainWrap.current.clientWidth, height: mainWrap.current.clientHeight,
    })
    chartRef.current = chart
    const vol = chart.addHistogramSeries({ priceFormat: { type: 'volume' }, priceScaleId: '' })
    vol.priceScale().applyOptions({ scaleMargins: { top: 0.85, bottom: 0 } })
    volRef.current = vol
    chart.subscribeCrosshairMove((p) => {
      const cb = onLegendRef.current
      if (!cb) return
      if (p.time == null) { cb(null); return }
      const c = candlesRef.current.get(p.time as Candle['time'])
      cb(c ? { o: c.open, h: c.high, l: c.low, c: c.close, v: c.volume } : null)
    })
    chart.timeScale().subscribeVisibleLogicalRangeChange(syncFrom(chart))
    chart.subscribeClick((param) => {
      const mode = drawModeRef.current
      if (mode === 'none' || !priceRef.current || !param.point) return
      const price = priceRef.current.coordinateToPrice(param.point.y)
      if (price == null) return
      if (mode === 'hline') {
        priceLinesRef.current.push(priceRef.current.createPriceLine({
          price: price as number, color: '#f2b24c', lineWidth: 1, lineStyle: LineStyle.Solid, axisLabelVisible: true, title: '',
        }))
      } else if (mode === 'trend' && param.time != null) {
        const pt = { time: param.time as Candle['time'], price: price as number }
        if (!pendingTrend.current) { pendingTrend.current = pt }
        else {
          const pair = [pendingTrend.current, pt].sort((a, b) => (a.time < b.time ? -1 : 1))
          const s = chart.addLineSeries({ color: '#f2b24c', lineWidth: 2, priceLineVisible: false, lastValueVisible: false, crosshairMarkerVisible: false })
          s.setData(pair.map((p) => ({ time: p.time as Time, value: p.price })))
          trendsRef.current.push(s)
          pendingTrend.current = null
        }
      }
    })
    const ro = new ResizeObserver(resizeAll)
    if (outer.current) ro.observe(outer.current)
    return () => { ro.disconnect(); chart.remove(); chartRef.current = null; priceRef.current = null }
  }, [])

  // ---- price series for chart type ----
  useEffect(() => {
    const chart = chartRef.current
    if (!chart) return
    if (priceRef.current) { chart.removeSeries(priceRef.current); priceRef.current = null }
    if (chartType === 'line') priceRef.current = chart.addLineSeries({ color: '#f2b24c', lineWidth: 2 })
    else if (chartType === 'area') priceRef.current = chart.addAreaSeries({ lineColor: '#f2b24c', topColor: 'rgba(242,178,76,0.25)', bottomColor: 'rgba(242,178,76,0)', lineWidth: 2 })
    else priceRef.current = chart.addCandlestickSeries({ upColor: '#3ddc97', downColor: '#ff6b6b', borderUpColor: '#3ddc97', borderDownColor: '#ff6b6b', wickUpColor: 'rgba(61,220,151,0.8)', wickDownColor: 'rgba(255,107,107,0.8)' })
    priceLinesRef.current = []  // old price lines died with the removed series
    fitKeyRef.current = ''
  }, [chartType])

  // ---- RSI pane create/destroy ----
  useEffect(() => {
    if (rsi && rsiWrap.current && !rsiChartRef.current) {
      const c = createChart(rsiWrap.current, { ...SUB_OPTS, width: rsiWrap.current.clientWidth, height: rsiWrap.current.clientHeight })
      rsiChartRef.current = c
      const s = c.addLineSeries({ color: '#d7c4ff', lineWidth: 1, priceLineVisible: false, lastValueVisible: false })
      s.createPriceLine({ price: 70, color: 'rgba(255,107,107,0.35)', lineStyle: LineStyle.Dashed, lineWidth: 1, axisLabelVisible: true, title: '' })
      s.createPriceLine({ price: 30, color: 'rgba(61,220,151,0.35)', lineStyle: LineStyle.Dashed, lineWidth: 1, axisLabelVisible: true, title: '' })
      rsiSerRef.current = s
      c.timeScale().subscribeVisibleLogicalRangeChange(syncFrom(c))
      pushRsi()
      const r = chartRef.current?.timeScale().getVisibleLogicalRange()
      if (r) c.timeScale().setVisibleLogicalRange(r as never)
    }
    if (!rsi && rsiChartRef.current) { rsiChartRef.current.remove(); rsiChartRef.current = null; rsiSerRef.current = null }
  }, [rsi])

  // ---- MACD pane create/destroy ----
  useEffect(() => {
    if (macd && macdWrap.current && !macdChartRef.current) {
      const c = createChart(macdWrap.current, { ...SUB_OPTS, width: macdWrap.current.clientWidth, height: macdWrap.current.clientHeight })
      macdChartRef.current = c
      macdHistRef.current = c.addHistogramSeries({ priceLineVisible: false, lastValueVisible: false })
      macdLineRef.current = c.addLineSeries({ color: '#f2b24c', lineWidth: 1, priceLineVisible: false, lastValueVisible: false })
      macdSigRef.current = c.addLineSeries({ color: '#7fb0ff', lineWidth: 1, priceLineVisible: false, lastValueVisible: false })
      c.timeScale().subscribeVisibleLogicalRangeChange(syncFrom(c))
      pushMacd()
      const r = chartRef.current?.timeScale().getVisibleLogicalRange()
      if (r) c.timeScale().setVisibleLogicalRange(r as never)
    }
    if (!macd && macdChartRef.current) { macdChartRef.current.remove(); macdChartRef.current = null; macdHistRef.current = null; macdLineRef.current = null; macdSigRef.current = null }
  }, [macd])

  // ---- data + overlays ----
  useEffect(() => {
    const chart = chartRef.current
    if (!chart || !priceRef.current || !volRef.current) return
    const display = chartType === 'heikin' ? heikinAshi(candles) : candles
    candlesRef.current = new Map(candles.map((c) => [c.time, c]))

    if (chartType === 'line' || chartType === 'area') {
      priceRef.current.setData(display.map((c) => ({ time: c.time as Time, value: c.close })) as LineData[])
    } else {
      priceRef.current.setData(display.map((c) => ({ time: c.time as Time, open: c.open, high: c.high, low: c.low, close: c.close })) as CandlestickData[])
    }
    volRef.current.setData(candles.map((c) => ({ time: c.time as Time, value: c.volume, color: c.close >= c.open ? 'rgba(61,220,151,0.2)' : 'rgba(255,107,107,0.2)' })) as never[])

    const closes = candles.map((c) => c.close)
    const want: Record<string, LineData[]> = {}
    if (overlays.sma20) want.sma20 = toLine(candles, smaArr(closes, 20)) as LineData[]
    if (overlays.sma50) want.sma50 = toLine(candles, smaArr(closes, 50)) as LineData[]
    if (overlays.ema20) want.ema20 = toLine(candles, emaArr(closes, 20)) as LineData[]
    if (overlays.boll) {
      const b = bollArr(closes, 20, 2)
      want.bollU = toLine(candles, b.upper) as LineData[]; want.bollM = toLine(candles, b.mid) as LineData[]; want.bollL = toLine(candles, b.lower) as LineData[]
    }
    for (const k of Object.keys(linesRef.current)) if (!(k in want)) { chart.removeSeries(linesRef.current[k]); delete linesRef.current[k] }
    const style = (k: string) => k === 'sma20' ? { color: COLORS.sma20, lineWidth: 1 as const }
      : k === 'sma50' ? { color: COLORS.sma50, lineWidth: 1 as const }
      : k === 'ema20' ? { color: COLORS.ema20, lineWidth: 1 as const }
      : k === 'bollM' ? { color: COLORS.mid, lineWidth: 1 as const, lineStyle: LineStyle.Dashed }
      : { color: COLORS.band, lineWidth: 1 as const }
    for (const [k, d] of Object.entries(want)) {
      if (!linesRef.current[k]) linesRef.current[k] = chart.addLineSeries({ ...style(k), priceLineVisible: false, lastValueVisible: false })
      linesRef.current[k].setData(d)
    }
    pushRsi(); pushMacd()

    lastRef.current = candles.length ? candles[candles.length - 1] : null
    if (fitKey !== fitKeyRef.current) { chart.timeScale().fitContent(); fitKeyRef.current = fitKey }
  }, [candles, chartType, overlays, fitKey])

  // ---- live last bar ----
  useEffect(() => {
    if (livePrice == null || !priceRef.current || !lastRef.current) return
    const last = lastRef.current
    if (chartType === 'line' || chartType === 'area') priceRef.current.update({ time: last.time as Time, value: livePrice } as LineData)
    else priceRef.current.update({ time: last.time as Time, open: last.open, high: Math.max(last.high, livePrice), low: Math.min(last.low, livePrice), close: livePrice } as CandlestickData)
  }, [livePrice, chartType])

  useEffect(() => { chartRef.current?.applyOptions({ timeScale: { secondsVisible } }); setTimeout(resizeAll, 0) }, [secondsVisible, rsi, macd])

  // clear drawings
  useEffect(() => {
    const chart = chartRef.current
    if (!chart) return
    for (const s of trendsRef.current) { try { chart.removeSeries(s) } catch { /* gone */ } }
    trendsRef.current = []
    if (priceRef.current) for (const pl of priceLinesRef.current) { try { priceRef.current.removePriceLine(pl) } catch { /* gone */ } }
    priceLinesRef.current = []
    pendingTrend.current = null
  }, [clearKey])

  return (
    <div ref={outer} className="flex h-full w-full flex-col">
      <div ref={mainWrap} className="min-h-0 flex-1" />
      {rsi && (
        <div className="relative shrink-0 border-t border-line" style={{ height: 96 }}>
          <span className="pointer-events-none absolute left-2 top-1 z-10 font-mono text-[10px] text-faint">RSI 14</span>
          <div ref={rsiWrap} className="h-full w-full" />
        </div>
      )}
      {macd && (
        <div className="relative shrink-0 border-t border-line" style={{ height: 96 }}>
          <span className="pointer-events-none absolute left-2 top-1 z-10 font-mono text-[10px] text-faint">MACD 12 26 9</span>
          <div ref={macdWrap} className="h-full w-full" />
        </div>
      )}
    </div>
  )
}
