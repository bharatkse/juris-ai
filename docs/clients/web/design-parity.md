# Design-parity review (claude.ai structure, Juris-AI brand)

| Screen | Deviation | Fix | Status |
|---|---|---|---|
| Sidebar | Settings, Memory, Theme lived in the rail | Work nav only; profile menu at bottom | Fixed |
| Sidebar sections | Recents only | Pinned → Projects → Recents; Documents + Plans as work links | Fixed |
| Conversation row | Archive icon only | `…` menu: pin, rename, delete, move to project | Fixed |
| Profile menu | `details/summary`, no keyboard trap | Popover, arrows, Esc, `aria-haspopup`, role gating | Fixed |
| Settings | Single scrolling page `/app/settings` | `/settings/*` two-column nav, `max-w-3xl` rows | Fixed |
| Settings on mobile | Same desktop cards | Top selector + content | Fixed |
| Memory | Flat card list | Master-detail + `/settings/memory/[id]` | Fixed |
| Projects | Missing | `/projects`, `/projects/[id]` | Fixed |
| Pinned | Missing | Sidebar section, reorder + keyboard Up/Down | Fixed |
| Search | Inline recents filter | ⌘K palette (chats, projects, actions) | Fixed |
| Shortcuts | Missing | `?` overlay | Fixed |
| Chat empty | Greeting already serif + starters | Unchanged (Juris-AI copy) | OK |
| Composer | `rounded-xl`, circular send | Unchanged | OK |
| Light theme | Pure white canvas | Tokens already `#FFFFFF` | OK |
| Toasts | top-right, surface token | Unchanged | OK |
| Share | No API | Hidden | OK |
| Documents / Plans | Hidden behind flags | Sidebar entries + honest empty/local UI | Fixed |
