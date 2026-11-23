# Web UI design system

Direction: **calm evidence workbench**. The UI is a neutral, high-contrast operations tool with one indigo accent. Colour is reserved for meaning: suspected versus confirmed, severity, and AI-generated content. It is modelled on real incident and ops tools (incident.io, Linear, Better Stack, Vercel Geist) rather than on concept shots.

## Tokens (`apps/web/src/app/globals.css`)

| Token | Value | Use |
|---|---|---|
| Surfaces | `zinc-50` page, `white` cards, `zinc-100/70` sidebar | Elevation comes from borders, not shadows |
| Accent | `indigo-600` (hover `700`) | Primary actions, focus rings, active nav |
| Success | emerald | Ready, CONFIRMED, REVIEWED, OK |
| Warning | amber | DRAFT, UNCONFIRMED, suspected, SEV3 |
| Danger | red | Failed, SEV1, safety warnings, destructive actions |
| Orange | orange | SEV2, high confidence |
| Info | sky | Queued, processing, investigating |
| AI | violet | `AI-generated` label only |
| Type | system sans stack; system mono for logs, commands and IDs | No web-font download |
| Radius | `rounded-control` 6px (inputs, buttons); `rounded-card` 10px (cards, dialogs) | |
| Spacing | Tailwind 4px scale; cards `p-4 sm:p-5`; page sections `space-y-6` | |
| Motion | 150ms colour transitions, spinner, skeleton pulse | Turned off under `prefers-reduced-motion` |
| Focus | 2px indigo `:focus-visible` outline on every control | |

## Components (`apps/web/src/components/ui.tsx`)

| Component | Purpose |
|---|---|
| `Button`, `btn(variant, size)` | Variants: primary, secondary, ghost, danger. `loading` shows a spinner and sets `aria-busy`. |
| `Field` | Label, hint and error, with `id` and `aria-describedby` wiring. |
| `input` | Shared class for inputs, selects and textareas. |
| `Card` | Optional title, description and actions header. `flush` removes padding for tables. |
| `PageHeader` | Title, one-line purpose, primary actions and breadcrumbs. |
| `Badge` | Picks its tone from the value (`SEV1`, `ready`, `UNCONFIRMED`…); includes a status dot. |
| `AiLabel` | Marks AI-generated content. |
| `Alert`, `ErrorBox` | Tones: info, warning, danger, success. Danger alerts use `role="alert"`. |
| `EmptyState` | Icon, title, explanation and optional action. |
| `StatCard` | KPI value with label and hint. |
| `Dialog` | Native `<dialog>`: focus trap, Escape and backdrop-click to close. Used for confirmations, previews and forms. |
| `Tabs` | WAI-ARIA tabs with arrow-key navigation. |
| `ToastProvider` / `useToast` | `aria-live` feedback after successful mutations. |
| `Skeleton`, `LoadingRows`, `Spinner` | Loading states. |
| `Icon` (`icons.tsx`) | Inline stroke icons, so there is no icon dependency. |

## Layout

- **App shell (`Nav.tsx`):** fixed 240px sidebar at `lg` and above. Below that, a sticky top bar with a drawer that closes on Escape, the backdrop or navigation. A skip link is included.
- **Tables:** become stacked card lists below `md`. Secondary columns hide below `xl`, and wide tables scroll inside their card.
- **Assistant:** the source excerpt sits in a sticky side panel at `lg` and above, and opens in a dialog on smaller screens.
- **Incident workspace:** Overview, Analysis and RCA tabs. The RCA review panel is sticky on desktop and lists every condition the confirm gate requires.
