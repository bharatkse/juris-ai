"use client";

import {
  type InfiniteData,
  useInfiniteQuery,
  useMutation,
  useQuery,
  useQueryClient,
} from "@tanstack/react-query";

import {
  deleteMemory,
  getMemorySettings,
  listMemories,
  updateMemorySettings,
} from "@/features/memory/api";
import type { MemoryItem, MemorySettings, Paginated } from "@/types/api";

export const MEMORY_PAGE_SIZE = 20;

export const memoryKeys = {
  all: ["memory"] as const,
  settings: () => [...memoryKeys.all, "settings"] as const,
  list: () => [...memoryKeys.all, "items"] as const,
};

export function flattenMemories(
  data?: InfiniteData<Paginated<MemoryItem>, unknown>,
): MemoryItem[] {
  return data?.pages.flatMap((page) => page.items) ?? [];
}

export function useMemorySettings() {
  return useQuery({
    queryKey: memoryKeys.settings(),
    queryFn: ({ signal }) => getMemorySettings(signal),
  });
}

export function useMemories(enabled: boolean) {
  return useInfiniteQuery({
    queryKey: memoryKeys.list(),
    queryFn: ({ pageParam, signal }) =>
      listMemories(pageParam, MEMORY_PAGE_SIZE, signal),
    initialPageParam: 0,
    enabled,
    getNextPageParam: (lastPage) =>
      lastPage.pagination.has_more
        ? lastPage.pagination.offset + lastPage.pagination.limit
        : undefined,
  });
}

export function useUpdateMemorySettings() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (enabled: boolean) => updateMemorySettings(enabled),
    onSuccess: (settings: MemorySettings) => {
      queryClient.setQueryData(memoryKeys.settings(), settings);
      if (!settings.enabled) {
        queryClient.removeQueries({ queryKey: memoryKeys.list() });
      } else {
        void queryClient.invalidateQueries({ queryKey: memoryKeys.list() });
      }
    },
  });
}

export function useDeleteMemory() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => deleteMemory(id),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: memoryKeys.list() });
    },
  });
}
