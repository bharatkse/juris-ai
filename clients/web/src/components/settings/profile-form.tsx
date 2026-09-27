"use client";

import { useEffect, useState } from "react";
import { zodResolver } from "@hookform/resolvers/zod";
import { Save, UserRound } from "lucide-react";
import { useForm } from "react-hook-form";
import { toast } from "sonner";

import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  profileFormValues,
  profileSchema,
  profileUpdatePayload,
  type ProfileValues,
} from "@/features/auth/profile";
import { useUpdateCurrentUser } from "@/features/auth/use-current-user";
import { ApiError } from "@/lib/api/errors";
import type { User } from "@/lib/api/types";

const profileFields = new Set<keyof ProfileValues>([
  "first_name",
  "last_name",
  "phone_number",
  "date_of_birth",
  "gender",
]);

function FieldError({ message }: { message?: string }) {
  return message ? <p className="text-xs text-danger-600">{message}</p> : null;
}

export function ProfileForm({
  user,
  loading = false,
}: {
  user?: User;
  loading?: boolean;
}) {
  const update = useUpdateCurrentUser(user?.id);
  const [formError, setFormError] = useState<string | null>(null);
  const {
    register,
    handleSubmit,
    reset,
    setError,
    formState: { errors, isDirty },
  } = useForm<ProfileValues>({
    resolver: zodResolver(profileSchema),
    defaultValues: profileFormValues(user),
  });

  useEffect(() => {
    reset(profileFormValues(user));
  }, [reset, user]);

  async function submit(values: ProfileValues) {
    setFormError(null);
    try {
      await update.mutateAsync(profileUpdatePayload(values));
      toast.success("Profile updated.");
    } catch (error) {
      if (error instanceof ApiError) {
        for (const [field, messages] of Object.entries(error.fields ?? {})) {
          if (profileFields.has(field as keyof ProfileValues)) {
            setError(field as keyof ProfileValues, { message: messages[0] });
          }
        }
        setFormError(
          error.requestId
            ? `${error.message} Request ID ${error.requestId}.`
            : error.message,
        );
      } else {
        setFormError("Could not update your profile. Please try again.");
      }
    }
  }

  const disabled = loading || update.isPending || !user;

  return (
    <Card>
      <CardHeader>
        <div className="mb-3 flex items-center gap-2 text-gold-600">
          <UserRound className="size-4" aria-hidden="true" />
          <span className="text-xs font-semibold uppercase tracking-[0.08em]">
            Profile
          </span>
        </div>
        <CardTitle>Personal details</CardTitle>
        <CardDescription>
          Optional fields can be cleared by saving them blank.
        </CardDescription>
      </CardHeader>
      <CardContent>
        <form className="space-y-5" onSubmit={handleSubmit(submit)} noValidate>
          {formError ? (
            <Alert tone="error">
              <AlertDescription>{formError}</AlertDescription>
            </Alert>
          ) : null}

          <div className="grid gap-5 sm:grid-cols-2">
            <div className="space-y-2">
              <Label htmlFor="settings-first-name">First name</Label>
              <Input
                id="settings-first-name"
                autoComplete="given-name"
                disabled={disabled}
                aria-invalid={Boolean(errors.first_name)}
                {...register("first_name")}
              />
              <FieldError message={errors.first_name?.message} />
            </div>
            <div className="space-y-2">
              <Label htmlFor="settings-last-name">Last name</Label>
              <Input
                id="settings-last-name"
                autoComplete="family-name"
                disabled={disabled}
                aria-invalid={Boolean(errors.last_name)}
                {...register("last_name")}
              />
              <FieldError message={errors.last_name?.message} />
            </div>
            <div className="space-y-2 sm:col-span-2">
              <Label htmlFor="settings-email">Email</Label>
              <Input
                id="settings-email"
                type="email"
                value={user?.email ?? ""}
                placeholder={loading ? "Loading…" : "Not available"}
                disabled
                readOnly
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="settings-phone">Phone</Label>
              <Input
                id="settings-phone"
                type="tel"
                autoComplete="tel"
                disabled={disabled}
                aria-invalid={Boolean(errors.phone_number)}
                {...register("phone_number")}
              />
              <FieldError message={errors.phone_number?.message} />
            </div>
            <div className="space-y-2">
              <Label htmlFor="settings-date-of-birth">Date of birth</Label>
              <Input
                id="settings-date-of-birth"
                type="date"
                autoComplete="bday"
                disabled={disabled}
                aria-invalid={Boolean(errors.date_of_birth)}
                {...register("date_of_birth")}
              />
              <FieldError message={errors.date_of_birth?.message} />
            </div>
            <div className="space-y-2 sm:col-span-2">
              <Label htmlFor="settings-gender">Gender</Label>
              <select
                id="settings-gender"
                disabled={disabled}
                className="h-10 w-full rounded-md border border-line-200 bg-paper px-3 text-sm text-ink-950 outline-none focus-visible:border-gold-600 focus-visible:ring-2 focus-visible:ring-gold-600/20 disabled:cursor-not-allowed disabled:opacity-60"
                {...register("gender")}
              >
                <option value="">Not provided</option>
                <option value="male">Male</option>
                <option value="female">Female</option>
                <option value="other">Other</option>
              </select>
              <FieldError message={errors.gender?.message} />
            </div>
          </div>

          <Button
            type="submit"
            loading={update.isPending}
            disabled={disabled || !isDirty}
          >
            <Save className="size-4" aria-hidden="true" />
            {update.isPending ? "Saving…" : "Save profile"}
          </Button>
        </form>
      </CardContent>
    </Card>
  );
}
