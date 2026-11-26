"use client";

import { useEffect, useRef, useState } from "react";
import { zodResolver } from "@hookform/resolvers/zod";
import { useForm } from "react-hook-form";
import { toast } from "sonner";

import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import { DeviceHint } from "@/components/ui/device-hint";
import { Input } from "@/components/ui/input";
import { SettingRow, SettingsSection } from "@/components/ui/setting-row";
import {
  profileFormValues,
  profileSchema,
  profileUpdatePayload,
  type ProfileValues,
} from "@/features/auth/profile";
import {
  useCurrentUser,
  useUpdateCurrentUser,
} from "@/features/auth/use-current-user";
import {
  usePreferences,
  usePreferencesPersistence,
  useSavePreferences,
} from "@/features/preferences/queries";
import { ApiError } from "@/lib/api/errors";
import { getInitials } from "@/lib/utils";

const fields = new Set<keyof ProfileValues>([
  "first_name",
  "last_name",
  "phone_number",
  "date_of_birth",
  "gender",
]);

export function ProfilePage() {
  const user = useCurrentUser();
  const update = useUpdateCurrentUser(user.data?.id);
  const prefs = usePreferences();
  const savePrefs = useSavePreferences();
  const persistence = usePreferencesPersistence();
  const fileRef = useRef<HTMLInputElement>(null);
  const [formError, setFormError] = useState<string | null>(null);
  const [confirmDelete, setConfirmDelete] = useState(false);
  const {
    register,
    handleSubmit,
    reset,
    setError,
    formState: { errors, isDirty },
  } = useForm<ProfileValues>({
    resolver: zodResolver(profileSchema),
    defaultValues: profileFormValues(user.data),
  });

  useEffect(() => {
    reset(profileFormValues(user.data));
  }, [reset, user.data]);

  async function submit(values: ProfileValues) {
    setFormError(null);
    try {
      await update.mutateAsync(profileUpdatePayload(values));
      toast.success("Profile updated.");
    } catch (error) {
      if (error instanceof ApiError) {
        for (const [field, messages] of Object.entries(error.fields ?? {})) {
          if (fields.has(field as keyof ProfileValues)) {
            setError(field as keyof ProfileValues, { message: messages[0] });
          }
        }
        setFormError(error.message);
      } else {
        setFormError("Could not update your profile.");
      }
    }
  }

  const initials = getInitials(
    user.data?.first_name,
    user.data?.last_name,
    user.data?.email,
  );
  const avatar = prefs.data?.avatarDataUrl;
  const disabled = user.isPending || update.isPending || !user.data;

  return (
    <div className="space-y-10">
      <SettingsSection
        title="Profile"
        description="How you appear in this workspace."
      >
        <SettingRow label="Avatar" description="Initials are used when no image is set.">
          <div className="flex items-center gap-3">
            <span className="grid size-12 place-items-center overflow-hidden rounded-full border border-border bg-hover text-sm font-semibold">
              {avatar ? (
                // eslint-disable-next-line @next/next/no-img-element
                <img src={avatar} alt="" className="size-full object-cover" />
              ) : (
                initials
              )}
            </span>
            <div className="flex flex-col gap-1">
              <input
                ref={fileRef}
                type="file"
                accept="image/*"
                className="sr-only"
                onChange={(event) => {
                  const file = event.target.files?.[0];
                  if (!file || !prefs.data) return;
                  const reader = new FileReader();
                  reader.onload = () => {
                    void savePrefs.mutateAsync({
                      ...prefs.data!,
                      avatarDataUrl: String(reader.result),
                    });
                  };
                  reader.readAsDataURL(file);
                }}
              />
              <Button
                type="button"
                variant="outline"
                size="sm"
                onClick={() => fileRef.current?.click()}
              >
                Upload
              </Button>
              {avatar ? (
                <Button
                  type="button"
                  variant="ghost"
                  size="sm"
                  onClick={() =>
                    prefs.data &&
                    void savePrefs.mutateAsync({
                      ...prefs.data,
                      avatarDataUrl: null,
                    })
                  }
                >
                  Remove
                </Button>
              ) : null}
              <DeviceHint persistence={persistence} />
            </div>
          </div>
        </SettingRow>
      </SettingsSection>

      <form onSubmit={handleSubmit(submit)} noValidate>
        <SettingsSection title="Personal details">
          {formError ? (
            <div className="py-3">
              <Alert tone="error">
                <AlertDescription>{formError}</AlertDescription>
              </Alert>
            </div>
          ) : null}
          <SettingRow label="First name" htmlFor="profile-first-name">
            <Input
              id="profile-first-name"
              disabled={disabled}
              aria-invalid={Boolean(errors.first_name)}
              {...register("first_name")}
            />
          </SettingRow>
          {errors.first_name ? (
            <p className="pb-3 text-xs text-danger">{errors.first_name.message}</p>
          ) : null}
          <SettingRow label="Last name" htmlFor="profile-last-name">
            <Input
              id="profile-last-name"
              disabled={disabled}
              aria-invalid={Boolean(errors.last_name)}
              {...register("last_name")}
            />
          </SettingRow>
          <SettingRow
            label="Email"
            description="Email comes from your account and cannot be changed here."
          >
            <Input value={user.data?.email ?? ""} disabled readOnly />
          </SettingRow>
          <SettingRow label="Phone" htmlFor="profile-phone">
            <Input
              id="profile-phone"
              type="tel"
              disabled={disabled}
              {...register("phone_number")}
            />
          </SettingRow>
          <SettingRow label="Date of birth" htmlFor="profile-dob">
            <Input
              id="profile-dob"
              type="date"
              disabled={disabled}
              {...register("date_of_birth")}
            />
          </SettingRow>
          <SettingRow label="Member since">
            <p className="text-sm">
              {user.data?.created_at
                ? new Date(user.data.created_at).toLocaleDateString()
                : "—"}
            </p>
          </SettingRow>
          <SettingRow label="Workspace">
            <p className="text-sm">Juris AI</p>
          </SettingRow>
          <SettingRow label="Role">
            <p className="text-sm">Member</p>
          </SettingRow>
        </SettingsSection>
        {isDirty ? (
          <div className="sticky bottom-0 mt-4 flex justify-end gap-2 border-t border-border bg-background/95 py-3">
            <Button type="submit" loading={update.isPending} disabled={disabled}>
              Save changes
            </Button>
          </div>
        ) : null}
      </form>

      <SettingsSection
        title="Danger zone"
        description="Account deletion is not available on the API yet."
      >
        <SettingRow
          label="Delete account"
          description="This would permanently remove your workspace data."
        >
          <Button
            type="button"
            variant="destructive"
            size="sm"
            onClick={() => setConfirmDelete(true)}
          >
            Delete account
          </Button>
        </SettingRow>
      </SettingsSection>

      <ConfirmDialog
        open={confirmDelete}
        onOpenChange={setConfirmDelete}
        title="Delete account?"
        description="The API has no delete-account route. This action is blocked until the backend ships it."
        confirmLabel="Understood"
        onConfirm={() => {
          setConfirmDelete(false);
          toast.error("Account deletion is not available yet.");
        }}
      />
    </div>
  );
}
