import { createFileRoute, Link } from "@tanstack/react-router";
import { Search, TrendingUp, Zap } from "lucide-react";

export const Route = createFileRoute("/tools/")({
  component: ToolsIndexPage,
});

const TOOLS = [
  { to: "/tools/check", label: "Check Numbers", icon: Search, desc: "Check if your 4D numbers have won since a given date." },
  { to: "/tools/gap", label: "Gap Analysis", icon: TrendingUp, desc: "Days between wins and dry-spell patterns for your numbers." },
  { to: "/tools/optimize", label: "Optimizer", icon: Zap, desc: "Best N numbers for profit and fewer dry spells." },
] as const;

function ToolsIndexPage() {
  return (
    <div className="mx-auto w-full max-w-4xl space-y-5 px-4 py-6 md:px-6 md:py-8">
      <header className="space-y-2">
        <h1 className="font-display text-2xl font-semibold tracking-tight text-foreground md:text-3xl">Tools</h1>
        <p className="max-w-2xl text-sm leading-relaxed text-muted-foreground md:text-base">
          Number checker, gap analysis, and optimizer. Pick one to run.
        </p>
      </header>
      <div className="grid gap-4 sm:grid-cols-2 md:grid-cols-3">
        {TOOLS.map(({ to, label, icon: Icon, desc }) => (
          <Link
            key={to}
            to={to}
            className="group flex flex-col rounded-xl border-2 border-border/80 bg-card p-5 shadow-sm transition-all duration-200 hover:border-primary/50 hover:shadow-md focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
          >
            <Icon className="size-8 text-primary" aria-hidden />
            <h2 className="mt-3 font-display text-lg font-bold tracking-tight text-foreground group-hover:text-primary">
              {label}
            </h2>
            <p className="mt-1 text-sm text-muted-foreground">{desc}</p>
          </Link>
        ))}
      </div>
    </div>
  );
}
