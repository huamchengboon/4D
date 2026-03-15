import { useState, useEffect } from "react";
import { createFileRoute, Link } from "@tanstack/react-router";
import { ExternalLink } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

const STRATEGY_SEARCH_KEY = "4d-strategy-search";

type StoredStrategySearch = {
  start_date?: string;
  end_date?: string;
  n?: number;
  chart_operator?: string[];
  chart_start_date?: string;
  chart_end_date?: string;
  bet_4d_big?: boolean;
  bet_4d_small?: boolean;
  bet_3d_big?: boolean;
  bet_3d_small?: boolean;
};

function getStoredStrategySearch(): StoredStrategySearch | null {
  if (typeof sessionStorage === "undefined") return null;
  try {
    const raw = sessionStorage.getItem(STRATEGY_SEARCH_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw) as StoredStrategySearch;
    return parsed && typeof parsed === "object" ? parsed : null;
  } catch {
    return null;
  }
}

export const Route = createFileRoute("/prizing")({
  component: PrizingPage,
});

const BET_TYPES = [
  { label: "4D Big", desc: "1st, 2nd, 3rd, Special, Consolation" },
  { label: "4D Small", desc: "1st, 2nd, 3rd only · higher payouts" },
  { label: "3D Big", desc: "Last 3 digits = 1st / 2nd / 3rd" },
  { label: "3D Small", desc: "Last 3 digits = 1st only" },
] as const;

const TABLE_4D = [
  { prize: "1st", big: "2,500", small: "3,500" },
  { prize: "2nd", big: "1,000", small: "2,000" },
  { prize: "3rd", big: "500", small: "1,000" },
  { prize: "Special", big: "180", small: "—" },
  { prize: "Consolation", big: "60", small: "—" },
];

const TABLE_3D = [
  { prize: "1st (last 3)", big: "250", small: "660" },
  { prize: "2nd", big: "210", small: "—" },
  { prize: "3rd", big: "150", small: "—" },
];

const SOURCES = [
  { label: "Magnum 4D Classic", href: "https://www.magnum4d.my/games/classic" },
  { label: "Sports Toto", href: "https://www.sportstoto.com.my/" },
  { label: "4dmoon Da Ma Cai", href: "https://www.4dmoon.com/damacai-prize-structure" },
  { label: "live4d2u prize structure", href: "https://www.live4d2u.net/malaysia-prize-structure" },
];

function PrizingPage() {
  const [backSearch, setBackSearch] = useState<StoredStrategySearch | null>(null);

  useEffect(() => {
    setBackSearch(getStoredStrategySearch());
  }, []);

  const linkSearch = backSearch
    ? {
        start_date: backSearch.start_date ?? undefined,
        end_date: backSearch.end_date ?? undefined,
        n: backSearch.n ?? 24,
        chart_operator: Array.isArray(backSearch.chart_operator) ? backSearch.chart_operator : [],
        chart_start_date: backSearch.chart_start_date ?? undefined,
        chart_end_date: backSearch.chart_end_date ?? undefined,
        bet_4d_big: backSearch.bet_4d_big ?? true,
        bet_4d_small: backSearch.bet_4d_small ?? false,
        bet_3d_big: backSearch.bet_3d_big ?? true,
        bet_3d_small: backSearch.bet_3d_small ?? false,
      }
    : {
        start_date: undefined,
        end_date: undefined,
        n: 24,
        chart_operator: [] as string[],
        chart_start_date: undefined,
        chart_end_date: undefined,
        bet_4d_big: true,
        bet_4d_small: false,
        bet_3d_big: true,
        bet_3d_small: false,
      };

  return (
    <div className="mx-auto w-full max-w-6xl space-y-5 px-4 py-6 md:px-6 md:py-8">
      <header className="space-y-2">
        <h1 className="font-display text-2xl font-semibold tracking-tight md:text-3xl">Prizing</h1>
        <p className="max-w-2xl text-sm leading-relaxed text-muted-foreground md:text-base">
          RM1 per type. Strategy uses your selection for cost and prizes.
        </p>
      </header>

      <Card className="border-border/70 bg-card shadow-sm">
        <CardHeader className="pb-3">
          <CardTitle className="text-lg">Bet types · RM1 each</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <p className="text-sm text-muted-foreground">
            Select on Strategy. Max 4 types = RM4 per number.
          </p>
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
            {BET_TYPES.map(({ label, desc }) => (
              <div
                key={label}
                className="rounded-md border border-border/70 bg-muted/20 p-3"
              >
                <p className="text-xs uppercase tracking-wide text-muted-foreground">{label}</p>
                <p className="mt-1 text-xs text-muted-foreground">{desc}</p>
              </div>
            ))}
          </div>
        </CardContent>
      </Card>

      <Card className="border-border/70 bg-card shadow-sm">
        <CardHeader className="pb-3">
          <CardTitle className="text-lg">4D — full 4-digit match (per RM1)</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="overflow-x-auto">
            <table className="w-full min-w-[260px] border-collapse text-sm">
              <thead>
                <tr className="border-b border-border/50 text-left text-xs text-muted-foreground">
                  <th scope="col" className="py-2 pr-4 font-medium">Prize</th>
                  <th scope="col" className="py-2 px-4 text-right font-medium">Big</th>
                  <th scope="col" className="py-2 pl-4 text-right font-medium">Small</th>
                </tr>
              </thead>
              <tbody>
                {TABLE_4D.map((row) => (
                  <tr key={row.prize} className="border-b border-border/20 text-muted-foreground">
                    <td className="py-2 pr-4">{row.prize}</td>
                    <td className="py-2 px-4 text-right font-medium tabular-nums">RM {row.big}</td>
                    <td className="py-2 pl-4 text-right font-medium tabular-nums">RM {row.small}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </CardContent>
      </Card>

      <Card className="border-border/70 bg-card shadow-sm">
        <CardHeader className="pb-3">
          <CardTitle className="text-lg">3D — last 3 digits match (per RM1)</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="overflow-x-auto">
            <table className="w-full min-w-[260px] border-collapse text-sm">
              <thead>
                <tr className="border-b border-border/50 text-left text-xs text-muted-foreground">
                  <th scope="col" className="py-2 pr-4 font-medium">Prize</th>
                  <th scope="col" className="py-2 px-4 text-right font-medium">Big</th>
                  <th scope="col" className="py-2 pl-4 text-right font-medium">Small</th>
                </tr>
              </thead>
              <tbody>
                {TABLE_3D.map((row) => (
                  <tr key={row.prize} className="border-b border-border/20 text-muted-foreground">
                    <td className="py-2 pr-4">{row.prize}</td>
                    <td className="py-2 px-4 text-right font-medium tabular-nums">RM {row.big}</td>
                    <td className="py-2 pl-4 text-right font-medium tabular-nums">RM {row.small}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </CardContent>
      </Card>

      <Card className="border-border/70 bg-muted/20">
        <CardContent className="pt-4">
          <p className="text-sm text-muted-foreground">
            Aligned with Magnum, Sports Toto, Da Ma Cai. Confirm stakes at your outlet.
          </p>
          <ul className="mt-3 flex flex-wrap gap-x-4 gap-y-1 text-sm">
            {SOURCES.map(({ label, href }) => (
              <li key={href}>
                <a
                  href={href}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="inline-flex items-center gap-1 text-primary hover:underline"
                >
                  {label}
                  <ExternalLink className="size-3" />
                </a>
              </li>
            ))}
          </ul>
        </CardContent>
      </Card>

      <p>
        <Link to="/" search={linkSearch} className="text-sm font-medium text-primary hover:underline">
          ← Back to Strategy
        </Link>
      </p>
    </div>
  );
}
