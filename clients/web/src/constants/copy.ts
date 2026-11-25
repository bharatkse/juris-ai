export interface StarterPrompt {
  id: "research" | "review" | "analyze" | "clauses" | "risks";
  title: string;
  prompt: string;
  expectsFile: boolean;
}

export const STARTER_PROMPTS: readonly StarterPrompt[] = [
  {
    id: "research",
    title: "Legal research",
    prompt: "What does the law say about …",
    expectsFile: false,
  },
  {
    id: "review",
    title: "Review contract",
    prompt: "Review this contract",
    expectsFile: true,
  },
  {
    id: "analyze",
    title: "Analyze agreement",
    prompt: "Analyze this agreement",
    expectsFile: false,
  },
  {
    id: "clauses",
    title: "Extract clauses",
    prompt: "Extract important clauses",
    expectsFile: false,
  },
  {
    id: "risks",
    title: "Identify risks",
    prompt: "Identify contractual risks",
    expectsFile: false,
  },
] as const;

export function getStarterPrompt(id: string): StarterPrompt | undefined {
  return STARTER_PROMPTS.find((starter) => starter.id === id);
}

export function starterConversationTitle(starter: StarterPrompt): string {
  return starter.title;
}

export const COPY = {
  legalDisclaimer:
    "Juris AI is a research assistant, not a lawyer. It does not create an attorney–client relationship. Verify citations against the source text before relying on them.",
  memoryOffWarning:
    "Turning memory off permanently deletes every saved fact. This cannot be undone.",
  approvalPayloadMissing:
    "The API did not persist the tool payload on this message. Approving resumes the stored agent action on the server; there is no GET /approvals/{id} to show a dry-run.",
} as const;
