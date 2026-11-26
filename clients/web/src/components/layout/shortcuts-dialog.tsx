"use client";

const SHORTCUTS = [
  { keys: "⌘ K", action: "Search chats and projects" },
  { keys: "?", action: "Keyboard shortcuts" },
  { keys: "Enter", action: "Send message" },
  { keys: "Shift + Enter", action: "New line in composer" },
  { keys: "Esc", action: "Close dialog or menu" },
] as const;

export function ShortcutsDialog({
  open,
  onClose,
}: {
  open: boolean;
  onClose: () => void;
}) {
  if (!open) return null;
  return (
    <div className="fixed inset-0 z-[60] flex items-center justify-center px-4">
      <button
        type="button"
        className="absolute inset-0 bg-foreground/40"
        aria-label="Close shortcuts"
        onClick={onClose}
      />
      <div
        role="dialog"
        aria-labelledby="shortcuts-title"
        className="relative z-10 w-full max-w-md rounded-xl border border-border bg-surface p-5"
      >
        <h2 id="shortcuts-title" className="text-lg font-semibold">
          Keyboard shortcuts
        </h2>
        <ul className="mt-4 space-y-2">
          {SHORTCUTS.map((item) => (
            <li
              key={item.keys}
              className="flex items-center justify-between gap-4 text-sm"
            >
              <span>{item.action}</span>
              <kbd className="rounded-md border border-border bg-hover px-2 py-0.5 text-xs">
                {item.keys}
              </kbd>
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
}
