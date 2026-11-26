import { featureBackends } from "@/config/feature-backends";
import { httpDocumentRepository } from "@/features/documents/adapters/http";
import { createLocalDocumentRepository } from "@/features/documents/adapters/local";
import type { DocumentRepository } from "@/features/documents/types";

export function getDocumentRepository(userId?: string): DocumentRepository {
  if (featureBackends.documents === "local") {
    if (!userId) {
      throw new Error("A signed-in user is required for the document library.");
    }
    return createLocalDocumentRepository(userId);
  }
  return httpDocumentRepository;
}
