"use client";

import { useState, type ReactNode } from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { Toaster } from "sonner";

import { ThemeProvider } from "@/features/theme/provider";
import { ApiError } from "@/lib/api/errors";

export function Providers({ children }: { children: ReactNode }) {
  const [queryClient] = useState(
    () =>
      new QueryClient({
        defaultOptions: {
          queries: {
            staleTime: 30_000,
            refetchOnWindowFocus: false,
            retry: (failureCount, error) =>
              !(error instanceof ApiError && error.httpStatus < 500) &&
              failureCount < 2,
          },
          mutations: {
            retry: false,
          },
        },
      }),
  );

  return (
    <QueryClientProvider client={queryClient}>
      <ThemeProvider>
        {children}
        <Toaster
          closeButton
          position="top-right"
          toastOptions={{
            classNames: {
              toast:
                "!rounded-md !border-border !bg-surface !text-foreground !shadow-none",
              description: "!text-muted-foreground",
              actionButton: "!bg-foreground !text-background",
            },
          }}
        />
      </ThemeProvider>
    </QueryClientProvider>
  );
}
