"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { useCurrentUser } from "@/features/auth/use-current-user";
import { getMemoryRepository } from "@/features/memory/repository";
import type {
  MemoryDraft,
  MemoryListQuery,
  MemoryRecord,
} from "@/features/memory/types";
import type { MemorySettings } from "@/types/api";

export const memoryKeys = {
  all: ["memory"] as const,
  settings: () => [...memoryKeys.all, "settings"] as const,
  list: (query?: MemoryListQuery) =>
    [...memoryKeys.all, "items", query ?? {}] as const,
  detail: (id: string) => [...memoryKeys.all, "item", id] as const,
};

function useRepo() {
  const user = useCurrentUser();
  return {
    userId: user.data?.id,
    ready: Boolean(user.data?.id),
    repo: user.data?.id ? getMemoryRepository(user.data.id) : null,
  };
}

export function useMemorySettings() {
  const { ready, repo } = useRepo();
  return useQuery({
    queryKey: memoryKeys.settings(),
    queryFn: ({ signal }) => repo!.getSettings(signal),
    enabled: ready && Boolean(repo),
  });
}

export function useMemories(query: MemoryListQuery, enabled = true) {
  const { ready, repo } = useRepo();
  return useQuery({
    queryKey: memoryKeys.list(query),
    queryFn: ({ signal }) => repo!.list(query, signal),
    enabled: ready && enabled && Boolean(repo),
  });
}

export function useMemory(id?: string) {
  const { ready, repo } = useRepo();
  return useQuery({
    queryKey: memoryKeys.detail(id ?? ""),
    queryFn: ({ signal }) => repo!.get(id as string, signal),
    enabled: ready && Boolean(id) && Boolean(repo),
  });
}

export function useUpdateMemorySettings() {
  const queryClient = useQueryClient();
  const { repo } = useRepo();
  return useMutation({
    mutationFn: (enabled: boolean) => {
      if (!repo) throw new Error("Sign in to update memory.");
      return repo.setEnabled(enabled);
    },
    onSuccess: (settings: MemorySettings) => {
      queryClient.setQueryData(memoryKeys.settings(), settings);
      void queryClient.invalidateQueries({ queryKey: memoryKeys.all });
    },
  });
}

export function useCreateMemory() {
  const queryClient = useQueryClient();
  const { repo } = useRepo();
  return useMutation({
    mutationFn: (draft: MemoryDraft) => {
      if (!repo) throw new Error("Sign in to add memory.");
      return repo.create(draft);
    },
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: memoryKeys.all });
    },
  });
}

export function useUpdateMemory() {
  const queryClient = useQueryClient();
  const { repo } = useRepo();
  return useMutation({
    mutationFn: ({
      id,
      draft,
    }: {
      id: string;
      draft: Partial<MemoryDraft>;
    }) => {
      if (!repo) throw new Error("Sign in to edit memory.");
      return repo.update(id, draft);
    },
    onSuccess: (record: MemoryRecord) => {
      queryClient.setQueryData(memoryKeys.detail(record.id), record);
      void queryClient.invalidateQueries({ queryKey: memoryKeys.all });
    },
  });
}

export function useDeleteMemory() {
  const queryClient = useQueryClient();
  const { repo } = useRepo();
  return useMutation({
    mutationFn: (id: string) => {
      if (!repo) throw new Error("Sign in to delete memory.");
      return repo.delete(id);
    },
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: memoryKeys.all });
    },
  });
}

export function useClearMemories() {
  const queryClient = useQueryClient();
  const { repo } = useRepo();
  return useMutation({
    mutationFn: () => {
      if (!repo) throw new Error("Sign in to clear memory.");
      return repo.clearAll();
    },
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: memoryKeys.all });
    },
  });
}

export function useMemoryPersistence() {
  const { repo } = useRepo();
  return repo?.persistence ?? "http";
}
