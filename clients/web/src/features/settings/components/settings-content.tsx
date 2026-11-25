"use client";

import { useRouter } from "next/navigation";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { Activity, Brain, LogOut } from "lucide-react";
import { toast } from "sonner";

import { LegalDisclaimer } from "@/components/legal-disclaimer";
import { ThemeToggle } from "@/features/theme/theme-toggle";
import { ProfileForm } from "@/features/settings/components/profile-form";
import {
  Alert,
  AlertDescription,
  AlertTitle,
} from "@/components/ui/alert";
import { Button, buttonVariants } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { apiFetch } from "@/lib/api/client";
import { getBackendHealth } from "@/features/health/api";
import {
  currentUserQueryKey,
  useCurrentUser,
} from "@/features/auth/use-current-user";

export function SettingsContent() {
  const user = useCurrentUser();
  const router = useRouter();
  const queryClient = useQueryClient();
  const health = useQuery({
    queryKey: ["health", "backend"],
    queryFn: ({ signal }) => getBackendHealth(signal),
  });
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

  return (
    <div className="mx-auto w-full max-w-5xl px-5 py-10 sm:px-8 sm:py-12">
      <div className="mb-8">
        <p className="text-xs font-semibold uppercase tracking-[0.12em] text-primary">
          Account
        </p>
        <h1 className="mt-2 text-2xl font-semibold tracking-[-0.02em]">
          Settings
        </h1>
        <p className="mt-2 text-sm leading-6 text-muted-foreground">
          Profile, appearance, memory, and API health. Usage limits are
          enforced on the server; there is no usage read API.
        </p>
      </div>

      <div className="space-y-5">
        {user.error && !user.data ? (
          <Alert tone="error">
            <AlertTitle>Could not load your profile</AlertTitle>
            <AlertDescription className="flex flex-wrap items-center justify-between gap-3">
              Check your connection and try again.
              <Button
                type="button"
                variant="outline"
                size="sm"
                onClick={() => void user.refetch()}
              >
                Retry
              </Button>
            </AlertDescription>
          </Alert>
        ) : null}
        <Card>
          <CardHeader>
            <CardTitle>Appearance</CardTitle>
            <CardDescription>
              Light or dark. Stored only in this browser.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <ThemeToggle />
          </CardContent>
        </Card>

        <ProfileForm user={user.data} loading={user.isPending} />

        <Card>
          <CardHeader>
            <Brain className="mb-2 size-5 text-primary" aria-hidden="true" />
            <CardTitle>Memory</CardTitle>
            <CardDescription>
              Account-level memory consent and saved facts.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <Link href="/app/memory" className={buttonVariants({ variant: "outline" })}>
              Open memory
            </Link>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <Activity className="mb-2 size-5 text-primary" aria-hidden="true" />
            <CardTitle>Service</CardTitle>
            <CardDescription>
              Live status from GET /health. Remaining quota is not exposed by
              the API.
            </CardDescription>
          </CardHeader>
          <CardContent>
            {health.isPending ? (
              <Skeleton className="h-16 w-full" />
            ) : health.error ? (
              <Alert tone="error">
                <AlertTitle>Could not reach the API</AlertTitle>
                <AlertDescription className="flex flex-wrap items-center justify-between gap-3">
                  <Button
                    type="button"
                    variant="outline"
                    size="sm"
                    onClick={() => void health.refetch()}
                  >
                    Retry
                  </Button>
                </AlertDescription>
              </Alert>
            ) : (
              <dl className="space-y-3 text-sm">
                <div className="flex justify-between gap-4 border-b border-border pb-3">
                  <dt className="text-muted-foreground">Status</dt>
                  <dd className="font-medium">{health.data.status}</dd>
                </div>
                {health.data.service ? (
                  <div className="flex justify-between gap-4 border-b border-border pb-3">
                    <dt className="text-muted-foreground">Service</dt>
                    <dd className="font-medium">{health.data.service}</dd>
                  </div>
                ) : null}
                {health.data.version ? (
                  <div className="flex justify-between gap-4">
                    <dt className="text-muted-foreground">Version</dt>
                    <dd className="font-medium">{health.data.version}</dd>
                  </div>
                ) : null}
              </dl>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Session</CardTitle>
            <CardDescription>
              Sign out on this browser and remove the secure session cookies.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <Button
              type="button"
              variant="destructive"
              loading={logout.isPending}
              onClick={() => logout.mutate()}
            >
              <LogOut className="size-4" aria-hidden="true" />
              {logout.isPending ? "Logging out…" : "Log out"}
            </Button>
          </CardContent>
        </Card>
      </div>

      <LegalDisclaimer className="mt-8" />
    </div>
  );
}
