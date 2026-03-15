import { useEffect } from "react";
import { useForm } from "@tanstack/react-form";
import { useNavigate } from "@tanstack/react-router";
import { DatePickerComponent } from "@syncfusion/ej2-react-calendars";
import { NumericTextBoxComponent } from "@syncfusion/ej2-react-inputs";
import { Play } from "lucide-react";

interface FiltersProps {
  startDate: string;
  endDate: string;
  n: number;
  dateMin: string;
  dateMax: string;
  chartOperator?: string[];
  bet4dBig: boolean;
  bet4dSmall: boolean;
  bet3dBig: boolean;
  bet3dSmall: boolean;
  operatorCount?: number;
}

interface StrategyFormValues {
  start: string;
  end: string;
  n: number;
  bet4dBig: boolean;
  bet4dSmall: boolean;
  bet3dBig: boolean;
  bet3dSmall: boolean;
}

const DATE_FORMAT = "yyyy-MM-dd";
const DATE_CACHE_KEY = "4d-strategy-dates";

function getCachedDates(): { start_date: string; end_date: string } | null {
  try {
    const raw = typeof window !== "undefined" ? localStorage.getItem(DATE_CACHE_KEY) : null;
    if (!raw) return null;
    const parsed = JSON.parse(raw) as { start_date?: string; end_date?: string };
    if (parsed && typeof parsed.start_date === "string" && typeof parsed.end_date === "string") {
      return { start_date: parsed.start_date, end_date: parsed.end_date };
    }
    return null;
  } catch {
    return null;
  }
}

function setCachedDates(start_date: string, end_date: string): void {
  try {
    if (typeof window !== "undefined" && start_date && end_date) {
      localStorage.setItem(DATE_CACHE_KEY, JSON.stringify({ start_date, end_date }));
    }
  } catch {
    /* ignore */
  }
}

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

function clampN(v: number) {
  return Math.max(1, Math.min(1000, Math.round(v)));
}

export function Filters({
  startDate,
  endDate,
  n,
  dateMin,
  dateMax,
  chartOperator = [],
  bet4dBig,
  bet4dSmall,
  bet3dBig,
  bet3dSmall,
  operatorCount = 3,
}: FiltersProps) {
  const navigate = useNavigate();

  const form = useForm({
    defaultValues: {
      start: startDate || (getCachedDates()?.start_date ?? ""),
      end: endDate || (getCachedDates()?.end_date ?? ""),
      n,
      bet4dBig,
      bet4dSmall,
      bet3dBig,
      bet3dSmall,
    } satisfies StrategyFormValues,
    onSubmit: async ({ value }) => {
      const atLeastOne = value.bet4dBig || value.bet4dSmall || value.bet3dBig || value.bet3dSmall;
      const startVal = value.start?.trim() || undefined;
      const endVal = value.end?.trim() || undefined;
      if (startVal && endVal) setCachedDates(startVal, endVal);
      navigate({
        to: "/",
        search: {
          start_date: startVal,
          end_date: endVal,
          n: clampN(value.n),
          chart_operator: chartOperator,
          chart_start_date: undefined,
          chart_end_date: undefined,
          bet_4d_big: atLeastOne ? value.bet4dBig : true,
          bet_4d_small: atLeastOne ? value.bet4dSmall : false,
          bet_3d_big: atLeastOne ? value.bet3dBig : true,
          bet_3d_small: atLeastOne ? value.bet3dSmall : false,
        },
      });
    },
  });

  useEffect(() => {
    form.reset({
      start: startDate || (getCachedDates()?.start_date ?? ""),
      end: endDate || (getCachedDates()?.end_date ?? ""),
      n,
      bet4dBig,
      bet4dSmall,
      bet3dBig,
      bet3dSmall,
    });
  }, [startDate, endDate, n, bet4dBig, bet4dSmall, bet3dBig, bet3dSmall]);

  const minDate = parseDateYMD(dateMin);
  const maxDate = parseDateYMD(dateMax);

  return (
    <form
      onSubmit={(e) => {
        e.preventDefault();
        e.stopPropagation();
        form.handleSubmit();
      }}
    >
      <div className="rounded-xl border border-border/70 bg-card shadow-sm">
        {/* Row 1: Date range + numbers per draw + run button */}
        <div className="flex flex-wrap items-center gap-2.5 px-3 py-2.5 sm:flex-nowrap sm:gap-3 sm:px-4">
          <form.Subscribe selector={(state) => ({ start: state.values.start, end: state.values.end })}>
            {({ start, end }) => (
              <>
                <form.Field name="start">
                  {(field) => {
                    const endVal = parseDateYMD(end);
                    const startMax =
                      endVal && maxDate
                        ? (endVal.getTime() < maxDate.getTime() ? endVal : maxDate)
                        : maxDate ?? undefined;
                    return (
                      <div className="flex items-center gap-1.5">
                        <span className="shrink-0 text-[11px] font-medium text-muted-foreground">From</span>
                        <DatePickerComponent
                          id="start_date"
                          value={parseDateYMD(field.state.value) ?? undefined}
                          min={minDate ?? undefined}
                          max={startMax}
                          format={DATE_FORMAT}
                          placeholder="Start"
                          strictMode={true}
                          change={(e) => field.handleChange(e.value ? formatDateYMD(e.value) : "")}
                          cssClass="dp-compact w-[7.5rem] text-sm"
                        />
                      </div>
                    );
                  }}
                </form.Field>
                <form.Field name="end">
                  {(field) => {
                    const startDateParsed = parseDateYMD(start);
                    const endPickerMin =
                      minDate && startDateParsed
                        ? (startDateParsed.getTime() > minDate.getTime() ? startDateParsed : minDate)
                        : minDate ?? undefined;
                    return (
                      <div className="flex items-center gap-1.5">
                        <span className="shrink-0 text-[11px] font-medium text-muted-foreground">To</span>
                        <DatePickerComponent
                          id="end_date"
                          value={parseDateYMD(field.state.value) ?? undefined}
                          min={endPickerMin}
                          max={maxDate ?? undefined}
                          format={DATE_FORMAT}
                          placeholder="End"
                          strictMode={true}
                          change={(e) => field.handleChange(e.value ? formatDateYMD(e.value) : "")}
                          cssClass="dp-compact w-[7.5rem] text-sm"
                        />
                      </div>
                    );
                  }}
                </form.Field>
              </>
            )}
          </form.Subscribe>

          <span className="hidden h-4 w-px bg-border sm:block" aria-hidden />

          <form.Field name="n">
            {(field) => (
              <div className="flex items-center gap-1.5">
                <span className="shrink-0 text-[11px] font-medium text-muted-foreground">Top</span>
                <NumericTextBoxComponent
                  id="n"
                  value={field.state.value}
                  min={1}
                  max={1000}
                  format="n0"
                  placeholder="N"
                  change={(e) => field.handleChange(clampN(e.value ?? field.state.value))}
                  cssClass="dp-compact w-16 text-sm"
                />
                <span className="shrink-0 text-[11px] text-muted-foreground">/draw</span>
              </div>
            )}
          </form.Field>

          <div className="ml-auto flex items-center">
            <form.Subscribe selector={(state) => [state.canSubmit, state.isSubmitting]}>
              {([canSubmit, isSubmitting]) => (
                <button
                  type="submit"
                  disabled={!canSubmit || isSubmitting}
                  className="inline-flex items-center gap-1.5 rounded-full border border-primary bg-primary px-4 py-1.5 text-xs font-semibold text-primary-foreground shadow-sm transition-colors hover:bg-primary/90 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:pointer-events-none disabled:opacity-50"
                >
                  <Play className="size-3 fill-current" />
                  {isSubmitting ? "Running…" : "Backtest"}
                </button>
              )}
            </form.Subscribe>
          </div>
        </div>

        {/* Row 2: Bet type chips + data range info */}
        <div className="flex flex-wrap items-center gap-x-3 gap-y-2 border-t border-border/60 bg-muted/15 px-3 py-2 sm:px-4">
          <div className="flex flex-wrap items-center gap-1.5" role="group" aria-label="Bet types">
            {(["bet4dBig", "bet4dSmall", "bet3dBig", "bet3dSmall"] as const).map((name) => {
              const labels: Record<string, string> = {
                bet4dBig: "4D Big",
                bet4dSmall: "4D Small",
                bet3dBig: "3D Big",
                bet3dSmall: "3D Small",
              };
              return (
                <form.Field key={name} name={name}>
                  {(field) => (
                    <button
                      type="button"
                      role="switch"
                      aria-checked={field.state.value}
                      aria-label={labels[name]}
                      onClick={() => field.handleChange(!field.state.value)}
                      className={`rounded-full border px-2.5 py-0.5 text-[11px] font-medium tabular-nums transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-1 ${
                        field.state.value
                          ? "border-primary/60 bg-primary/10 text-foreground"
                          : "border-border bg-muted/40 text-muted-foreground hover:bg-muted/60"
                      }`}
                    >
                      {labels[name]}
                    </button>
                  )}
                </form.Field>
              );
            })}
          </div>
          <form.Subscribe selector={(state) => [state.values.bet4dBig, state.values.bet4dSmall, state.values.bet3dBig, state.values.bet3dSmall, state.values.n] as const}>
            {([b4b, b4s, b3b, b3s, numN]) => {
              const betTypes = [b4b, b4s, b3b, b3s].filter(Boolean).length;
              const ops = operatorCount;
              return betTypes > 0 ? (
                <>
                  <span className="hidden h-3 w-px bg-border sm:block" aria-hidden />
                  <span className="text-[11px] tabular-nums text-muted-foreground">
                    RM1 × {betTypes} × {ops} ops × {numN} = <span className="font-semibold text-foreground">RM {betTypes * ops * numN}</span>/draw date
                  </span>
                </>
              ) : null;
            }}
          </form.Subscribe>
          {dateMin && dateMax && (
            <>
              <span className="hidden h-3 w-px bg-border sm:block" aria-hidden />
              <span className="text-[11px] text-muted-foreground">
                Data: {dateMin} → {dateMax}
              </span>
            </>
          )}
        </div>
      </div>
    </form>
  );
}
