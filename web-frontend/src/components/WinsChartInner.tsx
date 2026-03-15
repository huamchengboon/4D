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

export interface WinsChartSeries {
  name: string;
  dataSource: { x: string; y: number }[];
}

interface WinsChartInnerProps {
  series: WinsChartSeries[];
  title: string;
  xAxisTitle?: string;
  onPointClick?: (label: string) => void;
}

function shortHash(arr: { name: string }[]): number {
  let h = 0;
  for (let i = 0; i < arr.length; i++) h = ((h << 5) - h + arr[i].name.length) | 0;
  return h >>> 0;
}

export function WinsChartInner({ series, title, xAxisTitle = "Month", onPointClick }: WinsChartInnerProps) {
  const chartKey = `chart-${series.length}-${series[0]?.dataSource?.length ?? 0}-${shortHash(series)}`;

  const handlePointClick = (args: { point?: { x?: string } }) => {
    const label = args.point?.x;
    if (typeof label === "string" && onPointClick) onPointClick(label);
  };

  return (
    <div role="region" aria-label={title} className="min-h-0 min-w-0">
      <ChartComponent
        key={chartKey}
        primaryXAxis={{
        valueType: "Category",
        title: xAxisTitle,
        labelRotation: -45,
        majorGridLines: { width: 0 },
      }}
      primaryYAxis={{ title: "Wins" }}
      title={title}
      tooltip={{ enable: true }}
      zoomSettings={{
        enableMouseWheelZooming: true,
        enableSelectionZooming: true,
        enablePan: true,
        mode: "X",
        showToolbar: true,
      }}
      pointClick={onPointClick ? handlePointClick : undefined}
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
            animation={{ enable: false }}
          />
        ))}
      </SeriesCollectionDirective>
    </ChartComponent>
    </div>
  );
}

