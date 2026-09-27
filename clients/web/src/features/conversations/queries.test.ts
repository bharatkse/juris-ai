import { describe, expect, it } from "vitest";

import {
  filterConversations,
  flattenConversationEvents,
  flattenConversations,
  formatRelativeTime,
  mergeConversationEvents,
} from "@/features/conversations/queries";
import {
  buildConversationListUrl,
  normalizeConversationEvent,
} from "@/lib/api/conversations";
import type { Conversation, ConversationEvent, Paginated } from "@/lib/api/types";

const conversation: Conversation = {
  id: "conv_1",
  user_id: "user_1",
  title: "Article 21 research",
  is_active: true,
  created_at: "2026-09-15T10:00:00Z",
  updated_at: "2026-09-15T10:00:00Z",
};

describe("conversation API helpers", () => {
  it("builds a stable paginated URL", () => {
    expect(buildConversationListUrl(20, 10)).toBe(
      "/api/backend/conversations?offset=20&limit=10",
    );
  });

  it("normalizes either metadata serialization name", () => {
    const event = normalizeConversationEvent({
      id: "evt_1",
      conversation_id: "conv_1",
      parent_event_id: null,
      role: "assistant",
      content: "Answer",
      event_metadata: { agents: ["legal"] },
      created_at: "2026-09-15T10:00:00Z",
    });

    expect(event.metadata).toEqual({ agents: ["legal"] });
  });
});

describe("conversation query helpers", () => {
  it("flattens and filters loaded conversation pages", () => {
    const data = {
      pages: [
        {
          items: [conversation],
          pagination: { offset: 0, limit: 20, total: 1, has_more: false },
        },
      ] satisfies Paginated<Conversation>[],
      pageParams: [0],
    };

    expect(flattenConversations(data)).toEqual([conversation]);
    expect(filterConversations([conversation], "article 21")).toEqual([
      conversation,
    ]);
    expect(filterConversations([conversation], "contract")).toEqual([]);
  });

  it("sorts event pages chronologically", () => {
    const event = (id: string, created_at: string): ConversationEvent => ({
      id,
      conversation_id: "conv_1",
      parent_event_id: null,
      role: "user",
      content: id,
      metadata: {},
      created_at,
    });
    const data = {
      pages: [
        {
          items: [
            event("later", "2026-09-15T10:01:00Z"),
            event("earlier", "2026-09-15T10:00:00Z"),
          ],
          pagination: { offset: 0, limit: 100, total: 2, has_more: false },
        },
      ] satisfies Paginated<ConversationEvent>[],
      pageParams: [0],
    };

    expect(flattenConversationEvents(data).map(({ id }) => id)).toEqual([
      "earlier",
      "later",
    ]);
    expect(
      mergeConversationEvents(flattenConversationEvents(data), [
        event("newest", "2026-09-15T10:02:00Z"),
        event("later", "2026-09-15T10:01:00Z"),
      ]).map(({ id }) => id),
    ).toEqual(["earlier", "later", "newest"]);
  });

  it("formats concise relative timestamps", () => {
    const now = new Date("2026-09-15T10:00:00Z").getTime();
    expect(formatRelativeTime("2026-09-15T09:58:00Z", now)).toBe("2m");
    expect(formatRelativeTime("2026-09-14T10:00:00Z", now)).toBe("1d");
  });
});
