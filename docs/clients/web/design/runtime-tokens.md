# Runtime color tokens (web)

Values are HSL channels (`H S% L%`) consumed as `hsl(var(--token) / <alpha>)`. Source of truth: `clients/web/src/config/theme.ts`.

| Token | Light | Dark | Usage |
|---|---|---|---|
| `--background` | 40 36% 95% | 215 28% 9% | App canvas |
| `--foreground` | 215 51% 12% | 40 36% 95% | Body text |
| `--surface` | 38 100% 98% | 215 26% 12% | Cards, inputs, toasts |
| `--surface-elevated` | 38 100% 98% | 215 24% 16% | Raised panels |
| `--border` | 39 27% 86% | 215 16% 24% | Dividers, outlines |
| `--muted` | 40 30% 92% | 215 20% 15% | Hover washes, chips |
| `--muted-foreground` | 214 25% 32% | 214 18% 72% | Secondary text |
| `--primary` | 43 82% 28% | 43 78% 56% | Gold accent, brand |
| `--primary-foreground` | 38 100% 98% | 215 51% 10% | Text on gold |
| `--accent` | 43 89% 38% | 43 78% 56% | Same as primary unless branded |
| `--ring` | 43 89% 38% | 43 78% 56% | Focus rings |
| `--success` | 152 45% 28% | 152 38% 58% | Success |
| `--danger` | 0 56% 39% | 0 58% 68% | Errors, destructive |
| `--info` | 216 49% 33% | 214 55% 72% | Links, info |
| `--chat-user` | 215 51% 12% | 215 24% 18% | User bubbles |
| `--chat-assistant` | 38 100% 98% | 215 24% 16% | Assistant bubbles |
| `--code` | 215 51% 12% | 215 32% 7% | Fenced code |
| `--citation` | 45 69% 86% | 43 40% 20% | Citation chips |
| `--sidebar` | 215 51% 12% | 215 32% 7% | Nav / auth aside |
| `--selection` | 45 69% 86% | 43 40% 24% | Text selection |
| `--skeleton` | 39 20% 88% | 215 16% 20% | Loading placeholders |
