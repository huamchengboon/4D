import { useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { DatePickerComponent } from "@syncfusion/ej2-react-calendars";
import { Search, Loader2, CheckCircle2, XCircle } from "lucide-react";
import { checkNumbers } from "@/lib/api";
import type { CheckNumbersResponse } from "@/lib/api";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";

// CONSTANTS & DATA
const TODAY = new Date().toISOString().slice(0, 10);
const DATE_FORMAT = "yyyy-MM-dd";

function parseDateYMD(str: string): Date | null {
  if (!str) return null;
  const d = new Date(str + "T00:00:00");
  return Number.isNaN(d.getTime()) ? null : d;
}

function formatDateYMD(d: Date): string {
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  return `${y}-${m}-${day}`;
}
const PAGE_TITLE = "Number Checker";
const PAGE_DESC = "Check if your 4D numbers have won since a given date.";
const PRIZE_COLOR: Record<string, string> = {
  "1st": "text-[var(--prize-1st)]",
  "2nd": "text-[var(--prize-2nd)]",
  "3rd": "text-[var(--prize-3rd)]",
  Special: "text-[var(--prize-special)]",
  Consolation: "text-[var(--prize-consolation)]",
};

// COMPONENT DEFINITION
export function NumberChecker() {
  // HOOKS
  const [numbersText, setNumbersText] = useState("");
  const [sinceDate, setSinceDate] = useState(() => {
    const d = new Date();
    d.setDate(d.getDate() - 30);
    return d.toISOString().slice(0, 10);
  });
  const [include3d, setInclude3d] = useState(true);

  const { mutate, data, isPending, error, reset } = useMutation({
    mutationFn: (params: { numbers: string[]; since_date: string; include_3d: boolean }) =>
      checkNumbers(params),
  });

  // HELPERS
  const parseNumbers = (raw: string) =>
    raw
      .split(/[\s,\n]+/)
      .map((n) => n.trim().replace(/\D/g, "").padStart(4, "0"))
      .filter((n) => n.length === 4);

  // EVENT HANDLERS
  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    const numbers = parseNumbers(numbersText);
    if (!numbers.length) return;
    mutate({ numbers, since_date: sinceDate, include_3d: include3d });
  };

  // RENDER LOGIC
  const numbers = parseNumbers(numbersText);
  const hasResults = !!data;

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
          <form onSubmit={handleSubmit} className="space-y-4">
            <div className="space-y-1.5">
              <Label htmlFor="numbers">Numbers (space, comma, or newline separated)</Label>
              <textarea
                id="numbers"
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
            <div className="flex flex-wrap items-end gap-4">
              <div className="space-y-1.5">
                <Label htmlFor="since">Since date</Label>
                <DatePickerComponent
                  id="since"
                  value={parseDateYMD(sinceDate) ?? undefined}
                  max={parseDateYMD(TODAY) ?? undefined}
                  format={DATE_FORMAT}
                  placeholder="Since date"
                  strictMode={true}
                  change={(e) => {
                    setSinceDate(e.value ? formatDateYMD(e.value) : "");
                    reset();
                  }}
                  cssClass="min-w-[10rem]"
                />
              </div>
              <label className="flex cursor-pointer items-center gap-2 text-sm">
                <input
                  type="checkbox"
                  checked={include3d}
                  onChange={(e) => { setInclude3d(e.target.checked); reset(); }}
                  className="size-4 rounded border-input accent-primary"
                />
                Include 3D (last 3 digits)
              </label>
              <Button type="submit" size="lg" className="min-h-11" disabled={isPending || numbers.length === 0}>
                {isPending ? <Loader2 className="mr-2 size-4 animate-spin" /> : <Search className="mr-2 size-4" />}
                {isPending ? "Checking…" : "Check"}
              </Button>
            </div>
          </form>
        </CardContent>
      </Card>

      {/* Error */}
      {error && (
        <Card className="border-destructive/40 bg-destructive/5" role="alert">
          <CardContent className="pt-4 space-y-2">
            <p className="text-sm text-destructive">{(error as Error).message}</p>
            <p className="text-xs text-muted-foreground">Check your numbers and date, then submit again to retry.</p>
          </CardContent>
        </Card>
      )}

      {/* Results */}
      {hasResults && <Results data={data!} include3d={include3d} />}
    </div>
  );
}

function Results({ data, include3d }: { data: CheckNumbersResponse; include3d: boolean }) {
  const total4d = data.hits_4d.length;
  const total3d = data.hits_3d.length;
  const wonRM4d = data.hits_4d.reduce((s, h) => s + h.prize_value, 0);
  const wonRM3d = data.hits_3d.reduce((s, h) => s + h.prize_value, 0);

  return (
    <div className="anim-result space-y-5">
      {/* Summary chips */}
      <div className="flex flex-wrap gap-3">
        <StatChip label="4D wins" value={total4d} sub={`RM ${wonRM4d.toLocaleString()} / RM1 bet`} highlight={total4d > 0} className="anim-result" style={{ animationDelay: "0ms" }} />
        {include3d && <StatChip label="3D wins" value={total3d} sub={`RM ${wonRM3d.toLocaleString()} / RM1 Fireball`} highlight={total3d > 0} className="anim-result" style={{ animationDelay: "60ms" }} />}
        <StatChip label="Period" value={data.since_date} sub="→ latest draw" className="anim-result" style={{ animationDelay: "120ms" }} />
      </div>

      {/* Per-number summary */}
      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="text-sm font-semibold uppercase tracking-wide text-muted-foreground">Per-number summary</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-border/50 text-left text-xs text-muted-foreground">
                  <th scope="col" className="pb-2 pr-4 font-medium">Number</th>
                  <th scope="col" className="pb-2 pr-4 font-medium">4D wins</th>
                  {include3d && <th scope="col" className="pb-2 pr-4 font-medium">3D wins</th>}
                  <th scope="col" className="pb-2 pr-4 font-medium">Won (4D)</th>
                  {include3d && <th scope="col" className="pb-2 font-medium">Won (3D)</th>}
                </tr>
              </thead>
              <tbody>
                {data.summary.map((s, rowIdx) => (
                  <tr key={s.number} className="anim-row border-b border-border/20 last:border-0" style={{ animationDelay: `${rowIdx * 25}ms` }}>
                    <td className="py-1.5 pr-4 font-mono font-semibold">{s.number}</td>
                    <td className="py-1.5 pr-4">
                      {s.hits_4d > 0
                        ? <span className="inline-flex items-center gap-1 text-[var(--success)]"><CheckCircle2 className="size-3.5" />{s.hits_4d}</span>
                        : <span className="flex items-center gap-1 text-muted-foreground/50"><XCircle className="size-3.5" />0</span>}
                    </td>
                    {include3d && (
                      <td className="py-1.5 pr-4">
                        {s.hits_3d > 0
                          ? <span className="inline-flex items-center gap-1 text-[var(--prize-special)]"><CheckCircle2 className="size-3.5" />{s.hits_3d}</span>
                          : <span className="flex items-center gap-1 text-muted-foreground/50"><XCircle className="size-3.5" />0</span>}
                      </td>
                    )}
                    <td className="py-1.5 pr-4 font-mono">{s.total_won_4d > 0 ? `RM ${s.total_won_4d.toLocaleString()}` : "—"}</td>
                    {include3d && <td className="py-1.5 font-mono">{s.total_won_3d > 0 ? `RM ${s.total_won_3d.toLocaleString()}` : "—"}</td>}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </CardContent>
      </Card>

      {/* 4D hits */}
      {data.hits_4d.length > 0 && (
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-semibold uppercase tracking-wide text-muted-foreground">4D wins</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-border/50 text-left text-xs text-muted-foreground">
                    <th scope="col" className="pb-2 pr-4 font-medium">Date</th>
                    <th scope="col" className="pb-2 pr-4 font-medium">Operator</th>
                    <th scope="col" className="pb-2 pr-4 font-medium">Number</th>
                    <th scope="col" className="pb-2 pr-4 font-medium">Prize</th>
                    <th scope="col" className="pb-2 font-medium">Payout / RM1</th>
                  </tr>
                </thead>
                <tbody>
                  {data.hits_4d.map((h, i) => (
                    <tr key={i} className="anim-row border-b border-border/20 last:border-0" style={{ animationDelay: `${i * 20}ms` }}>
                      <td className="py-1.5 pr-4 font-mono text-xs">{h.date}</td>
                      <td className="max-w-24 truncate py-1.5 pr-4 text-xs" title={h.operator}>{h.operator}</td>
                      <td className="py-1.5 pr-4 font-mono font-semibold">{h.number}</td>
                      <td className={`py-1.5 pr-4 font-medium ${PRIZE_COLOR[h.prize] ?? ""}`}>{h.prize}</td>
                      <td className="py-1.5 font-mono text-[var(--success)]">RM {h.prize_value.toLocaleString()}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </CardContent>
        </Card>
      )}

      {/* 3D hits */}
      {include3d && data.hits_3d.length > 0 && (
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-semibold uppercase tracking-wide text-muted-foreground">3D wins (Fireball)</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-border/50 text-left text-xs text-muted-foreground">
                    <th scope="col" className="pb-2 pr-4 font-medium">Date</th>
                    <th scope="col" className="pb-2 pr-4 font-medium">Operator</th>
                    <th scope="col" className="pb-2 pr-4 font-medium">Your #</th>
                    <th scope="col" className="pb-2 pr-4 font-medium">Matched</th>
                    <th scope="col" className="pb-2 pr-4 font-medium">Prize</th>
                    <th scope="col" className="pb-2 font-medium">Payout / RM1</th>
                  </tr>
                </thead>
                <tbody>
                  {data.hits_3d.map((h, i) => (
                    <tr key={i} className="anim-row border-b border-border/20 last:border-0" style={{ animationDelay: `${i * 20}ms` }}>
                      <td className="py-1.5 pr-4 font-mono text-xs">{h.date}</td>
                      <td className="max-w-24 truncate py-1.5 pr-4 text-xs" title={h.operator}>{h.operator}</td>
                      <td className="py-1.5 pr-4 font-mono font-semibold">{h.your_number}</td>
                      <td className="py-1.5 pr-4 font-mono text-[var(--prize-special)]">{h.matched}</td>
                      <td className={`py-1.5 pr-4 font-medium ${PRIZE_COLOR[h.prize] ?? ""}`}>{h.prize}</td>
                      <td className="py-1.5 font-mono text-[var(--prize-special)]">RM {h.prize_value.toLocaleString()}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
}

function StatChip({
  label,
  value,
  sub,
  highlight,
  className,
  style,
}: {
  label: string;
  value: string | number;
  sub?: string;
  highlight?: boolean;
  className?: string;
  style?: React.CSSProperties;
}) {
  return (
    <div
      className={`rounded-lg border px-4 py-3 ${highlight ? "border-[var(--success)]/30 bg-[var(--success)]/5" : "border-border/50 bg-muted/20"} ${className ?? ""}`}
      style={style}
    >
      <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">{label}</p>
      <p className={`mt-0.5 text-xl font-bold tabular-nums ${highlight ? "text-[var(--success)]" : ""}`}>{value}</p>
      {sub && <p className="mt-0.5 text-xs text-muted-foreground">{sub}</p>}
    </div>
  );
}
