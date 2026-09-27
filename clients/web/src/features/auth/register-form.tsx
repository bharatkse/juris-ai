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
import {
  registerSchema,
  type RegisterValues,
} from "@/features/auth/schemas";
import { apiFetch, jsonRequest } from "@/lib/api/client";
import { ApiError } from "@/lib/api/errors";
import type { AuthResult } from "@/lib/api/types";

const formFields = new Set<keyof RegisterValues>([
  "first_name",
  "last_name",
  "email",
  "password",
  "confirm_password",
]);

export function RegisterForm({ nextPath }: { nextPath: string }) {
  const router = useRouter();
  const [formError, setFormError] = useState<string | null>(null);
  const {
    register,
    handleSubmit,
    setError,
    formState: { errors, isSubmitting },
  } = useForm<RegisterValues>({
    resolver: zodResolver(registerSchema),
    defaultValues: {
      first_name: "",
      last_name: "",
      email: "",
      password: "",
      confirm_password: "",
    },
  });

  async function onSubmit(values: RegisterValues) {
    setFormError(null);

    try {
      const result = await apiFetch<AuthResult>(
        "/api/auth/register",
        jsonRequest(values, { method: "POST" }),
      );

      if (result.authenticated) {
        toast.success("Your workspace is ready.");
        router.replace(nextPath);
        router.refresh();
        return;
      }

      router.replace(
        `/login?registered=1&next=${encodeURIComponent(nextPath)}`,
      );
    } catch (error) {
      if (!(error instanceof ApiError)) {
        setFormError("Something went wrong. Please try again.");
        return;
      }

      for (const [field, messages] of Object.entries(error.fields ?? {})) {
        if (formFields.has(field as keyof RegisterValues)) {
          setError(field as keyof RegisterValues, { message: messages[0] });
        }
      }

      setFormError(
        error.httpStatus === 409
          ? "An account with this email already exists."
          : error.requestId
            ? `${error.message} Request ID ${error.requestId}.`
            : error.message,
      );
    }
  }

  return (
    <form className="space-y-5" onSubmit={handleSubmit(onSubmit)} noValidate>
      {formError ? (
        <Alert tone="error" className="flex gap-2.5">
          <CircleAlert className="mt-0.5 size-4 shrink-0" aria-hidden="true" />
          <AlertDescription>{formError}</AlertDescription>
        </Alert>
      ) : null}

      <div className="grid gap-4 sm:grid-cols-2">
        <div className="space-y-2">
          <Label htmlFor="first-name">First name</Label>
          <Input
            id="first-name"
            autoComplete="given-name"
            disabled={isSubmitting}
            aria-invalid={Boolean(errors.first_name)}
            {...register("first_name")}
          />
          {errors.first_name ? (
            <p className="text-xs text-danger-600">{errors.first_name.message}</p>
          ) : null}
        </div>
        <div className="space-y-2">
          <Label htmlFor="last-name">Last name</Label>
          <Input
            id="last-name"
            autoComplete="family-name"
            disabled={isSubmitting}
            aria-invalid={Boolean(errors.last_name)}
            {...register("last_name")}
          />
          {errors.last_name ? (
            <p className="text-xs text-danger-600">{errors.last_name.message}</p>
          ) : null}
        </div>
      </div>

      <div className="space-y-2">
        <Label htmlFor="email">Email</Label>
        <Input
          id="email"
          type="email"
          inputMode="email"
          autoComplete="email"
          disabled={isSubmitting}
          aria-invalid={Boolean(errors.email)}
          {...register("email")}
        />
        {errors.email ? (
          <p className="text-xs text-danger-600">{errors.email.message}</p>
        ) : null}
      </div>

      <div className="space-y-2">
        <Label htmlFor="new-password">Password</Label>
        <Input
          id="new-password"
          type="password"
          autoComplete="new-password"
          disabled={isSubmitting}
          aria-invalid={Boolean(errors.password)}
          aria-describedby="password-help"
          {...register("password")}
        />
        <p
          id="password-help"
          className={errors.password ? "text-xs text-danger-600" : "text-xs text-ink-400"}
        >
          {errors.password?.message ?? "At least 8 characters."}
        </p>
      </div>

      <div className="space-y-2">
        <Label htmlFor="confirm-password">Confirm password</Label>
        <Input
          id="confirm-password"
          type="password"
          autoComplete="new-password"
          disabled={isSubmitting}
          aria-invalid={Boolean(errors.confirm_password)}
          {...register("confirm_password")}
        />
        {errors.confirm_password ? (
          <p className="text-xs text-danger-600">
            {errors.confirm_password.message}
          </p>
        ) : null}
      </div>

      <Button type="submit" className="w-full" loading={isSubmitting}>
        {isSubmitting ? "Creating account…" : "Create account"}
      </Button>

      <p className="text-center text-sm text-ink-600">
        Already have an account?{" "}
        <Link
          href={`/login?next=${encodeURIComponent(nextPath)}`}
          className="font-semibold text-ink-950 underline decoration-gold-600 underline-offset-4"
        >
          Sign in
        </Link>
      </p>
    </form>
  );
}
