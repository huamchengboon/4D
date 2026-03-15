import { useState, useMemo, useEffect, useRef, useCallback } from "react";
import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { useQuery, keepPreviousData } from "@tanstack/react-query";
import { DatePickerComponent } from "@syncfusion/ej2-react-calendars";
import { ChevronLeft, ChevronRight, X } from "lucide-react";
import {
  fetchLatestDraws,
  fetchDrawDates,
  fetchDrawsForDate,
  type LatestDraw,
} from "@/lib/api";
import { queryClient } from "@/lib/queryClient";
import { get4DPrizeRm, get3DPrizeRm } from "@/lib/prizing";
import { useResultsStore, DEFAULT_OPERATORS } from "@/stores/resultsStore";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { SlipCard } from "@/components/SlipCard";

export const Route = createFileRoute("/results")({
  validateSearch: (s: Record<string, unknown>) => ({
    date: typeof s.date === "string" && s.date.length >= 10 ? s.date.slice(0, 10) : undefined,
  }),
  loader: async () => {
    await Promise.all([
      queryClient.prefetchQuery({ queryKey: ["draw-dates"], queryFn: fetchDrawDates }),
      queryClient.prefetchQuery({ queryKey: ["latest-draws"], queryFn: fetchLatestDraws }),
    ]);
  },
  component: ResultsPage,
});

const OPERATOR_THEMES: Record<string, {
  headerBg: string;
  border: string;
  label: string;
  accentColor: string;
  stripeBg: string;
  logoText: string;
  logoIcon: string;
}> = {
  "Magnum 4D": {
    headerBg: "bg-[var(--operator-magnum-header)]",
    border: "border-[var(--operator-magnum-border)]",
    label: "text-[var(--operator-magnum-label)]",
    accentColor: "var(--operator-magnum-header)",
    stripeBg: "bg-[var(--operator-magnum-header)]/8",
    logoText: "MAGNUM",
    logoIcon: "M",
  },
  "Da Ma Cai 1+3D": {
    headerBg: "bg-[var(--operator-damacai-header)]",
    border: "border-[var(--operator-damacai-border)]",
    label: "text-[var(--operator-damacai-label)]",
    accentColor: "var(--operator-damacai-header)",
    stripeBg: "bg-[var(--operator-damacai-header)]/8",
    logoText: "DAMACAI",
    logoIcon: "D",
  },
  "Sports Toto 4D": {
    headerBg: "bg-[var(--operator-toto-header)]",
    border: "border-[var(--operator-toto-border)]",
    label: "text-[var(--operator-toto-label)]",
    accentColor: "var(--operator-toto-header)",
    stripeBg: "bg-[var(--operator-toto-header)]/8",
    logoText: "TOTO",
    logoIcon: "T",
  },
};

/** Operators that can be selected for betting (RM1 per number per bet type per operator). */
const BET_OPERATORS: string[] = [...DEFAULT_OPERATORS];

function getOperatorTheme(operator: string) {
  return OPERATOR_THEMES[operator] ?? {
    headerBg: "bg-muted",
    border: "border-border/70",
    label: "text-muted-foreground",
  };
}

function norm4(n: string): string {
  return String(n).trim().replace(/\D/g, "").padStart(4, "0").slice(-4);
}

/** Win highlight uses design token --success (index.css) for consistency. */
const HIGHLIGHT_CLASS =
  "border-[var(--success)] bg-[var(--success)]/20 text-foreground";

function NumberGrid({
  numbers,
  isHighlighted,
  is3DOnly,
  getTooltip,
  className = "",
}: {
  numbers: string[];
  isHighlighted?: (n4: string) => boolean;
  /** When true, highlight only the last 3 digits (for 3D-only match). */
  is3DOnly?: (n4: string) => boolean;
  getTooltip?: (n4: string) => string;
  className?: string;
}) {
  return (
    <div className={`grid grid-cols-5 gap-1 sm:gap-1.5 ${className}`}>
      {numbers.map((num) => {
        const n4 = norm4(num);
        const hit = isHighlighted?.(n4);
        const threeDOnly = hit && is3DOnly?.(n4);
        const cellClass = `rounded border px-1.5 py-1 text-center font-mono text-xs tabular-nums sm:text-sm ${
          hit && !threeDOnly ? HIGHLIGHT_CLASS : "border-border bg-muted/40"
        }`;
        const content =
          hit && threeDOnly ? (
            <>
              {n4.slice(0, 1)}
              <span className={`rounded px-0.5 ${HIGHLIGHT_CLASS}`}>{n4.slice(-3)}</span>
            </>
          ) : (
            n4
          );
        const tooltip = hit ? getTooltip?.(n4) ?? undefined : undefined;
        return (
          <span key={num} className={cellClass} title={tooltip}>
            {content}
          </span>
        );
      })}
    </div>
  );
}

function DrawCard({
  draw,
  animationDelay = 0,
  myNumbersSet,
  last3Set,
  bet4dBig,
  bet4dSmall,
  bet3dBig,
  bet3dSmall,
  selectedOperators,
}: {
  draw: LatestDraw;
  animationDelay?: number;
  myNumbersSet?: Set<string>;
  last3Set?: Set<string>;
  bet4dBig?: boolean;
  bet4dSmall?: boolean;
  bet3dBig?: boolean;
  bet3dSmall?: boolean;
  selectedOperators?: Set<string>;
}) {
  const { date, operator, draw_no, "1st": first, "2nd": second, "3rd": third, special, consolation } = draw;
  const theme = getOperatorTheme(operator);
  const isOperatorSelected = selectedOperators != null && selectedOperators.has(operator);
  const hasSets = myNumbersSet != null && last3Set != null && myNumbersSet.size > 0;
  const has4DBet = bet4dBig || bet4dSmall;
  const has3DBet = bet3dBig || bet3dSmall;
  const is4DMatch = (n4: string) => hasSets && myNumbersSet!.has(n4);
  const is3DMatch = (n4: string) => hasSets && last3Set!.has(n4.slice(-3));
  const show4D = (n4: string): boolean => Boolean(isOperatorSelected && is4DMatch(n4) && has4DBet);
  const show3D = (n4: string): boolean => Boolean(isOperatorSelected && is3DMatch(n4) && has3DBet);
  const isYourNumber = (n4: string): boolean => show4D(n4) || show3D(n4);
  const prizeTooltip = (prizeType: "1st" | "2nd" | "3rd", n4: string): string => {
    let total = 0;
    if (show4D(n4)) {
      total += (bet4dBig ? get4DPrizeRm(prizeType, false) : 0) + (bet4dSmall ? get4DPrizeRm(prizeType, true) : 0);
    }
    if (show3D(n4)) {
      total += (bet3dBig ? get3DPrizeRm(prizeType, false) : 0) + (bet3dSmall ? get3DPrizeRm(prizeType, true) : 0);
    }
    return total > 0 ? `RM ${total.toLocaleString()}` : "";
  };
  const specialTooltip = () => {
    const rm = bet4dBig ? get4DPrizeRm("Special", false) : 0;
    return rm > 0 ? `RM ${rm.toLocaleString()}` : "";
  };
  const consolationTooltip = () => {
    const rm = bet4dBig ? get4DPrizeRm("Consolation", false) : 0;
    return rm > 0 ? `RM ${rm.toLocaleString()}` : "";
  };
  const renderPrizeNumber = (val: string) => {
    if (!val) return "—";
    const n4 = norm4(val);
    if (!hasSets || !isYourNumber(n4)) return n4;
    if (show4D(n4)) return n4;
    return (
      <>
        {n4.slice(0, 1)}
        <span className={`rounded px-0.5 ${HIGHLIGHT_CLASS}`}>{n4.slice(-3)}</span>
      </>
    );
  };
  const prizeHit = (n4: string) => hasSets && (show4D(n4) || show3D(n4));
  const prizeTitle = (prizeType: "1st" | "2nd" | "3rd", n4: string): string | undefined => {
    const t = prizeTooltip(prizeType, n4);
    return t || undefined;
  };

  const accentVar = theme.accentColor;

  return (
    <SlipCard
      accent={accentVar}
      className="anim-result min-w-0"
      style={{ animationDelay: `${animationDelay}ms` }}
    >
      {/* ── Header band ──────────────────────────────── */}
      <div className={`slip-header ${theme.headerBg}`}>
        <div className="flex items-center gap-2">
          <span className="slip-logo-badge">{theme.logoIcon}</span>
          <span className="text-sm font-extrabold uppercase tracking-wide">{theme.logoText}</span>
          <span className="ml-0.5 text-[10px] font-bold text-white/70">4D</span>
        </div>
        <span className="text-[10px] font-semibold tabular-nums text-white/80">#{draw_no}</span>
      </div>

      {/* ── Date sub-strip ───────────────────────────── */}
      <div className="slip-date-strip" style={{ borderColor: `color-mix(in srgb, ${accentVar} 30%, transparent)` }}>
        <span className="text-[10px] font-semibold uppercase tracking-widest" style={{ color: accentVar }}>
          Draw Date
        </span>
        <span className="font-mono text-xs font-bold tabular-nums" style={{ color: accentVar }}>
          {date}
        </span>
      </div>

      {/* ── Slip body (paper) ────────────────────────── */}
      <div className="slip-body">
        {/* Top 3 prizes */}
        <table className="slip-prize-table" role="presentation">
          <tbody>
            {([["1st Prize", first, "1st"], ["2nd Prize", second, "2nd"], ["3rd Prize", third, "3rd"]] as const).map(([label, val, type]) => {
              if (!val) return null;
              const n4 = norm4(val);
              const hit = prizeHit(n4);
              return (
                <tr key={type}>
                  <td
                    className="slip-prize-label"
                    style={{ color: accentVar }}
                  >
                    {label}
                  </td>
                  <td className="slip-prize-num">
                    <span
                      className={hit ? "slip-prize-hit" : undefined}
                      title={hit ? prizeTitle(type, n4) : undefined}
                    >
                      {renderPrizeNumber(val)}
                    </span>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>

        {/* Special */}
        {special.length > 0 && (
          <>
            <div className="slip-section-divider" />
            <p className="slip-section-label" style={{ color: accentVar }}>Special</p>
            <NumberGrid
              numbers={special}
              isHighlighted={hasSets ? show4D : undefined}
              getTooltip={hasSets ? (n4) => (show4D(n4) ? specialTooltip() : "") : undefined}
              className="slip-numgrid"
            />
          </>
        )}

        {/* Consolation */}
        {consolation.length > 0 && (
          <>
            <div className="slip-section-divider" />
            <p className="slip-section-label" style={{ color: accentVar }}>Consolation</p>
            <NumberGrid
              numbers={consolation}
              isHighlighted={hasSets ? show4D : undefined}
              getTooltip={hasSets ? (n4) => (show4D(n4) ? consolationTooltip() : "") : undefined}
              className="slip-numgrid"
            />
          </>
        )}
      </div>
    </SlipCard>
  );
}

const DATE_FORMAT = "yyyy-MM-dd";

/** Extract valid 4-digit numbers from a blob of text. */
function extractNumbers(text: string): string[] {
  const raw = text
    .split(/[\s,\n]+/)
    .map((s) => s.replace(/\D/g, ""))
    .filter((s) => s.length >= 3);
  const out: string[] = [];
  const seen = new Set<string>();
  for (const s of raw) {
    const four = s.length >= 4 ? s.slice(-4) : s.padStart(4, "0");
    if (four.length === 4 && !seen.has(four)) {
      seen.add(four);
      out.push(four);
    }
  }
  return out;
}

type NumberHit = {
  operator: string;
  prizeType: string;
  is3D: boolean;
  prizeRm: number;
};

function checkNumberInDraws(
  num: string,
  draws: LatestDraw[],
  bet4dBig: boolean,
  bet4dSmall: boolean,
  bet3dBig: boolean,
  bet3dSmall: boolean,
  selectedOperators?: Set<string>,
): { hits: NumberHit[]; totalRm: number } {
  const hits: NumberHit[] = [];
  const last3 = num.slice(-3);
  for (const d of draws) {
    if (selectedOperators && !selectedOperators.has(d.operator)) continue;
    const first = (d["1st"] ?? "").trim().padStart(4, "0").slice(-4);
    const second = (d["2nd"] ?? "").trim().padStart(4, "0").slice(-4);
    const third = (d["3rd"] ?? "").trim().padStart(4, "0").slice(-4);
    const special = (d.special ?? []).map((s) => String(s).trim().replace(/\D/g, "").padStart(4, "0").slice(-4));
    const consolation = (d.consolation ?? []).map((s) => String(s).trim().replace(/\D/g, "").padStart(4, "0").slice(-4));
    const n4 = num.padStart(4, "0").slice(-4);
    if (n4 === first) {
      const rm = (bet4dBig ? get4DPrizeRm("1st", false) : 0) + (bet4dSmall ? get4DPrizeRm("1st", true) : 0);
      if (rm > 0) hits.push({ operator: d.operator, prizeType: "1st", is3D: false, prizeRm: rm });
    }
    if (n4 === second) {
      const rm = (bet4dBig ? get4DPrizeRm("2nd", false) : 0) + (bet4dSmall ? get4DPrizeRm("2nd", true) : 0);
      if (rm > 0) hits.push({ operator: d.operator, prizeType: "2nd", is3D: false, prizeRm: rm });
    }
    if (n4 === third) {
      const rm = (bet4dBig ? get4DPrizeRm("3rd", false) : 0) + (bet4dSmall ? get4DPrizeRm("3rd", true) : 0);
      if (rm > 0) hits.push({ operator: d.operator, prizeType: "3rd", is3D: false, prizeRm: rm });
    }
    if (special.includes(n4)) {
      const rm = bet4dBig ? get4DPrizeRm("Special", false) : 0;
      if (rm > 0) hits.push({ operator: d.operator, prizeType: "Special", is3D: false, prizeRm: rm });
    }
    if (consolation.includes(n4)) {
      const rm = bet4dBig ? get4DPrizeRm("Consolation", false) : 0;
      if (rm > 0) hits.push({ operator: d.operator, prizeType: "Consolation", is3D: false, prizeRm: rm });
    }
    const f3 = first.slice(-3);
    const s3 = second.slice(-3);
    const t3 = third.slice(-3);
    if (last3 === f3) {
      const rm = (bet3dBig ? get3DPrizeRm("1st", false) : 0) + (bet3dSmall ? get3DPrizeRm("1st", true) : 0);
      if (rm > 0) hits.push({ operator: d.operator, prizeType: "3D 1st", is3D: true, prizeRm: rm });
    }
    if (last3 === s3) {
      const rm = bet3dBig ? get3DPrizeRm("2nd", false) : 0;
      if (rm > 0) hits.push({ operator: d.operator, prizeType: "3D 2nd", is3D: true, prizeRm: rm });
    }
    if (last3 === t3) {
      const rm = bet3dBig ? get3DPrizeRm("3rd", false) : 0;
      if (rm > 0) hits.push({ operator: d.operator, prizeType: "3D 3rd", is3D: true, prizeRm: rm });
    }
  }
  const totalRm = hits.reduce((s, h) => s + h.prizeRm, 0);
  return { hits, totalRm };
}

function parseDateYMD(str: string): Date | null {
  if (!str) return null;
  const d = new Date(str + "T12:00:00");
  return Number.isNaN(d.getTime()) ? null : d;
}

function formatDateYMD(d: Date): string {
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  return `${y}-${m}-${day}`;
}

// Copy constants (clarified, user-facing)
const PAGE_TITLE = "4D draw results";
const PAGE_DESC_LATEST = "Winning numbers from the most recent draw for each operator. Use the controls below to view a different date.";
const PAGE_DESC_DATE = (d: string) => `Results for ${d}. The calendar only lists dates that have draw data.`;
const LABEL_VIEW_DATE = "View results for date";
const PLACEHOLDER_DATE = "Choose a date with results";
const BTN_LATEST = "Show latest";
const BTN_TRY_AGAIN = "Try again";
const ERROR_TITLE = "Results couldn’t be loaded";
const ERROR_DESC = "Something went wrong fetching draw data. Check your connection and try again.";
const EMPTY_LATEST = "No draw data to show yet. Add history data to the app, then come back here.";
const EMPTY_DATE = (d: string) => `No results for ${d}. Pick another date from the calendar.`;
const LOADING_SR = "Loading draw results…";
const CHECK_PLACEHOLDER = "1234 5678 9012…";

function ResultsPage() {
  const { date: selectedDate } = Route.useSearch();
  const navigate = useNavigate();
  const chipInputRef = useRef<HTMLInputElement>(null);

  const myNumbers = useResultsStore((s) => s.myNumbers);
  const selectedOperators = useResultsStore((s) => s.selectedOperators);
  const bet4dBig = useResultsStore((s) => s.bet4dBig);
  const bet4dSmall = useResultsStore((s) => s.bet4dSmall);
  const bet3dBig = useResultsStore((s) => s.bet3dBig);
  const bet3dSmall = useResultsStore((s) => s.bet3dSmall);

  const addNumbersStore = useResultsStore((s) => s.addNumbers);
  const removeNumber = useResultsStore((s) => s.removeNumber);
  const clearNumbers = useResultsStore((s) => s.clearNumbers);
  const setBet4dBig = useResultsStore((s) => s.setBet4dBig);
  const setBet4dSmall = useResultsStore((s) => s.setBet4dSmall);
  const setBet3dBig = useResultsStore((s) => s.setBet3dBig);
  const setBet3dSmall = useResultsStore((s) => s.setBet3dSmall);
  const toggleOperator = useResultsStore((s) => s.toggleOperator);
  const trackingEnabled = useResultsStore((s) => s.trackingEnabled);
  const visitedDates = useResultsStore((s) => s.visitedDates);
  const accumulatedCost = useResultsStore((s) => s.accumulatedCost);
  const accumulatedWon = useResultsStore((s) => s.accumulatedWon);
  const currentDrySpell = useResultsStore((s) => s.currentDrySpell);
  const drySpellLengths = useResultsStore((s) => s.drySpellLengths);
  const setTrackingEnabled = useResultsStore((s) => s.setTrackingEnabled);
  const recordVisit = useResultsStore((s) => s.recordVisit);
  const resetTracking = useResultsStore((s) => s.resetTracking);

  const [chipInput, setChipInput] = useState("");

  const addNumbers = useCallback(
    (text: string) => {
      const nums = extractNumbers(text);
      if (nums.length > 0) addNumbersStore(nums);
    },
    [addNumbersStore],
  );

  const clearAllNumbers = useCallback(() => {
    clearNumbers();
    setChipInput("");
    chipInputRef.current?.focus();
  }, [clearNumbers]);

  const { data: drawDatesData } = useQuery({
    queryKey: ["draw-dates"],
    queryFn: fetchDrawDates,
  });
  const drawDates = drawDatesData?.dates ?? [];
  const drawDatesSet = new Set(drawDates);

  const { data, isPending, isFetching, error, refetch } = useQuery({
    queryKey: selectedDate ? ["draws", selectedDate] : ["latest-draws"],
    queryFn: selectedDate ? () => fetchDrawsForDate(selectedDate) : fetchLatestDraws,
    placeholderData: keepPreviousData,
  });

  const draws = data?.draws ?? [];
  const isLoading = isPending && draws.length === 0;
  const isLatest = !selectedDate;
  const currentIndex = selectedDate ? drawDates.indexOf(selectedDate) : -1;
  const prevDate =
    isLatest ? (drawDates.length > 1 ? drawDates[1] : null) : currentIndex < drawDates.length - 1 ? drawDates[currentIndex + 1] : null;
  const nextDate =
    currentIndex > 0 ? drawDates[currentIndex - 1] : currentIndex === 0 ? "latest" : null;

  useEffect(() => {
    if (!prevDate) return;
    queryClient.prefetchQuery({
      queryKey: ["draws", prevDate],
      queryFn: () => fetchDrawsForDate(prevDate),
    });
  }, [prevDate]);
  useEffect(() => {
    if (nextDate === null) return;
    if (nextDate === "latest") {
      queryClient.prefetchQuery({ queryKey: ["latest-draws"], queryFn: fetchLatestDraws });
    } else {
      queryClient.prefetchQuery({
        queryKey: ["draws", nextDate],
        queryFn: () => fetchDrawsForDate(nextDate),
      });
    }
  }, [nextDate]);

  const myNumbersSet = useMemo(() => new Set(myNumbers), [myNumbers]);
  const last3Set = useMemo(() => new Set(myNumbers.map((n) => n.slice(-3))), [myNumbers]);
  const selectedOperatorsSet = useMemo(() => new Set(selectedOperators), [selectedOperators]);
  const betCount = [bet4dBig, bet4dSmall, bet3dBig, bet3dSmall].filter(Boolean).length;
  const operatorCount = selectedOperators.length;
  const totalCost = myNumbers.length * betCount * operatorCount;
  const totalWon = useMemo(
    () =>
      myNumbers.reduce(
        (sum, num) =>
          sum +
          checkNumberInDraws(
            num,
            draws,
            bet4dBig,
            bet4dSmall,
            bet3dBig,
            bet3dSmall,
            selectedOperatorsSet,
          ).totalRm,
        0,
      ),
    [myNumbers, draws, bet4dBig, bet4dSmall, bet3dBig, bet3dSmall, selectedOperatorsSet],
  );

  const viewKey = selectedDate ?? (draws[0]?.date ?? null);

  const drySpellStats = useMemo(() => {
    const arr = drySpellLengths;
    if (arr.length === 0) return { avg: null, median: null, stdDev: null };
    const sorted = [...arr].sort((a, b) => a - b);
    const n = arr.length;
    const sum = arr.reduce((a, b) => a + b, 0);
    const avg = sum / n;
    const median =
      n % 2 === 1 ? sorted[(n - 1) / 2]! : (sorted[n / 2 - 1]! + sorted[n / 2]!) / 2;
    const variance = arr.reduce((acc, x) => acc + (x - avg) ** 2, 0) / n;
    const stdDev = Math.sqrt(variance);
    return { avg, median, stdDev };
  }, [drySpellLengths]);

  useEffect(() => {
    if (!trackingEnabled || !viewKey || draws.length === 0) return;
    if (visitedDates.includes(viewKey)) return;
    recordVisit(viewKey, totalCost, totalWon);
  }, [trackingEnabled, viewKey, draws.length, totalCost, totalWon, visitedDates, recordVisit]);

  const goToPrev = () => {
    if (prevDate) navigate({ to: "/results", search: { date: prevDate } });
  };
  const goToNext = () => {
    if (nextDate === "latest") navigate({ to: "/results", search: { date: undefined } });
    else if (nextDate) navigate({ to: "/results", search: { date: nextDate } });
  };
  const goToLatest = () => navigate({ to: "/results", search: { date: undefined } });
  const onCalendarChange = (value: Date | null) => {
    if (!value) return;
    const ymd = formatDateYMD(value);
    if (drawDatesSet.has(ymd)) navigate({ to: "/results", search: { date: ymd } });
  };

  if (error) {
    return (
      <div className="mx-auto w-full max-w-6xl space-y-6 px-4 py-6 md:px-6 md:py-8">
        <header className="space-y-2">
          <h1 className="font-display text-2xl font-semibold tracking-tight text-foreground md:text-3xl">
            {PAGE_TITLE}
          </h1>
          <p className="max-w-2xl text-sm leading-relaxed text-muted-foreground md:text-base">
            {PAGE_DESC_LATEST}
          </p>
        </header>
        <Card className="border-2 border-destructive/50 bg-destructive/5" role="alert">
          <CardHeader className="pb-2">
            <CardTitle className="font-display text-xl font-bold text-destructive">{ERROR_TITLE}</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            <p className="text-sm text-muted-foreground">{ERROR_DESC}</p>
            <p className="text-xs text-muted-foreground">{error instanceof Error ? error.message : ""}</p>
            <Button
              type="button"
              variant="outline"
              size="sm"
              className="border-destructive/50 text-destructive hover:bg-destructive/10"
              onClick={() => refetch()}
            >
              {BTN_TRY_AGAIN}
            </Button>
          </CardContent>
        </Card>
      </div>
    );
  }

  return (
    <div className="mx-auto w-full max-w-6xl space-y-6 px-4 py-6 md:px-6 md:py-8">
      <header className="space-y-2">
        <h1 className="font-display text-2xl font-semibold tracking-tight text-foreground md:text-3xl">
          {PAGE_TITLE}
        </h1>
        <p className="max-w-2xl text-sm leading-relaxed text-muted-foreground md:text-base">
          {isLatest ? PAGE_DESC_LATEST : PAGE_DESC_DATE(selectedDate!)}
        </p>
        <div className="flex flex-wrap items-center gap-2 pt-1" role="group" aria-label="Choose which draw to view">
          {!isLatest && (
            <Button type="button" variant="ghost" size="sm" className="h-8 shrink-0 text-xs" onClick={goToLatest}>
              {BTN_LATEST}
            </Button>
          )}
          <Label htmlFor="results-draw-date" className="sr-only">{LABEL_VIEW_DATE}</Label>
          <DatePickerComponent
            id="results-draw-date"
            value={selectedDate ? parseDateYMD(selectedDate) ?? undefined : undefined}
            format={DATE_FORMAT}
            placeholder={PLACEHOLDER_DATE}
            strictMode={false}
            change={(e) => onCalendarChange(e.value ?? null)}
            renderDayCell={(args: { date: Date; isDisabled: boolean }) => {
              const ymd = formatDateYMD(args.date);
              if (!drawDatesSet.has(ymd)) {
                (args as { isDisabled?: boolean }).isDisabled = true;
              }
            }}
            cssClass="dp-compact w-24 text-sm"
          />
        </div>
      </header>

      <div className="flex items-stretch gap-0" role="group" aria-label="Navigate between draws">
        <div className="flex shrink-0 items-center pr-2 md:pr-4">
          <Button
            type="button"
            variant="ghost"
            size="icon"
            className="size-10 shrink-0 rounded-full"
            disabled={!prevDate}
            onClick={goToPrev}
            aria-label="View older draw"
          >
            <ChevronLeft className="size-5" />
          </Button>
        </div>
        <div
          className={`min-w-0 flex-1 transition-opacity duration-200 ${isFetching ? "opacity-90" : ""}`}
          aria-busy={isFetching}
        >
          {isLoading ? (
            <div
              className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3"
              aria-busy="true"
              aria-live="polite"
              aria-label="Loading draw results"
            >
              <span className="sr-only">{LOADING_SR}</span>
              {[1, 2, 3].map((i) => (
                <Card key={i} className="border border-border/70">
                  <CardHeader className="pb-2">
                    <div className="h-5 w-32 animate-pulse rounded bg-muted/70" />
                    <div className="h-3 w-24 animate-pulse rounded bg-muted/70" />
                  </CardHeader>
                  <CardContent className="space-y-4">
                    <div className="grid gap-2 sm:grid-cols-3">
                      {[1, 2, 3].map((j) => (
                        <div key={j} className="h-12 animate-pulse rounded-md bg-muted/70" />
                      ))}
                    </div>
                  </CardContent>
                </Card>
              ))}
            </div>
          ) : draws.length === 0 ? (
            <Card className="border border-border/70 bg-muted/10">
              <CardContent className="py-8 text-center">
                <p className="text-sm text-muted-foreground">
                  {selectedDate ? EMPTY_DATE(selectedDate) : EMPTY_LATEST}
                </p>
              </CardContent>
            </Card>
          ) : (
            <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
              {draws.map((draw, i) => (
                <DrawCard
                  key={`${draw.operator}-${draw.date}`}
                  draw={draw}
                  animationDelay={i * 80}
                  myNumbersSet={myNumbersSet}
                  last3Set={last3Set}
                  bet4dBig={bet4dBig}
                  bet4dSmall={bet4dSmall}
                  bet3dBig={bet3dBig}
                  bet3dSmall={bet3dSmall}
                  selectedOperators={selectedOperatorsSet}
                />
              ))}
            </div>
          )}
        </div>
        <div className="flex shrink-0 items-center pl-2 md:pl-4">
          <Button
            type="button"
            variant="ghost"
            size="icon"
            className="size-10 shrink-0 rounded-full"
            disabled={nextDate === null}
            onClick={goToNext}
            aria-label={nextDate === "latest" ? "Show latest draw" : "View newer draw"}
          >
            <ChevronRight className="size-5" />
          </Button>
        </div>
      </div>

      {/* ── Betting slip ─────────────────────────────────────── */}
      <div className="overflow-hidden rounded-xl border border-border/70 bg-card shadow-sm">
        {/* Number chips + inline input */}
        <div
          className="flex min-h-10 cursor-text flex-wrap items-center gap-1.5 px-3 py-2 sm:px-4"
          onClick={() => chipInputRef.current?.focus()}
        >
          {myNumbers.map((num) => (
            <span
              key={num}
              className="anim-row inline-flex items-center gap-1 rounded-md border border-border bg-muted/50 py-0.5 pl-2 pr-1 font-mono text-xs font-medium tabular-nums text-foreground"
            >
              {num}
              <button
                type="button"
                onClick={(e) => { e.stopPropagation(); removeNumber(num); }}
                className="inline-flex size-4 items-center justify-center rounded text-muted-foreground/70 transition-colors hover:bg-destructive/15 hover:text-destructive focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
                aria-label={`Remove ${num}`}
              >
                <X className="size-3" />
              </button>
            </span>
          ))}
          <input
            ref={chipInputRef}
            id="results-paste-numbers"
            type="text"
            inputMode="numeric"
            value={chipInput}
            onChange={(e) => {
              const val = e.target.value;
              if (/[\s,]/.test(val)) {
                addNumbers(val);
                setChipInput("");
                return;
              }
              const digits = val.replace(/\D/g, "");
              if (digits.length >= 4) {
                addNumbers(digits);
                setChipInput("");
              } else {
                setChipInput(digits);
              }
            }}
            onKeyDown={(e) => {
              if (e.key === "Enter") {
                e.preventDefault();
                if (chipInput.trim()) {
                  addNumbers(chipInput);
                  setChipInput("");
                }
              }
              if (e.key === "Backspace" && chipInput === "" && myNumbers.length > 0) {
                removeNumber(myNumbers[myNumbers.length - 1]);
              }
            }}
            onPaste={(e) => {
              e.preventDefault();
              const text = e.clipboardData.getData("text/plain");
              addNumbers(text);
              setChipInput("");
            }}
            placeholder={myNumbers.length === 0 ? CHECK_PLACEHOLDER : "Add more…"}
            className="min-w-[5rem] flex-1 bg-transparent py-1 font-mono text-sm tabular-nums placeholder:text-muted-foreground/50 focus-visible:outline-none"
            aria-label="Type or paste numbers"
          />
          {myNumbers.length > 0 && (
            <button
              type="button"
              onClick={clearAllNumbers}
              className="ml-auto shrink-0 rounded px-1.5 py-0.5 text-[10px] font-medium uppercase tracking-wider text-muted-foreground transition-colors hover:bg-muted hover:text-foreground focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
            >
              Clear
            </button>
          )}
        </div>

        {/* Operators + bet types + results strip */}
        <div className="flex flex-wrap items-center gap-x-3 gap-y-2 border-t border-border/60 bg-muted/15 px-3 py-2 sm:px-4">
          <div className="flex flex-wrap items-center gap-1.5" role="group" aria-label="Operators">
            {BET_OPERATORS.map((op) => (
              <button
                key={op}
                type="button"
                role="switch"
                aria-checked={selectedOperators.includes(op)}
                aria-label={op}
                onClick={() => toggleOperator(op)}
                className={`rounded-full border px-2 py-0.5 text-[11px] font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-1 ${
                  selectedOperators.includes(op)
                    ? "border-primary/60 bg-primary/10 text-foreground"
                    : "border-border bg-muted/40 text-muted-foreground hover:bg-muted/60"
                }`}
              >
                {op.replace(/\s*4D$|\s*1\+3D$/i, "").trim() || op}
              </button>
            ))}
          </div>
          <span className="h-3 w-px bg-border" aria-hidden />
          <div className="flex flex-wrap items-center gap-1.5" role="group" aria-label="Bet types">
            {([
              ["4D Big", bet4dBig, setBet4dBig],
              ["4D Small", bet4dSmall, setBet4dSmall],
              ["3D Big", bet3dBig, setBet3dBig],
              ["3D Small", bet3dSmall, setBet3dSmall],
            ] as const).map(([label, checked, setter]) => (
              <button
                key={label}
                type="button"
                role="switch"
                aria-checked={checked}
                aria-label={label}
                onClick={() => setter(!checked)}
                className={`rounded-full border px-2.5 py-0.5 text-[11px] font-medium tabular-nums transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-1 ${
                  checked
                    ? "border-primary/60 bg-primary/10 text-foreground"
                    : "border-border bg-muted/40 text-muted-foreground hover:bg-muted/60"
                }`}
              >
                {label}
              </button>
            ))}
          </div>
          {myNumbers.length > 0 && (
            <>
              <span className="hidden h-3 w-px bg-border sm:block" aria-hidden />
              <div className="flex flex-wrap items-center gap-2.5 text-xs tabular-nums">
                <span>
                  Cost <span className="font-semibold text-foreground">RM {totalCost}</span>
                  {(betCount > 0 || operatorCount > 0) && (
                    <span className="ml-0.5 text-muted-foreground">
                      ({myNumbers.length}×{betCount}×{operatorCount})
                    </span>
                  )}
                </span>
                <span className="h-3 w-px bg-border" aria-hidden />
                <span>
                  Won <span className="profit">RM {totalWon}</span>
                </span>
                <span className="h-3 w-px bg-border" aria-hidden />
                <span className={`font-semibold ${totalWon - totalCost >= 0 ? "profit" : "loss"}`}>
                  {totalWon - totalCost >= 0 ? "+" : ""}RM {totalWon - totalCost}
                </span>
              </div>
            </>
          )}
        </div>

        {/* Track across draws — accumulate cost/won per date, no double-count */}
        <div className="flex flex-wrap items-center gap-x-3 gap-y-2 border-t border-border/60 bg-muted/10 px-3 py-2 sm:px-4">
          <button
            type="button"
            role="switch"
            aria-checked={trackingEnabled}
            aria-label="Track cost and profit across draw dates"
            onClick={() => setTrackingEnabled(!trackingEnabled)}
            className={`rounded-full border px-2.5 py-0.5 text-[11px] font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-1 ${
              trackingEnabled
                ? "border-primary/60 bg-primary/10 text-foreground"
                : "border-border bg-muted/40 text-muted-foreground hover:bg-muted/60"
            }`}
          >
            Track across draws
          </button>
          {trackingEnabled && (
            <>
              <span className="h-3 w-px bg-border" aria-hidden />
              <div className="flex flex-wrap items-center gap-2.5 text-xs tabular-nums text-muted-foreground">
                <span>
                  Accumulated: Cost <span className="font-semibold text-foreground">RM {accumulatedCost}</span>
                  {" · "}
                  Won <span className="profit">RM {accumulatedWon}</span>
                  {" · "}
                  Net{" "}
                  <span
                    className={`font-semibold ${accumulatedWon - accumulatedCost >= 0 ? "profit" : "loss"}`}
                  >
                    {accumulatedWon - accumulatedCost >= 0 ? "+" : ""}RM {accumulatedWon - accumulatedCost}
                  </span>
                </span>
                <span className="text-muted-foreground/80">({visitedDates.length} dates)</span>
              </div>
              <span className="h-3 w-px bg-border" aria-hidden />
              <div className="flex flex-wrap items-center gap-x-2 gap-y-1 text-xs tabular-nums text-muted-foreground">
                <span>
                  Dry spell: {currentDrySpell} draw{currentDrySpell !== 1 ? "s" : ""}
                </span>
                {drySpellStats.avg != null && (
                  <>
                    <span className="text-muted-foreground/80">
                      Avg: {Math.round(drySpellStats.avg)} draws
                    </span>
                    <span className="text-muted-foreground/80">
                      Median: {Number.isInteger(drySpellStats.median) ? drySpellStats.median : drySpellStats.median.toFixed(1)} draws
                    </span>
                    <span className="text-muted-foreground/80">
                      σ: {drySpellStats.stdDev.toFixed(1)} draws
                    </span>
                  </>
                )}
              </div>
              <button
                type="button"
                onClick={resetTracking}
                className="rounded px-1.5 py-0.5 text-[10px] font-medium uppercase tracking-wider text-muted-foreground transition-colors hover:bg-muted hover:text-foreground focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
              >
                Reset
              </button>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
