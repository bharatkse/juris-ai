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
        "inline-flex max-w-full items-center gap-1.5 rounded-full border px-3 py-1.5 font-sans text-xs text-citation-foreground outline-none transition-colors focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2",
        selected
          ? "border-primary bg-citation"
          : "border-primary/35 bg-citation/65 hover:border-primary",
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
