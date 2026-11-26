"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { toast } from "sonner";

import { Composer } from "@/features/chat/components/composer";
import {
  STARTER_PROMPTS,
  starterConversationTitle,
} from "@/features/chat/starters";
import { useCreateConversation } from "@/features/conversations/queries";

export function EmptyWorkspace() {
  const router = useRouter();
  const createConversation = useCreateConversation();
  const [busy, setBusy] = useState(false);

  async function startConversation({
    prompt,
    title,
    expectsFile = false,
  }: {
    prompt?: string;
    title?: string;
    expectsFile?: boolean;
  }) {
    setBusy(true);
    try {
      const conversation = await createConversation.mutateAsync(title);
      const params = new URLSearchParams();
      if (prompt) params.set("prompt", prompt);
      if (expectsFile) params.set("expectsFile", "1");
      const query = params.size ? `?${params.toString()}` : "";
      router.push(`/app/c/${encodeURIComponent(conversation.id)}${query}`);
    } catch (error) {
      setBusy(false);
      toast.error(
        error instanceof Error ? error.message : "Could not create conversation.",
      );
    }
  }

  return (
    <div className="flex h-full min-h-0 flex-col">
      <div className="flex min-h-0 flex-1 flex-col items-center justify-center px-4">
        <div className="w-full max-w-chat text-center">
          <h1 className="font-serif text-3xl font-medium tracking-[-0.03em] text-foreground sm:text-4xl">
            What do you want to work on?
          </h1>
          <p className="mx-auto mt-3 max-w-md text-sm leading-6 text-muted-foreground">
            Answers are legal information, not advice. Name a jurisdiction when
            it matters.
          </p>
          <div className="mt-8 flex flex-wrap justify-center gap-2">
            {STARTER_PROMPTS.map((starter) => (
              <button
                type="button"
                key={starter.id}
                className="rounded-full border border-border bg-surface px-3 py-1.5 text-sm text-foreground outline-none transition-colors duration-fast hover:bg-hover focus-visible:ring-2 focus-visible:ring-ring"
                disabled={createConversation.isPending || busy}
                onClick={() =>
                  startConversation({
                    prompt: starter.prompt,
                    title: starterConversationTitle(starter),
                    expectsFile: starter.expectsFile,
                  })
                }
              >
                {starter.title}
              </button>
            ))}
          </div>
        </div>
      </div>
      <Composer
        sending={createConversation.isPending || busy}
        centered
        onSend={async ({ message, files }) => {
          await startConversation({
            prompt: message,
            title: message.slice(0, 80),
            expectsFile: files.length > 0,
          });
          return false;
        }}
      />
    </div>
  );
}
