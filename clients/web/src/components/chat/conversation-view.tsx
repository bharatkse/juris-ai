"use client";

import Link from "next/link";
import { useCallback, useState } from "react";
import { useRouter } from "next/navigation";
import { ArrowLeft, MessageSquareOff, RefreshCw } from "lucide-react";

import { Composer } from "@/components/chat/composer";
import { MessageList } from "@/components/chat/message-list";
import { ChatErrorBanner } from "@/components/chat/quota-banner";
import { CitationDrawer } from "@/components/citations/citation-drawer";
import { Button, buttonVariants } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { useApprovalDecision } from "@/features/approvals/queries";
import { useSendMessage, type SendMessageInput } from "@/features/chat/queries";
import {
  flattenConversationEvents,
  mergeConversationEvents,
  useConversation,
  useConversationAnswerDetails,
  useConversationApprovalStates,
  useConversationHistory,
} from "@/features/conversations/queries";
import { ApiError } from "@/lib/api/errors";
import type {
  ApprovalDecision,
  Citation,
  ConversationEvent,
  Source,
} from "@/lib/api/types";

function ConversationLoading() {
  return (
    <div className="flex min-h-0 flex-1 flex-col overflow-hidden">
      <div className="mx-auto w-full max-w-4xl flex-1 space-y-7 px-4 py-8 sm:px-6">
        <div className="flex justify-end">
          <Skeleton className="h-20 w-2/3 max-w-lg" />
        </div>
        <Skeleton className="h-44 w-5/6 max-w-2xl" />
        <div className="flex justify-end">
          <Skeleton className="h-16 w-1/2 max-w-md" />
        </div>
      </div>
      <div className="border-t border-line-200 p-4">
        <Skeleton className="mx-auto h-28 max-w-4xl" />
      </div>
    </div>
  );
}

function ConversationError({
  notFound,
  onRetry,
}: {
  notFound: boolean;
  onRetry: () => void;
}) {
  return (
    <div className="flex min-h-full items-center justify-center px-5 py-12">
      <div className="max-w-md text-center">
        <span className="mx-auto grid size-12 place-items-center rounded-full border border-line-200 bg-paper">
          <MessageSquareOff className="size-5 text-gold-600" aria-hidden="true" />
        </span>
        <h1 className="mt-5 text-xl font-semibold">
          {notFound ? "Conversation not found" : "Could not load conversation"}
        </h1>
        <p className="mt-2 text-sm leading-6 text-ink-600">
          {notFound
            ? "This conversation was archived or does not exist."
            : "The conversation could not be loaded. Check your connection and try again."}
        </p>
        <div className="mt-6 flex justify-center gap-3">
          <Link href="/app" className={buttonVariants({ variant: "outline" })}>
            <ArrowLeft className="size-4" aria-hidden="true" />
            Workspace
          </Link>
          {!notFound ? (
            <Button type="button" onClick={onRetry}>
              <RefreshCw className="size-4" aria-hidden="true" />
              Retry
            </Button>
          ) : null}
        </div>
      </div>
    </div>
  );
}

interface CitationPanelState {
  eventId: string;
  citations: Citation[];
  sources: Source[];
  selectedIndex: number;
}

export function ConversationView({
  conversationId,
  initialPrompt,
  expectsFile,
}: {
  conversationId: string;
  initialPrompt?: string;
  expectsFile?: boolean;
}) {
  const router = useRouter();
  const conversation = useConversation(conversationId);
  const history = useConversationHistory(conversationId);
  const answerDetails = useConversationAnswerDetails(conversationId);
  const approvalStates = useConversationApprovalStates(conversationId);
  const send = useSendMessage(conversationId);
  const approvalDecision = useApprovalDecision(conversationId);
  const [userFiles, setUserFiles] = useState<Record<string, File[]>>({});
  const [recentEvents, setRecentEvents] = useState<ConversationEvent[]>([]);
  const [citationPanel, setCitationPanel] =
    useState<CitationPanelState | null>(null);
  const [retryBlocked, setRetryBlocked] = useState(false);
  const [composerResetVersion, setComposerResetVersion] = useState(0);
  const [cancelledNotice, setCancelledNotice] = useState<string | null>(null);
  const openCitations = useCallback(
    (
      eventId: string,
      citations: Citation[],
      sources: Source[],
      index: number,
    ) => {
      setCitationPanel({
        eventId,
        citations,
        sources,
        selectedIndex: index,
      });
    },
    [],
  );
  const closeCitations = useCallback(() => setCitationPanel(null), []);

  if (conversation.isPending || history.isPending) {
    return <ConversationLoading />;
  }

  const queryError =
    (!conversation.data ? conversation.error : null) ??
    (!history.data ? history.error : null);
  if (queryError) {
    const notFound =
      queryError instanceof ApiError && queryError.httpStatus === 404;
    return (
      <ConversationError
        notFound={notFound}
        onRetry={() => {
          void conversation.refetch();
          void history.refetch();
        }}
      />
    );
  }

  const events = mergeConversationEvents(
    flattenConversationEvents(history.data),
    recentEvents,
  );
  const pending = send.isPending
    ? {
        content: send.variables.message,
        files: send.variables.files,
      }
    : undefined;
  const approvalError =
    approvalDecision.error instanceof ApiError && approvalDecision.variables
      ? {
          approvalId: approvalDecision.variables.approvalId,
          message:
            approvalDecision.error.httpStatus === 403
              ? "You are not authorized to decide this approval."
              : [409, 410, 422].includes(
                    approvalDecision.error.httpStatus,
                  )
                ? "This approval can no longer be processed. Refresh the conversation."
                : approvalDecision.error.requestId
                  ? `${approvalDecision.error.message} Request ID ${approvalDecision.error.requestId}.`
                  : approvalDecision.error.message,
        }
      : approvalDecision.error && approvalDecision.variables
        ? {
            approvalId: approvalDecision.variables.approvalId,
            message: "Could not process this approval. Please try again.",
          }
        : null;

  async function sendMessage(input: SendMessageInput): Promise<boolean> {
    setCancelledNotice(null);
    const result = await send.mutateAsync(input);
    if (result.kind === "cancelled") {
      setCancelledNotice(
        "Generation stopped. Your message and attachments are ready to resend.",
      );
      return false;
    }

    const now = Date.now();
    const userEvent =
      result.kind === "sync"
        ? result.response.user_event
        : {
            id: result.complete.metadata.user_event_id,
            conversation_id: result.complete.metadata.conversation_id,
            parent_event_id: null,
            role: "user" as const,
            content: input.message,
            metadata: {
              attachments: input.files.map((file) => ({
                name: file.name,
                size: file.size,
                type: file.type,
              })),
            },
            created_at: new Date(now).toISOString(),
          };
    const assistantEvent =
      result.kind === "sync"
        ? result.response.assistant_event
        : {
            id: result.complete.metadata.assistant_event_id,
            conversation_id: result.complete.metadata.conversation_id,
            parent_event_id: result.complete.metadata.user_event_id,
            role: "assistant" as const,
            content: result.complete.content,
            metadata: {
              ...result.complete.metadata.response_metadata,
              approval:
                result.complete.metadata.approval ??
                result.complete.metadata.response_metadata.approval,
              citations: result.complete.metadata.citations,
              sources: result.complete.metadata.sources,
              usage: result.complete.metadata.usage,
            },
            created_at: new Date(now + 1).toISOString(),
          };

    setRecentEvents((current) =>
      mergeConversationEvents(current, [userEvent, assistantEvent]),
    );
    if (input.files.length) {
      setUserFiles((current) => ({
        ...current,
        [userEvent.id]: input.files,
      }));
    }
    setComposerResetVersion((current) => current + 1);
    router.replace(`/app/c/${encodeURIComponent(conversationId)}`, {
      scroll: false,
    });
    return true;
  }

  async function decide(
    approvalId: string,
    decision: ApprovalDecision,
    reason?: string,
  ) {
    try {
      const response = await approvalDecision.mutateAsync({
        approvalId,
        decision,
        decisionReason: reason,
      });
      if (response.resumed_event) {
        setRecentEvents((current) =>
          mergeConversationEvents(current, [response.resumed_event as ConversationEvent]),
        );
      }
    } catch {
      // The inline approval card renders the normalized mutation error.
    }
  }

  return (
    <div className="flex h-full min-h-0 overflow-hidden">
      <div className="flex min-w-0 flex-1 flex-col overflow-hidden">
        <MessageList
          events={events}
          pending={pending}
          streamProgress={send.streamProgress}
          streamActive={send.streamActive}
          answerDetails={answerDetails.data}
          approvalStates={approvalStates.data}
          approvalPendingId={
            approvalDecision.isPending
              ? approvalDecision.variables.approvalId
              : undefined
          }
          approvalError={approvalError}
          selectedCitation={
            citationPanel
              ? {
                  eventId: citationPanel.eventId,
                  index: citationPanel.selectedIndex,
                }
              : undefined
          }
          userFiles={userFiles}
          hasMore={history.hasNextPage}
          loadingMore={history.isFetchingNextPage}
          onLoadMore={() => history.fetchNextPage()}
          onStop={send.stop}
          onOpenCitations={openCitations}
          onApprovalDecision={decide}
        />
        {send.error instanceof ApiError && !send.isPending ? (
          <div className="shrink-0 bg-paper-50 px-3 pt-2 sm:px-6">
            <div className="mx-auto max-w-4xl">
              <ChatErrorBanner
                error={send.error}
                retrying={send.isPending}
                onBlockedChange={setRetryBlocked}
                onRetry={() => {
                  if (send.variables) void sendMessage(send.variables);
                }}
              />
            </div>
          </div>
        ) : null}
        <Composer
          initialPrompt={initialPrompt}
          expectsFile={expectsFile}
          sending={send.isPending}
          sendBlocked={retryBlocked}
          resetVersion={composerResetVersion}
          statusMessage={cancelledNotice}
          onSend={sendMessage}
        />
      </div>
      {citationPanel ? (
        <CitationDrawer
          citations={citationPanel.citations}
          sources={citationPanel.sources}
          selectedIndex={citationPanel.selectedIndex}
          onSelect={(selectedIndex) =>
            setCitationPanel((current) =>
              current ? { ...current, selectedIndex } : current,
            )
          }
          onClose={closeCitations}
        />
      ) : null}
    </div>
  );
}
