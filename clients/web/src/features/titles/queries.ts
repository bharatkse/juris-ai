"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { useCurrentUser } from "@/features/auth/use-current-user";
import { getTitleRepository } from "@/features/titles/repository";

export const titleKeys = {
  all: ["titles"] as const,
};

export function useConversationTitles() {
  const user = useCurrentUser();
  const repo = user.data?.id ? getTitleRepository(user.data.id) : null;
  return useQuery({
    queryKey: titleKeys.all,
    queryFn: () => repo!.list(),
    enabled: Boolean(repo),
  });
}

export function useSetConversationTitle() {
  const queryClient = useQueryClient();
  const user = useCurrentUser();
  const repo = user.data?.id ? getTitleRepository(user.data.id) : null;
  return useMutation({
    mutationFn: ({ id, title }: { id: string; title: string }) => {
      if (!repo) throw new Error("Sign in to rename a conversation.");
      return repo.set(id, title);
    },
    onSuccess: (map) => {
      queryClient.setQueryData(titleKeys.all, map);
    },
  });
}

export function displayTitle(
  conversationId: string,
  apiTitle: string,
  overrides?: Record<string, string>,
): string {
  return overrides?.[conversationId] || apiTitle;
}
