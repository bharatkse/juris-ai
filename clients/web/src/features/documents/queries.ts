"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { useCurrentUser } from "@/features/auth/use-current-user";
import { getDocumentRepository } from "@/features/documents/repository";
import type { LibraryDocument } from "@/features/documents/types";

export const documentKeys = {
  all: ["documents"] as const,
  list: () => [...documentKeys.all, "list"] as const,
};

function useRepo() {
  const user = useCurrentUser();
  return {
    ready: Boolean(user.data?.id),
    repo: user.data?.id ? getDocumentRepository(user.data.id) : null,
  };
}

export function useDocuments() {
  const { ready, repo } = useRepo();
  return useQuery({
    queryKey: documentKeys.list(),
    queryFn: () => repo!.list(),
    enabled: ready && Boolean(repo),
  });
}

export function useAddDocument() {
  const queryClient = useQueryClient();
  const { repo } = useRepo();
  return useMutation({
    mutationFn: (meta: Pick<LibraryDocument, "name" | "mime" | "size">) => {
      if (!repo) throw new Error("Sign in to add a document.");
      return repo.add(meta);
    },
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: documentKeys.list() });
    },
  });
}

export function useRemoveDocument() {
  const queryClient = useQueryClient();
  const { repo } = useRepo();
  return useMutation({
    mutationFn: (id: string) => {
      if (!repo) throw new Error("Sign in to remove a document.");
      return repo.remove(id);
    },
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: documentKeys.list() });
    },
  });
}

export function useDocumentPersistence() {
  const { repo } = useRepo();
  return repo?.persistence ?? "local";
}
