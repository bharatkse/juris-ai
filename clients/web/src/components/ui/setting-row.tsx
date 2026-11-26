import type { ReactNode } from "react";

import { cn } from "@/lib/utils";

export function SettingRow({
  label,
  description,
  children,
  htmlFor,
}: {
  label: string;
  description?: string;
  children: ReactNode;
  htmlFor?: string;
}) {
  return (
    <div className="flex flex-col gap-3 border-b border-border py-4 last:border-b-0 sm:flex-row sm:items-center sm:justify-between sm:gap-8">
      <div className="min-w-0 flex-1">
        {htmlFor ? (
          <label htmlFor={htmlFor} className="text-sm font-medium text-foreground">
            {label}
          </label>
        ) : (
          <p className="text-sm font-medium text-foreground">{label}</p>
        )}
        {description ? (
          <p className="mt-1 text-sm leading-6 text-muted-foreground">
            {description}
          </p>
        ) : null}
      </div>
      <div className="flex shrink-0 items-center justify-start sm:w-56 sm:justify-end">
        {children}
      </div>
    </div>
  );
}

export function SettingsSection({
  title,
  description,
  children,
  className,
}: {
  title: string;
  description?: string;
  children: ReactNode;
  className?: string;
}) {
  return (
    <section className={cn("space-y-1", className)}>
      <div className="mb-4">
        <h1 className="text-2xl font-semibold tracking-[-0.02em]">{title}</h1>
        {description ? (
          <p className="mt-2 text-sm leading-6 text-muted-foreground">
            {description}
          </p>
        ) : null}
      </div>
      <div className="rounded-lg border border-border bg-surface px-4">
        {children}
      </div>
    </section>
  );
}
