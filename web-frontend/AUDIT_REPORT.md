# Frontend Audit Report — 4D Strategy Web App

**Date:** 2026-03-10  
**Scope:** `web-frontend/src` (React SPA: Strategy/Dashboard, Latest results, Prizing, Chart, Tools: Check Numbers, Gap Analysis, Optimizer)  
**Reference:** frontend-design skill (DO/DON'Ts, AI slop test), WCAG 2.1 AA, motion and color guidelines.

---

## Anti-Patterns Verdict

**Verdict: Partial pass — distinctive typography and clear data hierarchy; some template-like patterns and token gaps.**

**Specific tells (vs. frontend-design skill):**

- **Hero-style focal block:** The Decision summary uses one large profit number with supporting stats in an asymmetric layout. The skill says DON'T use "the hero metric layout template—big number, small label, supporting stats, gradient accent." This implementation avoids gradient accent and uses solid semantic colors (`.profit`/`.loss`), so it is a restrained hero moment rather than full template slop. **Low tell.**
- **Identical card grid:** Operator playbooks are a grid of same-sized cards (icon strip, title, stats, number chips). The skill warns against "same-sized cards with icon + heading + text, repeated endlessly." One card is visually featured (border/ring), but the structure is uniform. **Moderate tell.**
- **Hard-coded colors outside tokens:** `routes/results.tsx` uses hex values for operator themes (`#EAB308`, `#1E40AF`, `#B91C1C`, etc.) instead of design tokens. The skill says DON'T use "hard-coded colors" and DO use design tokens. **Clear tell.**
- **Rounded rectangles with shadow:** Cards use `rounded-xl` and `shadow-md`/`shadow-lg`. The skill: "rounded rectangles with generic drop shadows—safe, forgettable." Present but not excessive. **Mild tell.**
- **Good:** No gradient text on metrics or headings; no glassmorphism overload; no cyan/purple/neon AI palette; no bounce/elastic easing (cubic-bezier used); typography is distinctive (Bricolage Grotesque + Geist); OKLCH tokens in CSS; no nested cards; no modals; body uses tinted neutrals and subtle radial gradients.

**Conclusion:** The UI does not read as generic AI slop. It has a clear point of view (data-first, operator-colored results, bold type). The main gaps are operator theme hex in one file and the repetitive operator card layout; hero block is acceptable.

---

## Executive Summary

| Metric | Value |
|--------|--------|
| **Total issues** | 18 (0 Critical, 4 High, 8 Medium, 6 Low) |
| **Most critical** | Hard-coded operator hex (theming), inconsistent page titles (no-data/tools), small primary buttons (touch), nav link focus visibility |
| **Overall quality** | **B+** — Strong tokens and a11y base (skip link, labels, reduced motion); theming consistency and touch/focus need improvement |

**Recommended next steps:**

1. **High:** Replace operator hex in `results.tsx` with design tokens or theme variables; unify h1 styling (no-data and tools with main pages); ensure nav links and primary actions have visible focus and ≥44px touch targets where possible.
2. **Medium:** Add `scope="col"` to table headers; ensure Syncfusion chart has accessible name; optionally vary operator card layout or hierarchy.
3. **Low:** Consider preserving bet params on Prizing "Back to Strategy" link; document chart title for screen readers.

---

## Detailed Findings by Severity

### Critical Issues

*None.* No issues that block core functionality or constitute clear WCAG 2.1 Level A failures.

---

### High-Severity Issues

#### H1. Hard-coded hex colors for operator themes (results page)

- **Location:** `web-frontend/src/routes/results.tsx` (OPERATOR_THEMES, ~lines 12–26)
- **Severity:** High
- **Category:** Theming
- **Description:** Magnum, Da Ma Cai, and Sports Toto use literal hex values (`#EAB308`, `#1E40AF`, `#B91C1C`, etc.) for header, border, and label. Dark variants are also hex.
- **Impact:** Theme changes (e.g. primary hue, dark mode tweaks) do not affect operator cards; future design-token or contrast fixes require editing component code.
- **Recommendation:** Move operator accent colors into CSS variables (e.g. `--operator-magnum-header`, `--operator-damacai-header`) in `index.css` and reference them in Tailwind or inline styles. Or extend theme in Tailwind with named operator colors.
- **Suggested command:** `/normalize` (align with design system and tokens).

#### H2. Inconsistent heading hierarchy and styling (no-data and tools)

- **Location:** `Dashboard.tsx` (no-data state ~line 161); `NumberChecker.tsx` (~line 76); `Optimizer.tsx` (~line 48); `GapAnalysis.tsx` (~line 52)
- **Severity:** High
- **Category:** Accessibility / Theming
- **Description:** No-data state uses `<h1 className="text-2xl font-semibold ...">` without `font-display`. Tools pages use `<h1 className="text-2xl font-semibold ...">` while Strategy, Prizing, and Results use `font-display text-3xl ... lg:text-5xl`. CardTitle in no-data view is a `<div>`, not a heading.
- **Impact:** Inconsistent visual hierarchy and possibly confusing document outline; screen reader users get a single h1 then non-heading section titles.
- **WCAG/Standard:** WCAG 2.1 1.3.1 (Info and Relationships), 2.4.6 (Headings and Labels).
- **Recommendation:** Use the same h1 scale and `font-display` for all top-level page titles (including no-data). Optionally use a proper heading (e.g. h2) for CardTitle in no-data state, or keep div but ensure landmark/section structure is clear.
- **Suggested command:** `/normalize` (design system and typography consistency).

#### H3. Primary action buttons below 44px height

- **Location:** `Filters.tsx` (Apply button uses default Button); `NumberChecker.tsx`, `Optimizer.tsx`, `GapAnalysis.tsx` (Submit buttons); `web-frontend/src/components/ui/button.tsx` (default `h-8` = 32px)
- **Severity:** High
- **Category:** Responsive / Accessibility
- **Description:** Default button size is `h-8` (32px). Nav and chart filter toggles use `min-h-11` (44px). Primary form actions (Apply, Submit) do not.
- **Impact:** Touch targets for primary actions may be below the 44×44px recommendation (WCAG 2.5.5 Level AAA and common mobile guidelines), affecting touch and motor users.
- **WCAG/Standard:** WCAG 2.1 2.5.5 Target Size (AAA).
- **Recommendation:** Use a larger size for primary submit/apply buttons (e.g. `size="lg"` or custom `min-h-11`) so the tap area is at least 44px tall.
- **Suggested command:** `/normalize` or manual update to button usage and/or default size.

#### H4. Nav links lack explicit focus-visible ring

- **Location:** `web-frontend/src/routes/__root.tsx` (NavBar `Link` components, ~lines 20–28)
- **Severity:** High
- **Category:** Accessibility
- **Description:** Nav links use `transition-colors`, hover, and active styles but no `focus-visible:ring` or `focus-visible:outline`. Base layer applies `outline-ring/50` to `*`, which may be subtle or overridden.
- **Impact:** Keyboard users may not see a clear focus indicator on nav items, failing WCAG 2.4.7 (Focus Visible).
- **WCAG/Standard:** WCAG 2.1 2.4.7 Focus Visible (Level AA).
- **Recommendation:** Add `focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2` (or equivalent) to nav links so focus is clearly visible.
- **Suggested command:** `/harden` or manual a11y pass.

---

### Medium-Severity Issues

#### M1. Table headers without `scope`

- **Location:** `web-frontend/src/routes/prizing.tsx` (4D and 3D tables, ~lines 76–78, 105–107); `NumberChecker.tsx` (result tables)
- **Severity:** Medium
- **Category:** Accessibility
- **Description:** `<th>` elements do not have `scope="col"` (or `scope="row"` where appropriate).
- **Impact:** Screen readers may not associate headers with cells correctly in some modes.
- **WCAG/Standard:** WCAG 2.1 1.3.1 (Info and Relationships).
- **Recommendation:** Add `scope="col"` to column headers and `scope="row"` to row headers where applicable.
- **Suggested command:** Manual fix or `/harden`.

#### M2. Chart accessibility (title and data)

- **Location:** `WinsChartInner.tsx` (Syncfusion `ChartComponent` with `title` prop); chart used in `WinsChart.tsx` and `ChartFullscreen.tsx`
- **Severity:** Medium
- **Category:** Accessibility
- **Description:** Chart receives a `title` for visual display; it is unclear whether Syncfusion exposes this to assistive tech or provides an accessible name for the chart region/canvas.
- **Impact:** Screen reader users may not get a clear name or summary of the chart.
- **Recommendation:** Ensure the chart container or component has `aria-label` or `aria-labelledby` reflecting the chart title (e.g. "Top N numbers wins by month"). If Syncfusion supports it, set an accessible name on the chart root.
- **Suggested command:** Manual a11y fix or Syncfusion docs check.

#### M3. Placeholder text contrast

- **Location:** `NumberChecker.tsx` (textarea `placeholder="e.g. ..."`); `Filters.tsx` (Syncfusion placeholders); `GapAnalysis.tsx` (textarea placeholder)
- **Severity:** Medium
- **Category:** Accessibility / Theming
- **Description:** Placeholders use `placeholder:text-muted-foreground`. WCAG does not require 4.5:1 for placeholders, but low contrast can affect readability.
- **Impact:** Some users may have difficulty reading placeholder text.
- **Recommendation:** Ensure placeholder contrast is at least 3:1 against background, or document as an acceptable deviation. Prefer visible labels over reliance on placeholders.
- **Suggested command:** `/normalize` (tokens) or design review.

#### M4. Redundant or repeated intro copy

- **Location:** Several pages: e.g. Dashboard subtitle "Fast decision board for top-number strategy performance." under "4D Strategy"; Prizing intro; Results intro
- **Severity:** Medium
- **Category:** Anti-pattern (frontend-design)
- **Description:** The skill says DON'T "repeat the same information—redundant headers, intros that restate the heading." Some subtitles largely restate the h1.
- **Impact:** Minor; adds noise for screen reader users and can feel templated.
- **Recommendation:** Shorten or make subtitles additive (e.g. one line that adds context rather than restating the title).
- **Suggested command:** Copy edit; optional `/distill`.

#### M5. Global transition on all elements

- **Location:** `web-frontend/src/index.css` (~lines 182–186)
- **Severity:** Medium
- **Category:** Performance
- **Description:** `* { transition-duration: 180ms; transition-timing-function: cubic-bezier(...); }` is applied when `prefers-reduced-motion: no-preference`. Not all properties need transition.
- **Impact:** In theory can add cost if many elements change layout; in practice usually limited. No layout properties are animated (animations use transform/opacity).
- **Recommendation:** Consider scoping transitions to interactive elements or specific utility classes rather than `*`.
- **Suggested command:** `/optimize` or leave as-is if no perf issues observed.

#### M6. Operator cards uniform layout

- **Location:** `web-frontend/src/components/Dashboard.tsx` (operator playbooks grid, ~lines 296–371)
- **Severity:** Medium
- **Category:** Anti-pattern (frontend-design)
- **Description:** All operator cards share the same structure (top strip, title, strategy line, profit block, grid of draws/cost/winnings, number chips). One card is "featured" by border/ring only.
- **Impact:** Layout feels repetitive; skill warns against "identical card grids."
- **Recommendation:** Consider varying layout for the featured card (e.g. larger profit, different order) or adding a single hero operator block above the grid. Optional.
- **Suggested command:** Design iteration; optional `/bolder` or manual.

#### M7. Inline animation delays

- **Location:** `Dashboard.tsx`, `results.tsx` (e.g. `style={{ animationDelay: "0ms" }}`, `style={{ animationDelay: "200ms" }}`)
- **Severity:** Medium
- **Category:** Maintainability / Theming
- **Description:** Stagger delays are set via inline `style` rather than CSS custom properties or data attributes.
- **Impact:** Harder to tune globally; more inline style in JSX.
- **Recommendation:** Use a shared utility (e.g. `anim-delay-0`, `anim-delay-1`) or `--stagger-i` in CSS.
- **Suggested command:** `/normalize` (design system) or refactor.

#### M8. Prizing "Back to Strategy" drops bet params

- **Location:** `web-frontend/src/routes/prizing.tsx` (~lines 149–163)
- **Severity:** Medium
- **Category:** Interaction
- **Description:** The link to "/" passes `start_date`, `end_date`, `n`, `chart_operator`, etc. as `undefined` or empty, and does not pass `bet_4d_big`, `bet_4d_small`, `bet_3d_big`, `bet_3d_small`.
- **Impact:** Users who had bet types selected on Strategy will lose that selection when they go to Prizing and then "Back to Strategy."
- **Recommendation:** Either preserve current search params (including bet_*) when linking back, or accept intentional reset and document it.
- **Suggested command:** Manual fix (read search from router and pass through).

---

### Low-Severity Issues

#### L1. CardTitle is div, not heading

- **Location:** `web-frontend/src/components/ui/card.tsx` (CardTitle)
- **Severity:** Low
- **Category:** Accessibility
- **Description:** CardTitle renders as a `<div>`. When used for section titles (e.g. "Decision summary," "No historical data detected"), it is not in the heading tree.
- **Impact:** Outline/headings list in AT may not include these titles. Impact is low if there is only one h1 per page and sections are clear.
- **Recommendation:** For section-level titles, use an appropriate heading (e.g. `asChild` with h2) or ensure parent has `role="region"` and `aria-labelledby` pointing to the CardTitle id.
- **Suggested command:** Optional `/harden`.

#### L2. Syncfusion DatePicker/NumericTextBox id and label association

- **Location:** `web-frontend/src/components/Filters.tsx` (Label htmlFor="start_date", DatePickerComponent id="start_date", etc.)
- **Severity:** Low
- **Category:** Accessibility
- **Description:** Labels use `htmlFor` and Syncfusion components use matching `id`. If Syncfusion renders a wrapper and the focusable input has a different id, the association could break.
- **Impact:** Need to verify in DOM; if broken, screen readers might not announce the label.
- **Recommendation:** Inspect rendered DOM to confirm the focusable element has the same id or use `aria-label` on the control as fallback.
- **Suggested command:** Manual verification; fix if needed.

#### L3. No explicit `main` landmark on some early-return views

- **Location:** `Dashboard.tsx` error and no-data returns (wrappers are `<div className="mx-auto ...">`); `results.tsx` error state
- **Severity:** Low
- **Category:** Accessibility
- **Description:** Root has `<main id="main-content">` and the outlet renders inside it, so the main landmark is present. The early returns still render inside that main. No issue unless outlet structure changed.
- **Impact:** None if main wraps outlet.
- **Recommendation:** Confirm in DOM that all page content is inside `<main>`.
- **Suggested command:** Optional verification.

#### L4. Loading states not announced to screen readers

- **Location:** Dashboard loading skeleton; Results loading; Chart "Loading…"
- **Severity:** Low
- **Category:** Accessibility
- **Description:** Loading is visual only (skeleton, spinner, text). No `aria-live` or `aria-busy` on the loading regions.
- **Impact:** Screen reader users may not hear that content is loading.
- **Recommendation:** Add `aria-live="polite"` and `aria-busy="true"` on the loading container, and set `aria-busy="false"` when done. Optionally expose "Loading" text in a live region.
- **Suggested command:** `/harden`.

#### L5. Results page operator theme fallback

- **Location:** `web-frontend/src/routes/results.tsx` (getOperatorTheme fallback for unknown operator name)
- **Severity:** Low
- **Category:** Theming
- **Description:** Fallback uses `bg-muted`, `border-border/70`, `text-muted-foreground`. If CSV has a new operator name, it will look neutral. Fine for robustness.
- **Impact:** None for current data; future operators get neutral theme until added to OPERATOR_THEMES.
- **Recommendation:** Consider adding new operators to OPERATOR_THEMES when data source expands.
- **Suggested command:** None unless new operators appear.

#### L6. Multiple h1s only per route (not on same view)

- **Location:** App-wide
- **Severity:** Low
- **Category:** Accessibility
- **Description:** Each route has at most one h1. No duplicate h1 on a single view.
- **Impact:** None.
- **Recommendation:** Keep single h1 per route.
- **Suggested command:** None.

---

## Patterns & Systemic Issues

1. **Hard-coded colors:** Operator themes in `results.tsx` are the only significant use of hex outside tokens. Elsewhere, OKLCH and semantic tokens are used consistently.
2. **Touch targets:** Nav and chart toggles meet ~44px; primary form buttons (Apply, Submit) use default button height (32px). Inconsistent across primary actions.
3. **Focus visibility:** Buttons and Syncfusion inputs have focus styles; nav links rely on global outline. Explicit `focus-visible:ring` on nav would align with button treatment.
4. **Heading scale:** Two tiers—main app pages (Strategy, Prizing, Results) use large display font; no-data and tools use smaller, non–display font. Unify for consistency.
5. **Forms:** Labels are consistently associated via `htmlFor` and `id` in Filters, Optimizer, NumberChecker, GapAnalysis. Good pattern to keep.
6. **Motion:** Animations use transform/opacity; reduced motion respected. No layout thrashing from animations.

---

## Positive Findings

- **Skip link:** "Skip to main content" is present, focusable, and styled on focus (root).
- **Reduced motion:** `@media (prefers-reduced-motion: reduce)` disables custom animations and nav indicator transition (index.css).
- **Semantic tokens:** Core palette and dark mode use OKLCH and CSS variables; no pure #000/#fff in theme.
- **Error and alert roles:** Error cards use `role="alert"` (Optimizer, NumberChecker). Optimizer copy button has `aria-label` and `aria-live="polite"`.
- **Group and label:** Optimizer prize mode has `role="group"` and `aria-label="Prize mode"`; toggle has `aria-pressed`.
- **Responsive tables:** Prizing and NumberChecker tables use `overflow-x-auto` and `min-w-[260px]` to avoid horizontal layout break.
- **No gradient text or neon:** Metrics and headings use solid colors; hero profit uses `.profit`/`.loss` (semantic tokens).
- **Distinctive typography:** Bricolage Grotesque for headings and Geist for body; not generic system or overused web fonts.
- **Syncfusion focus:** Input focus ring aligned with design system (syncfusion-overrides.css).

---

## Recommendations by Priority

1. **Immediate (this sprint):**
   - Replace operator hex in `results.tsx` with design tokens or theme variables (H1).
   - Add visible focus style for nav links (H4).
   - Unify h1 styling for no-data and tools with main pages (H2).

2. **Short-term (next sprint):**
   - Increase primary action button size to ≥44px height where possible (H3).
   - Add `scope` to table headers in Prizing and NumberChecker (M1).
   - Ensure chart has an accessible name (M2).

3. **Medium-term (backlog):**
   - Tighten placeholder contrast or document (M3).
   - Shorten redundant intro copy (M4).
   - Optionally scope global transition (M5); add loading live regions (L4).

4. **Long-term (nice-to-have):**
   - Vary operator card layout for featured card (M6).
   - Move animation delays to utilities (M7).
   - Preserve bet params on Prizing back link (M8).

---

## Suggested Commands for Fixes

| Issue(s) | Command / Action |
|----------|-------------------|
| H1 (operator hex), H2 (heading consistency), H3 (button size), M3 (tokens), M7 (animation) | `/normalize` — align with design system and tokens |
| H4 (nav focus), M1 (table scope), M2 (chart a11y), L1 (CardTitle), L4 (loading) | `/harden` — resilience and a11y |
| M4 (redundant copy) | Copy edit or `/distill` |
| M5 (global transition) | `/optimize` (if perf is an issue) or leave as-is |
| M6 (operator cards) | Design pass or `/bolder` (optional) |
| M8 (Prizing back link) | Manual fix in prizing.tsx |

---

*Audit completed per audit skill. Fixes are not applied; use the suggested commands or manual changes to address findings.*
