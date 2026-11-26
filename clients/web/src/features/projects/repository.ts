import { featureBackends } from "@/config/feature-backends";
import { httpProjectRepository } from "@/features/projects/adapters/http";
import { createLocalProjectRepository } from "@/features/projects/adapters/local";
import type { ProjectRepository } from "@/features/projects/types";

export function getProjectRepository(userId?: string): ProjectRepository {
  if (featureBackends.projects === "local") {
    if (!userId) {
      throw new Error("A signed-in user is required for device projects.");
    }
    return createLocalProjectRepository(userId);
  }
  return httpProjectRepository;
}
