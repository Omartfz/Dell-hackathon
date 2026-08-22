# Design system prompt (Aside v1.0)

Copy this file into another agent. Replicate this design system exactly. It is a light, editorial product UI nicknamed **Aside v1.0**. Ink-on-white, not purple, not dark, not cream-serif. Atmosphere comes from sky, blush, and glass — the chrome stays black, white, and one blue accent.

Do not invent a new look. Match these tokens, type, surfaces, and component recipes.

## Personality

- Quiet luxury / travel-desk: calm, precise, slightly magazine-like.
- Lots of white. Color is tinted, never saturated fills.
- Tight negative tracking on headlines. Tiny uppercase-feel **mono labels** for metadata.
- Pills everywhere (buttons, chips, status, sticky bars). Almost no sharp rectangles.
- Glass cards sit on a soft atmospheric wash, not a flat gray page.
- Motion is slow and small: sky drift, bubble fade-in, a live pulse, a 4-bar waveform. Honor `prefers-reduced-motion`.

## Fonts

Load Google fonts:

- **UI / headings / body:** [Instrument Sans](https://fonts.google.com/specimen/Instrument+Sans) — weights 400–600. Variable CSS name `--font-instrument-sans`.
- **Meta, IDs, step numbers, timers, speaker labels:** [JetBrains Mono](https://fonts.google.com/specimen/JetBrains+Mono) — 400 and 500. Variable `--font-jetbrains-mono`.

Fallbacks: `system-ui, sans-serif` and `monospace`.

Apply antialiasing on `html`/`body`. Body is Instrument Sans.

## Type scale

Use these exact sizes, not Tailwind’s defaults.

| Role | Size | Weight | Tracking | Line-height | Color |
|---|---|---|---|---|---|
| Hero H1 | 40px → 56px sm | 600 | -0.035em | 1.05 | ink |
| Page H1 | 34–44px | 600 | -0.03 to -0.035em | 1.05–1.15 | ink |
| Section title / card title | 15–17px | 600 | -0.01 to -0.02em | — | ink |
| Body | 15–17px | 400 | — | 1.55 | ink-2 or muted |
| Small body | 13–14px | 400 | — | 1.5–1.55 | muted / ink-2 |
| Label | 13px | 600 | — | — | ink-2 |
| Eyebrow / kicker | 13px | 600 | -0.01em | — | accent |
| Mono eyebrow (section headers) | 11px | 400 | 0.06em | — | faint · ALL CAPS or `01 · HOTEL` |
| Mono micro (speaker, timer, IDs) | 10.5–11px | 400 | 0.04em | — | faint |
| Logo wordmark | 17px | 600 | -0.02em | — | ink |
| Primary button | 15px | 600 | — | — | white on ink |
| Chip / pill | 11–13px | 600 | — | — | semantic |

Body copy max-width ~46–62ch. Headlines can be tighter (`18ch` on dashboard).

## Color tokens

Hex values — these override any shadcn neutrals.

```
ink:            #0a0a0a     /* primary text, primary buttons */
ink-2:          #3a3a3a     /* secondary body */
muted:          #6b6b6b     /* supporting copy */
faint:          #9a9a9a     /* mono labels, placeholders */
line:           #eaeaea     /* card/table borders */
line-2:         #f2f2f2     /* inner dividers */
surface:        #f7f7f8
surface-2:      #f7f9fb
accent:         #1b6ef3     /* links, focus, live dot, selected chips */
accent-dark:    #0f4fbf
accent-tint:    #eaf1fe
success:        #3f9a63
success-ink:    #3f7a56
success-tint:   #e4f3ea
warn:           #c98a2e
warn-tint:      #fbf1e2
danger:         #c6453d
danger-tint:    #fbe9e8
border-input:   #dcdcdc
white:          #ffffff
page:           #ffffff
disabled-bg:    #f0f0f0
disabled-text:  #b4b4b4
mono-quiet:     #b0b0b0     /* truncated IDs in cards */
```

**Do not use a dark theme.** Page background is always white.

Semantic chips:

- queued → `#f3f3f3` / muted
- in progress / selected / info → accent-tint / accent
- success / completed → success-tint / success-ink
- partial / scripted / warn → warn-tint / warn
- failed / declined / error → danger-tint / danger

## Radius

- Inputs: **10px**
- Cards / glass panels: **12–14px**
- Floating product stage: **18px**
- Buttons, chips, sticky action bar: **9999 (full pill)**
- Chat agent bubble: `18px 18px 6px 18px` (tail bottom-right)
- Chat other bubble: `18px 18px 18px 6px` (tail bottom-left)
- Quote block: left accent bar, right radius 8px

## Shadows

```
raised:   0 1px 2px rgba(16,24,40,0.06), 0 4px 12px rgba(16,24,40,0.06)
overlay:  0 8px 32px rgba(16,24,40,0.12), 0 2px 6px rgba(16,24,40,0.06)
bubble:   0 6px 18px rgba(16,24,40,0.07), inset 0 1px 0 rgba(255,255,255,0.65)
```

Cards pick up `overlay` on hover. No heavy drop shadows, no colored glows except a 3px accent focus ring.

## Layout

- App shell max-width **1240px**, horizontal padding 24px (48px on md+).
- Narrow forms **640px** centered.
- Product stage / hero content ~720–760px.
- Header: logo left, optional faint mono tagline (`13px`), ghost pill right.
- Logo mark: 22px circle, 2px ink border, short ink dash rotated -45°. Wordmark beside it.
- Live pages: main + 320px aside on large screens.

## Backgrounds

Three layers — use the right one per screen.

### 1. Default product pages (dashboard, forms)

Fixed full-viewport ambient wash behind content (`z-index: -10`, `pointer-events: none`):

- Page fill `#fff`
- Three huge blurred orbs (`filter: blur(90px)`, opacity 0.75, `border-radius: 9999px`):
  - **Sky** top-left (~42rem): `linear-gradient(180deg, #bfe0ff 0%, #e9f4ff 60%, #fff 100%)`
  - **Blush** mid-right (~38rem): `linear-gradient(135deg, #f7d9e6 0%, #f3e3d6 55%, #efe9f6 100%)`
  - **Mist** bottom-center (~40rem): `linear-gradient(135deg, #cfe7fa 0%, #e4f1fb 100%)`

### 2. Marketing / hero

Full-bleed bright cyan sky + soft white clouds (`background-size: cover; background-position: center top`). Slow 60s `ease-in-out alternate` drift of `background-position` from `center top` to `58% top`. Fade the bottom 24vh into `#fff` so the next section is clean white. UI on top stays ink-on-light (white/60 glass pills), not inverted.

### 3. Transcript / chat surface

`linear-gradient(165deg, #edf5ff 0%, #f7faff 40%, #fdf6fa 100%)`

Notes header: `linear-gradient(135deg, #e8f3ff 0%, #f4faff 100%)`

## Glass

```
.glass:
  background: rgba(255,255,255,0.66)
  border: 1px solid rgba(255,255,255,0.75)
  box-shadow: raised
  backdrop-filter: blur(18px)

.glass-bar:   /* sticky bottom bar, floating stage chrome */
  background: rgba(255,255,255,0.8)
  border: 1px solid rgba(255,255,255,0.8)
  box-shadow: overlay
  backdrop-filter: blur(22px)
```

## Component recipes

**Primary CTA** — pill, `bg #0a0a0a`, white 15px semibold, px-5/6 py-2.5/3. Hover `#262626`. Disabled `#f0f0f0` / `#b4b4b4`. Optional leading glyph (`↓`).

**Ghost / secondary** — pill, `border #dcdcdc` or `white/70`, `bg white/60`, 13–15px semibold. Hover `border-ink`.

**Selected chip** — pill, `border-accent bg-accent-tint text-accent`. Inactive: `border-border-input bg-white/60 text-muted`, hover `border-ink`. Tiny 6px status dot on language chips.

**Status pills** — `rounded-full px-[11px] py-[5px] text-xs font-semibold` + semantic tint pair above.

**Inputs** — `rounded-[10px] border #dcdcdc bg-white/70 px-3.5 py-2.5 text-[15px]`. Focus: `border-accent` + `box-shadow: 0 0 0 3px rgba(27,110,243,0.14)`. Dashed border + faint text when a field is “agent will find this”. Auto-filled fields flash accent border + 4px accent glow for 1.6s.

**Form sections** — `.glass`, `rounded-[14px] p-6`, gap 18px. First child is mono step: `01 · SECTION`.

**Cards (list)** — glass, `rounded-[12px] p-[18px]`, hover overlay shadow. Status row → title 15px semibold → 13px faint subtitle → mono 11px ID on a `line-2` hairline.

**Empty state** — glass, centered, py-20, 17px semibold title, muted 14px body, ghost CTA.

**Sticky action bar** — fixed bottom, inner `.glass-bar` as a **full pill**, max-width matching the form (640px), contents: mode toggle + truncated meta + primary CTA.

**Chat bubbles**

- Agent (right): `linear-gradient(135deg, rgba(160,201,255,0.62), rgba(198,214,255,0.55) 55%, rgba(226,206,244,0.5))`, text `#123361`, white/70 border.
- Other (left): `linear-gradient(135deg, rgba(255,255,255,0.85), rgba(248,250,255,0.7))`, text `#2a2a2a`, white/90 border.
- Both: 1px border, bubble shadow, `backdrop-filter: blur(14px)`, text 13–14px / 1.55.
- Speaker label above in mono 10.5px faint.
- Enter: `opacity 0 + translateY(8px)` → rest, 0.45s ease-out.

**Live indicators**

- 7px round dot: accent + 1.4s opacity pulse when live; success when done; warn when queued; danger when failed.
- Waveform: 2px-wide rounded bars, accent/70, height 4→11px, 0.9s, staggered delay ~0.1s.

**Quotes** — left 2px accent bar, `bg-surface`, `px-3.5 py-3`, ink-2, curly quotes.

**Error banner** — `rounded-[12px] border-danger/30 bg-danger-tint text-danger text-[13px]`.

**Tables / discrepancy grids** — `rounded-[10px] border-line`, header row `bg-surface-2` mono 11px faint, body 14px, claimed in danger, confirmed medium.

## Motion

- Sky drift 60s.
- Bubble in 0.45s.
- Live dot pulse 1.4s.
- Wave 0.9s.
- Just-filled 1.6s.
- Kill all of the above under `prefers-reduced-motion: reduce`.

## What this is not

- Not shadcn default gray app chrome (tokens exist underneath; **Aside tokens win**).
- Not dark mode.
- Not Inter / Geist / system UI as the face font.
- Not thick colored buttons, not 8px radius everywhere, not heavy cards on `#f5f5f5`.
- Not purple SaaS, not cream editorial serif, not neon glassmorphism.

## Implementation notes for the new app

1. Set CSS variables for every token above; map Tailwind colors to them (`ink`, `ink-2`, `muted`, `faint`, `accent`, tints, etc.).
2. Load Instrument Sans + JetBrains Mono the same way (Next: `next/font/google` with CSS variables).
3. Recreate `.ambient` + blobs, `.glass` / `.glass-bar`, transcript/bubble classes, and the keyframes.
4. Rebuild buttons, chips, inputs, cards, and chat using the recipes — don’t restyle ad hoc.
5. Keep copy tone dry and specific; UI labels are short; section headers are mono + tracked out.

Match it so a screenshot of the new app could sit next to this one and look like the same product family.
