"use client";

import { useState, type ReactNode } from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { Toaster } from "sonner";

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
      {children}
      <Toaster
        closeButton
        position="top-right"
        toastOptions={{
          classNames: {
            toast:
              "!rounded-md !border-line-200 !bg-paper !text-ink-950 !shadow-none",
            description: "!text-ink-600",
            actionButton: "!bg-ink-950 !text-paper",
          },
        }}
      />
    </QueryClientProvider>
  );
}
