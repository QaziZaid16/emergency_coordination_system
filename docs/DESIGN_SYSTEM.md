# Design system

## Direction

The product uses a dark navy operations canvas with blue primary actions. It keeps the interface calm and legible while preserving saturated red for critical incident status and destructive actions. Success, warning, and informational states use green, amber, and blue respectively. The Flutter app and browser dashboard share these semantic colors and the same overall contrast strategy.

## Tokens

| Role | Value |
|---|---|
| Canvas | `#0A101B` |
| Main surface | `#111D2D` |
| Raised surface | `#162438` |
| Sidebar | `#0E1725` (web navigation only) |
| Border | `#26384E` |
| Primary action | `#2583D2` |
| Accent / selected | `#6DB7FB` |
| Success | `#5DD2A9` |
| Warning | `#EFBA68` |
| Critical | `#F2777D` |
| Main text | `#E8EDF5` |
| Muted text | `#94A5BA` |

The Flutter definitions are in `lib/presentation/design_system.dart`; the web tokens are custom properties at the top of `web/admin/style.css`. Both use platform system sans-serif fonts so the UI works offline and does not fetch a font at runtime.

## Hierarchy and spacing

Flutter uses Material 3 text styles with 4/8/12/16/20/24 dp spacing, 14 dp controls, 18 dp cards, and 48 dp primary buttons. The web console uses a compact 12 px data-table baseline, 8 px control radii, and responsive content padding; operational labels and values take priority over decoration. Status always includes text alongside color.

## Interaction

Use blue for the main forward action, neutral outlined controls for secondary actions, and semantic red for critical or destructive states. Keep focus rings visible on web. Loading and error states must not be represented as successful data. Onboarding transitions are restrained and do not autoplay.

## Known scope

These tokens are implemented, but a formal WCAG contrast audit, automated accessibility scan, TalkBack review, and browser keyboard walkthrough have not been run in this environment. The UI remains a development platform and has not received a production design validation.
