export interface LibraryDocument {
  id: string;
  name: string;
  mime: string;
  size: number;
  created_at: string;
}

export interface DocumentRepository {
  readonly persistence: "http" | "local";
  list(): Promise<LibraryDocument[]>;
  add(meta: Pick<LibraryDocument, "name" | "mime" | "size">): Promise<LibraryDocument>;
  remove(id: string): Promise<void>;
}
