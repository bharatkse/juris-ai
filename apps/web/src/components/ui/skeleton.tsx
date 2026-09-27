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
        "animate-shimmer rounded-md bg-[linear-gradient(90deg,rgba(122,139,161,0.12)_25%,rgba(244,232,196,0.22)_50%,rgba(122,139,161,0.12)_75%)] bg-[length:200%_100%]",
        className,
      )}
      {...props}
    />
  );
}
