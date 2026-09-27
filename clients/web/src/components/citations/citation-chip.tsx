import { BookOpenText } from "lucide-react";

import { cn } from "@/lib/utils";

export function CitationChip({
  index,
  title,
  selected = false,
  onClick,
}: {
  index: number;
  title: string;
  selected?: boolean;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      aria-label={`Open citation ${index + 1}: ${title}`}
      aria-pressed={selected}
      className={cn(
        "inline-flex max-w-full items-center gap-1.5 rounded-full border px-3 py-1.5 font-sans text-xs text-ink-800 outline-none transition-colors focus-visible:ring-2 focus-visible:ring-gold-600 focus-visible:ring-offset-2",
        selected
          ? "border-gold-600 bg-gold-100"
          : "border-gold-600/35 bg-gold-100/65 hover:border-gold-600",
      )}
      onClick={onClick}
    >
      <BookOpenText className="size-3.5 shrink-0" aria-hidden="true" />
      <span className="truncate">
        [{index + 1}] {title}
      </span>
    </button>
  );
}
