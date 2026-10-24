# Design system

## Direction

The Flutter app uses a dark navy canvas with blue primary actions. The browser operations dashboard uses a warm off-white canvas, a white navigation rail, dark selected navigation and primary actions, white data panels, and restrained chartreuse highlights. Red remains reserved for critical status and destructive actions; green and amber indicate persisted operational states.

## Tokens

| Role | Value |
|---|---|
| Flutter canvas | `#0A101B` |
| Flutter main surface | `#111D2D` |
| Flutter raised surface | `#162438` |
| Web canvas | `#EFEDE7` |
| Web main surface | `#FFFFFF` |
| Web sidebar | `#FFFFFF` |
| Dashboard shell | `#E7E5E1` |
| Web border | `#E6E3DC` |
| Primary action | `#191A18` |
| Web highlight | `#F1EA55` |
| Success | `#23835F` |
| Warning | `#B7791F` |
| Critical | `#C83B45` |
| Web main text | `#191A18` |
| Web muted text | `#777870` |

The Flutter definitions are in `lib/presentation/design_system.dart`; browser tokens and responsive styles are in `web/admin/redesign.css`, layered over existing component rules in `web/admin/style.css`. The website-only operations overview has a compact KPI row, a backend-counted incident lifecycle with status drill-down, and three lower panels for priority incidents, persisted analysis/workload, and coordinator attention. Detailed reports use dependency-free SVG: a line chart for daily submissions and a keyboard-operable donut for incident categories, with text legends and drill-down to the incident filters.

## Hierarchy and spacing

Flutter uses Material 3 text styles with 4/8/12/16/20/24 dp spacing, 14 dp controls, 18 dp cards, and 48 dp primary buttons. The web console uses compact 8–10 px supporting text, 12–16 px panel radii, a 4-measure overview, and a seven-stage status pipeline. Status always includes text alongside color. Charts have text summaries, selectable legends or drill-down controls, and explicit empty states. The desktop shell targets the screenshot's 1200 × 900 composition and collapses to a responsive navigation menu and stacked panels on narrow website viewports; the native mobile UI is unchanged.

## Interaction

Use dark for primary actions, neutral outlined controls for secondary actions, chartreuse for selected emphasis, and semantic red for critical or destructive states. Keep focus rings visible on web. Loading and error states must not be represented as successful data. Onboarding transitions are restrained and do not autoplay.

## Known scope

These tokens are implemented, but a screenshot comparison at 1200 × 900, formal WCAG contrast audit, automated accessibility scan, TalkBack review, and browser keyboard walkthrough have not been run in this environment. The UI remains a development platform and has not received a production design validation.
