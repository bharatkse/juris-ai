"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { apiFetch } from "@/lib/api/client";
import { updateProfile } from "@/lib/api/users";
import type { UpdateProfileInput, User } from "@/lib/api/types";

export const currentUserQueryKey = ["auth", "me"] as const;

export function useCurrentUser() {
  return useQuery({
    queryKey: currentUserQueryKey,
    queryFn: () => apiFetch<User>("/api/auth/me"),
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
