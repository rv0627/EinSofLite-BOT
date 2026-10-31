/**
 * Ein Sof Lite — API Client
 * Centralized service layer for all backend API calls.
 */

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8001';
const ADMIN_KEY = process.env.NEXT_PUBLIC_ADMIN_KEY || '';

// ── Types ──────────────────────────────────────────

export interface TickerData {
  ticker: string;
  exchange: string;
  price: string;
  change: string;
  sparkData: number[];
  confidence: number | null;
  noData?: boolean;
}

export interface DashboardMetrics {
  cache_hit_ratio: number;
  system_latency_ms: number;
  cache_hits: number;
  cache_misses: number;
  error?: string;
}

export interface ApiSource {
  name: string;
  description: string;
  status: 'active' | 'standby' | 'offline';
  color: 'cyan' | 'green' | 'amber' | 'red' | 'purple';
}

export interface ApiHealthData {
  sources: ApiSource[];
  gateway_online: boolean;
}

export interface TaskStatus {
  task_id: string;
  state: 'PENDING' | 'STARTED' | 'SUCCESS' | 'FAILURE' | 'RETRY';
  ready: boolean;
  result?: string;
  error?: string;
}

export interface TriggerResponse {
  message: string;
  task_id: string;
}

// ── API Functions ──────────────────────────────────

async function apiFetch<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE_URL}${path}`, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      ...(ADMIN_KEY ? { 'X-Admin-Key': ADMIN_KEY } : {}),
      ...options?.headers,
    },
  });

  if (!res.ok) {
    let errorMsg = `API Error: ${res.status} ${res.statusText}`;
    try {
      const errBody = await res.json();
      if (errBody && errBody.detail) {
        // Handle array of details (FastAPI validation errors) or single string
        errorMsg = Array.isArray(errBody.detail) ? errBody.detail[0].msg : errBody.detail;
      }
    } catch (e) {
      // Ignore JSON parse errors for non-JSON responses
    }
    throw new Error(errorMsg);
  }

  return res.json();
}

/** Fetch ticker data for dashboard cards */
export async function fetchTickers(limit: number = 3): Promise<TickerData[]> {
  const data = await apiFetch<{ tickers: TickerData[] }>(`/api/dashboard/tickers?limit=${limit}`);
  return data.tickers;
}

/** Fetch system metrics (cache hit ratio, latency) */
export async function fetchMetrics(): Promise<DashboardMetrics> {
  return apiFetch<DashboardMetrics>('/api/dashboard/metrics');
}

/** Fetch API health status for all data providers */
export async function fetchApiHealth(): Promise<ApiHealthData> {
  return apiFetch<ApiHealthData>('/api/dashboard/api-health');
}

/** Trigger Master EOD Bot */
export async function triggerEOD(): Promise<TriggerResponse> {
  return apiFetch<TriggerResponse>('/trigger/bot1/eod', { method: 'POST' });
}

/** Trigger Data Processing Bot */
export async function triggerDataProcessor(): Promise<TriggerResponse> {
  return apiFetch<TriggerResponse>('/trigger/bot2/process', { method: 'POST' });
}

/** Trigger Live Watchlist pull */
export async function triggerLiveWatchlist(): Promise<TriggerResponse> {
  return apiFetch<TriggerResponse>('/trigger/bot1/live', { method: 'POST' });
}

/** Fetch Infrastructure Health Nodes */
export async function fetchInfrastructureHealth(): Promise<InfrastructureNode[]> {
  return apiFetch<InfrastructureNode[]>('/api/infrastructure/health');
}

/** Fetch Routing Logs */
export async function fetchRoutingLogs(): Promise<RoutingLog[]> {
  return apiFetch<RoutingLog[]>('/api/infrastructure/logs');
}

/** Check Celery task status */
export async function fetchTaskStatus(taskId: string): Promise<TaskStatus> {
  return apiFetch<TaskStatus>(`/api/task-status/${taskId}`);
}

// ── Analytics API ──────────────────────────────────

export interface AnalyticsChartData {
  date: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
}

export interface AnalyticsEvent {
  title: string;
  desc: string;
  type: 'warning' | 'info' | 'error';
}

export interface DashboardData {
  metrics: DashboardMetrics;
  recentActivity: Array<{
    id: string;
    type: string;
    description: string;
    time: string;
  }>;
}

export interface InfrastructureNode {
  id: number;
  name: string;
  role: string;
  uptime: string;
  latency: string;
  health: number;
  isPrimary: boolean;
}

// ── Shadow Validation API ─────────────────────────────

export interface ShadowDailyLogData {
  day_number: number;
  trading_day: string;
  control_deployment_pct: number;
  variant_deployment_pct: number;
  variant_regime: string;
  variant_markov_modifier: number;
  control_portfolio_return: number | null;
  variant_portfolio_return: number | null;
  return_delta: number | null;
  control_cumulative_return: number | null;
  variant_cumulative_return: number | null;
  deployment_delta: number;
  actual_next_regime: string | null;
}

export interface ShadowValidationStatus {
  active: boolean;
  period_id?: number;
  period_name?: string;
  start_date?: string;
  target_end_date?: string;
  days_logged?: number;
  target_days?: number;
  progress_pct?: number;
  latest_day?: {
    date: string | null;
    control_return: number | null;
    variant_return: number | null;
    variant_regime: string | null;
    deployment_delta: number | null;
  } | null;
  latest_period?: {
    id: number;
    name: string;
    status: string;
    days_logged: number;
    verdict: string | null;
    start_date: string;
    end_date: string | null;
  };
}

export async function fetchShadowStatus(): Promise<ShadowValidationStatus> {
  return apiFetch<ShadowValidationStatus>('/api/v1/shadow/status');
}

export async function startShadowPeriod(periodName?: string): Promise<any> {
  let url = '/api/v1/shadow/start';
  if (periodName) url += `?period_name=${encodeURIComponent(periodName)}`;
  return apiFetch<any>(url, { method: 'POST' });
}

export async function fetchShadowDailyLogs(periodId: number): Promise<{ period_id: number; total: number; logs: ShadowDailyLogData[] }> {
  return apiFetch<any>(`/api/v1/shadow/daily-logs?period_id=${periodId}`);
}

export async function abortShadowPeriod(periodId: number, reason: string): Promise<any> {
  return apiFetch<any>(`/api/v1/shadow/abort?period_id=${periodId}&reason=${encodeURIComponent(reason)}`, { method: 'POST' });
}

export async function generateShadowReport(periodId: number): Promise<any> {
  return apiFetch<any>(`/api/v1/shadow/generate-report?period_id=${periodId}`, { method: 'POST' });
}

export async function triggerShadowComparison(): Promise<any> {
  return apiFetch<any>('/trigger/shadow/daily_comparison', { method: 'POST' });
}

export interface RoutingLog {
  id: string;
  provider: string;
  path: string;
  status: string;
  latency: string;
  isError: boolean;
}

export interface AnalyticsData {
  symbol: {
    ticker: string;
    exchange: string;
    name: string;
  };
  price: {
    live: number;
    change_pct: number;
  };
  chartData: AnalyticsChartData[];
  rawOHLCV: AnalyticsChartData[]; // Extended data for client-side indicator calculations
  dataQuality: {
    confidence: number;
    anomalies: number;
  };
  events: AnalyticsEvent[];
  sentiment: {
    bullish: number;
    bearish: number;
    news: string;
    social: string;
  };
}

/** Fetch comprehensive analytics data for a specific ticker */
export async function fetchAnalyticsData(ticker: string, interval: string = 'D'): Promise<AnalyticsData> {
  return apiFetch<AnalyticsData>(`/api/analytics/${ticker}?interval=${interval}`);
}

// ── Scoring Engine API ─────────────────────────────

export interface ScoringFactors {
  value: number;
  dividend: number;
  quality: number;
  momentum: number;
  volatility: number;
}

export interface ScoringRanking {
  rank: number;
  ticker: string;
  company_name: string;
  ein_score: number;
  factors: ScoringFactors;
  confidence_weight: number;
  date: string;
}

/** Fetch Ranked Dataset from Bot 3 */
export interface ScoringRankingsResponse {
  data: ScoringRanking[];
  total?: number;
  page?: number;
  total_pages?: number;
}

export async function fetchScoringRankings(page: number = 1, limit: number = 50): Promise<ScoringRankingsResponse> {
  return apiFetch<ScoringRankingsResponse>(`/api/scoring/rankings?page=${page}&limit=${limit}`);
}

export async function triggerBot3Score(): Promise<{message: string; task_id: string}> {
  return apiFetch<{message: string; task_id: string}>('/trigger/bot3/score', {
    method: 'POST',
  });
}

// ── System Settings API ───

export interface Bot3Weights {
  value: number;
  dividend: number;
  quality: number;
  momentum: number;
  volatility: number;
}

export interface Bot3Config {
  schedule: 'daily' | 'weekly';
  weights: Bot3Weights;
}

export async function fetchBot3Settings(): Promise<Bot3Config> {
  return apiFetch<Bot3Config>('/api/settings/bot3');
}

export async function updateBot3Settings(config: Bot3Config): Promise<{message: string}> {
  return apiFetch<{message: string}>('/api/settings/bot3', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(config),
  });
}

export async function flushRedisCache(): Promise<{message: string}> {
  return apiFetch<{message: string}>('/api/settings/flush-cache', {
    method: 'POST',
  });
}

export interface CacheHealth {
  used_mb: number;
  total_gb: number;
  status: string;
}

export async function fetchCacheHealth(): Promise<CacheHealth> {
  return apiFetch<CacheHealth>('/api/settings/cache-health');
}

/** API Key masked status (returned from backend) */
export interface ApiKeyStatus {
  configured: boolean;
  masked: string;
}

/** Fetch API Keys Config (masked response from backend) */
export interface ApiKeysConfig {
  twelveData?: ApiKeyStatus;
  eodhd?: ApiKeyStatus;
  alphaVantage?: ApiKeyStatus;
  marketstack?: ApiKeyStatus;
  zerodhaApiKey?: ApiKeyStatus;
  zerodhaAccessToken?: ApiKeyStatus;
  upstoxAccessToken?: ApiKeyStatus;
  nsebseApiKey?: ApiKeyStatus;
}

/** API Keys update payload (plaintext values for saving new keys) */
export interface ApiKeysUpdatePayload {
  twelveData?: string;
  eodhd?: string;
  alphaVantage?: string;
  marketstack?: string;
  zerodhaApiKey?: string;
  zerodhaAccessToken?: string;
  upstoxAccessToken?: string;
  nsebseApiKey?: string;
}

export async function fetchApiKeys(): Promise<ApiKeysConfig> {
  return apiFetch<ApiKeysConfig>('/api/settings/apikeys');
}

export async function updateApiKeys(keys: ApiKeysUpdatePayload): Promise<{ status: string }> {
  return apiFetch<{ status: string }>('/api/settings/apikeys', {
    method: 'POST',
    body: JSON.stringify(keys),
  });
}

/** Fetch Internal Config */
export interface InternalConfig {
  schedulerEnabled: boolean;
  rateLimitReqs: number;
}

export async function fetchInternalConfig(): Promise<InternalConfig> {
  return apiFetch<InternalConfig>('/api/settings/internal');
}

export async function updateInternalConfig(config: InternalConfig): Promise<{ status: string }> {
  return apiFetch<{ status: string }>('/api/settings/internal', {
    method: 'POST',
    body: JSON.stringify(config),
  });
}

/** Fetch Portfolio Holdings */
export interface PortfolioHolding {
  ticker: string;
  name: string;
  price: string;
  change: string;
  isPositive: boolean | null;
  sync: string;
}

export async function fetchPortfolioHoldings(): Promise<{data: PortfolioHolding[]}> {
  return apiFetch<{data: PortfolioHolding[]}>('/api/portfolio/holdings');
}

/** Fetch Portfolio Intelligence */
export interface PortfolioIntelligence {
  type: string;
  label: string;
  desc: string;
}

export async function fetchPortfolioIntelligence(): Promise<{data: PortfolioIntelligence[]}> {
  return apiFetch<{data: PortfolioIntelligence[]}>('/api/portfolio/intelligence');
}

// ── Bot 4 — Allocation & Risk Management API ──────

export interface AllocationResult {
  ticker: string;
  company_name: string;
  ein_score: number;
  raw_weight: number;
  risk_adjusted_weight: number;
  position_size_pct: number;
  sector: string;
  volatility_30d: number;
  risk_flag: string | null;
  date: string;
}

export interface RiskSummary {
  date: string;
  total_symbols: number;
  sector_count: number;
  sector_distribution: Record<string, number>;
  risk_distribution: { LOW: number; MEDIUM: number; HIGH: number };
  avg_volatility: number;
  diversification_score: number;
  flagged_positions: number;
  total_capital: number;
  error?: string;
}

export async function triggerBot4Allocate(): Promise<{message: string; task_id: string}> {
  return apiFetch<{message: string; task_id: string}>('/trigger/bot4/allocate', {
    method: 'POST',
  });
}

export async function fetchAllocationResults(limit: number = 50): Promise<{data: AllocationResult[]}> {
  return apiFetch<{data: AllocationResult[]}>(`/api/allocation/results?limit=${limit}`);
}

export async function fetchRiskSummary(): Promise<RiskSummary> {
  return apiFetch<RiskSummary>('/api/allocation/risk-summary');
}

// ── Bot 5 — Top 20 Portfolio API ─────────────────

export interface Top20Entry {
  rank: number;
  ticker: string;
  company_name: string;
  allocation_pct: number;
  allocation_amount: number;
  ein_score: number;
  risk_category: 'LOW' | 'MEDIUM' | 'HIGH';
  inclusion_reason: string;
  sector: string;
  date: string;
}

export interface Top20Summary {
  date: string;
  total_entries: number;
  total_allocation: number;
  avg_ein_score: number;
  risk_score: number;
  risk_distribution: { LOW: number; MEDIUM: number; HIGH: number };
  sector_count: number;
  sectors: string[];
  error?: string;
}

export async function triggerBot5Top20(): Promise<{message: string; task_id: string}> {
  return apiFetch<{message: string; task_id: string}>('/trigger/bot5/top20', {
    method: 'POST',
  });
}

export async function fetchTop20Portfolio(): Promise<{data: Top20Entry[]}> {
  return apiFetch<{data: Top20Entry[]}>('/api/top20/portfolio');
}

export async function fetchTop20Summary(): Promise<Top20Summary> {
  return apiFetch<Top20Summary>('/api/top20/summary');
}

// ── Bot 4 Settings API ──────────────────────────

export interface Bot4Config {
  total_capital: number;
  max_position_pct: number;
  max_sector_pct: number;
  min_confidence: number;
}

export async function fetchBot4Settings(): Promise<Bot4Config> {
  return apiFetch<Bot4Config>('/api/settings/bot4');
}

export async function updateBot4Settings(config: Bot4Config): Promise<{message: string}> {
  return apiFetch<{message: string}>('/api/settings/bot4', {
    method: 'POST',
    body: JSON.stringify(config),
  });
}

// ── Bot 6 — Stress Testing API ───────────────────

export interface RegimeSnapshot {
  regime: string;
  p_risk_on: number;
  p_neutral: number;
  p_risk_off: number;
  p_recovery: number;
  entropy: number;
  status: string;
  error?: string;
}

export async function fetchRegimeSnapshot(): Promise<RegimeSnapshot> {
  return apiFetch<RegimeSnapshot>('/api/regime/current');
}

export interface AllocationRunResult {
  run_id: string;
  markov_modifier: number;
  uncertainty_modifier: number;
  m_final: number;
  final_cash: number;
  symbol_count: number;
  error?: string;
}

export async function fetchAllocationRun(): Promise<AllocationRunResult> {
  return apiFetch<AllocationRunResult>('/api/portfolio/propose');
}

export interface MonteCarloResult {
  date: string;
  status: 'PASS' | 'WATCH' | 'REVIEW' | 'REJECT' | 'VETO';
  seed_hash: string;
  distribution_metrics: {
    [horizon: string]: {
      mean: number;
      median: number;
      pct_01: number;
      pct_05: number;
      pct_95: number;
      pct_99: number;
    }
  };
  tail_risk_metrics: {
    [horizon: string]: {
      var_95: number;
      var_99: number;
      cvar_95: number;
      cvar_99: number;
    }
  };
  loss_probabilities: {
    [horizon: string]: {
      loss: number;
      dd_10pct: number;
      dd_20pct: number;
    }
  };
  error?: string;
}

export async function triggerBot6StressTest(): Promise<{message: string; task_id: string; result?: MonteCarloResult}> {
  return apiFetch<{message: string; task_id: string; result?: MonteCarloResult}>('/trigger/bot6/stress_test', {
    method: 'POST',
  });
}

export async function fetchStressTestResult(): Promise<MonteCarloResult> {
  return apiFetch<MonteCarloResult>('/api/portfolio/stress_test');
}

// ── Bot 7 & 8 — Reporting API ───────────────────

export async function downloadDailyPdfReport(): Promise<void> {
  const res = await fetch(`${API_BASE_URL}/api/reports/daily/pdf`, {
    headers: {
      ...(ADMIN_KEY ? { 'X-Admin-Key': ADMIN_KEY } : {}),
    },
  });

  if (!res.ok) {
    let errorMsg = `API Error: ${res.status} ${res.statusText}`;
    try {
      const errBody = await res.json();
      if (errBody && errBody.detail) {
        errorMsg = Array.isArray(errBody.detail) ? errBody.detail[0].msg : errBody.detail;
      }
    } catch (e) {}
    throw new Error(errorMsg);
  }

  const blob = await res.blob();
  const url = window.URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = 'daily_portfolio_report.pdf';
  document.body.appendChild(a);
  a.click();
  a.remove();
  window.URL.revokeObjectURL(url);
}

// ── Bot 9: Model Governance & Audit ─────────────────

export interface GovernanceSummary {
  active_versions: Record<string, { version: string | null; status: string; promoted_at: string | null }>;
  latest_drift: { date: string | null; status: string; brier_score: number | null };
  recalibration: { needs_recalibration: boolean; stale_models: any[] };
  recent_events_7d: Record<string, number>;
}

export interface GovernanceEvent {
  id: number;
  event_type: string;
  model_type: string;
  model_version: string | null;
  actor: string;
  reason: string;
  evidence: any;
  previous_status: string | null;
  new_status: string | null;
  created_at: string;
}

export interface DriftReport {
  model_type: string;
  period_days: number;
  records: any[];
  summary: any;
}

export interface ModelVersion {
  id: number;
  model_type: string;
  version: string;
  status: string;
  promoted_at: string | null;
  retired_at: string | null;
  created_at: string;
}

export async function fetchGovernanceSummary(): Promise<GovernanceSummary> {
  const res = await fetch(`${API_BASE_URL}/api/v1/governance/summary`, {
    headers: { ...(ADMIN_KEY ? { 'X-Admin-Key': ADMIN_KEY } : {}) },
  });
  if (!res.ok) throw new Error(`API Error: ${res.status}`);
  return res.json();
}

export async function fetchGovernanceEvents(modelType?: string, eventType?: string, page: number = 1): Promise<{ total: number; events: GovernanceEvent[] }> {
  let url = `${API_BASE_URL}/api/v1/governance/events?page=${page}&limit=50`;
  if (modelType) url += `&model_type=${modelType}`;
  if (eventType) url += `&event_type=${eventType}`;
  
  const res = await fetch(url, {
    headers: { ...(ADMIN_KEY ? { 'X-Admin-Key': ADMIN_KEY } : {}) },
  });
  if (!res.ok) throw new Error(`API Error: ${res.status}`);
  return res.json();
}

export async function fetchDriftReport(modelType: string = "MARKOV", days: number = 30): Promise<DriftReport> {
  const res = await fetch(`${API_BASE_URL}/api/v1/governance/drift-report?model_type=${modelType}&days=${days}`, {
    headers: { ...(ADMIN_KEY ? { 'X-Admin-Key': ADMIN_KEY } : {}) },
  });
  if (!res.ok) throw new Error(`API Error: ${res.status}`);
  return res.json();
}

export async function fetchModelVersions(modelType?: string): Promise<{ versions: ModelVersion[] }> {
  const url = modelType ? `${API_BASE_URL}/api/v1/governance/versions?model_type=${modelType}` : `${API_BASE_URL}/api/v1/governance/versions`;
  const res = await fetch(url, {
    headers: { ...(ADMIN_KEY ? { 'X-Admin-Key': ADMIN_KEY } : {}) },
  });
  if (!res.ok) throw new Error(`API Error: ${res.status}`);
  return res.json();
}

export async function logGpOverride(payload: { model_type: string; decision: string; reason: string; actor: string }): Promise<any> {
  const res = await fetch(`${API_BASE_URL}/api/v1/governance/gp-override`, {
    method: 'POST',
    headers: { 
      'Content-Type': 'application/json',
      ...(ADMIN_KEY ? { 'X-Admin-Key': ADMIN_KEY } : {}) 
    },
    body: JSON.stringify(payload),
  });
  if (!res.ok) {
    const errorBody = await res.json().catch(() => ({}));
    throw new Error(errorBody.detail || `API Error: ${res.status}`);
  }
  return res.json();
}

export async function triggerRecalibration(payload: { model_type: string; actor?: string }): Promise<any> {
  const res = await fetch(`${API_BASE_URL}/api/v1/governance/recalibrate`, {
    method: 'POST',
    headers: { 
      'Content-Type': 'application/json',
      ...(ADMIN_KEY ? { 'X-Admin-Key': ADMIN_KEY } : {}) 
    },
    body: JSON.stringify(payload),
  });
  if (!res.ok) {
    const errorBody = await res.json().catch(() => ({}));
    throw new Error(errorBody.detail || `API Error: ${res.status}`);
  }
  return res.json();
}

export async function triggerBot9DriftMonitor(): Promise<TriggerResponse> {
  const res = await fetch(`${API_BASE_URL}/trigger/bot9/drift_monitor`, {
    method: 'POST',
    headers: { ...(ADMIN_KEY ? { 'X-Admin-Key': ADMIN_KEY } : {}) },
  });
  if (!res.ok) {
    const errorBody = await res.json().catch(() => ({}));
    throw new Error(errorBody.detail || `API Error: ${res.status}`);
  }
  return res.json();
}

