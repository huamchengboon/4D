import { Link, useNavigate } from "@tanstack/react-router";
import { AlertTriangle, ChartColumnIncreasing, Maximize2 } from "lucide-react";
import type { ApiDataResponse, ChartApiResponse } from "@/lib/api";
import { Filters } from "./Filters";
import { WinsChart } from "./WinsChart";
import { SlipCard } from "./SlipCard";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

// TYPES & INTERFACES
interface DashboardProps {
  applied: boolean;
  dashboardData: ApiDataResponse | undefined;
  chartData: ChartApiResponse | undefined;
  isChartFetching?: boolean;
  isLoading: boolean;
  error: Error | null;
  onRetry?: () => void;
  searchParams: {
    start_date?: string;
    end_date?: string;
    n: number;
    chart_operator: string[];
    chart_start_date?: string;
    chart_end_date?: string;
    bet_4d_big?: boolean;
    bet_4d_small?: boolean;
    bet_3d_big?: boolean;
    bet_3d_small?: boolean;
  };
}

// CONSTANTS & DATA
const PAGE_TITLE = "4D Strategy";
const PAGE_SUBTITLE = "Set date range and bet types, then Apply.";
const loadingRows = ["", "", ""];

const OPERATOR_ACCENT: Record<string, { header: string; accent: string; logo: string }> = {
  "Magnum 4D":      { header: "bg-[var(--operator-magnum-header)]",  accent: "var(--operator-magnum-header)",  logo: "M" },
  "Da Ma Cai 1+3D": { header: "bg-[var(--operator-damacai-header)]", accent: "var(--operator-damacai-header)", logo: "D" },
  "Sports Toto 4D": { header: "bg-[var(--operator-toto-header)]",    accent: "var(--operator-toto-header)",    logo: "T" },
};
const DEFAULT_ACCENT = { header: "bg-muted", accent: "var(--border)", logo: "?" };

// COMPONENT DEFINITION
export function Dashboard({
  applied,
  dashboardData,
  chartData,
  isChartFetching = false,
  isLoading,
  error,
  onRetry,
  searchParams,
}: DashboardProps) {
  // HOOKS
  const navigate = useNavigate();
  const { start_date, end_date, n, chart_operator, chart_start_date, chart_end_date, bet_4d_big, bet_4d_small, bet_3d_big, bet_3d_small } = searchParams;
  const betLabels: string[] = [];
  if (bet_4d_big) betLabels.push("4D Big");
  if (bet_4d_small) betLabels.push("4D Small");
  if (bet_3d_big) betLabels.push("3D Big");
  if (bet_3d_small) betLabels.push("3D Small");
  const betSummary = betLabels.length > 0 ? betLabels.join(" + ") : "4D Big + 3D Big";
  const data = dashboardData?.data;
  const operators = dashboardData?.operators ?? [];
  const dateMin = dashboardData?.date_min_csv ?? "";
  const dateMax = dashboardData?.date_max_csv ?? "";
  const topNumbersWithCounts = dashboardData?.top_numbers_with_counts;

  // EFFECTS
  // No side-effects required in this view.

  // HELPERS
  const getProfitClassName = (value: number) =>
    value >= 0 ? "profit" : "loss";

  // EVENT HANDLERS
  const baseSearch = () => ({
    start_date,
    end_date,
    n,
    chart_operator,
    bet_4d_big: bet_4d_big ?? true,
    bet_4d_small: bet_4d_small ?? false,
    bet_3d_big: bet_3d_big ?? true,
    bet_3d_small: bet_3d_small ?? false,
  });
  const handleChartDrillDown = (rangeStart: string, rangeEnd: string) => {
    navigate({ to: "/", search: { ...baseSearch(), chart_start_date: rangeStart, chart_end_date: rangeEnd } });
  };
  const handleChartShowFullRange = () => {
    navigate({ to: "/", search: { ...baseSearch(), chart_start_date: undefined, chart_end_date: undefined } });
  };

  // EARLY RETURNS
  if (error) {
    return (
      <div className="mx-auto w-full max-w-6xl px-4 py-6 md:px-6 md:py-10">
        <Card className="border-2 border-destructive/50 bg-destructive/5">
          <CardHeader className="flex-row items-center gap-3 space-y-0">
            <AlertTriangle className="size-6 shrink-0 text-destructive" />
            <CardTitle className="font-display text-xl font-bold">Unable to load dashboard</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            <p className="text-sm text-destructive">{error.message}</p>
            {onRetry && (
              <button
                type="button"
                onClick={onRetry}
                className="rounded-md border border-destructive/50 bg-destructive/10 px-3 py-1.5 text-sm font-medium text-destructive transition-colors hover:bg-destructive/20 focus:outline-none focus:ring-2 focus:ring-ring"
              >
                Try again
              </button>
            )}
          </CardContent>
        </Card>
      </div>
    );
  }

  if (!applied) {
    return (
      <div className="mx-auto w-full max-w-6xl space-y-6 px-4 py-6 md:px-6 md:py-8">
        <header className="space-y-2">
          <h1 className="font-display text-2xl font-semibold tracking-tight text-foreground md:text-3xl">{PAGE_TITLE}</h1>
          <p className="max-w-2xl text-sm leading-relaxed text-muted-foreground md:text-base">
            {PAGE_SUBTITLE}
          </p>
        </header>
        <Filters
          startDate={start_date ?? ""}
          endDate={end_date ?? ""}
          n={n}
          dateMin={dateMin}
          dateMax={dateMax}
          chartOperator={chart_operator}
          bet4dBig={bet_4d_big ?? true}
          bet4dSmall={bet_4d_small ?? false}
          bet3dBig={bet_3d_big ?? true}
          bet3dSmall={bet_3d_small ?? false}
        />
      </div>
    );
  }

  if (isLoading || !dashboardData) {
    return (
      <div className="mx-auto w-full max-w-6xl space-y-6 px-4 py-6 md:px-6 md:py-8">
        <div className="space-y-2">
          <h1 className="font-display text-2xl font-semibold tracking-tight md:text-3xl">{PAGE_TITLE}</h1>
          <p className="max-w-2xl text-sm leading-relaxed text-muted-foreground md:text-base">
            Using your selected bet types.
          </p>
        </div>
        <Card className="border-border/70">
          <CardContent className="space-y-4 pt-6" aria-live="polite">
            {loadingRows.map((_, idx) => (
              <div key={`loading-row-${idx}`} className="h-6 animate-pulse rounded-md bg-muted/70" aria-hidden />
            ))}
            <p className="muted">Crunching historical results…</p>
          </CardContent>
        </Card>
      </div>
    );
  }

  if (!data?.has_data) {
    return (
      <div className="mx-auto w-full max-w-6xl px-4 py-6 md:px-6 md:py-8">
        <h1 className="font-display text-2xl font-semibold tracking-tight text-foreground md:text-3xl">Strategy</h1>
        <Card className="mt-4 border-[var(--warning)]/60 bg-[var(--warning)]/10">
          <CardHeader>
            <CardTitle className="text-lg">No historical data detected</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-sm text-[var(--warning-foreground)]/90">
              Ensure <code>4d_history.csv</code> exists in the project root and has valid rows.
            </p>
          </CardContent>
        </Card>
      </div>
    );
  }

  // RENDER LOGIC
  const allOp = data.all_operators;
  const successfulOperators = data.operators.filter((op) => !op.error);

  // RENDER
  return (
    <div className="mx-auto w-full max-w-6xl space-y-6 px-4 py-6 md:px-6 md:py-8">
      <header className="space-y-2">
        <h1 className="font-display text-2xl font-semibold tracking-tight text-foreground md:text-3xl">
          {PAGE_TITLE}
        </h1>
        <p className="max-w-2xl text-sm leading-relaxed text-muted-foreground md:text-base">
          {PAGE_SUBTITLE}
        </p>
      </header>

      <Filters
        startDate={start_date ?? dateMin}
        endDate={end_date ?? dateMax}
        n={n}
        dateMin={dateMin}
        dateMax={dateMax}
        chartOperator={chart_operator}
        bet4dBig={bet_4d_big ?? true}
        bet4dSmall={bet_4d_small ?? false}
        bet3dBig={bet_3d_big ?? true}
        bet3dSmall={bet_3d_small ?? false}
        operatorCount={operators.length || 3}
      />

      {allOp && !allOp.error && (() => {
        const profitPositive = allOp.top24_profit >= 0;
        const roi = allOp.top24_cost_fmt
          ? ((allOp.top24_profit / (parseFloat(allOp.top24_cost_fmt.replace(/,/g, "")) || 1)) * 100)
          : null;
        const numbersData = topNumbersWithCounts ?? allOp.top24.map((num) => [num, 0] as [string, number]);
        const maxCount = topNumbersWithCounts
          ? Math.max(...topNumbersWithCounts.map(([, c]) => c), 1)
          : 1;

        return (
          <section
            className="anim-result rounded-xl border border-border/60 bg-card shadow-sm"
            style={{ animationDelay: "200ms" }}
          >
            {/* Profit hero strip */}
            <div className="flex flex-wrap items-end gap-x-6 gap-y-3 px-4 pt-4 pb-3 md:px-5">
              <div className="min-w-0">
                <p className="text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">
                  Net profit · Top {n} across all operators
                </p>
                <p className={`font-display text-2xl font-bold tabular-nums leading-tight sm:text-3xl ${getProfitClassName(allOp.top24_profit)}`}>
                  {profitPositive ? "+" : ""}{allOp.top24_profit_fmt} <span className="text-base font-semibold">RM</span>
                </p>
              </div>
              {roi !== null && (
                <span className={`mb-0.5 rounded-full border px-2 py-0.5 text-[11px] font-bold tabular-nums ${
                  profitPositive
                    ? "border-[var(--success)]/30 bg-[var(--success)]/10 text-[var(--success)]"
                    : "border-destructive/30 bg-destructive/10 text-destructive"
                }`}>
                  {profitPositive ? "+" : ""}{roi.toFixed(1)}% ROI
                </span>
              )}
            </div>

            {/* Financial breakdown strip */}
            <div className="flex flex-wrap items-center gap-x-4 gap-y-1.5 border-t border-border/50 bg-muted/8 px-4 py-2.5 md:px-5">
              <div className="flex items-center gap-1.5">
                <span className="inline-block size-1.5 rounded-full bg-[var(--success)]" aria-hidden />
                <span className="text-[11px] text-muted-foreground">Winnings</span>
                <span className="text-xs font-semibold tabular-nums text-foreground">{allOp.top24_winnings_fmt} RM</span>
              </div>
              <span className="h-3 w-px bg-border" aria-hidden />
              <div className="flex items-center gap-1.5">
                <span className="inline-block size-1.5 rounded-full bg-destructive/70" aria-hidden />
                <span className="text-[11px] text-muted-foreground">Cost</span>
                <span className="text-xs font-semibold tabular-nums text-foreground">{allOp.top24_cost_fmt} RM</span>
              </div>
              <span className="h-3 w-px bg-border" aria-hidden />
              <div className="flex items-center gap-1.5">
                <span className="text-[11px] text-muted-foreground">Draws</span>
                <span className="text-xs font-semibold tabular-nums text-foreground">{allOp.draws.toLocaleString()}</span>
              </div>
              <span className="h-3 w-px bg-border" aria-hidden />
              <div className="flex items-center gap-1.5">
                <span className="text-[11px] text-muted-foreground">Bet</span>
                <span className="text-xs font-semibold text-foreground">{betSummary}</span>
              </div>
            </div>

            {/* Numbers grid with win-frequency bars */}
            <div className="border-t border-border/50 px-4 py-3 md:px-5">
              <p className="mb-2 text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">
                Top {n} numbers {topNumbersWithCounts ? "· win frequency" : ""}
              </p>
              <div className="flex flex-wrap gap-1.5">
                {numbersData.map(([num, count], chipIdx) => {
                  const barWidth = topNumbersWithCounts ? Math.max(8, (count / maxCount) * 100) : 0;
                  return (
                    <span
                      key={`all-${num}`}
                      className="anim-row group relative rounded-md border border-border/70 bg-background/80 font-mono text-xs tabular-nums"
                      style={{ animationDelay: `${chipIdx * 18}ms` }}
                      title={topNumbersWithCounts ? `${num}: won ${count} time${count !== 1 ? "s" : ""}` : num}
                    >
                      {topNumbersWithCounts && (
                        <span
                          className="absolute inset-0 rounded-[inherit] bg-[var(--success)]/8 transition-all"
                          style={{ width: `${barWidth}%` }}
                          aria-hidden
                        />
                      )}
                      <span className="relative z-10 inline-flex items-center gap-1 px-2 py-0.5">
                        {num}
                        {topNumbersWithCounts && (
                          <span className="text-[10px] text-muted-foreground/70">{count}</span>
                        )}
                      </span>
                    </span>
                  );
                })}
              </div>
            </div>
          </section>
        );
      })()}

      {(() => {
        const rankedOps = successfulOperators
          .map((op) => {
            const roi = op.top24_cost > 0 ? (op.top24_profit / op.top24_cost) * 100 : 0;
            const profitPerDraw = op.draws > 0 ? op.top24_profit / op.draws : 0;
            return { ...op, roi, profitPerDraw };
          })
          .sort((a, b) => b.top24_profit - a.top24_profit);

        const bestProfit = rankedOps[0]?.top24_profit ?? 0;
        const worstProfit = rankedOps[rankedOps.length - 1]?.top24_profit ?? 0;
        const profitSpread = Math.max(Math.abs(bestProfit), Math.abs(worstProfit), 1);

        return (
          <section className="space-y-3">
            <div className="flex items-end justify-between gap-4">
              <div>
                <h2 className="font-display text-xl font-semibold tracking-tight md:text-2xl">Operator playbooks</h2>
                <p className="mt-0.5 text-xs text-muted-foreground">
                  Head-to-head Top-{n} performance · ranked by profit
                </p>
              </div>
              <div className="flex items-center gap-3 text-[10px] uppercase tracking-wider text-muted-foreground">
                <span className="flex items-center gap-1"><span className="inline-block size-2 rounded-full bg-[var(--success)]" />Profit</span>
                <span className="flex items-center gap-1"><span className="inline-block size-2 rounded-full bg-destructive/70" />Loss</span>
              </div>
            </div>

            <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
              {data.operators.map((rawOp, opIdx) => {
                if (rawOp.error) {
                  return (
                    <div key={rawOp.name} className="anim-result rounded-xl border border-destructive/40 bg-destructive/5 p-4" style={{ animationDelay: `${opIdx * 80}ms` }}>
                      <p className="font-display text-sm font-semibold">{rawOp.name}</p>
                      <p className="mt-1 text-xs loss">Error: {rawOp.error}</p>
                    </div>
                  );
                }

                const op = rankedOps.find((r) => r.name === rawOp.name)!;
                const rank = rankedOps.indexOf(op) + 1;
                const isBest = rank === 1;
                const profitPositive = op.top24_profit >= 0;
                const barPct = Math.min(100, Math.max(4, (Math.abs(op.top24_profit) / profitSpread) * 100));
                const opTheme = OPERATOR_ACCENT[op.name] ?? DEFAULT_ACCENT;

                return (
                  <SlipCard
                    key={op.name}
                    accent={opTheme.accent}
                    className="anim-result"
                    style={{ animationDelay: `${opIdx * 80}ms` }}
                  >
                    {/* Operator header band */}
                    <div className={`slip-header ${opTheme.header}`}>
                      <div className="flex items-center gap-2">
                        <span className="slip-logo-badge">{opTheme.logo}</span>
                        <span className="text-sm font-extrabold uppercase tracking-wide">{op.name}</span>
                      </div>
                      <span className="text-[10px] font-semibold text-white/80">#{rank}</span>
                    </div>

                    {/* Rank + ROI sub-strip */}
                    <div className="relative z-1 flex items-center justify-between px-3 pt-2.5 pb-1.5">
                      <span className={`flex size-6 shrink-0 items-center justify-center rounded text-[11px] font-bold ${
                        isBest
                          ? "bg-[var(--success)]/15 text-[var(--success)]"
                          : "bg-muted text-muted-foreground"
                      }`}>
                        {rank}
                      </span>
                      <span className={`shrink-0 rounded-full border px-1.5 py-px text-[10px] font-bold tabular-nums ${
                        profitPositive
                          ? "border-[var(--success)]/30 bg-[var(--success)]/8 text-[var(--success)]"
                          : "border-destructive/30 bg-destructive/8 text-destructive"
                      }`}>
                        {profitPositive ? "+" : ""}{op.roi.toFixed(1)}% ROI
                      </span>
                    </div>

                    {/* Profit bar */}
                    <div className="relative z-1 px-3 pb-2">
                      <div className="flex items-center gap-2">
                        <div className="relative h-2 flex-1 rounded-full bg-muted/60">
                          <div
                            className={`absolute inset-y-0 left-0 rounded-full transition-all ${
                              profitPositive ? "bg-[var(--success)]/50" : "bg-destructive/40"
                            }`}
                            style={{ width: `${barPct}%` }}
                          />
                        </div>
                        <span className={`shrink-0 text-sm font-bold tabular-nums ${getProfitClassName(op.top24_profit)}`}>
                          {profitPositive ? "+" : ""}{op.top24_profit_fmt}
                        </span>
                      </div>
                    </div>

                    {/* Stats row */}
                    <div className="slip-section-divider mx-3" />
                    <div className="relative z-1 flex items-center">
                      <div className="flex-1 px-3 py-1.5 text-center">
                        <p className="text-[10px] uppercase tracking-wider text-muted-foreground">Won</p>
                        <p className="text-xs font-semibold tabular-nums">{op.top24_winnings_fmt}</p>
                      </div>
                      <span className="h-5 w-px bg-border/50" aria-hidden />
                      <div className="flex-1 px-3 py-1.5 text-center">
                        <p className="text-[10px] uppercase tracking-wider text-muted-foreground">Cost</p>
                        <p className="text-xs font-semibold tabular-nums">{op.top24_cost_fmt}</p>
                      </div>
                      <span className="h-5 w-px bg-border/50" aria-hidden />
                      <div className="flex-1 px-3 py-1.5 text-center">
                        <p className="text-[10px] uppercase tracking-wider text-muted-foreground">Draws</p>
                        <p className="text-xs font-semibold tabular-nums">{op.draws.toLocaleString()}</p>
                      </div>
                      <span className="h-5 w-px bg-border/50" aria-hidden />
                      <div className="flex-1 px-3 py-1.5 text-center">
                        <p className="text-[10px] uppercase tracking-wider text-muted-foreground">Per draw</p>
                        <p className={`text-xs font-semibold tabular-nums ${getProfitClassName(op.profitPerDraw)}`}>
                          {op.profitPerDraw >= 0 ? "+" : ""}{op.profitPerDraw.toFixed(2)}
                        </p>
                      </div>
                    </div>

                    {/* Numbers */}
                    <div className="slip-section-divider mx-3" />
                    <div className="relative z-1 px-3 pb-2.5 pt-1.5">
                      <p className="mb-1.5 text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
                        Top {n} numbers
                      </p>
                      <div className="flex flex-wrap gap-1.5">
                        {op.top24.map((num, numIdx) => (
                          <span
                            key={`${op.name}-${num}`}
                            className="anim-row rounded border border-border/60 bg-background/80 px-1.5 py-px font-mono text-[11px] tabular-nums"
                            style={{ animationDelay: `${opIdx * 80 + numIdx * 12}ms` }}
                          >
                            {num}
                          </span>
                        ))}
                      </div>
                    </div>
                  </SlipCard>
                );
              })}
            </div>
          </section>
        );
      })()}

      {(chartData?.datasets?.length || (chart_operator?.length && isChartFetching)) ? (
        <section className="anim-result rounded-xl border border-border/60 bg-card shadow-sm" style={{ animationDelay: "350ms" }}>
          {/* Chart toolbar */}
          <div className="flex flex-wrap items-center justify-between gap-2 px-4 py-2.5 md:px-5">
            <div className="flex items-center gap-2">
              <ChartColumnIncreasing className="size-4 text-muted-foreground" />
              <h2 className="font-display text-sm font-semibold tracking-tight">
                Wins over time
              </h2>
              {chart_start_date && chart_end_date && (
                <span className="rounded-full border border-border bg-muted/40 px-2 py-px text-[10px] tabular-nums text-muted-foreground">
                  {chart_start_date} → {chart_end_date}
                </span>
              )}
              {isChartFetching && (
                <span className="size-3 animate-spin rounded-full border-2 border-muted-foreground/30 border-t-primary" aria-label="Loading" />
              )}
            </div>
            <div className="flex items-center gap-1.5">
              {chart_start_date && chart_end_date && (
                <button
                  type="button"
                  onClick={handleChartShowFullRange}
                  className="rounded-full border border-border bg-muted/30 px-2.5 py-0.5 text-[11px] font-medium text-muted-foreground transition-colors hover:bg-muted/60 hover:text-foreground"
                >
                  Reset zoom
                </button>
              )}
              <Link
                to="/chart"
                search={{
                  start_date,
                  end_date,
                  n,
                  chart_operator,
                  chart_start_date: chart_start_date ?? undefined,
                  chart_end_date: chart_end_date ?? undefined,
                  bet_4d_big: bet_4d_big ?? true,
                  bet_4d_small: bet_4d_small ?? false,
                  bet_3d_big: bet_3d_big ?? true,
                  bet_3d_small: bet_3d_small ?? false,
                }}
                className="inline-flex items-center gap-1 rounded-full border border-border bg-muted/30 px-2.5 py-0.5 text-[11px] font-medium text-muted-foreground transition-colors hover:bg-muted/60 hover:text-foreground"
                target="_blank"
                rel="noopener noreferrer"
                title="Open fullscreen chart"
              >
                <Maximize2 className="size-3" />
                Expand
              </Link>
            </div>
          </div>

          {/* Chart canvas */}
          {chartData?.datasets?.length ? (
            <div className="border-t border-border/50 px-2 pb-3 pt-1 md:px-3">
              <WinsChart
                chartData={chartData}
                operators={operators}
                chartOperatorsSelected={chart_operator ?? []}
                startDate={start_date ?? dateMin}
                endDate={end_date ?? dateMax}
                n={n}
                chartStartDate={chart_start_date}
                chartEndDate={chart_end_date}
                bet4dBig={bet_4d_big ?? true}
                bet4dSmall={bet_4d_small ?? false}
                bet3dBig={bet_3d_big ?? true}
                bet3dSmall={bet_3d_small ?? false}
                onDrillDown={handleChartDrillDown}
                onShowFullRange={handleChartShowFullRange}
              />
            </div>
          ) : (
            <div
              className="flex min-h-[200px] items-center justify-center border-t border-border/50 text-sm text-muted-foreground"
              aria-busy="true"
              aria-live="polite"
              aria-label="Loading chart"
            >
              <span className="flex items-center gap-2">
                <span className="size-4 animate-spin rounded-full border-2 border-muted-foreground/30 border-t-primary" />
                Loading chart…
              </span>
            </div>
          )}
        </section>
      ) : null}
    </div>
  );
}
