"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { useCurrentUser } from "@/features/auth/use-current-user";
import type { PinItem } from "@/features/pins/order";
import { getPinRepository } from "@/features/pins/repository";

export const pinKeys = {
  all: ["pins"] as const,
  list: () => [...pinKeys.all, "list"] as const,
};

function useRepo() {
  const user = useCurrentUser();
  return {
    ready: Boolean(user.data?.id),
    repo: user.data?.id ? getPinRepository(user.data.id) : null,
  };
}

export function usePins() {
  const { ready, repo } = useRepo();
  return useQuery({
    queryKey: pinKeys.list(),
    queryFn: () => repo!.list(),
    enabled: ready && Boolean(repo),
  });
}

export function useTogglePin() {
  const queryClient = useQueryClient();
  const { repo } = useRepo();
  return useMutation({
    mutationFn: (target: PinItem) => {
      if (!repo) throw new Error("Sign in to pin items.");
      return repo.toggle(target);
    },
    onSuccess: (items) => {
      queryClient.setQueryData(pinKeys.list(), items);
    },
  });
}

export function useReorderPins() {
  const queryClient = useQueryClient();
  const { repo } = useRepo();
  return useMutation({
    mutationFn: (items: PinItem[]) => {
      if (!repo) throw new Error("Sign in to reorder pins.");
      return repo.replace(items);
    },
    onSuccess: (items) => {
      queryClient.setQueryData(pinKeys.list(), items);
    },
  });
}

export function usePinPersistence() {
  const { repo } = useRepo();
  return repo?.persistence ?? "local";
}
