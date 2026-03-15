import { lazy, Suspense } from "react";
import { createFileRoute } from "@tanstack/react-router";
import { useQuery } from "@tanstack/react-query";
import { fetchChartData, fetchDashboardData, getChartGranularity } from "@/lib/api";
import { Loader2 } from "lucide-react";

const ChartFullscreen = lazy(() =>
  import("@/components/ChartFullscreen").then((m) => ({ default: m.ChartFullscreen })),
);

export const Route = createFileRoute("/chart")({
  validateSearch: (s: Record<string, unknown>) => ({
    start_date: (s.start_date as string) || undefined,
    end_date: (s.end_date as string) || undefined,
    n: s.n != null ? Number(s.n) : 24,
    chart_operator: Array.isArray(s.chart_operator)
      ? (s.chart_operator as string[])
      : s.chart_operator
        ? [String(s.chart_operator)]
        : [],
    chart_start_date: (s.chart_start_date as string) || undefined,
    chart_end_date: (s.chart_end_date as string) || undefined,
    bet_4d_big: s.bet_4d_big !== "0" && s.bet_4d_big !== "false",
    bet_4d_small: s.bet_4d_small === "1" || s.bet_4d_small === "true" || s.bet_4d_small === true,
    bet_3d_big: s.bet_3d_big !== "0" && s.bet_3d_big !== "false",
    bet_3d_small: s.bet_3d_small === "1" || s.bet_3d_small === "true" || s.bet_3d_small === true,
  }),
  component: ChartPage,
});

function ChartPage() {
  const { start_date, end_date, n, chart_operator, chart_start_date, chart_end_date, bet_4d_big, bet_4d_small, bet_3d_big, bet_3d_small } = Route.useSearch();

  const chartRangeStart = chart_start_date ?? start_date ?? "";
  const chartRangeEnd = chart_end_date ?? end_date ?? "";
  const granularity = chartRangeStart && chartRangeEnd ? getChartGranularity(chartRangeStart, chartRangeEnd) : "month";

  const { data: metaData } = useQuery({
    queryKey: ["dashboard-meta"],
    queryFn: () => fetchDashboardData({}),
  });

  const { data: chartData, isLoading } = useQuery({
    queryKey: ["chart", start_date, end_date, n, chart_operator, granularity, chart_start_date, chart_end_date],
    queryFn: () =>
      fetchChartData({
        start_date,
        end_date,
        n,
        chart_operator: chart_operator ?? [],
        granularity,
        chart_start_date: chart_start_date || undefined,
        chart_end_date: chart_end_date || undefined,
      }),
  });

  return (
    <Suspense
      fallback={
        <div
          className="anim-loading flex min-h-[50vh] items-center justify-center gap-2 text-sm text-muted-foreground"
          aria-busy="true"
          aria-live="polite"
          aria-label="Loading chart"
        >
          <Loader2 className="size-4 animate-spin" aria-hidden />
          <span>Loading chart…</span>
        </div>
      }
    >
      <ChartFullscreen
        chartData={chartData}
        isLoading={isLoading}
        operators={metaData?.operators ?? []}
        searchParams={{
          start_date,
          end_date,
          n,
          chart_operator,
          chart_start_date,
          chart_end_date,
          bet_4d_big: bet_4d_big ?? true,
          bet_4d_small: bet_4d_small ?? false,
          bet_3d_big: bet_3d_big ?? true,
          bet_3d_small: bet_3d_small ?? false,
        }}
      />
    </Suspense>
  );
}
