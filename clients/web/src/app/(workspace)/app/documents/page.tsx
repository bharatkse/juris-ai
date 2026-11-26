"use client";

import { DeviceHint } from "@/components/ui/device-hint";
import { Button } from "@/components/ui/button";
import {
  useAddDocument,
  useDocumentPersistence,
  useDocuments,
  useRemoveDocument,
} from "@/features/documents/queries";

export default function DocumentsPage() {
  const documents = useDocuments();
  const add = useAddDocument();
  const remove = useRemoveDocument();
  const persistence = useDocumentPersistence();

  return (
    <div className="mx-auto h-full w-full max-w-3xl overflow-y-auto px-4 py-8 sm:px-8">
      <h1 className="text-2xl font-semibold tracking-[-0.02em]">Documents</h1>
      <p className="mt-2 text-sm text-muted-foreground">
        Library metadata for this device. Chat uploads still travel with POST
        /chat.
      </p>
      <DeviceHint persistence={persistence} />
      <label className="mt-6 inline-flex cursor-pointer items-center rounded-md bg-primary px-3 py-2 text-sm font-semibold text-primary-foreground">
        Upload
        <input
          type="file"
          className="sr-only"
          onChange={(event) => {
            const file = event.target.files?.[0];
            if (!file) return;
            void add.mutateAsync({
              name: file.name,
              mime: file.type || "application/octet-stream",
              size: file.size,
            });
          }}
        />
      </label>
      {(documents.data ?? []).length === 0 ? (
        <p className="mt-8 text-sm text-muted-foreground">No documents yet.</p>
      ) : (
        <ul className="mt-6 space-y-2">
          {(documents.data ?? []).map((doc) => (
            <li
              key={doc.id}
              className="flex items-center justify-between rounded-md border border-border px-3 py-2 text-sm"
            >
              <span>{doc.name}</span>
              <Button
                type="button"
                variant="ghost"
                size="sm"
                onClick={() => void remove.mutateAsync(doc.id)}
              >
                Remove
              </Button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
