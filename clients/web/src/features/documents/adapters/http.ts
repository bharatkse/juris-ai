import type {
  DocumentRepository,
  LibraryDocument,
} from "@/features/documents/types";
import { apiFetch, jsonRequest } from "@/lib/api/client";

const ENDPOINT = "/api/backend/documents";

export const httpDocumentRepository: DocumentRepository = {
  persistence: "http",
  list() {
    return apiFetch<LibraryDocument[]>(ENDPOINT);
  },
  add(meta) {
    return apiFetch<LibraryDocument>(
      ENDPOINT,
      jsonRequest(meta, { method: "POST" }),
    );
  },
  remove(id) {
    return apiFetch<void>(`${ENDPOINT}/${encodeURIComponent(id)}`, {
      method: "DELETE",
    });
  },
};
