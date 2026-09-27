"use client";

import {
  useEffect,
  useRef,
  useState,
  type DragEvent,
  type FormEvent,
} from "react";
import { FileText, Paperclip, Send, X } from "lucide-react";

import { LegalDisclaimer } from "@/components/legal-disclaimer";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import {
  addValidatedFiles,
  CHAT_FILE_ACCEPT,
  formatFileSize,
  MAX_CHAT_FILES,
  MAX_CHAT_MESSAGE_LENGTH,
  validateChatMessage,
} from "@/features/chat/files";
import type { SendMessageInput } from "@/features/chat/queries";
import { cn } from "@/lib/utils";

export function Composer({
  initialPrompt = "",
  expectsFile = false,
  sending,
  sendBlocked = false,
  resetVersion = 0,
  statusMessage,
  onSend,
}: {
  initialPrompt?: string;
  expectsFile?: boolean;
  sending: boolean;
  sendBlocked?: boolean;
  resetVersion?: number;
  statusMessage?: string | null;
  onSend: (input: SendMessageInput) => Promise<boolean | void>;
}) {
  const [message, setMessage] = useState(initialPrompt);
  const [files, setFiles] = useState<File[]>([]);
  const [errors, setErrors] = useState<string[]>([]);
  const [dragging, setDragging] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);
  const formRef = useRef<HTMLFormElement>(null);

  useEffect(() => {
    setMessage(initialPrompt);
  }, [initialPrompt]);

  useEffect(() => {
    if (resetVersion > 0) {
      setMessage("");
      setFiles([]);
      setErrors([]);
    }
  }, [resetVersion]);

  function addFiles(incoming: readonly File[]) {
    const result = addValidatedFiles(files, incoming);
    setFiles(result.files);
    setErrors(result.errors);
  }

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (sendBlocked) return;
    const messageError = validateChatMessage(message);
    if (messageError) {
      setErrors([messageError]);
      return;
    }
    if (expectsFile && files.length === 0) {
      setErrors(["Attach a contract before sending this review prompt."]);
      return;
    }

    setErrors([]);
    try {
      const sent = await onSend({ message: message.trim(), files });
      if (sent === false) return;
      setMessage("");
      setFiles([]);
    } catch {
      // The mutation error is rendered by the parent; preserve the draft.
    }
  }

  function handleDrop(event: DragEvent<HTMLDivElement>) {
    event.preventDefault();
    setDragging(false);
    if (sending) return;
    addFiles(Array.from(event.dataTransfer.files));
  }

  return (
    <div className="shrink-0 border-t border-line-200 bg-paper-50/95 px-3 pb-3 pt-3 backdrop-blur sm:px-6 sm:pb-4">
      <form
        ref={formRef}
        className="mx-auto max-w-4xl"
        onSubmit={submit}
        noValidate
      >
        {errors.length ? (
          <Alert tone="error" className="mb-2">
            <AlertDescription>
              {errors.map((error) => (
                  <span className="block" key={error}>
                    {error}
                  </span>
                ))}
            </AlertDescription>
          </Alert>
        ) : statusMessage ? (
          <Alert tone="info" className="mb-2 py-2">
            <AlertDescription>{statusMessage}</AlertDescription>
          </Alert>
        ) : expectsFile && files.length === 0 ? (
          <Alert tone="warning" className="mb-2 py-2">
            <AlertDescription>
              This contract-review starter expects a file attachment.
            </AlertDescription>
          </Alert>
        ) : null}

        <div
          className={cn(
            "rounded-lg border border-line-200 bg-paper p-2 transition-colors focus-within:border-gold-600 focus-within:ring-2 focus-within:ring-gold-600/15",
            dragging && "border-gold-600 bg-gold-100/30 ring-2 ring-gold-600/20",
          )}
          onDragEnter={(event) => {
            event.preventDefault();
            if (!sending) setDragging(true);
          }}
          onDragOver={(event) => event.preventDefault()}
          onDragLeave={(event) => {
            if (!event.currentTarget.contains(event.relatedTarget as Node)) {
              setDragging(false);
            }
          }}
          onDrop={handleDrop}
        >
          {files.length ? (
            <div className="flex flex-wrap gap-2 px-1 pb-2">
              {files.map((file, index) => (
                <span
                  key={`${file.name}-${file.size}-${file.lastModified}`}
                  className="inline-flex max-w-full items-center gap-2 rounded-md border border-line-200 bg-paper-50 px-2.5 py-1.5 text-xs text-ink-600"
                >
                  <FileText className="size-3.5 shrink-0 text-gold-600" aria-hidden="true" />
                  <span className="max-w-48 truncate">{file.name}</span>
                  <span className="shrink-0 text-ink-400">
                    {formatFileSize(file.size)}
                  </span>
                  <button
                    type="button"
                    className="rounded-sm p-0.5 text-ink-400 outline-none hover:bg-line-200/60 hover:text-danger-600 focus-visible:ring-2 focus-visible:ring-gold-600"
                    aria-label={`Remove ${file.name}`}
                    disabled={sending}
                    onClick={() =>
                      setFiles((current) =>
                        current.filter((_, fileIndex) => fileIndex !== index),
                      )
                    }
                  >
                    <X className="size-3.5" aria-hidden="true" />
                  </button>
                </span>
              ))}
            </div>
          ) : null}

          {dragging ? (
            <div className="pointer-events-none flex min-h-[76px] items-center justify-center text-sm font-medium text-ink-600">
              Drop files to attach
            </div>
          ) : (
            <Textarea
              value={message}
              onChange={(event) => setMessage(event.target.value)}
              onKeyDown={(event) => {
                if ((event.metaKey || event.ctrlKey) && event.key === "Enter") {
                  event.preventDefault();
                  formRef.current?.requestSubmit();
                }
              }}
              maxLength={MAX_CHAT_MESSAGE_LENGTH}
              rows={2}
              disabled={sending}
              className="min-h-[72px] resize-none border-0 bg-transparent px-2 py-2 focus-visible:ring-0"
              placeholder="Ask a legal question or attach a contract…"
              aria-label="Legal question"
            />
          )}

          <div className="flex items-center justify-between gap-3 px-1 pb-1">
            <div className="flex min-w-0 items-center gap-2">
              <input
                ref={inputRef}
                type="file"
                multiple
                accept={CHAT_FILE_ACCEPT}
                className="sr-only"
                tabIndex={-1}
                onChange={(event) => {
                  addFiles(Array.from(event.target.files ?? []));
                  event.target.value = "";
                }}
              />
              <Button
                type="button"
                variant="ghost"
                size="sm"
                disabled={sending || files.length >= MAX_CHAT_FILES}
                onClick={() => inputRef.current?.click()}
              >
                <Paperclip className="size-4" aria-hidden="true" />
                <span className="hidden sm:inline">Attach</span>
              </Button>
              <span className="truncate text-[11px] text-ink-400">
                {message.length.toLocaleString()} /{" "}
                {MAX_CHAT_MESSAGE_LENGTH.toLocaleString()}
              </span>
            </div>
            <Button
              type="submit"
              size="sm"
              loading={sending}
              disabled={!message.trim() || sendBlocked}
            >
              <Send className="size-4" aria-hidden="true" />
              {sending ? "Working…" : "Send"}
            </Button>
          </div>
        </div>
        <div className="mt-2 flex flex-col items-center justify-between gap-1 sm:flex-row">
          <p className="text-[11px] text-ink-400">
            Cmd/Ctrl + Enter to send · PDF, DOCX, TXT, MD, HTML · 20 MB each
          </p>
          <LegalDisclaimer className="max-w-xl text-center sm:text-right" />
        </div>
      </form>
    </div>
  );
}
