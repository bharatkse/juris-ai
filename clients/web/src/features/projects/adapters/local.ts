import type {
  Project,
  ProjectDraft,
  ProjectRepository,
} from "@/features/projects/types";
import {
  browserStorage,
  readVersioned,
  userStoreKey,
  writeVersioned,
} from "@/lib/local-store";

const FEATURE = "projects";
const VERSION = 1;

function nowIso(): string {
  return new Date().toISOString();
}

function requireStorage(): Storage {
  const storage = browserStorage();
  if (!storage) {
    throw new Error("Local storage is not available in this browser.");
  }
  return storage;
}

function load(userId: string): Project[] {
  return readVersioned(
    requireStorage(),
    userStoreKey(userId, FEATURE),
    [] as Project[],
    { version: VERSION },
  );
}

function save(userId: string, projects: Project[]): void {
  writeVersioned(
    requireStorage(),
    userStoreKey(userId, FEATURE),
    projects,
    VERSION,
  );
}

function requireProject(projects: Project[], id: string): Project {
  const project = projects.find((item) => item.id === id);
  if (!project) {
    throw new Error(`Project ${id} was not found.`);
  }
  return project;
}

function replace(projects: Project[], next: Project): Project[] {
  return projects.map((item) => (item.id === next.id ? next : item));
}

export function createLocalProjectRepository(userId: string): ProjectRepository {
  return {
    persistence: "local",

    async list() {
      return load(userId).sort(
        (left, right) =>
          new Date(right.updated_at).getTime() -
          new Date(left.updated_at).getTime(),
      );
    },

    async get(id) {
      return requireProject(load(userId), id);
    },

    async create(draft: ProjectDraft) {
      const timestamp = nowIso();
      const project: Project = {
        id: globalThis.crypto.randomUUID(),
        name: draft.name.trim() || "Untitled project",
        description: draft.description?.trim() ?? "",
        instructions: draft.instructions?.trim() ?? "",
        conversation_ids: [],
        document_ids: [],
        created_at: timestamp,
        updated_at: timestamp,
      };
      save(userId, [project, ...load(userId)]);
      return project;
    },

    async update(id, draft) {
      const projects = load(userId);
      const current = requireProject(projects, id);
      const next: Project = {
        ...current,
        name: draft.name?.trim() || current.name,
        description:
          draft.description === undefined
            ? current.description
            : draft.description.trim(),
        instructions:
          draft.instructions === undefined
            ? current.instructions
            : draft.instructions.trim(),
        updated_at: nowIso(),
      };
      save(userId, replace(projects, next));
      return next;
    },

    async delete(id) {
      save(
        userId,
        load(userId).filter((item) => item.id !== id),
      );
    },

    async addConversation(projectId, conversationId) {
      const projects = load(userId);
      const current = requireProject(projects, projectId);
      if (current.conversation_ids.includes(conversationId)) return current;
      const next: Project = {
        ...current,
        conversation_ids: [...current.conversation_ids, conversationId],
        updated_at: nowIso(),
      };
      save(userId, replace(projects, next));
      return next;
    },

    async removeConversation(projectId, conversationId) {
      const projects = load(userId);
      const current = requireProject(projects, projectId);
      const next: Project = {
        ...current,
        conversation_ids: current.conversation_ids.filter(
          (id) => id !== conversationId,
        ),
        updated_at: nowIso(),
      };
      save(userId, replace(projects, next));
      return next;
    },

    async addDocument(projectId, documentId) {
      const projects = load(userId);
      const current = requireProject(projects, projectId);
      if (current.document_ids.includes(documentId)) return current;
      const next: Project = {
        ...current,
        document_ids: [...current.document_ids, documentId],
        updated_at: nowIso(),
      };
      save(userId, replace(projects, next));
      return next;
    },

    async removeDocument(projectId, documentId) {
      const projects = load(userId);
      const current = requireProject(projects, projectId);
      const next: Project = {
        ...current,
        document_ids: current.document_ids.filter((id) => id !== documentId),
        updated_at: nowIso(),
      };
      save(userId, replace(projects, next));
      return next;
    },
  };
}
