# Page Override — Home (`/`)

> Overrides `../MASTER.md` for this page. Master's colors, typography, spacing,
> and motion still apply; only the items below differ.

## Page Pattern — overrides Master

Master resolved **"Product Demo + Features"**, a SaaS landing pattern with a
product video and comparison table. This site is a résumé portfolio with no
product to demo, so that pattern does not apply.

Use **`portfolio-grid`** instead (`--domain landing`, verified match):

- **Section order:** Hero (name/role) → Projects → Experience → Skills → About → Contact
- **CTA placement:** Header (persistent) + hero + footer contact
- **Color strategy:** Neutral ground, let the work carry the page. Purple is an
  accent for eyebrow labels and links only — never a filled background behind
  body copy.

## Corrections applied to Master

- **Accent darkened** `#0891B2` → `#0E7490`. White on the original reached only
  3.7:1, below the 4.5:1 the checklist requires. `#0E7490` gives 5.4:1.
- **Easing is ease-out, not `back.out(1.4)`.** Master's own guidance says
  overshoot "reads as sloppy on informational UI" — a résumé is informational.
  Duration (450ms) and stagger (0.06s) follow Master's Standard tier.

## Verified

- Contrast: h1 14.9:1, body copy 5.3:1 — both modes
- Tap targets ≥ 44px at 375px; no horizontal overflow
- `prefers-reduced-motion` renders the final state immediately
- No-JS guard (`.js-reveal`) prevents a blank page when JS is unavailable
