import { Suspense } from "react";
import { createRootRoute, Link, Outlet, useRouterState } from "@tanstack/react-router";
import { BarChart3, CalendarDays, Info, Loader2, Zap } from "lucide-react";

const NAV_LINKS = [
  { to: "/", label: "Strategy", icon: BarChart3 },
  { to: "/results", label: "Latest results", icon: CalendarDays },
  { to: "/prizing", label: "Prizing", icon: Info },
  { to: "/tools", label: "Tools", icon: Zap },
] as const;

function NavBar() {
  const { location } = useRouterState();
  const pathname = location.pathname;
  const isToolsActive = pathname === "/tools" || pathname.startsWith("/tools/");

  return (
    <header className="sticky top-0 z-40 border-b-2 border-border/60 bg-background/95 backdrop-blur-md">
      <div className="mx-auto flex max-w-6xl flex-wrap items-center gap-2 px-4 py-3 md:flex-nowrap md:gap-3 md:px-6">
        <span className="mr-2 font-display text-xl font-extrabold tracking-tight text-foreground transition-colors hover:text-primary md:text-2xl">
          4D
        </span>
        {NAV_LINKS.map(({ to, label, icon: Icon }) => {
          const active = to === "/tools" ? isToolsActive : pathname === to;
          return (
            <Link
              key={to}
              to={to}
              preload={to === "/results" ? "intent" : undefined}
              aria-current={active ? "page" : undefined}
              className={`relative flex min-h-11 min-w-11 items-center justify-center gap-2 rounded-lg px-3 py-2 text-sm font-semibold text-muted-foreground transition-colors hover:bg-muted hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 sm:min-w-0 ${active ? "active bg-muted text-foreground" : ""}`}
            >
              <Icon className="size-3.5 shrink-0" />
              <span className="hidden sm:inline">{label}</span>
              <span className="nav-indicator" aria-hidden="true" />
            </Link>
          );
        })}
      </div>
    </header>
  );
}

function AnimatedOutlet() {
  const { location } = useRouterState();
  return (
    <div key={location.pathname} className="anim-page">
      <Outlet />
    </div>
  );
}

export const Route = createRootRoute({
  component: () => (
    <div className="min-h-screen bg-background text-foreground safe-area-x safe-area-b">
      <a
        href="#main-content"
        className="sr-only focus:not-sr-only focus:absolute focus:left-4 focus:top-4 focus:z-50 focus:rounded-md focus:bg-primary focus:px-3 focus:py-2 focus:text-sm focus:font-medium focus:text-primary-foreground focus:outline-none focus:ring-2 focus:ring-ring"
      >
        Skip to main content
      </a>
      <NavBar />
      <main id="main-content">
        <Suspense
          fallback={
            <div className="anim-loading flex min-h-[40vh] items-center justify-center text-muted-foreground">
              <Loader2 className="size-6 animate-spin" aria-hidden />
              <span className="sr-only">Loading…</span>
            </div>
          }
        >
          <AnimatedOutlet />
        </Suspense>
      </main>
    </div>
  ),
});
