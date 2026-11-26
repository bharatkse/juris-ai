"use client";

import { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { FolderKanban, Plus, Trash2 } from "lucide-react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import { DeviceHint } from "@/components/ui/device-hint";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { Textarea } from "@/components/ui/textarea";
import { Composer } from "@/features/chat/components/composer";
import { flattenConversations, useConversations, useCreateConversation } from "@/features/conversations/queries";
import {
  useAddDocument,
  useDocumentPersistence,
  useDocuments,
} from "@/features/documents/queries";
import { isPinned } from "@/features/pins/order";
import { usePins, useTogglePin } from "@/features/pins/queries";
import {
  useAttachProjectConversation,
  useAttachProjectDocument,
  useCreateProject,
  useDeleteProject,
  useProject,
  useProjectPersistence,
  useProjects,
  useUpdateProject,
} from "@/features/projects/queries";
import { displayTitle, useConversationTitles } from "@/features/titles/queries";

export function ProjectsIndex() {
  const projects = useProjects();
  const create = useCreateProject();
  const persistence = useProjectPersistence();
  const [open, setOpen] = useState(false);
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [instructions, setInstructions] = useState("");
  const router = useRouter();

  return (
    <div className="mx-auto h-full w-full max-w-3xl overflow-y-auto px-4 py-8 sm:px-8">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold tracking-[-0.02em]">Projects</h1>
          <p className="mt-2 text-sm text-muted-foreground">
            Group chats, instructions, and knowledge.
          </p>
          <DeviceHint persistence={persistence} />
        </div>
        <Button type="button" onClick={() => setOpen(true)}>
          <Plus className="size-4" aria-hidden="true" />
          New project
        </Button>
      </div>

      {projects.isPending ? (
        <div className="mt-6 space-y-3">
          <Skeleton className="h-24" />
          <Skeleton className="h-24" />
        </div>
      ) : projects.error ? (
        <p className="mt-6 text-sm">Could not load projects.</p>
      ) : (projects.data ?? []).length === 0 ? (
        <p className="mt-8 text-sm text-muted-foreground">No projects yet.</p>
      ) : (
        <ul className="mt-6 space-y-3">
          {(projects.data ?? []).map((project) => (
            <li key={project.id}>
              <Link
                href={`/projects/${project.id}`}
                className="block rounded-lg border border-border bg-surface p-4 hover:bg-hover"
              >
                <p className="font-medium">{project.name}</p>
                {project.description ? (
                  <p className="mt-1 text-sm text-muted-foreground">
                    {project.description}
                  </p>
                ) : null}
                <p className="mt-2 text-xs text-muted-foreground">
                  {project.conversation_ids.length} chats ·{" "}
                  {project.document_ids.length} documents
                </p>
              </Link>
            </li>
          ))}
        </ul>
      )}

      {open ? (
        <dialog
          open
          className="m-auto w-[min(92vw,480px)] rounded-lg border border-border bg-surface p-5 text-foreground backdrop:bg-foreground/55"
          onClose={() => setOpen(false)}
        >
          <h2 className="text-lg font-semibold">New project</h2>
          <form
            className="mt-4 space-y-3"
            onSubmit={(event) => {
              event.preventDefault();
              void create
                .mutateAsync({ name, description, instructions })
                .then((project) => {
                  setOpen(false);
                  router.push(`/projects/${project.id}`);
                })
                .catch((error: unknown) =>
                  toast.error(
                    error instanceof Error ? error.message : "Could not create.",
                  ),
                );
            }}
          >
            <Input
              value={name}
              onChange={(event) => setName(event.target.value)}
              placeholder="Name"
              aria-label="Project name"
              required
            />
            <Textarea
              value={description}
              onChange={(event) => setDescription(event.target.value)}
              placeholder="Description"
              aria-label="Project description"
              rows={3}
            />
            <Textarea
              value={instructions}
              onChange={(event) => setInstructions(event.target.value)}
              placeholder="Instructions for chats in this project"
              aria-label="Project instructions"
              rows={4}
            />
            <div className="flex justify-end gap-2">
              <Button type="button" variant="outline" onClick={() => setOpen(false)}>
                Cancel
              </Button>
              <Button type="submit" loading={create.isPending}>
                Create
              </Button>
            </div>
          </form>
        </dialog>
      ) : null}
    </div>
  );
}

export function ProjectDetail({ projectId }: { projectId: string }) {
  const project = useProject(projectId);
  const update = useUpdateProject();
  const remove = useDeleteProject();
  const attachChat = useAttachProjectConversation();
  const attachDoc = useAttachProjectDocument();
  const createConversation = useCreateConversation();
  const conversations = useConversations();
  const titles = useConversationTitles();
  const documents = useDocuments();
  const addDocument = useAddDocument();
  const pins = usePins();
  const togglePin = useTogglePin();
  const persistence = useProjectPersistence();
  const docPersistence = useDocumentPersistence();
  const router = useRouter();
  const [instructions, setInstructions] = useState<string | null>(null);
  const [confirmDelete, setConfirmDelete] = useState(false);

  if (project.isPending) {
    return (
      <div className="p-8">
        <Skeleton className="h-10 w-64" />
      </div>
    );
  }
  if (project.error || !project.data) {
    return (
      <div className="p-8">
        <h1 className="text-xl font-semibold">Project not found</h1>
        <Link href="/projects" className="mt-3 inline-block text-sm text-primary">
          Back to projects
        </Link>
      </div>
    );
  }

  const data = project.data;
  const instructionValue = instructions ?? data.instructions;
  const loaded = flattenConversations(conversations.data);
  const chats = loaded.filter((item) => data.conversation_ids.includes(item.id));
  const knowledge = (documents.data ?? []).filter((item) =>
    data.document_ids.includes(item.id),
  );
  const pinned = isPinned(pins.data ?? [], { type: "project", id: data.id });

  return (
    <div className="mx-auto h-full w-full max-w-3xl overflow-y-auto px-4 py-8 sm:px-8">
      <div className="flex items-start justify-between gap-3">
        <div>
          <div className="mb-1 flex items-center gap-2 text-muted-foreground">
            <FolderKanban className="size-4" aria-hidden="true" />
            <Link href="/projects" className="text-sm hover:underline">
              Projects
            </Link>
          </div>
          <h1 className="text-2xl font-semibold tracking-[-0.02em]">{data.name}</h1>
          {data.description ? (
            <p className="mt-2 text-sm text-muted-foreground">{data.description}</p>
          ) : null}
          <DeviceHint persistence={persistence} />
        </div>
        <div className="flex gap-2">
          <Button
            type="button"
            variant="outline"
            size="sm"
            onClick={() =>
              void togglePin.mutateAsync({ type: "project", id: data.id })
            }
          >
            {pinned ? "Unpin" : "Pin"}
          </Button>
          <Button
            type="button"
            variant="ghost"
            size="sm"
            className="text-danger"
            onClick={() => setConfirmDelete(true)}
          >
            <Trash2 className="size-4" aria-hidden="true" />
          </Button>
        </div>
      </div>

      <section className="mt-8">
        <h2 className="text-sm font-semibold">Instructions</h2>
        <Textarea
          className="mt-2"
          rows={5}
          value={instructionValue}
          onChange={(event) => setInstructions(event.target.value)}
          aria-label="Project instructions"
        />
        <Button
          type="button"
          size="sm"
          className="mt-2"
          disabled={instructionValue === data.instructions}
          onClick={() =>
            void update
              .mutateAsync({ id: data.id, draft: { instructions: instructionValue } })
              .then(() => toast.success("Instructions saved."))
          }
        >
          Save instructions
        </Button>
      </section>

      <section className="mt-8">
        <div className="flex items-center justify-between">
          <h2 className="text-sm font-semibold">Knowledge</h2>
          <DeviceHint persistence={docPersistence} />
        </div>
        <div className="mt-2 flex flex-wrap gap-2">
          <label className="inline-flex cursor-pointer items-center rounded-md border border-border px-3 py-1.5 text-sm hover:bg-hover">
            Upload
            <input
              type="file"
              className="sr-only"
              onChange={(event) => {
                const file = event.target.files?.[0];
                if (!file) return;
                void addDocument
                  .mutateAsync({
                    name: file.name,
                    mime: file.type || "application/octet-stream",
                    size: file.size,
                  })
                  .then((doc) =>
                    attachDoc.mutateAsync({
                      projectId: data.id,
                      documentId: doc.id,
                    }),
                  );
              }}
            />
          </label>
          {(documents.data ?? [])
            .filter((doc) => !data.document_ids.includes(doc.id))
            .map((doc) => (
              <Button
                key={doc.id}
                type="button"
                variant="outline"
                size="sm"
                onClick={() =>
                  void attachDoc.mutateAsync({
                    projectId: data.id,
                    documentId: doc.id,
                  })
                }
              >
                Attach {doc.name}
              </Button>
            ))}
        </div>
        {knowledge.length === 0 ? (
          <p className="mt-3 text-sm text-muted-foreground">No documents yet.</p>
        ) : (
          <ul className="mt-3 space-y-2">
            {knowledge.map((doc) => (
              <li
                key={doc.id}
                className="flex items-center justify-between rounded-md border border-border px-3 py-2 text-sm"
              >
                <span>{doc.name}</span>
                <Button
                  type="button"
                  variant="ghost"
                  size="sm"
                  onClick={() =>
                    void attachDoc.mutateAsync({
                      projectId: data.id,
                      documentId: doc.id,
                      remove: true,
                    })
                  }
                >
                  Remove
                </Button>
              </li>
            ))}
          </ul>
        )}
      </section>

      <section className="mt-8">
        <h2 className="text-sm font-semibold">Chats</h2>
        {chats.length === 0 ? (
          <p className="mt-3 text-sm text-muted-foreground">
            No chats in this project yet.
          </p>
        ) : (
          <ul className="mt-3 space-y-1">
            {chats.map((conversation) => (
              <li key={conversation.id}>
                <Link
                  href={`/app/c/${conversation.id}`}
                  className="block rounded-md px-2 py-2 text-sm hover:bg-hover"
                >
                  {displayTitle(conversation.id, conversation.title, titles.data)}
                </Link>
              </li>
            ))}
          </ul>
        )}
        <div className="mt-4">
          <Composer
            sending={createConversation.isPending}
            centered
            onSend={async ({ message }) => {
              const conversation = await createConversation.mutateAsync(
                message.slice(0, 80) || data.name,
              );
              await attachChat.mutateAsync({
                projectId: data.id,
                conversationId: conversation.id,
              });
              const params = new URLSearchParams();
              if (message) params.set("prompt", message);
              router.push(
                `/app/c/${encodeURIComponent(conversation.id)}?${params.toString()}`,
              );
              return true;
            }}
          />
        </div>
      </section>

      <ConfirmDialog
        open={confirmDelete}
        onOpenChange={setConfirmDelete}
        title="Delete this project?"
        description="Chats are not deleted. Only the project grouping on this device is removed."
        confirmLabel="Delete project"
        loading={remove.isPending}
        onConfirm={async () => {
          await remove.mutateAsync(data.id);
          router.push("/projects");
        }}
      />
    </div>
  );
}
