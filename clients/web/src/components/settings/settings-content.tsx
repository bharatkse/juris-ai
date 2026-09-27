"use client";

import { useRouter } from "next/navigation";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { BookOpen, Gauge, LogOut } from "lucide-react";
import { toast } from "sonner";

import { LegalDisclaimer } from "@/components/legal-disclaimer";
import { ProfileForm } from "@/components/settings/profile-form";
import {
  Alert,
  AlertDescription,
  AlertTitle,
} from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { apiFetch } from "@/lib/api/client";
import {
  currentUserQueryKey,
  useCurrentUser,
} from "@/features/auth/use-current-user";

export function SettingsContent() {
  const user = useCurrentUser();
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

  return (
    <div className="mx-auto w-full max-w-4xl px-5 py-10 sm:px-8 sm:py-12">
      <div className="mb-8">
        <p className="text-xs font-semibold uppercase tracking-[0.12em] text-gold-600">
          Account
        </p>
        <h1 className="mt-2 text-2xl font-semibold tracking-[-0.02em]">
          Settings
        </h1>
        <p className="mt-2 text-sm leading-6 text-ink-600">
          Review your profile, service limits, and current session.
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
        <ProfileForm user={user.data} loading={user.isPending} />

        <div className="grid gap-5 md:grid-cols-2">
          <Card>
            <CardHeader>
              <Gauge className="mb-2 size-5 text-gold-600" aria-hidden="true" />
              <CardTitle>Usage</CardTitle>
              <CardDescription>
                Current service limits. Remaining usage is not yet API-backed.
              </CardDescription>
            </CardHeader>
            <CardContent>
              <dl className="space-y-3 text-sm">
                <div className="flex justify-between gap-4 border-b border-line-200 pb-3">
                  <dt className="text-ink-600">Requests</dt>
                  <dd className="font-medium">20 / minute</dd>
                </div>
                <div className="flex justify-between gap-4">
                  <dt className="text-ink-600">Tokens</dt>
                  <dd className="font-medium">200,000 / day</dd>
                </div>
              </dl>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <BookOpen className="mb-2 size-5 text-gold-600" aria-hidden="true" />
              <CardTitle>Document library</CardTitle>
              <CardDescription>
                The document library is not available in v1. Attach documents
                directly to a chat.
              </CardDescription>
            </CardHeader>
          </Card>
        </div>

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
