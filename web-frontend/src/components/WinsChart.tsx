import { useMemo, useCallback } from "react";
import { useNavigate } from "@tanstack/react-router";
import type { ChartApiResponse, ChartGranularity } from "@/lib/api";
import { Checkbox } from "@/components/ui/checkbox";
import { Label } from "@/components/ui/label";
import { WinsChartInner } from "./WinsChartInner";

// TYPES & INTERFACES
interface WinsChartProps {
  chartData: ChartApiResponse;
  operators: string[];
  chartOperatorsSelected: string[];
  startDate: string;
  endDate: string;
  n: number;
  chartStartDate?: string;
  chartEndDate?: string;
  bet4dBig?: boolean;
  bet4dSmall?: boolean;
  bet3dBig?: boolean;
  bet3dSmall?: boolean;
  onDrillDown?: (rangeStart: string, rangeEnd: string) => void;
  onShowFullRange?: () => void;
}

// CONSTANTS & DATA
const CHART_NOTE = "Click a bar to zoom (year → months, month → days).";

/** Return [startDate, endDate] for drill-down from a bar label; null if no drill. */
function getDrillRange(label: string, granularity: ChartGranularity): [string, string] | null {
  if (granularity === "year" && /^\d{4}$/.test(label)) {
    return [`${label}-01-01`, `${label}-12-31`];
  }
  if (granularity === "month" && /^\d{4}-\d{2}$/.test(label)) {
    const [y, m] = label.split("-");
    const lastDay = new Date(Number(y), Number(m), 0).getDate();
    return [`${label}-01`, `${label}-${String(lastDay).padStart(2, "0")}`];
  }
  return null;
}

export function WinsChart({
  chartData,
  operators,
  chartOperatorsSelected,
  startDate,
  endDate,
  n,
  chartStartDate,
  chartEndDate,
  bet4dBig = true,
  bet4dSmall = false,
  bet3dBig = true,
  bet3dSmall = false,
  onDrillDown,
}: WinsChartProps) {
  const navigate = useNavigate();
  const granularity = chartData.granularity ?? "month";

  const getNextOperatorSelection = (operator: string, checked: boolean) =>
    checked
      ? [...chartOperatorsSelected, operator]
      : chartOperatorsSelected.filter((currentOperator) => currentOperator !== operator);

  const series = useMemo(
    () =>
      chartData.datasets.map((dataset) => ({
        name: dataset.number,
        dataSource: chartData.labels.map((month, index) => ({
          x: month,
          y: dataset.counts[index] ?? 0,
        })),
      })),
    [chartData.datasets, chartData.labels]
  );

  const handleOperatorChange = (op: string, checked: boolean) => {
    const next = getNextOperatorSelection(op, checked);
    navigate({
      to: "/",
      search: {
        start_date: startDate,
        end_date: endDate,
        n,
        chart_operator: next,
        chart_start_date: chartStartDate ?? undefined,
        chart_end_date: chartEndDate ?? undefined,
        bet_4d_big: bet4dBig,
        bet_4d_small: bet4dSmall,
        bet_3d_big: bet3dBig,
        bet_3d_small: bet3dSmall,
      },
    });
  };

  const handlePointClick = useCallback(
    (label: string) => {
      const range = getDrillRange(label, granularity);
      if (range && onDrillDown) onDrillDown(range[0], range[1]);
    },
    [granularity, onDrillDown]
  );

  const axisLabel = granularity === "year" ? "Year" : granularity === "day" ? "Date" : "Month";
  const chartTitle = `Top ${series.length} numbers: ${chartData.filter_label ?? "All operators"} (${granularity})`;

  return (
    <div className="space-y-3">
      <div className="space-y-2">
        <p className="text-sm font-medium">Chart filters</p>
        <div className="flex flex-wrap gap-2.5">
          {operators.map((op) => (
            <Label
              key={op}
              htmlFor={`chart-operator-${op}`}
              className={`inline-flex min-h-11 min-w-11 cursor-pointer items-center gap-2 rounded-md border px-2.5 py-1.5 text-sm font-medium transition-colors duration-200 hover:bg-muted/60 sm:min-w-0 ${
                chartOperatorsSelected.includes(op)
                  ? "border-primary/60 bg-primary/10 text-foreground"
                  : "border-border/80 bg-muted/20"
              }`}
            >
              <Checkbox
                id={`chart-operator-${op}`}
                name="chart_operator"
                checked={chartOperatorsSelected.includes(op)}
                onCheckedChange={(checked) => handleOperatorChange(op, checked === true)}
              />
              {op}
            </Label>
          ))}
        </div>
        <p className="muted">{CHART_NOTE}</p>
      </div>

      <div className="min-w-0 rounded-md border border-border/70 bg-card p-3">
        <div className="chart-canvas-wrapper min-h-0 min-w-0">
          <WinsChartInner
            series={series}
            title={chartTitle}
            xAxisTitle={axisLabel}
            onPointClick={onDrillDown ? handlePointClick : undefined}
          />
        </div>
      </div>
    </div>
  );
}
