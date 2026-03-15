const API_BASE = import.meta.env.VITE_API_BASE_URL ?? "";

export interface OperatorData {
  name: string;
  draws: number;
  top24: string[];
  top24_profit: number;
  top24_profit_fmt: string;
  top24_winnings: number;
  top24_winnings_fmt: string;
  top24_cost: number;
  top24_cost_fmt: string;
  error?: string;
}

export interface AllOperatorsData {
  draws: number;
  top24: string[];
  top24_profit: number;
  top24_profit_fmt: string;
  top24_winnings_fmt: string;
  top24_cost_fmt: string;
  error?: string;
}

export interface DashboardData {
  has_data: boolean;
  operators: OperatorData[];
  all_operators: AllOperatorsData | null;
}

export type BetTypeKey = "4d_big" | "4d_small" | "3d_big" | "3d_small";

export interface ApiDataResponse {
  data: DashboardData | null;
  date_min_csv: string;
  date_max_csv: string;
  operators: string[];
  top_numbers_with_counts: [string, number][] | null;
  /** Chart for "All operators" – avoids separate /api/chart request on initial load */
  chart_data?: ChartApiResponse | null;
  start_date: string;
  end_date: string;
  n: number;
  /** Selected bet types (e.g. ["4d_big", "3d_big"]). Cost per number = RM1 × length. */
  bet_types?: string[];
}

export interface ChartDataset {
  number: string;
  counts: number[];
}

export type ChartGranularity = "year" | "month" | "day";

export interface ChartApiResponse {
  labels: string[];
  datasets: ChartDataset[];
  filter_label: string;
  all_months?: string[];
  granularity?: ChartGranularity;
}

/** Compact response: l=labels, n=numbers, d=base64(matrix), f=filter_label, g=granularity */
interface ChartCompactResponse {
  l: string[];
  n: string[];
  d: string;
  f: string;
  g?: string;
}

function isCompactChartResponse(
  raw: ChartApiResponse | ChartCompactResponse
): raw is ChartCompactResponse {
  return "l" in raw && "n" in raw && "d" in raw;
}

function decodeCompactChart(raw: ChartCompactResponse): ChartApiResponse {
  const labels = raw.l ?? [];
  const numbers = raw.n ?? [];
  const granularity = (raw.g === "year" || raw.g === "month" || raw.g === "day" ? raw.g : undefined) as ChartGranularity | undefined;
  if (labels.length === 0 || numbers.length === 0 || !raw.d) {
    return { labels, datasets: [], filter_label: raw.f ?? "All operators", granularity };
  }
  const bin = atob(raw.d);
  const bytes = new Uint8Array(bin.length);
  for (let i = 0; i < bin.length; i++) bytes[i] = bin.charCodeAt(i);
  const view = new DataView(bytes.buffer);
  const cols = labels.length;
  const datasets: ChartDataset[] = [];
  for (let r = 0; r < numbers.length; r++) {
    const counts: number[] = [];
    for (let c = 0; c < cols; c++) {
      const offset = (r * cols + c) * 2;
      counts.push(offset + 2 <= view.byteLength ? view.getUint16(offset, true) : 0);
    }
    datasets.push({ number: numbers[r], counts });
  }
  return { labels, datasets, filter_label: raw.f ?? "All operators", granularity };
}

export interface BetTypeFlags {
  bet_4d_big?: boolean;
  bet_4d_small?: boolean;
  bet_3d_big?: boolean;
  bet_3d_small?: boolean;
}

export async function fetchDashboardData(params: {
  start_date?: string;
  end_date?: string;
  n?: number;
  bet_4d_big?: boolean;
  bet_4d_small?: boolean;
  bet_3d_big?: boolean;
  bet_3d_small?: boolean;
}): Promise<ApiDataResponse> {
  const search = new URLSearchParams();
  if (params.start_date) search.set("start_date", params.start_date);
  if (params.end_date) search.set("end_date", params.end_date);
  if (params.n != null) search.set("n", String(params.n));
  if (params.bet_4d_big) search.set("bet_4d_big", "1");
  if (params.bet_4d_small) search.set("bet_4d_small", "1");
  if (params.bet_3d_big) search.set("bet_3d_big", "1");
  if (params.bet_3d_small) search.set("bet_3d_small", "1");
  const res = await fetch(`${API_BASE}/api/data?${search}`);
  if (!res.ok) throw new Error(res.statusText);
  return res.json();
}

export interface LatestDraw {
  date: string;
  operator: string;
  draw_no: string;
  "1st": string;
  "2nd": string;
  "3rd": string;
  special: string[];
  consolation: string[];
}

export interface LatestDrawsResponse {
  draws: LatestDraw[];
}

export async function fetchLatestDraws(): Promise<LatestDrawsResponse> {
  const res = await fetch(`${API_BASE}/api/latest-draws`);
  if (!res.ok) throw new Error(res.statusText);
  return res.json();
}

export interface DrawDatesResponse {
  dates: string[];
}

export async function fetchDrawDates(): Promise<DrawDatesResponse> {
  const res = await fetch(`${API_BASE}/api/draw-dates`);
  if (!res.ok) throw new Error(res.statusText);
  return res.json();
}

export async function fetchDrawsForDate(date: string): Promise<LatestDrawsResponse> {
  const res = await fetch(`${API_BASE}/api/draws?date=${encodeURIComponent(date)}`);
  if (!res.ok) throw new Error(res.statusText);
  return res.json();
}

export async function fetchChartData(params: {
  start_date?: string;
  end_date?: string;
  n?: number;
  chart_operator?: string[];
  chart_start_month?: string;
  chart_end_month?: string;
  initial_months?: number;
  granularity?: ChartGranularity;
  chart_start_date?: string;
  chart_end_date?: string;
}): Promise<ChartApiResponse> {
  const search = new URLSearchParams();
  if (params.start_date) search.set("start_date", params.start_date);
  if (params.end_date) search.set("end_date", params.end_date);
  if (params.n != null) search.set("n", String(params.n));
  (params.chart_operator ?? []).forEach((o) => search.append("chart_operator", o));
  if (params.chart_start_month) search.set("chart_start_month", params.chart_start_month);
  if (params.chart_end_month) search.set("chart_end_month", params.chart_end_month);
  if (params.initial_months != null) search.set("initial_months", String(params.initial_months));
  if (params.granularity) search.set("granularity", params.granularity);
  if (params.chart_start_date) search.set("chart_start_date", params.chart_start_date);
  if (params.chart_end_date) search.set("chart_end_date", params.chart_end_date);
  const res = await fetch(`${API_BASE}/api/chart?${search}`);
  if (!res.ok) throw new Error(res.statusText);
  const raw = await res.json();
  if (isCompactChartResponse(raw)) return decodeCompactChart(raw);
  return raw as ChartApiResponse;
}

/** Derive chart granularity from date range: >5 years → year, <12 months → day, else month. */
export function getChartGranularity(startDate: string, endDate: string): ChartGranularity {
  const start = new Date(startDate);
  const end = new Date(endDate);
  const months = (end.getFullYear() - start.getFullYear()) * 12 + (end.getMonth() - start.getMonth()) + 1;
  if (months > 60) return "year";
  if (months < 12) return "day";
  return "month";
}

// ── Tools API ───────────────────────────────────────────────────────────────

export interface Hit4D {
  date: string;
  operator: string;
  draw: string;
  number: string;
  prize: string;
  prize_value: number;
}

export interface Hit3D {
  date: string;
  operator: string;
  draw: string;
  your_number: string;
  tail3: string;
  matched: string;
  prize: string;
  prize_value: number;
}

export interface NumberSummary {
  number: string;
  hits_4d: number;
  hits_3d: number;
  total_won_4d: number;
  total_won_3d: number;
}

export interface CheckNumbersResponse {
  hits_4d: Hit4D[];
  hits_3d: Hit3D[];
  summary: NumberSummary[];
  since_date: string;
}

export async function checkNumbers(params: {
  numbers: string[];
  since_date: string;
  include_3d?: boolean;
}): Promise<CheckNumbersResponse> {
  const res = await fetch(`${API_BASE}/api/tools/check-numbers`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ numbers: params.numbers, since_date: params.since_date, include_3d: params.include_3d ?? true }),
  });
  if (!res.ok) throw new Error(res.statusText);
  return res.json();
}

export interface NumberGapStats {
  number: string;
  total_wins: number;
  first_win: string | null;
  last_win: string | null;
  avg_gap: number | null;
  min_gap: number | null;
  max_gap: number | null;
  days_since_last: number | null;
}

export interface CombinedGap {
  win_days: number;
  max_gap: number;
  avg_gap: number;
  min_gap: number;
  days_since_last: number | null;
}

export interface GapAnalysisResponse {
  per_number: NumberGapStats[];
  combined: CombinedGap | Record<string, never>;
}

export async function gapAnalysis(params: {
  numbers: string[];
}): Promise<GapAnalysisResponse> {
  const res = await fetch(`${API_BASE}/api/tools/gap-analysis`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ numbers: params.numbers }),
  });
  if (!res.ok) throw new Error(res.statusText);
  return res.json();
}

export interface OptimizeSetResult {
  profit: number;
  max_gap: number;
  avg_gap: number;
  numbers: string[];
}

export interface OptimizeResponse {
  n: number;
  n_draws: number;
  date_from: string;
  date_to: string;
  prize_mode: string;
  top_n: OptimizeSetResult;
  greedy: OptimizeSetResult;
  error?: string;
}

export async function optimizeNumbers(params: {
  n: number;
  pool?: number;
  penalty?: number;
  prize_mode?: "full" | "top3" | "4d_only";
}): Promise<OptimizeResponse> {
  const res = await fetch(`${API_BASE}/api/tools/optimize`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      n: params.n,
      pool: params.pool ?? 300,
      penalty: params.penalty ?? 15,
      prize_mode: params.prize_mode ?? "full",
    }),
  });
  if (!res.ok) throw new Error(res.statusText);
  return res.json();
}
