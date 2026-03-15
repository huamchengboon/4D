import { useMemo } from "react";
import { Link, useNavigate } from "@tanstack/react-router";
import { ChartColumnIncreasing, Loader2 } from "lucide-react";
import {
  ChartComponent,
  SeriesCollectionDirective,
  SeriesDirective,
  Inject,
  StackingColumnSeries,
  Category,
  Legend,
  Tooltip,
  Zoom,
} from "@syncfusion/ej2-react-charts";
import type { ChartApiResponse } from "@/lib/api";
import { Checkbox } from "@/components/ui/checkbox";
import { Label } from "@/components/ui/label";
import { buttonVariants } from "@/components/ui/button";
import { cn } from "@/lib/utils";

// TYPES & INTERFACES
interface ChartFullscreenProps {
  chartData: ChartApiResponse | undefined;
  isLoading: boolean;
  operators: string[];
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
const EMPTY_STATE_TEXT = "No chart data found for this filter.";

// COMPONENT DEFINITION
export function ChartFullscreen({
  chartData,
  isLoading,
  operators,
  searchParams,
}: ChartFullscreenProps) {
  // HOOKS
  const navigate = useNavigate();
  const { start_date, end_date, n, chart_operator, chart_start_date, chart_end_date, bet_4d_big, bet_4d_small, bet_3d_big, bet_3d_small } = searchParams;

  // EFFECTS
  // No side-effects required.

  // HELPERS
  const series = useMemo(
    () =>
      chartData?.datasets?.map((ds) => ({
        name: ds.number,
        dataSource: chartData.labels.map((month, i) => ({
          x: month,
          y: ds.counts[i] ?? 0,
        })),
      })) ?? [],
    [chartData?.datasets, chartData?.labels]
  );

  const getNextOperatorSelection = (operator: string, checked: boolean) =>
    checked
      ? [...chart_operator, operator]
      : chart_operator.filter((currentOperator) => currentOperator !== operator);

  // EVENT HANDLERS
  const handleOperatorChange = (op: string, checked: boolean) => {
    const next = getNextOperatorSelection(op, checked);
    navigate({
      to: "/chart",
      search: {
        start_date,
        end_date,
        n,
        chart_operator: next,
        chart_start_date: chart_start_date ?? undefined,
        chart_end_date: chart_end_date ?? undefined,
        bet_4d_big: bet_4d_big ?? true,
        bet_4d_small: bet_4d_small ?? false,
        bet_3d_big: bet_3d_big ?? true,
        bet_3d_small: bet_3d_small ?? false,
      },
    });
  };

  // EARLY RETURNS
  // Not required.

  // RENDER LOGIC
  const title = `Top ${series.length} numbers: ${chartData?.filter_label ?? "All operators"}`;

  // RENDER
  return (
    <div className="flex h-screen flex-col bg-background">
      <header className="flex flex-wrap items-center justify-between gap-3 border-b border-border/70 bg-card px-4 py-3">
        <div className="flex flex-wrap items-center gap-2">
          <ChartColumnIncreasing className="size-4 text-muted-foreground" />
          <span className="text-sm font-medium">Chart filter</span>
          {operators.map((op) => (
            <Label
              key={op}
              htmlFor={`fullscreen-chart-operator-${op}`}
              className={`inline-flex min-h-11 min-w-11 cursor-pointer items-center gap-2 rounded-md border px-2.5 py-1.5 text-xs transition-colors duration-200 hover:bg-muted/70 md:min-w-0 md:text-sm ${
                chart_operator.includes(op)
                  ? "border-primary/60 bg-primary/10 text-foreground"
                  : "border-border/80 bg-muted/30"
              }`}
            >
              <Checkbox
                id={`fullscreen-chart-operator-${op}`}
                name="chart_operator"
                checked={chart_operator.includes(op)}
                onCheckedChange={(checked) => handleOperatorChange(op, checked === true)}
              />
              {op}
            </Label>
          ))}
        </div>
        <div className="flex items-center gap-3">
          <span className="text-xs text-muted-foreground">Top numbers by monthly wins.</span>
          <Link
            to="/"
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
            className={cn(buttonVariants({ variant: "outline", size: "sm" }), "min-h-11")}
          >
          Back to dashboard
          </Link>
        </div>
      </header>
      <main className="min-h-0 flex-1 p-4">
        {isLoading ? (
          <div
            className="flex h-full items-center justify-center gap-2 text-sm text-muted-foreground"
            aria-busy="true"
            aria-live="polite"
            aria-label="Loading chart"
          >
            <Loader2 className="size-4 animate-spin" aria-hidden />
            <span>Loading chart…</span>
          </div>
        ) : series.length ? (
          <div role="region" aria-label={title} className="h-full min-h-0 min-w-0">
          <ChartComponent
            primaryXAxis={{ valueType: "Category", title: "Month" }}
            primaryYAxis={{ title: "Wins" }}
            title={title}
            tooltip={{ enable: true }}
            zoomSettings={{
              enableMouseWheelZooming: false,
              enableSelectionZooming: false,
              enablePan: false,
            }}
            height="100%"
            width="100%"
          >
            <Inject services={[StackingColumnSeries, Category, Legend, Tooltip, Zoom]} />
            <SeriesCollectionDirective>
              {series.map((s) => (
                <SeriesDirective
                  key={s.name}
                  dataSource={s.dataSource}
                  xName="x"
                  yName="y"
                  name={s.name}
                  type="StackingColumn"
                />
              ))}
            </SeriesCollectionDirective>
          </ChartComponent>
          </div>
        ) : (
          <div className="flex h-full items-center justify-center">
            <p className="muted">{EMPTY_STATE_TEXT}</p>
          </div>
        )}
      </main>
    </div>
  );
}
