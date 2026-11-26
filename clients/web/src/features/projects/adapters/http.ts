import type {
  Project,
  ProjectDraft,
  ProjectRepository,
} from "@/features/projects/types";
import { apiFetch, jsonRequest } from "@/lib/api/client";

const ENDPOINT = "/api/backend/projects";

export const httpProjectRepository: ProjectRepository = {
  persistence: "http",

  list() {
    return apiFetch<Project[]>(ENDPOINT);
  },

  get(id) {
    return apiFetch<Project>(`${ENDPOINT}/${encodeURIComponent(id)}`);
  },

  create(draft: ProjectDraft) {
    return apiFetch<Project>(ENDPOINT, jsonRequest(draft, { method: "POST" }));
  },

  update(id, draft) {
    return apiFetch<Project>(
      `${ENDPOINT}/${encodeURIComponent(id)}`,
      jsonRequest(draft, { method: "PATCH" }),
    );
  },

  delete(id) {
    return apiFetch<void>(`${ENDPOINT}/${encodeURIComponent(id)}`, {
      method: "DELETE",
    });
  },

  addConversation(projectId, conversationId) {
    return apiFetch<Project>(
      `${ENDPOINT}/${encodeURIComponent(projectId)}/conversations`,
      jsonRequest({ conversation_id: conversationId }, { method: "POST" }),
    );
  },

  removeConversation(projectId, conversationId) {
    return apiFetch<Project>(
      `${ENDPOINT}/${encodeURIComponent(projectId)}/conversations/${encodeURIComponent(conversationId)}`,
      { method: "DELETE" },
    );
  },

  addDocument(projectId, documentId) {
    return apiFetch<Project>(
      `${ENDPOINT}/${encodeURIComponent(projectId)}/documents`,
      jsonRequest({ document_id: documentId }, { method: "POST" }),
    );
  },

  removeDocument(projectId, documentId) {
    return apiFetch<Project>(
      `${ENDPOINT}/${encodeURIComponent(projectId)}/documents/${encodeURIComponent(documentId)}`,
      { method: "DELETE" },
    );
  },
};
