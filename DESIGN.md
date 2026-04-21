# Design System — Atlas

## Product Context
- **What this is:** Sovereign-finance intelligence platform for development finance institutions
- **Who it's for:** Sovereign finance analysts at institutions like OPEC Fund (Vienna), making investment decisions on African and MENA countries
- **Space/industry:** Institutional finance, sovereign risk analysis. Peers: Bloomberg Terminal, World Bank data tools, IMF dashboards, Moody's Analytics
- **Project type:** Professional analytics dashboard / data-heavy web app

## Aesthetic Direction
- **Direction:** Industrial/Utilitarian with Luxury undertones
- **Decoration level:** Minimal — typography and data do the talking
- **Mood:** Authoritative, data-dense, fast. Like a well-built cockpit: every element earns its place. Dark theme signals "professional tool" to analysts who live in terminals. Premium enough for institutional boardrooms, functional enough for daily analytical work.
- **Anti-patterns:** No gradients, no decorative blobs, no rounded-everything, no consumer-SaaS friendliness. This is a tool, not a toy.

## Typography
- **Display/Hero:** Geist Sans — sharp, geometric, modern. Designed for data products. Reads cleanly at all sizes on dark backgrounds.
- **Body:** Geist Sans — same family for consistency. Beautiful at 13-16px, excellent x-height for readability.
- **UI/Labels:** Geist Sans at 12-13px, medium weight for labels, regular for values
- **Data/Tables:** Geist Sans with `font-variant-numeric: tabular-nums` — numbers align in columns, critical for financial data
- **Code/Mono:** JetBrains Mono — ligatures, clear distinction between similar characters (0/O, 1/l/I)
- **Loading:** Google Fonts CDN (`family=Geist:wght@400;500;600;700`) or self-hosted for production
- **Scale:**
  - `text-xs`: 12px / 16px line-height (table cells, chips, timestamps)
  - `text-sm`: 14px / 20px (body text, form labels, sidebar nav)
  - `text-base`: 16px / 24px (primary content)
  - `text-lg`: 18px / 28px (section headers)
  - `text-xl`: 20px / 28px (page titles)
  - `text-2xl`: 24px / 32px (dashboard KPI values)
  - `text-3xl`: 30px / 36px (hero numbers, giant KPIs)

## Color

### Approach: Restrained on dark
Color is rare and meaningful. The dark background is the canvas. Data colors (risk heat, semantic states) are the only things that pop. Accent blue is used sparingly for interactive elements.

### Surfaces (dark to light, for layering depth)
```
--surface-950: #030712   /* deepest background, behind sidebar */
--surface-900: #0b1220   /* sidebar background */
--surface-800: #111827   /* main content area background */
--surface-700: #1f2937   /* cards, elevated surfaces, inputs */
--surface-600: #374151   /* borders, dividers, hover states */
```

### Text
```
--text-100: #f3f4f6   /* headings, primary content (not pure white, reduces eye strain) */
--text-200: #e5e7eb   /* emphasized body text */
--text-300: #d1d5db   /* standard body text */
--text-400: #9ca3af   /* muted text, secondary labels, timestamps */
--text-500: #6b7280   /* disabled text, placeholders */
```

### Accent
```
--accent-400: #60a5fa   /* hover state, links */
--accent-500: #3b82f6   /* primary interactive: buttons, active nav, focus rings */
--accent-600: #2563eb   /* pressed state */
--accent-700: #1d4ed8   /* dark accent for backgrounds */
```

### Semantic
```
--positive: #22c55e    /* good: upgrades, improvements, positive deltas */
--warning:  #f59e0b    /* caution: watch items, moderate risk */
--danger:   #ef4444    /* bad: downgrades, high risk, negative deltas, critical alerts */
--info:     #3b82f6    /* neutral information, same as accent */
```

### Risk Heat Scale (for scores, badges, table row tints)
```
Low risk (0-25):      #22c55e (positive green)
Moderate (25-45):     #84cc16 (lime, cautious optimism)
Elevated (45-60):     #f59e0b (warning amber)
High (60-75):         #f97316 (orange, serious concern)
Critical (75-100):    #ef4444 (danger red)
```

### Dark mode
This IS the dark mode. No light mode planned for prototype. If light mode is added later: invert surface scale, reduce semantic color saturation by 15-20%, swap text scale direction.

## Spacing
- **Base unit:** 4px
- **Density:** Compact-to-comfortable. Analysts want information density. Cards get `p-4`, not `p-8`. Table rows are tight. Whitespace is earned, not default.
- **Scale:**
  - `2xs`: 2px (inline spacing, tight gaps)
  - `xs`: 4px (icon-to-text, chip padding)
  - `sm`: 8px (between related items, card inner padding minimum)
  - `md`: 16px (card padding, section gaps)
  - `lg`: 24px (between sections)
  - `xl`: 32px (major section breaks)
  - `2xl`: 48px (page-level spacing, rarely used)

## Layout
- **Approach:** Grid-disciplined
- **Navigation:** Fixed left sidebar, `w-56` expanded / `w-14` collapsed. Dark (`surface-900`), always visible.
- **Content area:** Flexible, scrollable. No fixed max-width for data tables (they need room). Card grids use `max-w-7xl` for dashboard layouts.
- **Grid:** CSS Grid for dashboard layouts, flexbox for sidebar + content split
- **Border radius:** Tight and purposeful
  - `sm`: 4px (badges, chips, small elements)
  - `md`: 6px (cards, buttons, inputs)
  - `lg`: 8px (modals, popovers)
  - No `full` rounding except for avatar circles and status dots
- **Borders:** `1px solid surface-600`. Borders are structural, not decorative. Every border separates information zones.

## Motion
- **Approach:** Minimal-functional
- **Easing:** `ease-out` for enters, `ease-in` for exits
- **Duration:** 
  - Hover states: 150ms
  - Expand/collapse: 200ms
  - Page transitions: none (instant)
  - Toast notifications: 200ms enter, 150ms exit
- **Rules:** No entrance animations on page load. No scroll-driven effects. No loading spinners that spin for fun. Skeleton placeholders use subtle `animate-pulse` only.

## Component Patterns

### Cards (Glassmorphism)
```
background: rgba(255,255,255,0.03)
backdrop-filter: blur(12px)
border: 1px solid rgba(255,255,255,0.06)
border-radius: 10px
box-shadow: 0 4px 30px rgba(0,0,0,0.2), inset 0 1px 0 rgba(255,255,255,0.04)
```
Elevated cards use `glass-strong`: `rgba(255,255,255,0.05)` bg, `blur(16px)`, `rgba(255,255,255,0.08)` border.
No solid backgrounds. Frosted glass effect with subtle inner light edge. The page background has faint radial gradients (blue/indigo/cyan) that show through the glass.

### Tables
```
Header: bg-surface-700/50 text-text-400 text-xs font-medium uppercase tracking-wide
Rows: border-b border-surface-600 hover:bg-surface-700/30
Cells: px-3 py-2 text-sm text-text-300 font-mono (for numbers)
```
Tables are the primary data display. They should feel dense and scannable.

### Buttons
```
Primary:   bg-accent-500 hover:bg-accent-400 text-white rounded-md px-4 py-2 text-sm font-medium
Secondary: border border-surface-600 hover:border-surface-500 text-text-300 rounded-md px-4 py-2 text-sm
Danger:    bg-danger hover:bg-danger/90 text-white rounded-md px-4 py-2 text-sm font-medium
Ghost:     hover:bg-surface-700 text-text-400 rounded-md px-3 py-1.5 text-sm
```

### Badges / Chips
```
Risk badge:  px-2 py-0.5 rounded text-xs font-medium (background from risk heat scale at 15% opacity, text at full)
Status chip: px-2 py-0.5 rounded text-xs font-medium bg-surface-600 text-text-400
Active tag:  px-2 py-0.5 rounded text-xs font-medium bg-accent-500/15 text-accent-400
```

### Sidebar Navigation
```
Background: bg-surface-900
Item:       px-3 py-2 text-sm text-text-400 hover:bg-surface-800 hover:text-text-200 rounded-md
Active:     bg-surface-800 text-text-100 border-l-2 border-accent-500
Section:    text-xs font-medium uppercase tracking-wide text-text-500 px-3 py-2
```

### KPI Cards (Dashboard)
```
bg-surface-700 border border-surface-600 rounded-md p-4
Label: text-xs text-text-400 uppercase tracking-wide
Value: text-2xl font-semibold text-text-100 font-mono tabular-nums
Delta: text-sm font-mono (positive/danger color based on direction)
```

## Decisions Log
| Date | Decision | Rationale |
|------|----------|-----------|
| 2026-04-18 | Dark theme only, no light mode | Target users (sovereign analysts) work in dark-themed tools (Bloomberg, trading platforms). Reduces eye strain during extended analysis sessions. |
| 2026-04-18 | Geist Sans as sole typeface | Designed for data products, excellent tabular figures for financial data, clean at small sizes on dark backgrounds. Single family reduces visual noise. |
| 2026-04-18 | Compact spacing density | Analysts need information density. Every pixel of whitespace costs context. Tight tables, dense cards, minimal padding. |
| 2026-04-18 | Risk heat-mapped UI | Core differentiator. Every data point with a risk dimension gets color-coded. The UI should "breathe" risk information at a glance. |
| 2026-04-18 | Glassmorphism cards | Frosted glass with backdrop-blur, semi-transparent backgrounds, subtle inner light edge. Radial ambient gradients on page background bleed through glass. Gives futuristic depth without solid opaque blocks. |
| 2026-04-18 | Subtle KPI glow | KPI values get a faint downward text-shadow in their semantic color (0.15 opacity, 12px spread). Noticeable but not neon. |
| 2026-04-18 | Glowing alert dots | Critical/warning dots get box-shadow glow matching severity color. Draws the eye without being garish. |
| 2026-04-18 | Gradient risk bars | Portfolio ranking bars use color gradients (green→amber→red) rather than flat fills. Reinforces the heat-mapped UI principle. |
| 2026-04-18 | Summary card left border glow | Synopsis cards have a gradient left border with soft box-shadow glow matching severity. Subtle depth cue. |
| 2026-04-18 | Minimal motion | Analysts value speed over delight. No entrance animations, no scroll effects. Only functional state transitions. |
