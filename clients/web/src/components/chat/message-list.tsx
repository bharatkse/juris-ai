"use client";

import { useEffect, useRef, useState } from "react";
import {
  Bot,
  FileText,
  LoaderCircle,
  Square,
  TerminalSquare,
  UserRound,
} from "lucide-react";
import { useVirtualizer } from "@tanstack/react-virtual";

import { ApprovalCard } from "@/components/approvals/approval-card";
import { AssistantMarkdown } from "@/components/chat/assistant-markdown";
import { CitationChip } from "@/components/citations/citation-chip";
import { Button } from "@/components/ui/button";
import { formatFileSize } from "@/features/chat/files";
import { shouldVirtualizeMessages } from "@/features/chat/virtualization";
import type { ChatStreamProgress } from "@/lib/api/chat-stream";
import type {
  ApprovalDecision,
  ApprovalMetadata,
  AssistantAnswerDetails,
  Citation,
  ConversationEvent,
  Source,
} from "@/lib/api/types";
import { cn } from "@/lib/utils";

export interface PendingUserMessage {
  content: string;
  files: File[];
}

function lifecycleLabel(progress?: ChatStreamProgress | null): string {
  if (!progress) {
    return "Researching and drafting…";
  }
  if (progress.status === "connecting") {
    return "Connecting to Juris AI…";
  }
  const value = (progress.phase || progress.status).replaceAll("_", " ");
  return `${value.charAt(0).toUpperCase()}${value.slice(1)}`;
}

function WorkingIndicator({
  progress,
  canStop,
  onStop,
}: {
  progress?: ChatStreamProgress | null;
  canStop: boolean;
  onStop: () => void;
}) {
  const [elapsed, setElapsed] = useState(0);

  useEffect(() => {
    const started = Date.now();
    const timer = window.setInterval(
      () => setElapsed(Math.floor((Date.now() - started) / 1000)),
      1000,
    );
    return () => window.clearInterval(timer);
  }, []);

  const minutes = Math.floor(elapsed / 60);
  const seconds = String(elapsed % 60).padStart(2, "0");

  return (
    <div
      className="flex max-w-xl items-center gap-3 rounded-lg border border-line-200 bg-paper px-4 py-3 text-sm text-ink-600"
      role="status"
      aria-live="polite"
    >
      <span className="flex gap-1" aria-hidden="true">
        {[0, 1, 2].map((index) => (
          <span
            key={index}
            className="size-1.5 animate-pulse rounded-full bg-gold-600"
            style={{ animationDelay: `${index * 180}ms` }}
          />
        ))}
      </span>
      <span>{lifecycleLabel(progress)}</span>
      <span
        className="ml-auto font-mono text-xs text-ink-400"
        aria-hidden="true"
      >
        {minutes}:{seconds}
      </span>
      {canStop ? (
        <Button
          type="button"
          variant="outline"
          size="sm"
          className="border-danger-600/30 text-danger-600 hover:bg-danger-50"
          onClick={onStop}
        >
          <Square className="size-3 fill-current" aria-hidden="true" />
          Stop
        </Button>
      ) : null}
    </div>
  );
}

function StreamingAssistantDraft({ content }: { content: string }) {
  if (!content) return null;
  return (
    <div className="flex items-start gap-3">
      <span className="mt-1 hidden size-8 shrink-0 place-items-center rounded-full border border-dashed border-gold-600 bg-gold-100/40 text-gold-600 sm:grid">
        <Bot className="size-4" aria-hidden="true" />
      </span>
      <article
        className="min-w-0 max-w-[min(100%,800px)] flex-1 rounded-lg border border-dashed border-gold-600/50 bg-paper px-4 py-4 sm:px-6"
        aria-label="Juris AI draft response"
        aria-busy="true"
      >
        <p className="mb-3 text-[11px] font-semibold uppercase tracking-[0.08em] text-gold-600">
          Drafting · not final
        </p>
        <AssistantMarkdown content={content} />
      </article>
    </div>
  );
}

function AttachedFiles({ files }: { files: readonly File[] }) {
  if (!files.length) return null;
  return (
    <div className="mb-3 flex flex-wrap justify-end gap-2">
      {files.map((file) => (
        <span
          key={`${file.name}-${file.size}-${file.lastModified}`}
          className="inline-flex items-center gap-1.5 rounded-md border border-paper/20 bg-paper/10 px-2.5 py-1 text-xs text-paper"
        >
          <FileText className="size-3.5" aria-hidden="true" />
          <span className="max-w-44 truncate">{file.name}</span>
          <span className="text-paper/55">{formatFileSize(file.size)}</span>
        </span>
      ))}
    </div>
  );
}

function UserMessage({
  content,
  files = [],
  pending = false,
}: {
  content: string;
  files?: readonly File[];
  pending?: boolean;
}) {
  return (
    <div className="flex justify-end">
      <article
        className={cn(
          "max-w-[min(88%,680px)] rounded-lg bg-ink-800 px-4 py-3 text-paper",
          pending && "opacity-80",
        )}
        aria-label={pending ? "Sending message" : "Your message"}
      >
        <AttachedFiles files={files} />
        <p className="whitespace-pre-wrap text-sm leading-6">{content}</p>
        {pending ? (
          <span className="mt-2 flex items-center justify-end gap-1.5 text-[11px] text-paper/55">
            <LoaderCircle className="size-3 animate-spin" aria-hidden="true" />
            Sending
          </span>
        ) : null}
      </article>
    </div>
  );
}

function AssistantMessage({
  event,
  details,
  selectedCitation,
  approval,
  approvalPending,
  approvalError,
  onOpenCitations,
  onApprovalDecision,
}: {
  event: ConversationEvent;
  details?: AssistantAnswerDetails;
  selectedCitation?: number;
  approval?: ApprovalMetadata | null;
  approvalPending: boolean;
  approvalError?: string | null;
  onOpenCitations: (
    eventId: string,
    citations: Citation[],
    sources: Source[],
    index: number,
  ) => void;
  onApprovalDecision: (
    approvalId: string,
    decision: ApprovalDecision,
    reason?: string,
  ) => Promise<void>;
}) {
  const citations = details?.citations ?? event.metadata.citations ?? [];
  const sources = details?.sources ?? event.metadata.sources ?? [];
  const usage = details?.usage ?? event.metadata.usage;
  const agents = event.metadata.agents ?? [];
  const eventApproval = approval ?? event.metadata.approval;

  return (
    <div className="flex items-start gap-3">
      <span className="mt-1 hidden size-8 shrink-0 place-items-center rounded-full border border-line-200 bg-paper text-gold-600 sm:grid">
        <Bot className="size-4" aria-hidden="true" />
      </span>
      <article
        className="min-w-0 max-w-[min(100%,800px)] flex-1 rounded-lg border border-line-200 bg-paper px-4 py-4 sm:px-6 sm:py-5"
        aria-label="Juris AI response"
      >
        <AssistantMarkdown content={event.content} />
        {citations.length ? (
          <div className="mt-5 border-t border-line-200 pt-4">
            <p className="mb-2 text-[11px] font-semibold uppercase tracking-[0.08em] text-ink-400">
              Citations
            </p>
            <div className="flex flex-wrap gap-2">
              {citations.map((citation, index) => (
                <CitationChip
                  key={`${citation.title}-${citation.reference ?? index}`}
                  index={index}
                  title={citation.title}
                  selected={selectedCitation === index}
                  onClick={() =>
                    onOpenCitations(
                      event.id,
                      citations,
                      sources,
                      index,
                    )
                  }
                />
              ))}
            </div>
          </div>
        ) : sources.length ? (
          <Button
            type="button"
            variant="outline"
            size="sm"
            className="mt-5"
            onClick={() => onOpenCitations(event.id, [], sources, 0)}
          >
            View {sources.length} source{sources.length === 1 ? "" : "s"}
          </Button>
        ) : null}
        {eventApproval ? (
          <ApprovalCard
            approval={eventApproval}
            pending={approvalPending}
            error={approvalError}
            onDecision={(decision, reason) =>
              onApprovalDecision(
                eventApproval.approval_id,
                decision,
                reason,
              )
            }
          />
        ) : null}
        {agents.length || usage?.total_tokens ? (
          <p className="mt-4 font-sans text-[11px] text-ink-400">
            {agents.length ? agents.join(", ") : "Juris AI"}
            {usage?.latency_ms ? ` · ${(usage.latency_ms / 1000).toFixed(1)}s` : ""}
            {usage?.total_tokens ? ` · ${usage.total_tokens.toLocaleString()} tokens` : ""}
          </p>
        ) : null}
      </article>
    </div>
  );
}

function OperationalMessage({ event }: { event: ConversationEvent }) {
  const tool = event.role === "tool";
  const Icon = tool ? TerminalSquare : UserRound;
  return (
    <div className="mx-auto flex max-w-2xl items-start gap-2 rounded-md border border-line-200 bg-paper-50 px-3 py-2 text-xs leading-5 text-ink-600">
      <Icon className="mt-0.5 size-3.5 shrink-0 text-ink-400" aria-hidden="true" />
      <div>
        <span className="mr-2 font-semibold uppercase tracking-[0.06em]">
          {tool ? "Tool" : "System"}
        </span>
        <span className="whitespace-pre-wrap">{event.content}</span>
      </div>
    </div>
  );
}

export function MessageList({
  events,
  pending,
  streamProgress,
  streamActive = false,
  answerDetails,
  approvalStates,
  approvalPendingId,
  approvalError,
  selectedCitation,
  userFiles,
  hasMore = false,
  loadingMore = false,
  onLoadMore,
  onStop,
  onOpenCitations,
  onApprovalDecision,
}: {
  events: ConversationEvent[];
  pending?: PendingUserMessage;
  streamProgress?: ChatStreamProgress | null;
  streamActive?: boolean;
  answerDetails: Record<string, AssistantAnswerDetails>;
  approvalStates: Record<string, ApprovalMetadata>;
  approvalPendingId?: string;
  approvalError?: { approvalId: string; message: string } | null;
  selectedCitation?: { eventId: string; index: number };
  userFiles: Record<string, File[]>;
  hasMore?: boolean;
  loadingMore?: boolean;
  onLoadMore?: () => Promise<unknown> | void;
  onStop: () => void;
  onOpenCitations: (
    eventId: string,
    citations: Citation[],
    sources: Source[],
    index: number,
  ) => void;
  onApprovalDecision: (
    approvalId: string,
    decision: ApprovalDecision,
    reason?: string,
  ) => Promise<void>;
}) {
  const scrollRef = useRef<HTMLDivElement>(null);
  const endRef = useRef<HTMLDivElement>(null);
  const lastEventId = events.at(-1)?.id;
  const hasPendingMessage = Boolean(pending);
  const virtualized = shouldVirtualizeMessages(events.length);
  const virtualizer = useVirtualizer({
    count: events.length,
    getScrollElement: () => scrollRef.current,
    getItemKey: (index) => events[index]?.id ?? index,
    estimateSize: (index) => {
      const role = events[index]?.role;
      return role === "assistant" ? 260 : role === "user" ? 140 : 90;
    },
    overscan: 8,
    enabled: virtualized,
  });

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [
    lastEventId,
    hasPendingMessage,
    streamProgress?.draftContent.length,
  ]);

  async function loadMore() {
    const element = scrollRef.current;
    const previousHeight = element?.scrollHeight ?? 0;
    const previousTop = element?.scrollTop ?? 0;
    await onLoadMore?.();
    window.requestAnimationFrame(() => {
      if (element) {
        element.scrollTop =
          previousTop + Math.max(0, element.scrollHeight - previousHeight);
      }
    });
  }

  function messageFor(event: ConversationEvent) {
    if (event.role === "user") {
      return (
        <UserMessage content={event.content} files={userFiles[event.id]} />
      );
    }
    if (event.role !== "assistant") {
      return <OperationalMessage event={event} />;
    }
    return (
      <AssistantMessage
        event={event}
        details={answerDetails[event.id]}
        selectedCitation={
          selectedCitation?.eventId === event.id
            ? selectedCitation.index
            : undefined
        }
        approval={
          event.metadata.approval
            ? approvalStates[event.metadata.approval.approval_id]
            : undefined
        }
        approvalPending={
          approvalPendingId === event.metadata.approval?.approval_id
        }
        approvalError={
          approvalError &&
          approvalError.approvalId === event.metadata.approval?.approval_id
            ? approvalError.message
            : null
        }
        onOpenCitations={onOpenCitations}
        onApprovalDecision={onApprovalDecision}
      />
    );
  }

  return (
    <div
      ref={scrollRef}
      role="log"
      aria-label="Conversation messages"
      tabIndex={0}
      className="min-h-0 flex-1 overflow-y-auto outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-gold-600"
    >
      <div className="mx-auto flex min-h-full w-full max-w-4xl flex-col px-4 py-6 sm:px-6 sm:py-8">
        {hasMore ? (
          <Button
            type="button"
            variant="ghost"
            size="sm"
            className="mx-auto mb-6"
            disabled={loadingMore}
            onClick={() => void loadMore()}
          >
            {loadingMore ? (
              <LoaderCircle className="size-3.5 animate-spin" aria-hidden="true" />
            ) : null}
            {loadingMore ? "Loading…" : "Load more history"}
          </Button>
        ) : null}

        {!events.length && !pending ? (
          <div className="m-auto max-w-md py-16 text-center">
            <Bot className="mx-auto size-6 text-gold-600" aria-hidden="true" />
            <h2 className="mt-4 text-lg font-semibold">
              Ask the first question
            </h2>
            <p className="mt-2 text-sm leading-6 text-ink-600">
              Add context, name the jurisdiction, or attach a document for
              review.
            </p>
          </div>
        ) : (
          <>
            {virtualized ? (
              <div
                className="relative w-full"
                style={{ height: virtualizer.getTotalSize() }}
                data-virtualized="true"
              >
                {virtualizer.getVirtualItems().map((row) => (
                  <div
                    key={row.key}
                    ref={virtualizer.measureElement}
                    data-index={row.index}
                    className="absolute left-0 top-0 w-full pb-6"
                    style={{ transform: `translateY(${row.start}px)` }}
                  >
                    {messageFor(events[row.index])}
                  </div>
                ))}
              </div>
            ) : (
              <div className="mt-auto space-y-6" data-virtualized="false">
                {events.map((event) => (
                  <div key={event.id}>{messageFor(event)}</div>
                ))}
              </div>
            )}
            {pending ? (
              <div className="mt-6 space-y-6">
                <UserMessage
                  content={pending.content}
                  files={pending.files}
                  pending
                />
                <WorkingIndicator
                  progress={streamProgress}
                  canStop={streamActive}
                  onStop={onStop}
                />
                <StreamingAssistantDraft
                  content={streamProgress?.draftContent ?? ""}
                />
              </div>
            ) : null}
          </>
        )}
        <div ref={endRef} aria-hidden="true" />
      </div>
    </div>
  );
}
