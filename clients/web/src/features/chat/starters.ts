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
