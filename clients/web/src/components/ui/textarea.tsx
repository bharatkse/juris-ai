import * as React from "react";

import { cn } from "@/lib/utils";

export type TextareaProps = React.TextareaHTMLAttributes<HTMLTextAreaElement>;

export const Textarea = React.forwardRef<HTMLTextAreaElement, TextareaProps>(
  ({ className, ...props }, ref) => (
    <textarea
      ref={ref}
      className={cn(
        "flex min-h-24 w-full resize-y rounded-md border border-border bg-surface px-3 py-3 text-sm leading-6 text-foreground outline-none transition-colors placeholder:text-muted-foreground hover:border-muted-foreground focus-visible:border-primary focus-visible:ring-2 focus-visible:ring-ring/20 disabled:cursor-not-allowed disabled:opacity-60 aria-[invalid=true]:border-danger",
        className,
      )}
      {...props}
    />
  ),
);
Textarea.displayName = "Textarea";
