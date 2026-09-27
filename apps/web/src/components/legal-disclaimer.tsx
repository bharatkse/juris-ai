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
        inverse ? "text-paper/60" : "text-ink-600",
        className,
      )}
    >
      <ShieldCheck
        className="mt-0.5 size-3.5 shrink-0 text-gold-600"
        aria-hidden="true"
      />
      <span>{LEGAL_DISCLAIMER}</span>
    </p>
  );
}
