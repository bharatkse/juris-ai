"use client";

import { Button } from "@/components/ui/button";

export default function WorkspaceError({
  reset,
}: {
  error: Error;
  reset: () => void;
}) {
  return (
    <div className="flex min-h-full flex-col items-center justify-center px-6 py-16 text-center">
      <h1 className="text-xl font-semibold">Workspace failed to load</h1>
      <p className="mt-2 text-sm text-muted-foreground">
        Retry this view without leaving the app.
      </p>
      <Button type="button" className="mt-6" onClick={() => reset()}>
        Try again
      </Button>
    </div>
  );
}
