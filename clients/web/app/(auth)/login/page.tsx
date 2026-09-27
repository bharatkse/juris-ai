import type { Metadata } from "next";

import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { LoginForm } from "@/features/auth/login-form";
import { getSafeNextPath } from "@/lib/utils";

export const metadata: Metadata = {
  title: "Sign in",
};

export default async function LoginPage({
  searchParams,
}: {
  searchParams: Promise<{ next?: string; registered?: string }>;
}) {
  const params = await searchParams;
  const nextPath = getSafeNextPath(params.next);

  return (
    <Card className="animate-fade-in bg-paper">
      <CardHeader className="px-6 pb-3 pt-7 sm:px-8 sm:pt-8">
        <p className="text-xs font-semibold uppercase tracking-[0.12em] text-gold-600">
          Secure access
        </p>
        <h1 className="pt-2 text-2xl font-semibold tracking-[-0.02em]">
          Sign in
        </h1>
        <p className="text-sm leading-6 text-ink-600">
          Continue to your legal research workspace.
        </p>
      </CardHeader>
      <CardContent className="px-6 pb-7 pt-4 sm:px-8 sm:pb-8">
        <LoginForm
          nextPath={nextPath}
          registrationComplete={params.registered === "1"}
        />
      </CardContent>
    </Card>
  );
}
