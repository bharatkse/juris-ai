"use client";

import {
  type InfiniteData,
  useInfiniteQuery,
  useMutation,
  useQuery,
  useQueryClient,
} from "@tanstack/react-query";

import {
  archiveConversation,
  createConversation,
  getConversation,
  listConversationEvents,
  listConversations,
  renameConversation,
} from "@/lib/api/conversations";
import type {
  Conversation,
  ConversationAnswerCache,
  ConversationApprovalCache,
  ConversationEvent,
  Paginated,
} from "@/lib/api/types";

export const CONVERSATION_PAGE_SIZE = 20;
export const HISTORY_PAGE_SIZE = 100;

export const conversationKeys = {
  all: ["conversations"] as const,
  list: () => [...conversationKeys.all, "list"] as const,
  detail: (id: string) => [...conversationKeys.all, "detail", id] as const,
  history: (id: string) => [...conversationKeys.all, "history", id] as const,
  answers: (id: string) => [...conversationKeys.all, "answers", id] as const,
  approvals: (id: string) => [...conversationKeys.all, "approvals", id] as const,
};

export function flattenConversations(
  data?: InfiniteData<Paginated<Conversation>, unknown>,
): Conversation[] {
  return data?.pages.flatMap((page) => page.items) ?? [];
}

export function filterConversations(
  conversations: readonly Conversation[],
  search: string,
): Conversation[] {
  const query = search.trim().toLocaleLowerCase();
  if (!query) {
    return [...conversations];
  }
  return conversations.filter((conversation) =>
    conversation.title.toLocaleLowerCase().includes(query),
  );
}

export function flattenConversationEvents(
  data?: InfiniteData<Paginated<ConversationEvent>, unknown>,
): ConversationEvent[] {
  return (
    data?.pages
      .flatMap((page) => page.items)
      .sort(
        (left, right) =>
          new Date(left.created_at).getTime() -
          new Date(right.created_at).getTime(),
      ) ?? []
  );
}

export function mergeConversationEvents(
  history: readonly ConversationEvent[],
  recent: readonly ConversationEvent[],
): ConversationEvent[] {
  const byId = new Map<string, ConversationEvent>();
  for (const event of [...recent, ...history]) {
    byId.set(event.id, event);
  }
  return [...byId.values()].sort(
    (left, right) =>
      new Date(left.created_at).getTime() -
      new Date(right.created_at).getTime(),
  );
}

export function formatRelativeTime(
  isoDate: string,
  now = Date.now(),
): string {
  const timestamp = new Date(isoDate).getTime();
  if (!Number.isFinite(timestamp)) {
    return "";
  }

  const seconds = Math.max(0, Math.floor((now - timestamp) / 1000));
  if (seconds < 60) return "now";
  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return `${minutes}m`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h`;
  const days = Math.floor(hours / 24);
  if (days < 7) return `${days}d`;

  return new Intl.DateTimeFormat(undefined, {
    month: "short",
    day: "numeric",
  }).format(timestamp);
}

export function useConversations() {
  return useInfiniteQuery({
    queryKey: conversationKeys.list(),
    queryFn: ({ pageParam }) =>
      listConversations(pageParam, CONVERSATION_PAGE_SIZE),
    initialPageParam: 0,
    getNextPageParam: (lastPage) =>
      lastPage.pagination.has_more
        ? lastPage.pagination.offset + lastPage.pagination.limit
        : undefined,
  });
}

export function useConversation(id?: string) {
  return useQuery({
    queryKey: conversationKeys.detail(id ?? ""),
    queryFn: () => getConversation(id as string),
    enabled: Boolean(id),
  });
}

interface HistoryPageParam {
  offset: number;
  limit: number;
}

async function loadHistoryPage(
  id: string,
  page: HistoryPageParam,
): Promise<Paginated<ConversationEvent>> {
  if (page.offset >= 0) {
    return listConversationEvents(id, page.offset, page.limit);
  }

  const first = await listConversationEvents(id, 0, HISTORY_PAGE_SIZE);
  if (!first.pagination.has_more) {
    return first;
  }

  const latestOffset = Math.max(
    0,
    first.pagination.total - HISTORY_PAGE_SIZE,
  );
  return listConversationEvents(id, latestOffset, HISTORY_PAGE_SIZE);
}

export function useConversationHistory(id: string) {
  return useInfiniteQuery({
    queryKey: conversationKeys.history(id),
    queryFn: ({ pageParam }) => loadHistoryPage(id, pageParam),
    initialPageParam: { offset: -1, limit: HISTORY_PAGE_SIZE },
    getNextPageParam: (lastPage): HistoryPageParam | undefined => {
      const currentOffset = lastPage.pagination.offset;
      if (currentOffset <= 0) return undefined;
      const offset = Math.max(0, currentOffset - HISTORY_PAGE_SIZE);
      return { offset, limit: currentOffset - offset };
    },
  });
}

export function useConversationAnswerDetails(id: string) {
  return useQuery({
    queryKey: conversationKeys.answers(id),
    queryFn: async (): Promise<ConversationAnswerCache> => ({}),
    initialData: {},
    staleTime: Number.POSITIVE_INFINITY,
  });
}

export function useConversationApprovalStates(id: string) {
  return useQuery({
    queryKey: conversationKeys.approvals(id),
    queryFn: async (): Promise<ConversationApprovalCache> => ({}),
    initialData: {},
    staleTime: Number.POSITIVE_INFINITY,
  });
}

export function useCreateConversation() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (title?: string) => createConversation(title),
    onSuccess: (conversation) => {
      queryClient.setQueryData(
        conversationKeys.detail(conversation.id),
        conversation,
      );
      void queryClient.invalidateQueries({ queryKey: conversationKeys.list() });
    },
  });
}

export function useRenameConversation() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ id, title }: { id: string; title: string }) =>
      renameConversation(id, title),
    onSuccess: (conversation) => {
      queryClient.setQueryData(
        conversationKeys.detail(conversation.id),
        conversation,
      );
      queryClient.setQueryData<
        InfiniteData<Paginated<Conversation>, number>
      >(conversationKeys.list(), (current) =>
        current
          ? {
              ...current,
              pages: current.pages.map((page) => ({
                ...page,
                items: page.items.map((item) =>
                  item.id === conversation.id ? conversation : item,
                ),
              })),
            }
          : current,
      );
    },
  });
}

export function useArchiveConversation() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (id: string) => archiveConversation(id),
    onSuccess: (_, id) => {
      queryClient.removeQueries({ queryKey: conversationKeys.detail(id) });
      queryClient.removeQueries({ queryKey: conversationKeys.history(id) });
      queryClient.removeQueries({ queryKey: conversationKeys.answers(id) });
      queryClient.removeQueries({ queryKey: conversationKeys.approvals(id) });
      queryClient.setQueryData<
        InfiniteData<Paginated<Conversation>, number>
      >(conversationKeys.list(), (current) =>
        current
          ? {
              ...current,
              pages: current.pages.map((page) => ({
                ...page,
                items: page.items.filter((item) => item.id !== id),
                pagination: {
                  ...page.pagination,
                  total: Math.max(0, page.pagination.total - 1),
                },
              })),
            }
          : current,
      );
      void queryClient.invalidateQueries({ queryKey: conversationKeys.list() });
    },
  });
}
