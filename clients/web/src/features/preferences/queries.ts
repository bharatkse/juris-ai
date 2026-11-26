"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { useCurrentUser } from "@/features/auth/use-current-user";
import {
  defaultPreferences,
  getPreferencesRepository,
  type UserPreferences,
} from "@/features/preferences/repository";

export const preferenceKeys = {
  all: ["preferences"] as const,
};

export function usePreferences() {
  const user = useCurrentUser();
  const repo = user.data?.id ? getPreferencesRepository(user.data.id) : null;
  return useQuery({
    queryKey: preferenceKeys.all,
    queryFn: () => repo!.get(),
    enabled: Boolean(repo),
    placeholderData: defaultPreferences(),
  });
}

export function useSavePreferences() {
  const queryClient = useQueryClient();
  const user = useCurrentUser();
  const repo = user.data?.id ? getPreferencesRepository(user.data.id) : null;
  return useMutation({
    mutationFn: (next: UserPreferences) => {
      if (!repo) throw new Error("Sign in to save preferences.");
      return repo.save(next);
    },
    onSuccess: (prefs) => {
      queryClient.setQueryData(preferenceKeys.all, prefs);
    },
  });
}

export function usePreferencesPersistence() {
  const user = useCurrentUser();
  return user.data?.id
    ? getPreferencesRepository(user.data.id).persistence
    : "local";
}
