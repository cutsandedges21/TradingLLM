import { useEffect, useRef } from 'react'
import {
  createChart, ColorType, CrosshairMode,
  type IChartApi, type ISeriesApi, type CandlestickData, type Time,
} from 'lightweight-charts'
import type { Candle } from '../types'

export function CandleChart({ candles, livePrice, secondsVisible = false, fitKey = '' }: {
  candles: Candle[]; livePrice?: number | null; secondsVisible?: boolean; fitKey?: string
}) {
  const wrap = useRef<HTMLDivElement>(null)
  const chartRef = useRef<IChartApi | null>(null)
  const candleRef = useRef<ISeriesApi<'Candlestick'> | null>(null)
  const volRef = useRef<ISeriesApi<'Histogram'> | null>(null)
  const lastRef = useRef<Candle | null>(null)
  const fitKeyRef = useRef<string>('')

  useEffect(() => {
    if (!wrap.current) return
    const chart = createChart(wrap.current, {
      layout: {
        background: { type: ColorType.Solid, color: 'transparent' },
        textColor: '#9b9ba5',
        fontFamily: "'JetBrains Mono', monospace",
        fontSize: 11,
      },
      grid: {
        vertLines: { color: 'rgba(255,255,255,0.035)' },
        horzLines: { color: 'rgba(255,255,255,0.035)' },
      },
      rightPriceScale: { borderColor: 'rgba(255,255,255,0.08)' },
      timeScale: { borderColor: 'rgba(255,255,255,0.08)', timeVisible: true, secondsVisible },
      crosshair: {
        mode: CrosshairMode.Normal,
        vertLine: { color: 'rgba(242,178,76,0.4)', labelBackgroundColor: '#b9852f' },
        horzLine: { color: 'rgba(242,178,76,0.4)', labelBackgroundColor: '#b9852f' },
      },
      width: wrap.current.clientWidth,
      height: wrap.current.clientHeight,
    })

    const candleSeries = chart.addCandlestickSeries({
      upColor: '#3ddc97', downColor: '#ff6b6b',
      borderUpColor: '#3ddc97', borderDownColor: '#ff6b6b',
      wickUpColor: 'rgba(61,220,151,0.8)', wickDownColor: 'rgba(255,107,107,0.8)',
    })
    const volSeries = chart.addHistogramSeries({ priceFormat: { type: 'volume' }, priceScaleId: '' })
    volSeries.priceScale().applyOptions({ scaleMargins: { top: 0.82, bottom: 0 } })

    chartRef.current = chart
    candleRef.current = candleSeries
    volRef.current = volSeries

    const ro = new ResizeObserver(() => {
      if (wrap.current) chart.applyOptions({ width: wrap.current.clientWidth, height: wrap.current.clientHeight })
    })
    ro.observe(wrap.current)

    return () => {
      ro.disconnect()
      chart.remove()
      chartRef.current = null
      candleRef.current = null
      volRef.current = null
    }
  }, [])

  useEffect(() => {
    if (!candleRef.current || !volRef.current) return
    candleRef.current.setData(
      candles.map((c) => ({ time: c.time as Time, open: c.open, high: c.high, low: c.low, close: c.close })) as CandlestickData[],
    )
    volRef.current.setData(
      candles.map((c) => ({
        time: c.time as Time,
        value: c.volume,
        color: c.close >= c.open ? 'rgba(61,220,151,0.22)' : 'rgba(255,107,107,0.22)',
      })) as never[],
    )
    lastRef.current = candles.length ? candles[candles.length - 1] : null
    // Only auto-fit when the symbol/timeframe changes — NOT on every live refresh,
    // so the user's manual zoom is preserved while data updates.
    if (fitKey !== fitKeyRef.current) {
      chartRef.current?.timeScale().fitContent()
      fitKeyRef.current = fitKey
    }
  }, [candles, fitKey])

  useEffect(() => {
    if (livePrice == null || !candleRef.current || !lastRef.current) return
    const last = lastRef.current
    candleRef.current.update({
      time: last.time as Time,
      open: last.open,
      high: Math.max(last.high, livePrice),
      low: Math.min(last.low, livePrice),
      close: livePrice,
    } as CandlestickData)
  }, [livePrice])

  useEffect(() => {
    chartRef.current?.applyOptions({ timeScale: { secondsVisible } })
  }, [secondsVisible])

  return <div ref={wrap} className="h-full w-full" />
}
