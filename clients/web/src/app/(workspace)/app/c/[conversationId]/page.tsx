import { ConversationView } from "@/features/chat/components/conversation-view";

export default async function ConversationPage({
  params,
  searchParams,
}: {
  params: Promise<{ conversationId: string }>;
  searchParams: Promise<{ prompt?: string; expectsFile?: string }>;
}) {
  const { conversationId } = await params;
  const query = await searchParams;

  return (
    <ConversationView
      conversationId={conversationId}
      initialPrompt={query.prompt}
      expectsFile={query.expectsFile === "1"}
    />
  );
}
