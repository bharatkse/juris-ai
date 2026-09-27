"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { zodResolver } from "@hookform/resolvers/zod";
import { CircleAlert } from "lucide-react";
import { useForm } from "react-hook-form";
import { toast } from "sonner";

import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { apiFetch, jsonRequest } from "@/lib/api/client";
import { ApiError } from "@/lib/api/errors";
import type { AuthResult } from "@/lib/api/types";
import {
  loginSchema,
  type LoginValues,
} from "@/features/auth/schemas";

export function LoginForm({
  nextPath,
  registrationComplete = false,
}: {
  nextPath: string;
  registrationComplete?: boolean;
}) {
  const router = useRouter();
  const [formError, setFormError] = useState<string | null>(null);
  const {
    register,
    handleSubmit,
    setError,
    formState: { errors, isSubmitting },
  } = useForm<LoginValues>({
    resolver: zodResolver(loginSchema),
    defaultValues: { email: "", password: "" },
  });

  async function onSubmit(values: LoginValues) {
    setFormError(null);

    try {
      await apiFetch<AuthResult>(
        "/api/auth/login",
        jsonRequest(values, { method: "POST" }),
      );
      toast.success("Welcome back.");
      router.replace(nextPath);
      router.refresh();
    } catch (error) {
      if (!(error instanceof ApiError)) {
        setFormError("Something went wrong. Please try again.");
        return;
      }

      for (const [field, messages] of Object.entries(error.fields ?? {})) {
        if (field === "email" || field === "password") {
          setError(field, { message: messages[0] });
        }
      }

      if (error.httpStatus === 401) {
        setFormError("Invalid email or password.");
      } else if (error.httpStatus === 403) {
        setFormError("This account is inactive.");
      } else {
        setFormError(
          error.requestId
            ? `${error.message} Request ID ${error.requestId}.`
            : error.message,
        );
      }
    }
  }

  return (
    <form className="space-y-5" onSubmit={handleSubmit(onSubmit)} noValidate>
      {registrationComplete ? (
        <Alert tone="success">
          <AlertDescription>
            Account created. Sign in to continue.
          </AlertDescription>
        </Alert>
      ) : null}

      {formError ? (
        <Alert tone="error" className="flex gap-2.5">
          <CircleAlert className="mt-0.5 size-4 shrink-0" aria-hidden="true" />
          <AlertDescription>{formError}</AlertDescription>
        </Alert>
      ) : null}

      <div className="space-y-2">
        <Label htmlFor="email">Email</Label>
        <Input
          id="email"
          type="email"
          autoComplete="email"
          inputMode="email"
          disabled={isSubmitting}
          aria-invalid={Boolean(errors.email)}
          aria-describedby={errors.email ? "email-error" : undefined}
          {...register("email")}
        />
        {errors.email ? (
          <p id="email-error" className="text-xs text-danger-600">
            {errors.email.message}
          </p>
        ) : null}
      </div>

      <div className="space-y-2">
        <Label htmlFor="password">Password</Label>
        <Input
          id="password"
          type="password"
          autoComplete="current-password"
          disabled={isSubmitting}
          aria-invalid={Boolean(errors.password)}
          aria-describedby={errors.password ? "password-error" : undefined}
          {...register("password")}
        />
        {errors.password ? (
          <p id="password-error" className="text-xs text-danger-600">
            {errors.password.message}
          </p>
        ) : null}
      </div>

      <Button type="submit" className="w-full" loading={isSubmitting}>
        {isSubmitting ? "Signing in…" : "Sign in"}
      </Button>

      <p className="text-center text-sm text-ink-600">
        New here?{" "}
        <Link
          href={`/register?next=${encodeURIComponent(nextPath)}`}
          className="font-semibold text-ink-950 underline decoration-gold-600 underline-offset-4"
        >
          Create an account
        </Link>
      </p>
    </form>
  );
}
