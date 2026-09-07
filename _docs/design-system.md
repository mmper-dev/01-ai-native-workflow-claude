# Design system

Read this before touching the UI. Every value here is already decided — implement it, don't
re-decide it. Blocks the MVP does not build name the issue that does.

## The non-negotiable rules

1. Phone first, one column of cards. Desktop is the same column with more air.
2. One chore is one card. One primary action per card, a button on the right.
3. The card is the unit HTMX swaps. An action never navigates the whole page.
4. Near-neutral palette. Colour carries state and nothing else.
5. Estimated minutes and difficulty are plain text — never coloured, never badged.
6. Overdue is a red pill on a card that is still the assignee's. Never its own section.
7. A done card stays in place, greyed and struck through. An action never removes a card.
8. Sentence case, no emoji, buttons verb-first and one to three words.
9. No state is carried by colour alone. Every pill carries a word.
10. Plain CSS in `static/css/app.css`. No build step, no framework, no icon set, no web font.

## Layout

Used standing in a kitchen, one-handed, often with wet hands. That is the whole reason for
the large targets and the generous spacing; shrinking them is a regression.

- Narrowest viewport supported: **360 CSS px**. Nothing may scroll sideways there.
- One column at every width. There is **no second layout**: above `--layout-max-width` the
  column stops growing and the page gutter grows, and that is the only difference between
  phone and desktop.
- Content column: `width: 100%; max-width: var(--layout-max-width); margin-inline: auto;`
  with `padding-inline: var(--space-4)` up to 480px and `var(--space-6)` above it.
- `var(--space-4)` between cards, `var(--space-6)` between blocks.

## Colour rule

Colour means state: **red is overdue, green is done, accent is unclaimed.** Nothing else is
coloured; difficulty and estimated minutes are plain secondary text. A list where six things
are coloured stops answering the one question the screen exists for — what do I owe right
now. A number that is merely large is not a state.

## Tokens

Declared once, in a single `:root` block at the top of `static/css/app.css`. Names are roles,
not appearances (`--color-state-overdue-surface`, never `--red-100`), so #50 adds a second
block of values instead of rewriting rules.

```css
:root {
  /* surfaces and text; muted surface is the done card, border a decorative hairline,
     border-strong the field and quiet-button edges */
  --color-bg-page: #f4f4f5;   --color-surface-card: #ffffff; --color-surface-muted: #f4f4f5;
  --color-border: #d4d4d8;    --color-border-strong: #71717a;
  --color-text-primary: #18181b; --color-text-secondary: #52525b;
  --color-text-muted: #71717a;   --color-text-on-dark: #ffffff;
  /* state */
  --color-state-overdue-surface: #fee2e2;   --color-state-overdue-border: #dc2626;
  --color-state-overdue-text: #991b1b;
  --color-state-done-surface: #dcfce7;      --color-state-done-border: #15803d;
  --color-state-done-text: #166534;
  --color-state-unclaimed-surface: #dbeafe; --color-state-unclaimed-border: #2563eb;
  --color-state-unclaimed-text: #1e40af;
  /* actions */
  --color-action-primary: #1d4ed8;     --color-action-primary-hover: #1e3a8a;
  --color-action-danger: #b91c1c;      --color-action-danger-hover: #991b1b;
  --color-action-disabled-bg: #e4e4e7; --color-focus-ring: #1d4ed8;
  /* type */
  --font-sans: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto,
               "Helvetica Neue", Arial, "Noto Sans", sans-serif;
  --text-xs: 0.8125rem; --leading-xs: 1.4;    /* 13px pills, strip labels */
  --text-sm: 0.875rem;  --leading-sm: 1.45;   /* 14px meta, help, errors  */
  --text-base: 1rem;    --leading-base: 1.5;  /* 16px body and all inputs */
  --text-lg: 1.125rem;  --leading-lg: 1.35;   /* 18px chore name          */
  --text-xl: 1.5rem;    --leading-xl: 1.25;   /* 24px page header         */
  --weight-regular: 400; --weight-semibold: 600;
  /* space, radius, borders, layout */
  --space-1: 0.25rem; --space-2: 0.5rem; --space-3: 0.75rem; --space-4: 1rem;
  --space-5: 1.5rem;  --space-6: 2rem;   --space-7: 3rem;
  --radius-sm: 4px; --radius-md: 8px; --radius-pill: 999px;
  --border-width: 1px; --border-width-thick: 2px; --focus-ring-width: 3px;
  --touch-min: 2.75rem; /* 44px */     --layout-max-width: 34rem; /* 544px */
}
```

**No rule anywhere uses a spacing, size or radius from outside these scales.** If a layout
seems to need 18px, it needs 16px or 24px. Body text is **16px**, and so is every `input`,
`select` and `textarea` — below 16px mobile Safari zooms the page when a field takes focus and
does not zoom back. Two weights, 400 and 600. No web font: there is no build step and no
self-hosting story, so the system stack is the font.

## Page shell

**The global bar in `base.html`** carries the app name "Chores" on the left, linking to the
chore list, and account identity on the right: the signed-in account's email (or full name if
set) plus a **Log out** control, or a **Log in** link when anonymous. Nothing
household-specific belongs in it — no household name, no switcher (#43). Keeping household
logic out of the base template is #8's constraint and this document does not break it.

**The page header block is rendered by the screen, not the shell**: household name at
`--text-xl`/600, today's date under it at `--text-sm` secondary ("Sunday 7 September"), in the
household's timezone. Django messages render between the two — see Forms and messages.

## The owed summary

One line at `--text-base`, directly under the page header.

| Case | Text |
|---|---|
| Nothing owed | `You owe nothing right now.` |
| One thing | `You owe one chore, due {when}.` |
| Several | `You owe {n} chores. The next is due {when}.` |
| Anything overdue | `You owe {n} chores, and {m} are overdue.` |

The overdue line replaces the other two whenever `m >= 1`; singular form `You owe one chore,
and it's overdue.` `{when}` is `today at 6:00 pm`, `tomorrow at 9:00 am` or `on Fri 12 Sep at
9:00 am`. The overdue count is `--weight-semibold` — emphasis by weight, not colour.

## The seven-day strip

Seven cells, `display: flex; gap: var(--space-1)`, each `flex: 1 1 0; min-width: 0`. At 360px
that is 328px of content and 24px of gaps, 43px a cell: it fits with no wrap and no sideways
scroll. A cell holds the weekday abbreviation (`Mon`) at `--text-xs` secondary, the day number
at `--text-base`/600, and a **6px dot** in `--color-action-primary` when that day has at least
one chore. A day with no chores renders **an empty 6px slot** in place of the dot, so no cell
changes height. Today's cell has `background: var(--color-text-primary)`,
`--color-text-on-dark` text and `border-radius: var(--radius-md)`. The strip is **display only
in the MVP** — no cell is tappable, so the 44px rule does not apply; an issue that makes days
tappable must reach 44px tall first. Each cell carries an `aria-label` ("Friday 12 September,
3 chores" / "…, no chores"), because a dot is a shape, not a word.

## The card

The card **is** the list row — there is no separate row component, and the detail page uses
this same card. A text column on the left, exactly one primary action button on the right,
vertically centred. `background: var(--color-surface-card)`; `border: var(--border-width)
solid var(--color-border)`; `border-radius: var(--radius-md)`; `padding: var(--space-4)`;
`gap: var(--space-4)`.

| # | Field | Style |
|---|---|---|
| 1 | state pill, on its own line | see The state pill |
| 2 | chore name | `--text-lg`/600, primary text |
| 3 | due date and time | `--text-sm` secondary — `Due Fri 12 Sep at 9:00 am` |
| 4 | assignee, or the literal word `Unclaimed` | `--text-sm` secondary |
| 5 | assignment reason (#7) | `--text-sm` secondary, one line |
| 6 | effort | `--text-sm` secondary — `25 min · difficulty 3` |

Effort is read from the **occurrence's own** `estimated_minutes` and `difficulty`, never from
the definition (AGENTS.md) — editing a definition must not rewrite what a past card said.

**When a field is absent** — #6, #7, #10, #11, #41 and #42 are all open, so cards will be
rendered with holes:

- no assignee → line 4 reads `Unclaimed` and the unclaimed pill shows. Never blank.
- no assignment reason → line 5 is **omitted entirely**. No placeholder, no empty row.
- no pill → line 1 is omitted, the name is the first line. Space is not reserved.
- no action available → the button is **not rendered** and the text column takes the full
  width. Never a disabled placeholder button.

Cards are stacked, so a card with holes is simply shorter and nothing else moves. At 360px the
button keeps its natural width and the text column wraps beside it.

## The state pill

One component, three variants. Inline, first line of the card's text column, left aligned.
`--text-xs`/600, `padding: var(--space-1) var(--space-3)`, `border-radius:
var(--radius-pill)`, `border: var(--border-width) solid`. The word is the carrier, never the
colour, so the state survives a greyscale screenshot and a screen reader.

| Variant | Word | Surface / border / text tokens |
|---|---|---|
| overdue | `Overdue` | `--color-state-overdue-{surface,border,text}` |
| done | `Done` | `--color-state-done-{surface,border,text}` |
| unclaimed | `Unclaimed` | `--color-state-unclaimed-{surface,border,text}` |

**An overdue card is a normal card with a red pill.** It still shows its assignee, its due
date and its action button. No screen may collect overdue chores into their own section, their
own list or a different card — overdue is a flag, not a state (AGENTS.md), and the work is
still owed by the same person.

## The done card

`.card--done`: `background: var(--color-surface-muted)`, all text `--color-text-muted`, the
chore name `text-decoration: line-through`, a green `Done` pill, and a completion line
replacing the effort line — `Done by Alex on Fri 12 Sep at 7:14 pm`. **No action button.**

The rule this expresses: **an action taken on a card never removes that card.** Marking done
swaps the card into this form, in place, keeping its position; the feed is append-only and the
screen behaves the same way. #9's list is "what is still owed" and filters done occurrences
out of it; where a just-completed card then lives is a genuine conflict between the two and
**#51 settles it**. The shape is decided here either way.

## Buttons

Shared: `--text-base`/600, sentence case, `border-radius: var(--radius-md)`, `padding:
var(--space-3) var(--space-4)`, `min-height` and `min-width` of `var(--touch-min)`.

| Variant | Background | Text | Border | Hover background |
|---|---|---|---|---|
| primary | `--color-action-primary` | `--color-text-on-dark` | transparent | `--color-action-primary-hover` |
| quiet | `--color-surface-card` | `--color-text-primary` | 1px `--color-border-strong` | `--color-bg-page` |
| destructive | `--color-action-danger` | `--color-text-on-dark` | transparent | `--color-action-danger-hover` |

- **focus:** the shared focus ring below. Never removed, on any variant.
- **disabled:** `--color-action-disabled-bg`, `--color-text-muted`, `cursor: not-allowed`, no
  hover change. **In flight:** `hx-disabled-elt="this"` renders the button disabled for the
  duration and HTMX's `htmx-request` class adds `cursor: progress` — no spinner, no label
  change, there is no icon set.
- **labels:** verb-first, one to three words — `Mark done`, `Claim`, `Reassign`, `Log in`,
  `Sign up`, `Save chore`, `Log out`.
- **touch:** 44x44 CSS px minimum including padding, and at least `var(--space-2)` (8px)
  between two adjacent tappable things.

## Forms and messages

For #8's login, signup and logout pages, and every form after them.

- **Label above the field**, `--text-sm`/600, primary text, `margin-bottom: var(--space-1)`.
- **Field:** full width, `min-height: var(--touch-min)`, `padding: var(--space-3)`,
  `font-size: var(--text-base)` (16px, see Tokens), `border: var(--border-width) solid
  var(--color-border-strong)`, `border-radius: var(--radius-sm)`, `background:
  var(--color-surface-card)`; `var(--space-4)` between fields.
- **Help text:** under the field, `--text-sm`, `--color-text-secondary`.
- **Field error:** border becomes `var(--border-width-thick) solid
  var(--color-state-overdue-border)` and a message line sits under the field in `--text-sm`
  `--color-action-danger`. The field gets `aria-invalid="true"` and `aria-describedby`
  pointing at that line — the red border alone is not the carrier.
- **Form-level error block:** above the first field. Overdue surface, 1px overdue border,
  `--radius-md`, `padding: var(--space-3) var(--space-4)`, overdue text, opening line
  `Something needs fixing.` then the errors as a list.

**Django messages** render in `base.html`, in the content column, below the global bar and
above the page header — the first thing under the chrome, so they are seen. Same block shape
as the form-level error, one per message, starting with the word `Success`, `Error` or `Note`
in 600 so the level is never colour alone: success uses the done tokens with text `#14532d`,
error the overdue tokens, info the unclaimed tokens with text `#1e3a8a`.

## Empty states, the detail page, the scoreboard

**Empty states** are a single line of plain text on a normal card: `--text-base`, secondary,
centred. No illustration, no icon, no oversized heading. Exact wording — nothing due:
`Nothing is due right now.` Not in a household, for #8's landing page: `You're not in a
household yet. A household admin has to add you before you'll see any chores.`

**The detail page** is the same card, alone at the top of the content column, nothing
truncated. Below it a named region — `<section class="detail-actions" id="detail-actions">` —
where #10 (mark done), #11 (claim) and #41 (reassign) attach their controls, as a row of
buttons `var(--space-2)` apart, wrapping to a second row rather than shrinking below 44px.
**It renders nothing at all in the MVP** — no empty box, no border — so #9 leaves room
without designing them.

**The monthly scoreboard is not built in the MVP; #22 builds it.** No MVP task is blocked on
it — the look is decided here so it is not invented twice. A card at the foot of the page,
heading `This month` at `--text-lg`/600, then one row per member: name left, score right,
`--text-base` with the score in 600, sorted by score descending. Plain numbers, no bars, no
colour, no ranking ornament. Scores reset monthly (plan.md) and the heading says so.

## HTMX behaviour

HTMX is the whole of the interactivity. **Alpine is dropped** (AGENTS.md): a screen that
believes it needs browser-local state raises that rather than adding a library.

**The card is the swap unit.** An action replaces that card's own markup, the card keeps its
place in the list, and nothing navigates the whole page:

```html
<article class="card" id="occurrence-42" tabindex="-1">
  …
  <button class="btn btn--primary" id="action-occurrence-42"
          hx-post="{% url 'occurrence-done' occurrence.pk %}"
          hx-target="closest .card" hx-swap="outerHTML"
          hx-disabled-elt="this">Mark done</button>
</article>
```

`hx-target="closest .card"` with `hx-swap="outerHTML"` is the convention everywhere; the method
attribute is whichever of `hx-post` / `hx-delete` the action needs, and the response is the
re-rendered card and nothing else.

**In flight:** the disabled button plus `cursor: progress`, so the reader can see the tap
landed. **On failure:** a rejected action — not your chore, already done — returns **200 with
the same card re-rendered**, carrying a `--text-sm` `--color-action-danger` line inside it
saying why, so the swap always happens and a card cannot silently fail to change. HTMX does not
swap on a genuine 4xx or 5xx, so `base.html` listens for `htmx:responseError` and
`htmx:sendError` and renders an error message block reading `Error. That didn't save. Try
again.` That listener is the only script in the project besides HTMX itself.

**Focus after a swap:** every action button carries a stable id (`action-occurrence-42`), and
HTMX restores focus to the element with the same id after a swap, so a card that keeps its
button keeps focus for free. When the swap removes the button — marking done — the card root
takes focus instead: it carries `id="occurrence-42"` and `tabindex="-1"`, and the button asks
for it with `hx-on::after-request="document.getElementById('occurrence-42')?.focus()"`. Never
`autofocus`, and never scroll to the swapped card — the reader is already looking at it.

## Accessibility

Floors: **4.5:1** for body text, **3:1** for large text (18px/600 and up) and for meaningful
non-text — pill borders, focus rings, button and field edges. To check a pair, paste the two
hex values into the WebAIM contrast checker, or select the element in Chrome DevTools and read
the ratio in the Accessibility pane. For the colour-alone check: DevTools → Rendering → Emulate
vision deficiencies → Achromatopsia, then confirm every state still reads as a word.

Pairs measured against the tokens above:

| Pair | Ratio | Floor |
|---|---|---|
| primary / secondary / muted text on card surface | 17.7 / 7.7 / 4.8 | 4.5 |
| secondary text on page background | 7.0 | 4.5 |
| pill text on its own surface — overdue / done / unclaimed | 6.8 / 6.5 / 7.2 | 4.5 |
| pill border on card surface — overdue / done / unclaimed | 4.8 / 5.0 / 5.2 | 3 |
| button text on primary / destructive button | 6.7 / 6.5 | 4.5 |
| field and quiet-button edge on card surface | 4.8 | 3 |
| focus ring on card surface / page background | 6.7 / 6.1 | 3 |
| success / info message text on their surfaces | 8.3 / 8.5 | 4.5 |
| disabled button text on disabled background | 3.8 | exempt |

`--color-border` (#d4d4d8, 1.5:1 on card surface) is a decorative hairline carrying no meaning —
the card is also separated by its surface and its spacing. Anything identifying a control or a
state uses `--color-border-strong` or a state border, all of which clear 3:1.

**Focus ring**, on everything focusable, no exceptions. `outline: none` without a replacement of
at least equal visibility is not allowed anywhere in this project.

```css
:focus-visible {
  outline: var(--focus-ring-width) solid var(--color-focus-ring);
  outline-offset: 2px;
}
```

**Touch:** 44x44 CSS px minimum, `var(--space-2)` minimum between adjacent targets. **No state
anywhere is carried by colour alone:** overdue, done and unclaimed each carry a word, message
blocks carry a level word, field errors carry a message line. The check is the greyscale
screenshot — if it still reads, it passes.

## Words, mechanics and scope

Sentence case everywhere, including buttons and headings; no Title Case. No emoji, anywhere.
Contractions are fine: `You're not in a household yet` reads better than `You are not`. Buttons
are verb-first and one to three words. Domain vocabulary is used as-is, so class names,
templates and the backlog agree: a chore is a **chore**, a due instance is an **occurrence**, a
household is a **household**, a person in one is a **member**. Not "task", not "event", not
"user" in prose.

- **One stylesheet: `static/css/app.css`.** Templates carry no `style` attributes and no
  `<style>` blocks. A value needed in two places is a token.
- Everything here is hand-written CSS. No build step, no npm, no utility framework, no icon set,
  no web font. If something appears to need one, that is a dependency decision to raise first
  (AGENTS.md).
- **Dark mode is out of scope for the MVP.** Not "left open" — not being built now. #50 adds it
  as a second block of values under `@media (prefers-color-scheme: dark)`, which is why every
  token is named for its role.
- Specified here but not built by the MVP: the monthly scoreboard (#22), the public feed (#19),
  the needs-attention list (#29) and dark mode (#50) — all post-MVP. Nothing in this document
  requires an open issue to exist; the card spec says exactly what to render while #6, #7, #10,
  #11, #41 and #42 are still open.
- Not planned at all: a logo or brand treatment, illustrations, motion or transitions, a
  component library. The HTMX swap is instant and that is the whole story.
