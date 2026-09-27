import { apiFetch, jsonRequest } from "@/lib/api/client";
import type { UpdateProfileInput, User } from "@/lib/api/types";

export async function updateProfile(
  userId: string,
  input: UpdateProfileInput,
): Promise<User> {
  return apiFetch<User>(
    `/api/backend/users/${encodeURIComponent(userId)}`,
    jsonRequest(input, { method: "PATCH" }),
  );
}
