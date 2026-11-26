"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { useCurrentUser } from "@/features/auth/use-current-user";
import { getProjectRepository } from "@/features/projects/repository";
import type { Project, ProjectDraft } from "@/features/projects/types";

export const projectKeys = {
  all: ["projects"] as const,
  list: () => [...projectKeys.all, "list"] as const,
  detail: (id: string) => [...projectKeys.all, "detail", id] as const,
};

function useRepo() {
  const user = useCurrentUser();
  return {
    ready: Boolean(user.data?.id),
    repo: user.data?.id ? getProjectRepository(user.data.id) : null,
  };
}

export function useProjects() {
  const { ready, repo } = useRepo();
  return useQuery({
    queryKey: projectKeys.list(),
    queryFn: () => repo!.list(),
    enabled: ready && Boolean(repo),
  });
}

export function useProject(id?: string) {
  const { ready, repo } = useRepo();
  return useQuery({
    queryKey: projectKeys.detail(id ?? ""),
    queryFn: () => repo!.get(id as string),
    enabled: ready && Boolean(id) && Boolean(repo),
  });
}

export function useCreateProject() {
  const queryClient = useQueryClient();
  const { repo } = useRepo();
  return useMutation({
    mutationFn: (draft: ProjectDraft) => {
      if (!repo) throw new Error("Sign in to create a project.");
      return repo.create(draft);
    },
    onSuccess: (project: Project) => {
      queryClient.setQueryData(projectKeys.detail(project.id), project);
      void queryClient.invalidateQueries({ queryKey: projectKeys.list() });
    },
  });
}

export function useUpdateProject() {
  const queryClient = useQueryClient();
  const { repo } = useRepo();
  return useMutation({
    mutationFn: ({
      id,
      draft,
    }: {
      id: string;
      draft: Partial<ProjectDraft>;
    }) => {
      if (!repo) throw new Error("Sign in to update a project.");
      return repo.update(id, draft);
    },
    onSuccess: (project: Project) => {
      queryClient.setQueryData(projectKeys.detail(project.id), project);
      void queryClient.invalidateQueries({ queryKey: projectKeys.list() });
    },
  });
}

export function useDeleteProject() {
  const queryClient = useQueryClient();
  const { repo } = useRepo();
  return useMutation({
    mutationFn: (id: string) => {
      if (!repo) throw new Error("Sign in to delete a project.");
      return repo.delete(id);
    },
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: projectKeys.all });
    },
  });
}

export function useAttachProjectConversation() {
  const queryClient = useQueryClient();
  const { repo } = useRepo();
  return useMutation({
    mutationFn: ({
      projectId,
      conversationId,
      remove = false,
    }: {
      projectId: string;
      conversationId: string;
      remove?: boolean;
    }) => {
      if (!repo) throw new Error("Sign in to update a project.");
      return remove
        ? repo.removeConversation(projectId, conversationId)
        : repo.addConversation(projectId, conversationId);
    },
    onSuccess: (project: Project) => {
      queryClient.setQueryData(projectKeys.detail(project.id), project);
      void queryClient.invalidateQueries({ queryKey: projectKeys.list() });
    },
  });
}

export function useAttachProjectDocument() {
  const queryClient = useQueryClient();
  const { repo } = useRepo();
  return useMutation({
    mutationFn: ({
      projectId,
      documentId,
      remove = false,
    }: {
      projectId: string;
      documentId: string;
      remove?: boolean;
    }) => {
      if (!repo) throw new Error("Sign in to update a project.");
      return remove
        ? repo.removeDocument(projectId, documentId)
        : repo.addDocument(projectId, documentId);
    },
    onSuccess: (project: Project) => {
      queryClient.setQueryData(projectKeys.detail(project.id), project);
      void queryClient.invalidateQueries({ queryKey: projectKeys.list() });
    },
  });
}

export function useProjectPersistence() {
  const { repo } = useRepo();
  return repo?.persistence ?? "local";
}
