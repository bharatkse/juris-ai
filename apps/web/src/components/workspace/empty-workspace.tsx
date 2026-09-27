"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import {
  BookOpenText,
  FileSearch,
  ListTree,
  Paperclip,
  Scale,
  Send,
  ShieldAlert,
} from "lucide-react";
import { toast } from "sonner";

import { LegalDisclaimer } from "@/components/legal-disclaimer";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import {
  STARTER_PROMPTS,
  starterConversationTitle,
  type StarterPrompt,
} from "@/features/chat/starters";
import { useCreateConversation } from "@/features/conversations/queries";
import { cn } from "@/lib/utils";

const starterIcons = {
  research: BookOpenText,
  review: FileSearch,
  analyze: Scale,
  clauses: ListTree,
  risks: ShieldAlert,
} satisfies Record<StarterPrompt["id"], typeof Scale>;

export function EmptyWorkspace() {
  const [message, setMessage] = useState("");
  const router = useRouter();
  const createConversation = useCreateConversation();

  async function startConversation({
    prompt,
    title,
    expectsFile = false,
  }: {
    prompt?: string;
    title?: string;
    expectsFile?: boolean;
  }) {
    try {
      const conversation = await createConversation.mutateAsync(title);
      const params = new URLSearchParams();
      if (prompt) params.set("prompt", prompt);
      if (expectsFile) params.set("expectsFile", "1");
      const query = params.size ? `?${params.toString()}` : "";
      router.push(`/app/c/${encodeURIComponent(conversation.id)}${query}`);
    } catch (error) {
      toast.error(
        error instanceof Error ? error.message : "Could not create conversation.",
      );
    }
  }

  return (
    <div className="flex min-h-full flex-col">
      <section className="mx-auto flex w-full max-w-6xl flex-1 flex-col justify-center px-5 py-12 sm:px-8 sm:py-16">
        <div className="mx-auto w-full max-w-4xl text-center">
          <span className="mx-auto grid size-12 place-items-center rounded-full border border-gold-600/30 bg-gold-100/60">
            <Scale className="size-5 text-gold-600" aria-hidden="true" />
          </span>
          <h1 className="mt-6 text-2xl font-semibold tracking-[-0.025em] sm:text-3xl">
            What do you want to work on?
          </h1>
          <p className="mx-auto mt-3 max-w-2xl text-sm leading-6 text-ink-600">
            Answers are legal information, not advice. Name a jurisdiction when
            it matters; Indian-law materials are a useful starting point.
          </p>
        </div>

        <div className="mt-10 grid gap-3 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-5">
          {STARTER_PROMPTS.map((starter) => {
            const Icon = starterIcons[starter.id];
            return (
            <button
              type="button"
              key={starter.id}
              className={cn(
                "group min-h-36 rounded-lg border border-line-200 bg-paper p-4 text-left outline-none transition-colors hover:border-gold-600/60 hover:bg-gold-100/20 focus-visible:ring-2 focus-visible:ring-gold-600 focus-visible:ring-offset-2",
              )}
              disabled={createConversation.isPending}
              onClick={() =>
                startConversation({
                  prompt: starter.prompt,
                  title: starterConversationTitle(starter),
                  expectsFile: starter.expectsFile,
                })
              }
            >
              <span className="grid size-9 place-items-center rounded-md border border-line-200 text-gold-600 transition-colors group-hover:border-gold-600/35">
                <Icon className="size-4" aria-hidden="true" />
              </span>
              <span className="mt-5 block text-sm font-semibold text-ink-950">
                {starter.title}
              </span>
              <span className="mt-1 block text-xs leading-5 text-ink-600">
                {starter.prompt}
              </span>
              {starter.expectsFile ? (
                <span className="mt-2 flex items-center gap-1 text-[11px] text-gold-600">
                  <Paperclip className="size-3" aria-hidden="true" />
                  File required
                </span>
              ) : null}
            </button>
            );
          })}
        </div>
      </section>

      <div className="sticky bottom-0 border-t border-line-200 bg-paper-50/95 px-4 pb-4 pt-3 backdrop-blur sm:px-6 sm:pb-5">
        <form
          className="mx-auto max-w-4xl"
          onSubmit={async (event) => {
            event.preventDefault();
            const prompt = message.trim();
            if (!prompt) return;
            await startConversation({
              prompt,
              title: prompt.slice(0, 80),
            });
          }}
        >
          <div className="rounded-lg border border-line-200 bg-paper p-2 focus-within:border-gold-600 focus-within:ring-2 focus-within:ring-gold-600/15">
            <Textarea
              value={message}
              onChange={(event) => setMessage(event.target.value)}
              maxLength={10_000}
              rows={2}
              className="min-h-[68px] resize-none border-0 bg-transparent px-2 py-2 focus-visible:ring-0"
              placeholder="Ask a legal question or attach a contract…"
              aria-label="Legal question"
            />
            <div className="flex items-center justify-between gap-3 px-1 pb-1">
              <div className="flex items-center gap-2">
                <Button
                  type="button"
                  variant="ghost"
                  size="sm"
                  disabled={createConversation.isPending}
                  onClick={() =>
                    startConversation({
                      title: "Contract review",
                      expectsFile: true,
                    })
                  }
                >
                  <Paperclip className="size-4" aria-hidden="true" />
                  <span className="hidden sm:inline">Attach</span>
                </Button>
                <span className="text-[11px] text-ink-400">
                  {message.length.toLocaleString()} / 10,000
                </span>
              </div>
              <Button
                type="submit"
                size="sm"
                loading={createConversation.isPending}
                disabled={!message.trim()}
              >
                <Send className="size-4" aria-hidden="true" />
                {createConversation.isPending ? "Creating…" : "Send"}
              </Button>
            </div>
          </div>
          <LegalDisclaimer className="mx-auto mt-2 max-w-2xl justify-center text-center" />
        </form>
      </div>
    </div>
  );
}
