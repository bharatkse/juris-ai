export interface Project {
  id: string;
  name: string;
  description: string;
  instructions: string;
  conversation_ids: string[];
  document_ids: string[];
  created_at: string;
  updated_at: string;
}

export interface ProjectDraft {
  name: string;
  description?: string;
  instructions?: string;
}

export interface ProjectRepository {
  readonly persistence: "http" | "local";
  list(): Promise<Project[]>;
  get(id: string): Promise<Project>;
  create(draft: ProjectDraft): Promise<Project>;
  update(id: string, draft: Partial<ProjectDraft>): Promise<Project>;
  delete(id: string): Promise<void>;
  addConversation(projectId: string, conversationId: string): Promise<Project>;
  removeConversation(
    projectId: string,
    conversationId: string,
  ): Promise<Project>;
  addDocument(projectId: string, documentId: string): Promise<Project>;
  removeDocument(projectId: string, documentId: string): Promise<Project>;
}

export function recentProjects(
  projects: readonly Project[],
  limit = 8,
): Project[] {
  return [...projects]
    .sort(
      (left, right) =>
        new Date(right.updated_at).getTime() -
        new Date(left.updated_at).getTime(),
    )
    .slice(0, limit);
}
