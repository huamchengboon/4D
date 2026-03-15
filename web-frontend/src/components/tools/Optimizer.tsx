import { useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { NumericTextBoxComponent } from "@syncfusion/ej2-react-inputs";
import { Zap, Loader2, Copy, Check } from "lucide-react";
import { optimizeNumbers } from "@/lib/api";
import type { OptimizeResponse, OptimizeSetResult } from "@/lib/api";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";

// TYPES & INTERFACES
type PrizeMode = "full" | "top3" | "4d_only";

// CONSTANTS & DATA
const PAGE_TITLE = "Number Optimizer";
const PAGE_DESC = "Best N numbers for profit and fewer dry spells.";

const PRIZE_MODE_OPTIONS: { value: PrizeMode; label: string; desc: string }[] = [
  { value: "full", label: "Full", desc: "All 4D prizes + 3D for 1st/2nd/3rd" },
  { value: "top3", label: "Top 3 + 3D", desc: "4D 1st/2nd/3rd + 3D only" },
  { value: "4d_only", label: "4D only", desc: "All 4D prizes, no 3D" },
];

// COMPONENT DEFINITION
export function Optimizer() {
  // HOOKS
  const [n, setN] = useState(24);
  const [pool, setPool] = useState(300);
  const [penalty, setPenalty] = useState(15);
  const [prizeMode, setPrizeMode] = useState<PrizeMode>("full");

  const { mutate, data, isPending, error, reset } = useMutation({
    mutationFn: () => optimizeNumbers({ n, pool, penalty, prize_mode: prizeMode }),
  });

  // EVENT HANDLERS
  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    reset();
    mutate();
  };

  // RENDER
  return (
    <div className="mx-auto w-full max-w-4xl space-y-5 px-4 py-6 md:px-6 md:py-8">
      <header className="space-y-2">
        <h1 className="font-display text-2xl font-semibold tracking-tight text-foreground md:text-3xl">{PAGE_TITLE}</h1>
        <p className="max-w-2xl text-sm leading-relaxed text-muted-foreground md:text-base">{PAGE_DESC}</p>
      </header>

      {/* Form */}
      <Card>
        <CardContent className="pt-5">
          <form onSubmit={handleSubmit} className="space-y-5">
            {/* Prize mode */}
            <div className="space-y-1.5" role="group" aria-label="Prize mode">
              <Label>Prize mode</Label>
              <div className="flex flex-wrap gap-2">
                {PRIZE_MODE_OPTIONS.map((opt) => (
                  <button
                    key={opt.value}
                    type="button"
                    aria-pressed={prizeMode === opt.value}
                    onClick={() => { setPrizeMode(opt.value); reset(); }}
                    className={`min-h-11 min-w-[7rem] rounded-lg border px-3 py-2 text-left transition-colors ${
                      prizeMode === opt.value
                        ? "border-primary bg-primary/10 text-foreground"
                        : "border-border/50 bg-muted/20 text-muted-foreground hover:border-border"
                    }`}
                  >
                    <p className="text-sm font-medium">{opt.label}</p>
                    <p className="mt-0.5 text-xs">{opt.desc}</p>
                  </button>
                ))}
              </div>
            </div>

            {/* Number controls */}
            <div className="grid grid-cols-2 gap-4 sm:grid-cols-3">
              <div className="space-y-1.5">
                <Label htmlFor="opt-n">Numbers to pick (N)</Label>
                <NumericTextBoxComponent
                  id="opt-n"
                  value={n}
                  min={8}
                  max={100}
                  format="n0"
                  change={(e) => {
                    setN(Math.max(8, Math.min(100, Math.round(e.value ?? n))));
                    reset();
                  }}
                  cssClass="w-full"
                />
                <p className="text-xs text-muted-foreground">Costs RM {n}/draw</p>
              </div>
              <div className="space-y-1.5">
                <Label htmlFor="opt-pool">Candidate pool</Label>
                <NumericTextBoxComponent
                  id="opt-pool"
                  value={pool}
                  min={n}
                  max={500}
                  format="n0"
                  change={(e) => {
                    setPool(Math.max(n, Math.min(500, Math.round(e.value ?? pool))));
                    reset();
                  }}
                  cssClass="w-full"
                />
                <p className="text-xs text-muted-foreground">Top K by winnings</p>
              </div>
              <div className="space-y-1.5">
                <Label htmlFor="opt-penalty">Gap penalty</Label>
                <NumericTextBoxComponent
                  id="opt-penalty"
                  value={penalty}
                  min={0}
                  max={500}
                  step={5}
                  format="n0"
                  change={(e) => {
                    setPenalty(Math.max(0, Math.min(500, Math.round((e.value ?? penalty) / 5) * 5)));
                    reset();
                  }}
                  cssClass="w-full"
                />
                <p className="text-xs text-muted-foreground">RM per dry-spell day in score</p>
              </div>
            </div>

            <div className="flex items-center gap-3">
              <Button type="submit" size="lg" className="min-h-11" disabled={isPending}>
                {isPending ? <Loader2 className="mr-2 size-4 animate-spin" /> : <Zap className="mr-2 size-4" />}
                {isPending ? "Optimizing… (~15s)" : "Run optimizer"}
              </Button>
              {isPending && (
                <p className="text-xs text-muted-foreground animate-pulse">
                  Scanning {pool.toLocaleString()} candidates across 40 years of draws…
                </p>
              )}
            </div>
          </form>
        </CardContent>
      </Card>

      {error && (
        <Card className="border-destructive/40 bg-destructive/5" role="alert">
          <CardContent className="pt-4 space-y-2">
            <p className="text-sm text-destructive">{(error as Error).message}</p>
            <p className="text-xs text-muted-foreground">Run the optimizer again to retry.</p>
          </CardContent>
        </Card>
      )}

      {data && !data.error && <Results data={data} />}
    </div>
  );
}

function Results({ data }: { data: OptimizeResponse }) {
  const modeLabel = PRIZE_MODE_OPTIONS.find((o) => o.value === data.prize_mode)?.label ?? data.prize_mode;
  const betterSet: "top_n" | "greedy" =
    data.top_n.profit - 15 * data.top_n.max_gap >= data.greedy.profit - 15 * data.greedy.max_gap
      ? "top_n"
      : "greedy";

  return (
    <div className="anim-result space-y-5">
      {/* Meta */}
      <div className="flex flex-wrap gap-2 text-xs text-muted-foreground">
        <span className="anim-row rounded border border-border/40 px-2 py-0.5" style={{ animationDelay: "0ms" }}>{data.n_draws.toLocaleString()} draws</span>
        <span className="anim-row rounded border border-border/40 px-2 py-0.5" style={{ animationDelay: "30ms" }}>{data.date_from} → {data.date_to}</span>
        <span className="anim-row rounded border border-border/40 px-2 py-0.5" style={{ animationDelay: "60ms" }}>Mode: {modeLabel}</span>
        <span className="anim-row rounded border border-border/40 px-2 py-0.5" style={{ animationDelay: "90ms" }}>N = {data.n}</span>
      </div>

      {/* Two result cards */}
      <div className="grid gap-4 sm:grid-cols-2">
        <ResultCard
          title="Best profit (Top N)"
          subtitle="Sorted by raw winnings — highest possible return"
          result={data.top_n}
          featured={betterSet === "top_n"}
          delay={0}
        />
        <ResultCard
          title="Shortest dry spell (Greedy)"
          subtitle="Chosen to minimise the longest gap between wins"
          result={data.greedy}
          featured={betterSet === "greedy"}
          delay={100}
        />
      </div>
    </div>
  );
}

function ResultCard({
  title,
  subtitle,
  result,
  featured,
  delay = 0,
}: {
  title: string;
  subtitle: string;
  result: OptimizeSetResult;
  featured: boolean;
  delay?: number;
}) {
  const [copied, setCopied] = useState(false);

  // EVENT HANDLERS
  const copy = () => {
    navigator.clipboard.writeText(result.numbers.join(" "));
    setCopied(true);
    setTimeout(() => setCopied(false), 1800);
  };

  // RENDER LOGIC
  const profitColor = result.profit >= 0 ? "text-[var(--success)]" : "text-[var(--destructive)]";

  // RENDER
  return (
    <Card
      className={`anim-result ${featured ? "border-primary/40 shadow-md" : ""}`}
      style={{ animationDelay: `${delay}ms` }}
    >
      <CardHeader className="pb-2">
        <div className="flex items-start justify-between gap-2">
          <div>
            <CardTitle className="text-sm font-semibold">{title}</CardTitle>
            <p className="mt-0.5 text-xs text-muted-foreground">{subtitle}</p>
          </div>
          {featured && (
            <span className="shrink-0 rounded-full bg-primary/10 px-2 py-0.5 text-xs font-medium text-primary">
              Recommended
            </span>
          )}
        </div>
      </CardHeader>
      <CardContent className="space-y-3">
        {/* Stats row */}
        <div className="grid grid-cols-3 gap-2 text-center">
          <div className="rounded-md bg-muted/30 px-2 py-2">
            <p className="text-xs text-muted-foreground">Profit</p>
            <p className={`mt-0.5 text-base font-bold tabular-nums ${profitColor}`}>
              {result.profit >= 0 ? "+" : ""}RM {Math.round(result.profit).toLocaleString()}
            </p>
          </div>
          <div className="rounded-md bg-muted/30 px-2 py-2">
            <p className="text-xs text-muted-foreground">Max dry spell</p>
            <p className="mt-0.5 text-base font-bold tabular-nums">{result.max_gap}d</p>
          </div>
          <div className="rounded-md bg-muted/30 px-2 py-2">
            <p className="text-xs text-muted-foreground">Avg gap</p>
            <p className="mt-0.5 text-base font-bold tabular-nums">{result.avg_gap}d</p>
          </div>
        </div>

        {/* Numbers chips */}
        <div>
          <div className="mb-1.5 flex items-center justify-between">
            <p className="text-xs font-medium text-muted-foreground">
              {result.numbers.length} numbers
            </p>
            <button
              type="button"
              onClick={copy}
              aria-label={copied ? "Copied to clipboard" : "Copy numbers to clipboard"}
              className="min-h-9 min-w-9 flex items-center justify-center gap-1 rounded px-2 py-1.5 text-xs text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
            >
              {copied ? <Check className="size-3 text-[var(--success)]" /> : <Copy className="size-3" />}
              <span aria-live="polite">{copied ? "Copied" : "Copy"}</span>
            </button>
          </div>
          <div className="flex flex-wrap gap-1">
            {result.numbers.map((num, chipIdx) => (
              <span
                key={num}
                className="anim-row rounded-md border border-border/60 bg-muted/20 px-2 py-0.5 font-mono text-xs"
                style={{ animationDelay: `${delay + 120 + chipIdx * 15}ms` }}
              >
                {num}
              </span>
            ))}
          </div>
        </div>
      </CardContent>
    </Card>
  );
}
