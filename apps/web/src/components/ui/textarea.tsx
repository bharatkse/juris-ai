import * as React from "react";

import { cn } from "@/lib/utils";

export type TextareaProps = React.TextareaHTMLAttributes<HTMLTextAreaElement>;

export const Textarea = React.forwardRef<HTMLTextAreaElement, TextareaProps>(
  ({ className, ...props }, ref) => (
    <textarea
      ref={ref}
      className={cn(
        "flex min-h-24 w-full resize-y rounded-md border border-line-200 bg-paper px-3 py-3 text-sm leading-6 text-ink-950 outline-none transition-colors placeholder:text-ink-400 hover:border-ink-400 focus-visible:border-gold-600 focus-visible:ring-2 focus-visible:ring-gold-600/20 disabled:cursor-not-allowed disabled:opacity-60 aria-[invalid=true]:border-danger-600",
        className,
      )}
      {...props}
    />
  ),
);
Textarea.displayName = "Textarea";
