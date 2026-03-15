import { useEffect } from "react";
import { createFileRoute } from "@tanstack/react-router";
import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { fetchDashboardData, fetchChartData, getChartGranularity } from "@/lib/api";
import { Dashboard } from "@/components/Dashboard";

const STRATEGY_SEARCH_KEY = "4d-strategy-search";

export const Route = createFileRoute("/")({
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
    bet_4d_big: s.bet_4d_big !== false && s.bet_4d_big !== "0" && s.bet_4d_big !== "false",
    bet_4d_small: s.bet_4d_small === "1" || s.bet_4d_small === "true" || s.bet_4d_small === true,
    bet_3d_big: s.bet_3d_big !== false && s.bet_3d_big !== "0" && s.bet_3d_big !== "false",
    bet_3d_small: s.bet_3d_small === "1" || s.bet_3d_small === "true" || s.bet_3d_small === true,
  }),
  component: IndexPage,
});

function IndexPage() {
  const { start_date, end_date, n, chart_operator, chart_start_date, chart_end_date, bet_4d_big, bet_4d_small, bet_3d_big, bet_3d_small } = Route.useSearch();

  const applied = !!(start_date && end_date);
  const hasBetType = bet_4d_big || bet_4d_small || bet_3d_big || bet_3d_small;
  const effectiveBet4dBig = hasBetType ? bet_4d_big : true;
  const effectiveBet3dBig = hasBetType ? bet_3d_big : true;

  const chartRangeStart = chart_start_date ?? start_date ?? "";
  const chartRangeEnd = chart_end_date ?? end_date ?? "";
  const granularity = applied && chartRangeStart && chartRangeEnd ? getChartGranularity(chartRangeStart, chartRangeEnd) : "month";

  const { data: dashboardData, isLoading, error, refetch } = useQuery({
    queryKey: ["dashboard", start_date, end_date, n, effectiveBet4dBig, bet_4d_small, effectiveBet3dBig, bet_3d_small],
    queryFn: () =>
      fetchDashboardData({
        start_date,
        end_date,
        n,
        bet_4d_big: effectiveBet4dBig,
        bet_4d_small: bet_4d_small ?? false,
        bet_3d_big: effectiveBet3dBig,
        bet_3d_small: bet_3d_small ?? false,
      }),
    enabled: applied,
    refetchInterval: applied ? 120_000 : false,
  });

  const chartEnabled =
    !!dashboardData?.data?.has_data &&
    !!dashboardData?.data?.all_operators &&
    !dashboardData?.data?.all_operators?.error;

  const { data: chartData, isFetching: isChartFetching } = useQuery({
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
    enabled: chartEnabled,
    refetchInterval: chartEnabled ? 120_000 : false,
    placeholderData: keepPreviousData,
  });

  const effectiveChartData = chartData ?? dashboardData?.chart_data ?? undefined;

  useEffect(() => {
    if (!applied || !start_date || !end_date) return;
    try {
      sessionStorage.setItem(
        STRATEGY_SEARCH_KEY,
        JSON.stringify({
          start_date,
          end_date,
          n,
          chart_operator: chart_operator ?? [],
          chart_start_date: chart_start_date ?? undefined,
          chart_end_date: chart_end_date ?? undefined,
          bet_4d_big: effectiveBet4dBig,
          bet_4d_small: bet_4d_small ?? false,
          bet_3d_big: effectiveBet3dBig,
          bet_3d_small: bet_3d_small ?? false,
        })
      );
    } catch {
      // ignore
    }
  }, [applied, start_date, end_date, n, chart_operator, chart_start_date, chart_end_date, effectiveBet4dBig, bet_4d_small, effectiveBet3dBig, bet_3d_small]);

  return (
    <Dashboard
      applied={applied}
      dashboardData={dashboardData}
      chartData={effectiveChartData}
      isChartFetching={chartEnabled ? isChartFetching : false}
      isLoading={isLoading}
      error={error}
      onRetry={() => refetch()}
      searchParams={{
        start_date,
        end_date,
        n,
        chart_operator,
        chart_start_date,
        chart_end_date,
        bet_4d_big: effectiveBet4dBig,
        bet_4d_small: bet_4d_small ?? false,
        bet_3d_big: effectiveBet3dBig,
        bet_3d_small: bet_3d_small ?? false,
      }}
    />
  );
}
