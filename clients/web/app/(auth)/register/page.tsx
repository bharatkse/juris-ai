import type { Metadata } from "next";

import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { RegisterForm } from "@/features/auth/register-form";
import { getSafeNextPath } from "@/lib/utils";

export const metadata: Metadata = {
  title: "Create account",
};

export default async function RegisterPage({
  searchParams,
}: {
  searchParams: Promise<{ next?: string }>;
}) {
  const params = await searchParams;

  return (
    <Card className="animate-fade-in bg-paper">
      <CardHeader className="px-6 pb-3 pt-7 sm:px-8 sm:pt-8">
        <p className="text-xs font-semibold uppercase tracking-[0.12em] text-gold-600">
          Individual workspace
        </p>
        <h1 className="pt-2 text-2xl font-semibold tracking-[-0.02em]">
          Create an account
        </h1>
        <p className="text-sm leading-6 text-ink-600">
          Start a private workspace for research and document review.
        </p>
      </CardHeader>
      <CardContent className="px-6 pb-7 pt-4 sm:px-8 sm:pb-8">
        <RegisterForm nextPath={getSafeNextPath(params.next)} />
      </CardContent>
    </Card>
  );
}
