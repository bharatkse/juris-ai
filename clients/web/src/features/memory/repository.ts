import { featureBackends } from "@/config/feature-backends";
import { httpMemoryRepository } from "@/features/memory/adapters/http";
import { createLocalMemoryRepository } from "@/features/memory/adapters/local";
import type { MemoryRepository } from "@/features/memory/types";

export function getMemoryRepository(userId?: string): MemoryRepository {
  if (featureBackends.memory === "local") {
    if (!userId) {
      throw new Error("A signed-in user is required for device memory.");
    }
    return createLocalMemoryRepository(userId);
  }
  return httpMemoryRepository;
}

export type { MemoryRepository } from "@/features/memory/types";
