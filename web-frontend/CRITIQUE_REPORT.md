# Design Critique — 4D Strategy Web App

**Date:** 2026-03-10  
**Scope:** Frontend (Strategy/Dashboard, Latest results, Prizing, Chart, Tools).  
**Reference:** Frontend-design anti-patterns, WCAG 2.1 AA, design-director lens.

---

## Anti-Patterns Verdict

**Verdict: Does not read as generic AI slop.**

- **No gradient text** on metrics or headings; profit/loss use solid semantic colors (`.profit` / `.loss`).
- **No glassmorphism**, no cyan/purple/neon palette, no dark mode with glowing accents.
- **Distinct typography**: Bricolage Grotesque (display) + Geist (body); not system or generic web fonts.
- **Token-based theming**: OKLCH + CSS variables; operator accents on Results use design tokens (`--operator-*`).
- **Restrained hero**: Decision summary uses one large profit number and asymmetric layout but no gradient accent—reads as intentional focal point, not template.
- **Operator cards**: Uniform grid of three same-sized cards with one “featured” (border/ring); structure is consistent, not “endless identical cards” at scale.
- **Mild tells**: Rounded cards with shadow (`rounded-xl`, `shadow-md`) are common; not excessive. No nested cards or modals.

**Conclusion:** If you said “AI made this,” someone might believe it—but it doesn’t hit the usual AI slop checklist. It has a clear, data-first point of view and avoids the worst tropes.

---

## Overall Impression

**What works:** The app feels like a focused strategy tool. Typography and color support hierarchy; the main profit number and “Set date range and bet types, then Apply” make the primary task clear. Skip link, focus-visible on nav, loading/error handling, and token-based theming show care for accessibility and consistency.

**What doesn’t:** The Strategy page asks for a lot before showing value (dates, n, bet types, then Apply). First-time users may not know what “Apply” will do or how long it will take. The six nav items spread attention; tools (Check, Gap, Optimizer) could be grouped. Some states (e.g. unapplied) still carry `aria-busy="true"` by mistake.

**Biggest opportunity:** Make the primary path unmistakable (one clear “Run strategy” moment) and reduce perceived complexity before first result—e.g. stronger framing of “Apply” as “Run backtest” and a one-line expectation (“Results in a few seconds”).

---

## What’s Working

1. **Clear focal number**  
   The “Top N profit (all operators)” block uses a single large number, semantic color (profit/loss), and asymmetric layout. It reads as the answer to “how did this strategy do?” and supports quick scanning.

2. **Consistent, token-driven UI**  
   One display font, one body font, OKLCH tokens, and operator colors from CSS variables keep the UI coherent. Results page operator cards feel part of the same system, not a one-off theme.

3. **Accessible baseline**  
   Skip link, focus-visible on nav links, `aria-live`/`aria-busy` on loading, retry on errors, and reduced-motion handling show that accessibility and state are taken seriously.

---

## Priority Issues

### 1. Primary action is understated

- **What:** “Apply” is the main action on Strategy but lives in a dense filter block; it doesn’t visually dominate. Section title “Run backtest” helps but isn’t tied to the button.
- **Why it matters:** Users may not realize that clicking Apply is the critical step; the page can feel like a form without a clear “submit.”
- **Fix:** Make Apply the obvious CTA: e.g. same row as the button with “Run backtest” as label, or a larger/primary-style button with “Run backtest” as text. Consider a short line under the button: “Run backtest for your date range and bet types.”
- **Command:** Copy/layout tweak; optional `/distill` to simplify the block and emphasize one action.

### 2. No feedback on what “Apply” will do or how long it takes

- **What:** Before Apply, there’s no indication of cost (e.g. “~5–15 s”) or what will appear (summary, operator cards, chart). After Apply, loading says “Using your selected bet types” and “Crunching historical results...” which is good but only after the fact.
- **Why it matters:** Users may hesitate to click or think the app is broken during the first load.
- **Fix:** Near the Apply button or date range, add one line: e.g. “Backtest usually finishes in under 15 seconds.” On loading, keep current copy; optionally add a simple progress note (e.g. “Loading strategy…”).
- **Command:** Copy + optional small UX pass.

### 3. Six nav items dilute focus

- **What:** Nav has Strategy, Latest results, Prizing, Check Numbers, Gap Analysis, Optimizer. All same weight; no grouping.
- **Why it matters:** Strategy is the main use case; tools are secondary. Equal weight suggests equal importance and increases cognitive load.
- **Fix:** Group tools under one entry (e.g. “Tools” with dropdown or a tools index page) or visually secondary (e.g. smaller type, or “Strategy” slightly emphasized). Keep Prizing and Latest results as primary nav if they’re used often.
- **Command:** Information architecture; implement in `__root.tsx` (nav structure) and possibly one new route.

### 4. Unapplied state has wrong `aria-busy`

- **What:** When the user hasn’t applied yet, the Strategy container has `aria-busy="true"`. That’s incorrect—nothing is loading.
- **Why it matters:** Screen readers may announce that the region is busy and confuse users.
- **Fix:** Remove `aria-busy` from the unapplied-state container. Use `aria-busy` only when `isLoading` (or equivalent) is true.
- **Command:** Quick fix in `Dashboard.tsx` (remove from the `!applied` return).

### 5. Operator cards: “Best profit” vs “Top N individual” is easy to miss

- **What:** The only difference for the featured operator is border/ring and the label “Best profit” instead of “Top N individual.” In a quick scan, all three cards still look very similar.
- **Why it matters:** The “best performer” insight doesn’t stand out enough for users who want to pick one operator quickly.
- **Fix:** Keep same-size cards (per your preference) but strengthen the featured state: e.g. slightly stronger background (`bg-primary/5`), or a small “Best profit” badge with more contrast. Avoid making the card larger; keep hierarchy in color and label.
- **Command:** Small design tweak in `Dashboard.tsx` (featured card styles).

---

## Minor Observations

- **Filters section title:** “Run backtest” is good; consider moving it closer to the Apply button (e.g. above the button) so the action and label are visually tied.
- **Chart section:** “Wins by period” + “Click a bar to zoom” is clear; Fullscreen (new tab) is discoverable. No change needed unless you add more chart actions.
- **Prizing / Results:** Short intros and “Back to Strategy” with preserved params work well. No major issues.
- **Tools (Check, Gap, Optimizer):** Each has a clear purpose and one primary submit; consider consistent placement of the submit button (e.g. always at bottom of form) if you add more tools.
- **Empty / no data:** “No historical data detected” and “Ensure 4d_history.csv exists…” are clear and actionable for the intended (technical) audience.

---

## Questions to Consider

- **What if “Apply” were the only prominent button above the fold?** (e.g. dates + bet types + one big “Run backtest”)
- **Do we need all six items in the top nav?** What if “Tools” were one entry (with Check, Gap, Optimizer inside)?
- **Would a one-line “What you’ll see” (e.g. “Summary + operator comparison + chart”) before Apply set expectations better?**
- **For the featured operator card: is “Best profit” enough, or would a tiny icon/badge make it scan even faster without changing layout?**

---

## Fixes applied (post-critique)

1. **Primary action (Issue 1)** — Button label changed from "Apply" to "Run backtest". Expectation line added under the button: "Backtest usually finishes in under 15 seconds." Helper copy updated to "Choose dates and bet types, then Run backtest to load results."
2. **Feedback before Apply (Issue 2)** — Same expectation line addresses hesitation; loading copy unchanged.
3. **Nav grouping (Issue 3)** — Six nav items reduced to four: Strategy, Latest results, Prizing, **Tools**. New `/tools` index page lists Check Numbers, Gap Analysis, Optimizer as cards; Tools nav link is active when on `/tools` or any `/tools/*` route.
4. **aria-busy (Issue 4)** — Removed from unapplied-state container in `Dashboard.tsx`.
5. **Featured operator card (Issue 5)** — Featured card now uses `bg-primary/5`, and a pill badge "Best profit" (primary background, primary-foreground text) next to the operator name for quicker scanning.

---

*Critique completed per critique skill. Fixes applied as above.*
