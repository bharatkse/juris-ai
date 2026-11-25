"use client";

import {
  useEffect,
  useRef,
  useState,
  type DragEvent,
  type FormEvent,
} from "react";
import { ArrowUp, FileText, Paperclip, Square, X } from "lucide-react";

import { LegalDisclaimer } from "@/components/legal-disclaimer";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
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
  onStop,
  centered = false,
}: {
  initialPrompt?: string;
  expectsFile?: boolean;
  sending: boolean;
  sendBlocked?: boolean;
  resetVersion?: number;
  statusMessage?: string | null;
  onSend: (input: SendMessageInput) => Promise<boolean | void>;
  onStop?: () => void;
  centered?: boolean;
}) {
  const [message, setMessage] = useState(initialPrompt);
  const [files, setFiles] = useState<File[]>([]);
  const [errors, setErrors] = useState<string[]>([]);
  const [dragging, setDragging] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);
  const formRef = useRef<HTMLFormElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

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

  useEffect(() => {
    const el = textareaRef.current;
    if (!el) return;
    el.style.height = "auto";
    const max = 8 * 24;
    el.style.height = `${Math.min(el.scrollHeight, max)}px`;
  }, [message]);

  function addFiles(incoming: readonly File[]) {
    const result = addValidatedFiles(files, incoming);
    setFiles(result.files);
    setErrors(result.errors);
  }

  async function submit(event?: FormEvent<HTMLFormElement>) {
    event?.preventDefault();
    if (sendBlocked || sending) return;
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
    <div
      className={cn(
        "shrink-0 bg-background px-3 pb-[max(0.75rem,env(safe-area-inset-bottom))] pt-2 sm:px-4",
        centered && "pt-4",
      )}
    >
      <form
        ref={formRef}
        className="mx-auto w-full max-w-chat"
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
            "rounded-xl border border-border bg-surface p-3 shadow-sm transition-colors duration-fast focus-within:border-primary/50",
            dragging && "border-primary bg-hover ring-2 ring-ring/20",
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
            <div className="flex flex-wrap gap-2 pb-2">
              {files.map((file, index) => (
                <span
                  key={`${file.name}-${file.size}-${file.lastModified}`}
                  className="inline-flex max-w-full items-center gap-2 rounded-md border border-border bg-hover px-2.5 py-1.5 text-xs text-muted-foreground"
                >
                  <FileText className="size-3.5 shrink-0 text-primary" aria-hidden="true" />
                  <span className="max-w-48 truncate">{file.name}</span>
                  <span className="shrink-0">{formatFileSize(file.size)}</span>
                  <button
                    type="button"
                    className="rounded-sm p-0.5 text-muted-foreground outline-none hover:bg-muted hover:text-danger focus-visible:ring-2 focus-visible:ring-ring"
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
            <div className="pointer-events-none flex min-h-[76px] items-center justify-center text-sm font-medium text-muted-foreground">
              Drop files to attach
            </div>
          ) : (
            <textarea
              ref={textareaRef}
              value={message}
              onChange={(event) => setMessage(event.target.value)}
              onKeyDown={(event) => {
                if (event.key === "Enter" && !event.shiftKey) {
                  event.preventDefault();
                  void submit();
                }
              }}
              maxLength={MAX_CHAT_MESSAGE_LENGTH}
              rows={1}
              disabled={sending}
              className="max-h-[192px] min-h-[44px] w-full resize-none overflow-y-auto bg-transparent px-1 py-2 text-sm leading-6 text-foreground outline-none placeholder:text-muted-foreground"
              placeholder="Ask a legal question or attach a contract…"
              aria-label="Legal question"
            />
          )}

          <div className="flex items-center justify-between gap-3 pt-1">
            <div className="flex min-w-0 items-center gap-1">
              <input
                ref={inputRef}
                id="composer-files"
                type="file"
                multiple
                accept={CHAT_FILE_ACCEPT}
                className="sr-only"
                tabIndex={-1}
                aria-label="Attach documents"
                onChange={(event) => {
                  addFiles(Array.from(event.target.files ?? []));
                  event.target.value = "";
                }}
              />
              <Button
                type="button"
                variant="ghost"
                size="icon"
                className="size-8"
                disabled={sending || files.length >= MAX_CHAT_FILES}
                aria-label="Attach files"
                onClick={() => inputRef.current?.click()}
              >
                <Paperclip className="size-4" aria-hidden="true" />
              </Button>
            </div>
            {sending && onStop ? (
              <Button
                type="button"
                size="icon"
                className="size-8 rounded-full"
                aria-label="Stop"
                onClick={onStop}
              >
                <Square className="size-3 fill-current" aria-hidden="true" />
              </Button>
            ) : (
              <Button
                type="submit"
                size="icon"
                className="size-8 rounded-full"
                loading={sending}
                disabled={!message.trim() || sendBlocked}
                aria-label="Send"
              >
                <ArrowUp className="size-4" aria-hidden="true" />
              </Button>
            )}
          </div>
        </div>
        <LegalDisclaimer className="mx-auto mt-2 max-w-xl justify-center text-center" />
      </form>
    </div>
  );
}
