import { useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { TrendingUp, Loader2 } from "lucide-react";
import { gapAnalysis } from "@/lib/api";
import type { GapAnalysisResponse, NumberGapStats } from "@/lib/api";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";

// CONSTANTS & DATA
const PAGE_TITLE = "Gap Analysis";
const PAGE_DESC = "Days between wins and dry-spell patterns for your numbers.";

// COMPONENT DEFINITION
export function GapAnalysis() {
  // HOOKS
  const [numbersText, setNumbersText] = useState("");
  const { mutate, data, isPending, error, reset } = useMutation({
    mutationFn: (numbers: string[]) => gapAnalysis({ numbers }),
  });

  // HELPERS
  const parseNumbers = (raw: string) =>
    raw
      .split(/[\s,\n]+/)
      .map((n) => n.trim().replace(/\D/g, "").padStart(4, "0"))
      .filter((n) => n.length === 4);

  const gapBar = (val: number | null, max: number) => {
    if (val === null || max === 0) return 0;
    return Math.round((val / max) * 100);
  };

  // EVENT HANDLERS
  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    const numbers = parseNumbers(numbersText);
    if (!numbers.length) return;
    mutate(numbers);
  };

  // EARLY RETURNS
  // (none needed)

  // RENDER LOGIC
  const numbers = parseNumbers(numbersText);
  const combined = data && "win_days" in data.combined ? data.combined : null;
  const worstMaxGap = data
    ? Math.max(...data.per_number.map((r) => r.max_gap ?? 0), combined?.max_gap ?? 0)
    : 0;

  // RENDER
  return (
    <div className="mx-auto w-full max-w-4xl space-y-6 px-4 py-6 md:px-6 md:py-8">
      <header className="space-y-3">
        <h1 className="font-display text-2xl font-semibold tracking-tight text-foreground md:text-3xl">{PAGE_TITLE}</h1>
        <p className="max-w-2xl text-sm leading-relaxed text-muted-foreground md:text-base">{PAGE_DESC}</p>
      </header>

      {/* Form */}
      <Card>
        <CardContent className="pt-5">
          <form onSubmit={handleSubmit} className="space-y-4">
            <div className="space-y-1.5">
              <label htmlFor="gap-numbers" className="text-sm font-medium leading-none">
                Numbers
              </label>
              <textarea
                id="gap-numbers"
                rows={4}
                value={numbersText}
                onChange={(e) => { setNumbersText(e.target.value); reset(); }}
                placeholder="e.g. 3184 6554 4092&#10;5194 7605"
                className="w-full rounded-md border border-input bg-transparent px-3 py-2 font-mono text-sm leading-relaxed placeholder:text-muted-foreground focus:outline-none focus:ring-1 focus:ring-ring"
              />
              {numbers.length > 0 && (
                <p className="text-xs text-muted-foreground">{numbers.length} number{numbers.length !== 1 ? "s" : ""} parsed</p>
              )}
            </div>
            <Button type="submit" size="lg" className="min-h-11" disabled={isPending || numbers.length === 0}>
              {isPending ? <Loader2 className="mr-2 size-4 animate-spin" /> : <TrendingUp className="mr-2 size-4" />}
              {isPending ? "Analysing…" : "Analyse gaps"}
            </Button>
          </form>
        </CardContent>
      </Card>

      {error && (
        <Card className="border-destructive/40 bg-destructive/5" role="alert">
          <CardContent className="pt-4 space-y-2">
            <p className="text-sm text-destructive">{(error as Error).message}</p>
            <p className="text-xs text-muted-foreground">Check your numbers and submit again to retry.</p>
          </CardContent>
        </Card>
      )}

      {data && <Results data={data} worstMaxGap={worstMaxGap} combined={combined} gapBar={gapBar} />}
    </div>
  );
}

function Results({
  data,
  worstMaxGap,
  combined,
  gapBar,
}: {
  data: GapAnalysisResponse;
  worstMaxGap: number;
  combined: GapAnalysisResponse["combined"] | null;
  gapBar: (val: number | null, max: number) => number;
}) {
  // RENDER LOGIC
  const isCombined = combined && "win_days" in combined;

  // RENDER
  return (
    <div className="anim-result space-y-5">
      {/* Combined summary */}
      {isCombined && combined && "win_days" in combined && (
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
          <SummaryCard label="Winning days" value={String(combined.win_days)} className="anim-result" style={{ animationDelay: "0ms" }} />
          <SummaryCard label="Max dry spell" value={`${combined.max_gap}d`} warn={combined.max_gap > 60} className="anim-result" style={{ animationDelay: "60ms" }} />
          <SummaryCard label="Avg gap" value={`${combined.avg_gap}d`} className="anim-result" style={{ animationDelay: "120ms" }} />
          <SummaryCard label="Days since last win" value={combined.days_since_last != null ? `${combined.days_since_last}d` : "—"} warn={(combined.days_since_last ?? 0) > combined.max_gap} className="anim-result" style={{ animationDelay: "180ms" }} />
        </div>
      )}

      {/* Per-number table */}
      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="text-sm font-semibold uppercase tracking-wide text-muted-foreground">
            Per-number breakdown (full history)
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-border/50 text-left text-xs text-muted-foreground">
                  <th scope="col" className="pb-2 pr-3 font-medium">Number</th>
                  <th scope="col" className="pb-2 pr-3 font-medium">Wins</th>
                  <th scope="col" className="pb-2 pr-3 font-medium">Last win</th>
                  <th scope="col" className="pb-2 pr-3 font-medium">Since last</th>
                  <th scope="col" className="pb-2 pr-3 font-medium">Avg gap</th>
                  <th scope="col" className="pb-2 font-medium">Max gap</th>
                </tr>
              </thead>
              <tbody>
                {data.per_number.map((r: NumberGapStats, rowIdx) => {
                  const overdue = r.avg_gap != null && r.days_since_last != null && r.days_since_last > r.avg_gap * 1.5;
                  return (
                    <tr
                      key={r.number}
                      className="anim-row border-b border-border/20 last:border-0"
                      style={{ animationDelay: `${rowIdx * 25}ms` }}
                    >
                      <td className="py-1.5 pr-3 font-mono font-bold">{r.number}</td>
                      <td className="py-1.5 pr-3 tabular-nums">{r.total_wins}</td>
                      <td className="py-1.5 pr-3 font-mono text-xs">{r.last_win ?? "—"}</td>
                      <td className={`py-1.5 pr-3 tabular-nums ${overdue ? "font-semibold text-[var(--warning)]" : ""}`}>
                        {r.days_since_last != null ? `${r.days_since_last}d` : "—"}
                        {overdue && " ⚡"}
                      </td>
                      <td className="py-1.5 pr-3 tabular-nums text-muted-foreground">
                        {r.avg_gap != null ? `${r.avg_gap}d` : "—"}
                      </td>
                      <td className="py-1.5">
                        <GapBar pct={gapBar(r.max_gap, worstMaxGap)} val={r.max_gap} />
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
          <p className="mt-3 text-xs text-muted-foreground">
            ⚡ = days since last win is &gt;1.5× the average gap — potentially overdue.
          </p>
        </CardContent>
      </Card>
    </div>
  );
}

function GapBar({ pct, val }: { pct: number; val: number | null }) {
  if (val === null) return <span className="text-muted-foreground/50">—</span>;
  const color = pct > 70 ? "bg-[var(--destructive)]/70" : pct > 40 ? "bg-[var(--warning)]/70" : "bg-[var(--success)]/60";
  return (
    <div className="flex items-center gap-2">
      <div className="h-1.5 w-20 overflow-hidden rounded-full bg-muted">
        <div
          className={`h-full rounded-full gap-bar-fill ${color}`}
          style={{ transform: `scaleX(${pct / 100})` }}
        />
      </div>
      <span className="w-10 tabular-nums text-xs">{val}d</span>
    </div>
  );
}

function SummaryCard({
  label,
  value,
  warn,
  className,
  style,
}: {
  label: string;
  value: string;
  warn?: boolean;
  className?: string;
  style?: React.CSSProperties;
}) {
  return (
    <div
      className={`rounded-lg border px-4 py-3 ${warn ? "border-[var(--warning)]/30 bg-[var(--warning)]/5" : "border-border/50 bg-muted/20"} ${className ?? ""}`}
      style={style}
    >
      <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">{label}</p>
      <p className={`mt-0.5 text-xl font-bold tabular-nums ${warn ? "text-[var(--warning)]" : ""}`}>{value}</p>
    </div>
  );
}
