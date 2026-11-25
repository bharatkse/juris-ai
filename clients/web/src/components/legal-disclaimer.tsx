import { ShieldCheck } from "lucide-react";

import { cn, LEGAL_DISCLAIMER } from "@/lib/utils";

export function LegalDisclaimer({
  className,
  inverse = false,
}: {
  className?: string;
  inverse?: boolean;
}) {
  return (
    <p
      className={cn(
        "flex items-start gap-2 text-xs leading-5",
        inverse ? "text-sidebar-foreground/60" : "text-muted-foreground",
        className,
      )}
    >
      <ShieldCheck
        className="mt-0.5 size-3.5 shrink-0 text-primary"
        aria-hidden="true"
      />
      <span>{LEGAL_DISCLAIMER}</span>
    </p>
  );
}
