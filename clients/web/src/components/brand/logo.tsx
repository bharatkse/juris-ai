import { Scale } from "lucide-react";

import { cn } from "@/lib/utils";

export function Logo({
  inverse = false,
  compact = false,
  className,
}: {
  inverse?: boolean;
  compact?: boolean;
  className?: string;
}) {
  return (
    <span
      aria-label="Juris AI"
      className={cn(
        "inline-flex items-center gap-2.5 font-semibold",
        inverse ? "text-sidebar-foreground" : "text-foreground",
        className,
      )}
    >
      <span
        className={cn(
          "grid size-8 place-items-center rounded-md border",
          inverse
            ? "border-sidebar-foreground/20 bg-sidebar-foreground/10"
            : "border-border bg-surface",
        )}
        aria-hidden="true"
      >
        <Scale className="size-[18px]" strokeWidth={1.8} />
      </span>
      {!compact ? (
        <span aria-hidden="true" className="tracking-[0.12em]">
          JURIS <span className="text-primary">AI</span>
        </span>
      ) : null}
    </span>
  );
}
