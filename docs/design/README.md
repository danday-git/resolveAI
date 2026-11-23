# Web UI design system

Direction: **Console**, an app-screen theme from [Hallmark](https://github.com/nutlope/hallmark). Graphite surfaces, pale ink and hairline rules, with no shadows, gradients or blur. A switch in the sidebar and on the sign-in page changes to the light "paper" colourway of the same theme. It is built for long sessions on dense operational data. The stamp at the top of `apps/web/src/app/globals.css` records the theme, the navigation, the signature and everything the redesign dropped.

## What colour and type mean

| Signal | Meaning |
|---|---|
| Amber (`accent`) | A person: the primary action, the reviewer, the confirm step, focus rings |
| Cool blue (`cool`) | The instrument: AI-generated labels, suspected causes, ids, provider and model names, request ids |
| Green (`ok`) and red (`bad`) | Status only: ready, confirmed, failed, SEV1, safety warnings |
| Host Grotesk | Everything a person wrote or reads as prose |
| Atkinson Hyperlegible Mono (`.measured`) | Everything the system wrote: logs, commands, ids, timestamps, token counts, routes |

## Tokens (`apps/web/src/app/tokens.css`)

Tokens are a Tailwind v4 `@theme` block, so every one is also a utility (`bg-paper-2`, `text-muted`, `border-rule`, `rounded-card`). Pages use no default Tailwind palette colours.

| Token | Use |
|---|---|
| `paper`, `paper-2`, `paper-3` | Page, panel, and the well under inputs, logs and code |
| `ink`, `ink-2`, `muted` | Primary text, secondary text, labels and hints |
| `rule`, `rule-2`, `edge` | Hairline seams, stronger dividers, input borders |
| `accent`, `cool`, `ok`, `bad` (each with a `-soft` fill) | See the table above |
| `radius-card` 10px, `radius-pill` 6px, `radius-chip` 4px | Panels and dialogs, controls, badges |
| `--breakpoint-nav` 60rem | The `nav:` variant, where the sidebar gives way to a top bar with a menu |
| `--breakpoint-lg` 79rem | The `lg:` variant for two-column pages: Tailwind's 64rem plus the 15rem sidebar |

The light colourway overrides the colour tokens under `html[data-theme="paper"]` in the same file. `ThemeToggle` (`Nav.tsx`) sets that attribute and stores the choice in `localStorage`; an inline script in `layout.tsx` applies it before first paint. Components never branch on the theme.

Motion is limited to 120ms colour transitions, the spinner and the loading skeleton. All of it stops under `prefers-reduced-motion`.

## Components (`apps/web/src/components/ui.tsx`)

| Component | Purpose |
|---|---|
| `Button`, `btn(variant, size)` | Variants: primary (amber), secondary, ghost, danger. Controls are 32 or 36px high with a 44px hit area. `loading` shows a spinner and sets `aria-busy`. An action with a clear metaphor carries an icon before its label (`icon` prop, or `<Icon>` inside a `btn()` link); a control that moves you on (Next, Open the RCA, View all) puts a chevron after it. Cancel, Save and form submits stay text only. |
| `Field`, `input` | Label, hint and error with `id` and `aria-describedby` wiring; one shared class for inputs, selects and textareas. |
| `Card`, `Section` | A hairline panel with a header, and an unboxed titled section for tables. |
| `.panels` | A grid whose cells share hairline seams. Used for figures and side-by-side records instead of separate cards. |
| `PageHeader` | Title, one-line purpose, actions and breadcrumb. |
| `Badge` | Picks its tone from the value (`SEV1`, `ready`, `UNCONFIRMED`…). Tones: neutral, ok, bad, person, instrument. |
| `AiLabel` | Marks AI-generated content, in the instrument colour. |
| `Alert`, `ErrorBox` | Danger alerts use `role="alert"`. |
| `EmptyState`, `Empty` | Says what belongs here and what to do next. |
| `StatCard` | One figure with a label and a hint, placed inside `.panels`. |
| `Dialog` | Native `<dialog>`. Used only to confirm deleting a document. |
| `Tabs` | WAI-ARIA tabs with arrow-key navigation. |
| `Skeleton`, `LoadingRows`, `Spinner` | Loading states. |
| `th`, `td`, `link` | Shared classes for hairline tables and text links. |

There are no toasts. Every action changes something already visible on the page (a new row, a status badge, the "No unsaved changes." line), so that is the feedback.

## Layout

- **App shell (`Nav.tsx`):** a 240px sidebar with the wordmark, five links, the account and the theme switch. Below 60rem it becomes a top bar with a menu that traps focus and closes on Escape, on navigation and when the window widens. A skip link is included.
- **Evidence trail (signature):** the incident Analysis tab puts observations, knowledge base evidence, suspected causes with their read-only checks, and missing information on one spine. It ends in an amber "Reviewer decision" entry, the only step a person owns.
- **Inline instead of dialogs:** the new incident form, the document preview and the assistant's source excerpt on small screens all open in the page.
- **State in the URL:** search, filters, the open "New incident" form and the incident tab are mirrored into the query string (`lib/url.ts`), so a view survives reload and can be shared.
- **Tables:** real tables on desktop; the document list becomes labelled rows below `md`.
- **RCA:** the review panel is sticky on desktop and lists every condition the confirm gate requires.

## Checking a change

Hallmark's linter runs against the source and the rendered pages. See `skills/hallmark/SKILL.md` in the Hallmark repository for setup.

```bash
node <hallmark>/skills/hallmark/scripts/sloplint.mjs apps/web/src --genre modern-minimal --scope app
```
