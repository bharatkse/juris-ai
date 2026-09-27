import { z } from "zod";

import type { UpdateProfileInput, User } from "@/lib/api/types";

function validDate(value: string): boolean {
  if (!/^\d{4}-\d{2}-\d{2}$/u.test(value)) return false;
  const parsed = new Date(`${value}T00:00:00Z`);
  return (
    Number.isFinite(parsed.getTime()) &&
    parsed.toISOString().slice(0, 10) === value
  );
}

const optionalName = z
  .string()
  .trim()
  .max(100, "Use 100 characters or fewer.")
  .refine(
    (value) => value.length === 0 || value.length >= 2,
    "Use at least 2 characters or leave blank.",
  );

export const profileSchema = z.object({
  first_name: optionalName,
  last_name: optionalName,
  phone_number: z
    .string()
    .trim()
    .refine(
      (value) => value.length === 0 || value.length >= 10,
      "Use at least 10 characters or leave blank.",
    )
    .refine(
      (value) => value.length <= 20,
      "Use 20 characters or fewer.",
    ),
  date_of_birth: z
    .string()
    .refine(
      (value) => value.length === 0 || validDate(value),
      "Enter a valid date.",
    ),
  gender: z.enum(["", "male", "female", "other"]),
});

export type ProfileValues = z.infer<typeof profileSchema>;

export function profileFormValues(user?: User): ProfileValues {
  return {
    first_name: user?.first_name ?? "",
    last_name: user?.last_name ?? "",
    phone_number: user?.phone_number ?? "",
    date_of_birth: user?.date_of_birth ?? "",
    gender: user?.gender ?? "",
  };
}

export function profileUpdatePayload(
  values: ProfileValues,
): UpdateProfileInput {
  return {
    first_name: values.first_name.trim() || null,
    last_name: values.last_name.trim() || null,
    phone_number: values.phone_number.trim() || null,
    date_of_birth: values.date_of_birth || null,
    gender: values.gender || null,
  };
}
