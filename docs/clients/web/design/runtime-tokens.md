# Runtime color tokens (web)

Values are HSL channels (`H S% L%`) consumed as `hsl(var(--token) / <alpha>)`.
Source of truth: `clients/web/src/config/theme.ts` (synced into `src/styles/theme.css`).

Themes: **light** and **dark** only. Light `--background` is pure white (`0 0% 100%` → `#FFFFFF`).

| Token | Light | Dark | Usage |
|---|---|---|---|
| `--background` | 0 0% 100% (`#FFFFFF`) | 220 16% 10% | Page, chat canvas, main content |
| `--foreground` | 222 47% 11% | 210 20% 96% | Body text (near-black, not `#000`) |
| `--surface` | 0 0% 100% | 220 14% 12% | Cards, inputs, composer |
| `--surface-elevated` | 0 0% 100% | 220 12% 15% | Raised panels |
| `--hover` | 210 20% 98% (`#F9FAFB`) | 220 12% 16% | Hover, user bubble, chips |
| `--border` | 220 13% 91% | 220 10% 22% | 1px separators |
| `--muted` | 210 20% 98% | 220 12% 16% | Washes |
| `--muted-foreground` | 220 9% 32% | 214 14% 72% | Secondary text |
| `--primary` | 43 82% 28% | 43 78% 56% | Brand gold |
| `--primary-foreground` | 0 0% 100% | 220 20% 8% | Text on gold |
| `--accent` | 43 82% 28% | 43 78% 56% | Accents |
| `--ring` | 43 82% 28% | 43 78% 56% | Focus rings |
| `--success` | 152 45% 28% | 152 38% 58% | Success |
| `--danger` | 0 56% 39% | 0 58% 68% | Errors |
| `--info` | 216 49% 33% | 214 55% 72% | Links |
| `--chat-user` | 210 20% 98% | 220 12% 16% | User message bubble |
| `--chat-assistant` | 0 0% 100% | 220 16% 10% | Assistant canvas (no bubble) |
| `--code` | 222 20% 14% | 220 18% 8% | Fenced code |
| `--citation` | 43 55% 92% | 43 30% 18% | Citation chips |
| `--sidebar` | 210 20% 98% | 220 16% 8% | Nav rail |
| `--sidebar-foreground` | 222 47% 11% | 210 20% 96% | Nav text |
| `--sidebar-muted` | 220 9% 32% | 214 12% 70% | Nav secondary |
| `--sidebar-border` | 220 13% 91% | 220 10% 18% | Nav edge |
| `--selection` | 43 55% 90% | 43 30% 22% | Text selection |
| `--skeleton` | 220 14% 94% | 220 10% 18% | Placeholders |

Radii: `--radius-sm` 6px, `--radius-md` 10px, `--radius-lg` 16px, `--radius-xl` 24px (composer). Chat column: `--chat-column` 48rem (`max-w-chat` / `max-w-3xl`).
