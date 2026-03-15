import { create } from "zustand";
import { persist, createJSONStorage } from "zustand/middleware";

/** Default operator list for bet slip; must match OPERATOR_THEMES keys in results.tsx. */
export const DEFAULT_OPERATORS = [
  "Magnum 4D",
  "Da Ma Cai 1+3D",
  "Sports Toto 4D",
] as const;

export type ResultsState = {
  myNumbers: string[];
  selectedOperators: string[];
  bet4dBig: boolean;
  bet4dSmall: boolean;
  bet3dBig: boolean;
  bet3dSmall: boolean;
  /** When true, accumulate cost/won as user navigates draw dates (no double-count per date). */
  trackingEnabled: boolean;
  /** Draw dates already counted into accumulated cost/won. */
  visitedDates: string[];
  accumulatedCost: number;
  accumulatedWon: number;
  /** Last draw date (YYYY-MM-DD) where user had a win. */
  lastWinDate: string | null;
  /** Running count: +1 per no-win draw visited, reset to 0 on win. */
  currentDrySpell: number;
  /** Completed dry spell lengths (for average). Pushed when a win ends a dry spell. */
  drySpellLengths: number[];
};

type ResultsActions = {
  setMyNumbers: (numbers: string[] | ((prev: string[]) => string[])) => void;
  addNumbers: (numbers: string[]) => void;
  removeNumber: (num: string) => void;
  clearNumbers: () => void;
  setBet4dBig: (v: boolean) => void;
  setBet4dSmall: (v: boolean) => void;
  setBet3dBig: (v: boolean) => void;
  setBet3dSmall: (v: boolean) => void;
  toggleOperator: (operator: string) => void;
  setTrackingEnabled: (v: boolean) => void;
  /** Record this draw date's cost and won (idempotent per date). Updates currentDrySpell: +1 if no win, 0 if win. */
  recordVisit: (dateKey: string, cost: number, won: number) => void;
  resetTracking: () => void;
};

const defaultOperatorsSet = new Set<string>(DEFAULT_OPERATORS);

function validateOperators(operators: string[]): string[] {
  const valid = operators.filter((o) => defaultOperatorsSet.has(o));
  return valid.length > 0 ? valid : [...DEFAULT_OPERATORS];
}

function validateNumbers(numbers: unknown): string[] {
  if (!Array.isArray(numbers)) return [];
  return (numbers as string[]).filter((n) => typeof n === "string" && /^\d{4}$/.test(n));
}

export const useResultsStore = create<ResultsState & ResultsActions>()(
  persist(
    (set) => ({
      myNumbers: [],
      selectedOperators: [...DEFAULT_OPERATORS],
      bet4dBig: true,
      bet4dSmall: false,
      bet3dBig: true,
      bet3dSmall: false,
      trackingEnabled: false,
      visitedDates: [],
      accumulatedCost: 0,
      accumulatedWon: 0,
      lastWinDate: null,
      currentDrySpell: 0,
      drySpellLengths: [],

      setMyNumbers: (payload) =>
        set((s) => ({
          myNumbers: typeof payload === "function" ? payload(s.myNumbers) : payload,
        })),

      addNumbers: (numbers) =>
        set((s) => {
          const existing = new Set(s.myNumbers);
          const merged = [...s.myNumbers];
          for (const n of numbers) {
            if (!existing.has(n)) {
              existing.add(n);
              merged.push(n);
            }
          }
          return { myNumbers: merged };
        }),

      removeNumber: (num) =>
        set((s) => ({ myNumbers: s.myNumbers.filter((n) => n !== num) })),

      clearNumbers: () => set({ myNumbers: [] }),

      setBet4dBig: (v) => set({ bet4dBig: v }),
      setBet4dSmall: (v) => set({ bet4dSmall: v }),
      setBet3dBig: (v) => set({ bet3dBig: v }),
      setBet3dSmall: (v) => set({ bet3dSmall: v }),

      toggleOperator: (operator) =>
        set((s) => {
          const next = s.selectedOperators.includes(operator)
            ? s.selectedOperators.filter((o) => o !== operator)
            : [...s.selectedOperators, operator];
          return {
            selectedOperators: next.length > 0 ? next : [...DEFAULT_OPERATORS],
          };
        }),

      setTrackingEnabled: (v) => set({ trackingEnabled: v }),

      recordVisit: (dateKey, cost, won) =>
        set((s) => {
          if (s.visitedDates.includes(dateKey)) return s;
          const nextVisited = [...s.visitedDates, dateKey];
          const nextCost = s.accumulatedCost + cost;
          const nextWon = s.accumulatedWon + won;
          let nextLastWin = s.lastWinDate;
          let nextCurrentDrySpell = s.currentDrySpell;
          let nextDrySpellLengths = s.drySpellLengths;
          if (won > 0) {
            if (s.currentDrySpell > 0) nextDrySpellLengths = [...s.drySpellLengths, s.currentDrySpell];
            nextCurrentDrySpell = 0;
            nextLastWin = dateKey;
          } else {
            nextCurrentDrySpell = s.currentDrySpell + 1;
          }
          return {
            visitedDates: nextVisited,
            accumulatedCost: nextCost,
            accumulatedWon: nextWon,
            lastWinDate: nextLastWin,
            currentDrySpell: nextCurrentDrySpell,
            drySpellLengths: nextDrySpellLengths,
          };
        }),

      resetTracking: () =>
        set({
          visitedDates: [],
          accumulatedCost: 0,
          accumulatedWon: 0,
          lastWinDate: null,
          currentDrySpell: 0,
          drySpellLengths: [],
        }),
    }),
    {
      name: "4d-results-betslip",
      storage: createJSONStorage<ResultsState>(() => localStorage),
      partialize: (state) => ({
        myNumbers: state.myNumbers,
        selectedOperators: state.selectedOperators,
        bet4dBig: state.bet4dBig,
        bet4dSmall: state.bet4dSmall,
        bet3dBig: state.bet3dBig,
        bet3dSmall: state.bet3dSmall,
        trackingEnabled: state.trackingEnabled,
        visitedDates: state.visitedDates,
        accumulatedCost: state.accumulatedCost,
        accumulatedWon: state.accumulatedWon,
        lastWinDate: state.lastWinDate,
        currentDrySpell: state.currentDrySpell,
        drySpellLengths: state.drySpellLengths,
      }),
      merge: (persisted, current) => {
        const p = persisted as Partial<ResultsState> | undefined;
        if (!p) return current;
        return {
          ...current,
          myNumbers: validateNumbers(p.myNumbers) ?? current.myNumbers,
          selectedOperators: validateOperators(p.selectedOperators ?? current.selectedOperators),
          bet4dBig: typeof p.bet4dBig === "boolean" ? p.bet4dBig : current.bet4dBig,
          bet4dSmall: typeof p.bet4dSmall === "boolean" ? p.bet4dSmall : current.bet4dSmall,
          bet3dBig: typeof p.bet3dBig === "boolean" ? p.bet3dBig : current.bet3dBig,
          bet3dSmall: typeof p.bet3dSmall === "boolean" ? p.bet3dSmall : current.bet3dSmall,
          trackingEnabled: typeof p.trackingEnabled === "boolean" ? p.trackingEnabled : current.trackingEnabled,
          visitedDates: Array.isArray(p.visitedDates) ? p.visitedDates : current.visitedDates,
          accumulatedCost: typeof p.accumulatedCost === "number" ? p.accumulatedCost : current.accumulatedCost,
          accumulatedWon: typeof p.accumulatedWon === "number" ? p.accumulatedWon : current.accumulatedWon,
          lastWinDate:
            p.lastWinDate === null || (typeof p.lastWinDate === "string" && /^\d{4}-\d{2}-\d{2}$/.test(p.lastWinDate))
              ? p.lastWinDate ?? current.lastWinDate
              : current.lastWinDate,
          currentDrySpell: typeof p.currentDrySpell === "number" && p.currentDrySpell >= 0 ? p.currentDrySpell : current.currentDrySpell,
          drySpellLengths: Array.isArray(p.drySpellLengths)
            ? (p.drySpellLengths as number[]).filter((n) => typeof n === "number" && n >= 0)
            : current.drySpellLengths,
        };
      },
    },
  ),
);
