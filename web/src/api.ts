import type {
  Account, Position, WatchRow, ChatResponse, Status, Proposal,
  Quote, Candle, SettingsView, Order, SkillMeta, SkillPack,
  StrategyMeta, BacktestRun, OptimizeRun, FactorBench, CoachData, ShadowData, StrategyResult,
  Regime, SignalBundle, EventStudy, IdeasResponse, TrackRecord,
  RiskCheck, RiskDashboard, RiskSize, EdgeSignals, ScanResult,
  AlertRule, AlertFields, AlertEval, RuleBacktest,
} from './types'

async function j<T>(url: string, opts?: RequestInit): Promise<T> {
  const r = await fetch(url, {
    headers: { 'Content-Type': 'application/json' },
    ...opts,
  })
  if (!r.ok) throw new Error(`${url} -> ${r.status}`)
  return r.json() as Promise<T>
}

export const api = {
  status: () => j<Status>('/api/status'),
  account: () => j<Account>('/api/account'),
  positions: () => j<Position[]>('/api/positions'),
  watchlist: () => j<WatchRow[]>('/api/watchlist'),
  quotes: (symbols: string[]) =>
    j<Quote[]>(`/api/quotes?symbols=${encodeURIComponent(symbols.join(','))}`),
  bars: (s: string) => j<{ symbol: string; closes: number[] }>(`/api/bars/${encodeURIComponent(s)}`),
  candles: (symbol: string, tf: string) =>
    j<{ symbol: string; tf: string; candles: Candle[]; source?: string }>(`/api/candles/${encodeURIComponent(symbol)}?tf=${tf}`),
  tick: (symbol: string) =>
    j<{ symbol: string; price: number | null }>(`/api/tick/${encodeURIComponent(symbol)}`),
  learn: () => j<{ markdown: string }>('/api/learn'),
  getSettings: () => j<SettingsView>('/api/settings'),
  saveSettings: (patch: Partial<SettingsView>) =>
    j<SettingsView>('/api/settings', { method: 'POST', body: JSON.stringify(patch) }),
  chat: (message: string, deep: boolean) =>
    j<ChatResponse>('/api/chat', { method: 'POST', body: JSON.stringify({ message, deep }) }),
  trade: (p: Proposal) =>
    j<Record<string, unknown>>('/api/trade', { method: 'POST', body: JSON.stringify(p) }),
  orders: () => j<Order[]>('/api/orders'),
  deleteOrder: (ts: string, symbol?: string) =>
    j<{ ok: boolean }>('/api/orders/delete', { method: 'POST', body: JSON.stringify({ ts, symbol }) }),
  reset: (cash?: number) =>
    j<{ ok: boolean; account: Account }>('/api/reset', { method: 'POST', body: JSON.stringify({ cash: cash ?? null }) }),
  setBrainMode: (mode: 'local' | 'cloud') =>
    j<{ brain_mode: string }>('/api/brain', { method: 'POST', body: JSON.stringify({ mode }) }),
  setBeginner: (on: boolean) =>
    j<{ beginner_mode: boolean }>('/api/beginner', { method: 'POST', body: JSON.stringify({ on }) }),
  skills: () => j<SkillMeta[]>('/api/skills'),
  skill: (name: string) => j<SkillPack>(`/api/skills/${encodeURIComponent(name)}`),
  strategies: () => j<StrategyMeta[]>('/api/strategies'),
  runBacktest: (spec: Record<string, unknown>) =>
    j<BacktestRun>('/api/backtest', { method: 'POST', body: JSON.stringify(spec) }),
  runOptimize: (spec: Record<string, unknown>) =>
    j<OptimizeRun>('/api/optimize', { method: 'POST', body: JSON.stringify(spec) }),
  factorsBench: (spec: Record<string, unknown>) =>
    j<FactorBench>('/api/factors/bench', { method: 'POST', body: JSON.stringify(spec) }),
  coach: () => j<CoachData>('/api/coach'),
  shadow: () => j<ShadowData>('/api/shadow'),
  generateStrategy: (body: { description: string; symbol?: string; period?: string }) =>
    j<StrategyResult>('/api/strategy/generate', { method: 'POST', body: JSON.stringify(body) }),
  regime: () => j<Regime>('/api/regime'),
  signals: (symbol: string) => j<SignalBundle>(`/api/signals/${encodeURIComponent(symbol)}`),
  studySignal: (symbol: string, kind: string) =>
    j<EventStudy>(`/api/signals/study/${encodeURIComponent(symbol)}?kind=${encodeURIComponent(kind)}`),
  signalIdeas: () => j<IdeasResponse>('/api/signals/ideas'),
  trackRecord: () => j<TrackRecord>('/api/signals/track-record'),
  riskCheck: (p: Proposal) =>
    j<RiskCheck>('/api/risk/check', { method: 'POST', body: JSON.stringify(p) }),
  riskDashboard: () => j<RiskDashboard>('/api/risk/dashboard'),
  riskSize: (body: { symbol: string; entry?: number | null; stop?: number | null; risk_pct?: number | null; method?: string }) =>
    j<RiskSize>('/api/risk/size', { method: 'POST', body: JSON.stringify(body) }),
  edgeSignals: (symbol: string) => j<EdgeSignals>(`/api/edge/${encodeURIComponent(symbol)}`),
  scanner: () => j<ScanResult>('/api/scanner'),
  alertFields: () => j<AlertFields>('/api/alerts/fields'),
  alertRules: () => j<AlertRule[]>('/api/alerts/rules'),
  saveAlertRule: (r: AlertRule) => j<AlertRule>('/api/alerts/rules', { method: 'POST', body: JSON.stringify(r) }),
  deleteAlertRule: (id: string) => j<{ ok: boolean }>('/api/alerts/rules/delete', { method: 'POST', body: JSON.stringify({ id }) }),
  evaluateAlerts: () => j<AlertEval>('/api/alerts/evaluate'),
  backtestRule: (rule: AlertRule, symbol?: string) =>
    j<RuleBacktest>('/api/alerts/backtest', { method: 'POST', body: JSON.stringify({ rule, symbol: symbol ?? null }) }),
}
