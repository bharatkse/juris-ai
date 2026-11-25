"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { apiFetch } from "@/lib/api/client";
import { updateProfile } from "@/features/auth/api";
import type { UpdateProfileInput, User } from "@/types/api";

export const currentUserQueryKey = ["auth", "me"] as const;

export function useCurrentUser() {
  return useQuery({
    queryKey: currentUserQueryKey,
    queryFn: ({ signal }) => apiFetch<User>("/api/auth/me", { signal }),
  });
}

export function useUpdateCurrentUser(userId?: string) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (input: UpdateProfileInput) => {
      if (!userId) throw new Error("The user profile is not loaded.");
      return updateProfile(userId, input);
    },
    onSuccess: (user) => {
      queryClient.setQueryData(currentUserQueryKey, user);
    },
  });
}
