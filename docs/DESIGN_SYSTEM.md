# Design system

## Direction

The Flutter app uses a dark navy canvas with blue primary actions. The browser operations dashboard uses a light canvas with a deep navy navigation rail, blue actions, and white data panels. Both preserve red for critical status and destructive actions, with green, amber, and blue for success, warning, and informational states.

## Tokens

| Role | Value |
|---|---|
| Flutter canvas | `#0A101B` |
| Flutter main surface | `#111D2D` |
| Flutter raised surface | `#162438` |
| Web canvas | `#F3F6FA` |
| Web main surface | `#FFFFFF` |
| Web sidebar | `#12243A` |
| Web border | `#E1E7EF` |
| Primary action | `#2878D0` |
| Success | `#23835F` |
| Warning | `#B7791F` |
| Critical | `#C83B45` |
| Web main text | `#17263B` |
| Web muted text | `#69788D` |

The Flutter definitions are in `lib/presentation/design_system.dart`; browser tokens (color, spacing, radii, chart palette, focus ring, and motion) and responsive styles are in `web/admin/redesign.css`, layered over existing component rules in `web/admin/style.css`. Both use platform system sans-serif fonts so the UI works offline and does not fetch a font at runtime. Dashboard visualizations are dependency-free SVG: a line chart for daily submissions and a keyboard-operable donut for incident categories, with text legends and drill-down to the incident filters.

## Hierarchy and spacing

Flutter uses Material 3 text styles with 4/8/12/16/20/24 dp spacing, 14 dp controls, 18 dp cards, and 48 dp primary buttons. The web console uses 12 px data-table text, 8 px control radii, 11–13 px panel radii, responsive content spacing, and a four-measure overview. Status always includes text alongside color. Charts have text summaries, selectable legends or drill-down controls, and explicit empty states.

## Interaction

Use blue for the main forward action, neutral outlined controls for secondary actions, and semantic red for critical or destructive states. Keep focus rings visible on web. Loading and error states must not be represented as successful data. Onboarding transitions are restrained and do not autoplay.

## Known scope

These tokens are implemented, but a formal WCAG contrast audit, automated accessibility scan, TalkBack review, and browser keyboard walkthrough have not been run in this environment. The UI remains a development platform and has not received a production design validation.
