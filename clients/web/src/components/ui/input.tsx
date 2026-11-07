import * as React from "react";

import { cn } from "@/lib/utils";

export type InputProps = React.InputHTMLAttributes<HTMLInputElement>;

export const Input = React.forwardRef<HTMLInputElement, InputProps>(
  ({ className, type, ...props }, ref) => (
    <input
      ref={ref}
      type={type}
      className={cn(
        "flex h-10 w-full rounded-md border border-line-200 bg-paper px-3 py-2 text-sm text-ink-950 outline-none transition-colors placeholder:text-ink-400 hover:border-ink-400 focus-visible:border-gold-600 focus-visible:ring-2 focus-visible:ring-gold-600/20 disabled:cursor-not-allowed disabled:opacity-60 aria-[invalid=true]:border-danger-600 aria-[invalid=true]:ring-danger-600/15",
        className,
      )}
      {...props}
    />
  ),
);
Input.displayName = "Input";
