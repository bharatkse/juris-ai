import * as React from "react";

import { cn } from "@/lib/utils";

export function Skeleton({
  className,
  ...props
}: React.HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      aria-hidden="true"
      className={cn(
        "animate-shimmer rounded-md bg-[linear-gradient(90deg,hsl(var(--skeleton)/0.65)_25%,hsl(var(--primary)/0.18)_50%,hsl(var(--skeleton)/0.65)_75%)] bg-[length:200%_100%]",
        className,
      )}
      {...props}
    />
  );
}
