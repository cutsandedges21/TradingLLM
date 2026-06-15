export interface Account {
  equity?: number
  cash?: number
  buying_power?: number
  portfolio_value?: number
  day_pl?: number
  day_pl_pct?: number
  currency?: string
  status?: string
}

export interface Position {
  symbol: string
  qty: number
  side: string
  avg_entry: number
  current_price: number
  market_value: number
  unrealized_pl: number
  unrealized_plpc: number
}

export interface WatchRow {
  symbol: string
  price: number | null
  change_pct: number | null
  rsi: number | null
  trend: string | null
}

export interface Proposal {
  action: string
  symbol: string
  qty?: number | null
  notional?: number | null
  order_type: string
  limit_price?: number | null
  rationale: string
  est_cost?: number | null
  source?: string
  signal_kind?: string
}

export interface DebateTranscript {
  ticker: string
  market_report: string
  news_report: string
  research_debate: string
  investment_plan: string
  trader_plan: string
  risk_debate: string
  final_decision: string
  rating: string
}

export interface Cited {
  name: string
  title: string
}

export interface SkillMeta {
  name: string
  title: string
  tags: string[]
  level: string
  summary: string
}

export interface SkillPack extends SkillMeta {
  body: string
}

export interface ChatResponse {
  reply: string
  provider: string
  proposal: Proposal | null
  transcript?: DebateTranscript
  analysis_kind?: string
  skills?: Cited[]
}

export interface Status {
  providers: Record<string, unknown>
  data_sources: string[]
  trading: string
  market_open?: boolean | null
  next_open?: string | null
  next_open_ts?: number | null
  brain_mode?: string
  beginner_mode?: boolean
}

export interface ChatMessage {
  role: 'user' | 'assistant' | 'system'
  text: string
  provider?: string
  ts: number
  transcript?: DebateTranscript
  skills?: Cited[]
}

export interface Quote {
  symbol: string
  price: number | null
  change_pct: number | null
}

export interface Candle {
  time: string | number
  open: number
  high: number
  low: number
  close: number
  volume: number
}

export interface SettingsView {
  watchlist: string[]
  mock_starting_cash: number
  data_source_order: string[]
  default_timeframe: string
}

export interface Order {
  ts: string
  type: string
  symbol?: string
  side?: string
  qty?: number
  price?: number
  status?: string
  rationale?: string
  error?: string
}

export interface StrategyMeta {
  name: string
  label: string
  description: string
  defaults: Record<string, unknown>
}

export interface EquityPoint { date: string; equity: number; benchmark: number }

export interface BacktestRun {
  ok: boolean
  symbol: string
  strategy: string
  params?: Record<string, unknown>
  error?: string
  metrics: Record<string, number>
  equity_curve: EquityPoint[]
  trades: Record<string, unknown>[]
  explanation: string
}

export interface OptimizeRun {
  ok: boolean
  symbol: string
  strategy: string
  metric: string
  error?: string
  best_params: Record<string, unknown>
  default_params?: Record<string, unknown>
  n_combos?: number
  results: Record<string, any>[]
  explanation: string
}

export interface FactorBench {
  ok: boolean
  error?: string
  n_symbols: number
  n_days: number
  horizon: number
  results: Record<string, any>[]
  explanation: string
}

export interface StrategyResult {
  ok: boolean
  symbol?: string
  name?: string
  rules?: string
  metrics?: Record<string, number>
  equity_curve?: EquityPoint[]
  pine?: string
  explanation?: string
  error?: string
}

export interface CoachData {
  reply: string
  coach: { scorecard: Record<string, any>; challenges: Record<string, any>[] }
}

export interface ShadowData {
  reply: string
  shadow: { ok: boolean; n_trips: number; profile: Record<string, any> }
}

export type View = 'terminal' | 'charts' | 'watchlist' | 'studio' | 'smartmoney' | 'library' | 'settings'

export interface Regime {
  ok: boolean
  label: string          // risk_on | neutral | risk_off
  trend: string          // up | sideways | down
  vol: string            // low | normal | high
  breadth_pct: number
  spy_vs_200dma_pct: number
  realized_vol_20d: number
  momentum_3m_pct: number
  summary: string
  as_of: string
}

export interface SmartSignal {
  kind: string           // insider_buy | insider_sell | inst_13f | congress
  symbol: string
  date: string
  actor: string
  direction: number
  size_usd: number
  detail: string
  source_url: string
  as_of: string
  lag_note: string
}

export interface SignalBundle {
  symbol: string
  signals: SmartSignal[]
  net_insider_usd_30d: number
  net_insider_usd_90d: number
  insider_buys_30d: number
  insider_sells_30d: number
  funds_holding: number
  congress_trades_90d: number
  stale: boolean
  sources_unavailable: string[]
}

export interface EventStudyRow {
  horizon: number
  n: number
  mean_ret_pct: number
  mean_alpha_pct: number
  baseline_alpha_pct: number
  edge_pct: number
  hit_rate_pct: number
  t_stat: number
  is_alpha_pct: number
  oos_alpha_pct: number
  n_is: number
  n_oos: number
}

export interface EventStudy {
  ok: boolean
  symbol?: string
  kind?: string
  n_events?: number
  window?: { start: string; end: string }
  horizons?: EventStudyRow[]
  verdict?: string
  explain?: string
  reason?: string
}

export interface SignalIdea {
  symbol: string
  side: string
  score: number
  net_insider_30d: number
  buys_30d: number
  funds_holding: number
  regime: string
  rationale: string
  proposal: Proposal
}

export interface IdeasResponse {
  regime: string
  notional_each: number
  ideas: SignalIdea[]
}

export interface TrackGroup {
  n: number
  wins: number
  win_rate_pct: number
  avg_alpha_pct: number
}

export interface TrackRecord {
  overall: TrackGroup
  by_group: Record<string, TrackGroup>
  pending: number
  total: number
}

export interface RiskCheckItem { name: string; status: string; detail: string }
export interface RiskCheck {
  verdict: string
  headline: string
  fails: number
  warns: number
  checks: RiskCheckItem[]
}

export interface RiskDashboard {
  equity: number
  heat: { gross_exposure: number; gross_pct: number; open_risk: number; open_risk_pct: number; n_positions: number }
  rules: { account_risk_pct: number; max_portfolio_heat_pct: number; max_position_usd: number; default_stop_pct: number }
  n_trips: number
  stats: { win_rate: number; payoff: number; expectancy_r: number } | null
  kelly?: number
  suggested_risk_pct?: number
  ruin?: { at_current: number; at_suggested: number; at_5pct: number }
  note?: string
}

export interface Seasonality {
  ok: boolean
  reason?: string
  current_month_name?: string
  current?: { avg_pct: number; win_rate: number; n: number } | null
  best_month?: { name: string; avg_pct: number; win_rate: number; n: number } | null
  worst_month?: { name: string; avg_pct: number; win_rate: number; n: number } | null
  day_of_week?: Record<string, number>
  turn_of_month_edge_pct?: number | null
  years?: number
}

export interface ShortInterest {
  ok: boolean
  reason?: string
  short_pct_float?: number | null
  days_to_cover?: number | null
  change_pct?: number | null
  squeeze_score?: number | null
  label?: string
  note?: string
}

export interface OptionsUnusual {
  side: string; strike: number; volume: number; open_interest: number; vol_oi_ratio: number; last: number
}

export interface OptionsFlow {
  ok: boolean
  reason?: string
  put_call_volume_ratio?: number | null
  put_call_oi_ratio?: number | null
  atm_iv_pct?: number | null
  total_call_volume?: number
  total_put_volume?: number
  unusual?: OptionsUnusual[]
  sentiment?: string
  spot?: number
  note?: string
}

export interface Pead {
  ok: boolean
  reason?: string
  last_earnings?: string
  last_reaction_pct?: number
  last_drift_pct?: number | null
  pos_reaction_avg_drift_pct?: number | null
  neg_reaction_avg_drift_pct?: number | null
  n_pos?: number
  n_neg?: number
  has_pead?: boolean
  verdict?: string
  note?: string
}

export interface EdgeSignals {
  symbol: string
  seasonality: Seasonality
  short_interest: ShortInterest
  options_flow: OptionsFlow
  pead: Pead
}

export interface ScanComponent {
  name: string
  label: string
  signal: number
  weight: number
  points: number
}

export interface ScanRow {
  symbol: string
  score: number
  signal: number
  direction: string
  components: ScanComponent[]
  available: string[]
  n_components: number
  readings?: {
    net_insider_30d?: number | null
    funds_holding?: number | null
    seasonality_month_pct?: number | null
    squeeze_score?: number | null
    trend?: string | null
  }
}

export interface ScanResult {
  regime: string
  scanned: number
  results: ScanRow[]
  note: string
}

export interface AlertCondition {
  field: string
  op: string
  value: number | string
  value_seen?: number | string | null
  pass?: boolean
}

export interface AlertRule {
  id?: string
  name: string
  conditions: AlertCondition[]
  scope: string
  symbols: string[]
  action: string
  hold_days: number
  risk_pct: number
  enabled: boolean
  created?: string
}

export interface AlertFieldMeta { label: string; type: string; pit: boolean; choices?: string[] }
export interface AlertFields { fields: Record<string, AlertFieldMeta>; ops: string[] }

export interface AlertMatch {
  rule_id: string
  rule_name: string
  symbol: string
  matched: AlertCondition[]
  proposal: Proposal
}

export interface AlertEval { regime: string; alerts: AlertMatch[]; scanned: number; note: string }

export interface RuleBacktest extends EventStudy {
  n_entries?: number
  hold_days?: number
  skipped_forward_only?: string[]
  backtested_conditions?: string[]
}

export interface RiskSize {
  symbol: string
  shares: number
  notional: number
  risk_dollars: number
  risk_per_share: number
  pct_of_equity: number
  entry: number
  stop: number
  risk_pct: number
  method: string
  ruin_at_risk_pct?: number
  note?: string
}
