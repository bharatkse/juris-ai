"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { ChevronDown, LogOut, Settings } from "lucide-react";
import { toast } from "sonner";

import { Skeleton } from "@/components/ui/skeleton";
import { apiFetch } from "@/lib/api/client";
import type { User } from "@/lib/api/types";
import { currentUserQueryKey } from "@/features/auth/use-current-user";
import { cn, getInitials } from "@/lib/utils";

export function AccountMenu({
  user,
  loading = false,
  inverse = false,
}: {
  user?: User;
  loading?: boolean;
  inverse?: boolean;
}) {
  const router = useRouter();
  const queryClient = useQueryClient();
  const logout = useMutation({
    mutationFn: () =>
      apiFetch<{ authenticated: boolean }>("/api/auth/logout", {
        method: "POST",
      }),
    onSuccess: () => {
      queryClient.removeQueries({ queryKey: currentUserQueryKey });
      router.replace("/login");
      router.refresh();
    },
    onError: () => toast.error("Could not log out. Please try again."),
  });

  if (loading) {
    return (
      <div className="flex items-center gap-3 px-2 py-1.5" aria-label="Loading account">
        <Skeleton className="size-9 shrink-0 rounded-full" />
        <div className="hidden flex-1 space-y-2 sm:block">
          <Skeleton className="h-3 w-24" />
          <Skeleton className="h-2.5 w-32" />
        </div>
      </div>
    );
  }

  const displayName =
    [user?.first_name, user?.last_name].filter(Boolean).join(" ") ||
    user?.email ||
    "Juris user";

  return (
    <details className="group relative">
      <summary
        className={cn(
          "flex cursor-pointer list-none items-center gap-3 rounded-md px-2 py-1.5 outline-none transition-colors focus-visible:ring-2 focus-visible:ring-gold-600 [&::-webkit-details-marker]:hidden",
          inverse
            ? "text-paper hover:bg-paper/10"
            : "text-ink-950 hover:bg-line-200/45",
        )}
      >
        <span
          className={cn(
            "grid size-9 shrink-0 place-items-center rounded-full border text-xs font-semibold",
            inverse
              ? "border-paper/20 bg-paper/10 text-paper"
              : "border-line-200 bg-paper text-ink-950",
          )}
        >
          {getInitials(user?.first_name, user?.last_name, user?.email)}
        </span>
        <span className="min-w-0 flex-1 text-left">
          <span className="block truncate text-sm font-medium">{displayName}</span>
          {user?.email && displayName !== user.email ? (
            <span
              className={cn(
                "block truncate text-xs",
                inverse ? "text-paper/55" : "text-ink-400",
              )}
            >
              {user.email}
            </span>
          ) : null}
        </span>
        <ChevronDown
          className="size-4 transition-transform group-open:rotate-180"
          aria-hidden="true"
        />
      </summary>

      <div
        className={cn(
          "absolute right-0 z-40 w-52 rounded-md border p-1.5",
          inverse
            ? "bottom-[calc(100%+8px)] border-paper/15 bg-ink-800 text-paper"
            : "top-[calc(100%+8px)] border-line-200 bg-paper text-ink-950",
        )}
      >
        <Link
          href="/app/settings"
          className={cn(
            "flex items-center gap-2 rounded-sm px-3 py-2 text-sm outline-none focus-visible:ring-2 focus-visible:ring-gold-600",
            inverse ? "hover:bg-paper/10" : "hover:bg-line-200/45",
          )}
        >
          <Settings className="size-4" aria-hidden="true" />
          Settings
        </Link>
        <button
          type="button"
          className={cn(
            "flex w-full items-center gap-2 rounded-sm px-3 py-2 text-left text-sm outline-none focus-visible:ring-2 focus-visible:ring-gold-600 disabled:opacity-60",
            inverse ? "hover:bg-paper/10" : "hover:bg-line-200/45",
          )}
          disabled={logout.isPending}
          onClick={() => logout.mutate()}
        >
          <LogOut className="size-4" aria-hidden="true" />
          {logout.isPending ? "Logging out…" : "Log out"}
        </button>
      </div>
    </details>
  );
}
