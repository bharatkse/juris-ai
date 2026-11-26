import { expect, test, type Page, type Route } from "@playwright/test";

const user = {
  id: "user_e2e",
  email: "researcher@example.com",
  first_name: "Legal",
  last_name: "Researcher",
  gender: null,
  phone_number: null,
  date_of_birth: null,
  created_at: "2026-09-15T10:00:00Z",
  updated_at: "2026-09-15T10:00:00Z",
};

const conversation = {
  id: "conv_e2e",
  user_id: user.id,
  title: "Article 21 research",
  is_active: true,
  memory_disabled: false,
  created_at: "2026-09-15T10:00:00Z",
  updated_at: "2026-09-15T10:00:00Z",
};

function envelope(data: unknown) {
  return JSON.stringify({ success: true, data, metadata: {} });
}

async function fulfillJson(route: Route, data: unknown, status = 200) {
  await route.fulfill({
    status,
    contentType: "application/json",
    body: envelope(data),
  });
}

async function authenticate(page: Page) {
  await page.context().addCookies([
    {
      name: "juris_access_token",
      value: "e2e-access-token",
      domain: "127.0.0.1",
      path: "/",
      httpOnly: true,
      sameSite: "Lax",
    },
  ]);
  await page.route("**/api/auth/me", (route) => fulfillJson(route, user));
}

function conversationPage(items: typeof conversation[] = []) {
  return {
    items,
    pagination: {
      offset: 0,
      limit: 20,
      total: items.length,
      has_more: false,
    },
  };
}

function eventPage(items: unknown[]) {
  return {
    items,
    pagination: {
      offset: 0,
      limit: 100,
      total: items.length,
      has_more: false,
    },
  };
}

test("login reaches the authenticated workspace", async ({ page }) => {
  await page.route("**/api/auth/login", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      headers: {
        "set-cookie":
          "juris_access_token=e2e-access-token; Path=/; HttpOnly; SameSite=Lax",
      },
      body: envelope({ authenticated: true }),
    });
  });
  await page.route("**/api/auth/me", (route) => fulfillJson(route, user));
  await page.route("**/api/backend/conversations**", (route) =>
    fulfillJson(route, conversationPage()),
  );

  await page.goto("/login");
  await page.getByLabel("Email").fill(user.email);
  await page.getByLabel("Password").fill("correct-horse-battery-staple");
  await page.getByRole("button", { name: "Sign in" }).click();

  await expect(page).toHaveURL(/\/app$/u, { timeout: 15_000 });
  await expect(
    page.getByRole("heading", { name: "What do you want to work on?" }),
  ).toBeVisible();
});

test("creates a thread, sends chat, and opens real citations", async ({
  page,
}) => {
  await authenticate(page);
  let created = false;
  let events: unknown[] = [];

  await page.route("**/api/backend/**", async (route) => {
    const request = route.request();
    const url = new URL(request.url());
    const path = url.pathname.replace("/api/backend", "");

    if (path === "/conversations" && request.method() === "POST") {
      created = true;
      await fulfillJson(route, conversation, 201);
      return;
    }
    if (path === "/conversations" && request.method() === "GET") {
      await fulfillJson(route, conversationPage(created ? [conversation] : []));
      return;
    }
    if (
      path === `/conversations/${conversation.id}` &&
      request.method() === "PATCH"
    ) {
      await fulfillJson(route, {
        ...conversation,
        title: "Fundamental rights research",
      });
      return;
    }
    if (path === `/conversations/${conversation.id}`) {
      await fulfillJson(route, conversation);
      return;
    }
    if (path === `/conversations/${conversation.id}/messages`) {
      await fulfillJson(route, eventPage(events));
      return;
    }
    if (path === "/chat/stream" && request.method() === "POST") {
      const userEvent = {
        id: "event_user",
        conversation_id: conversation.id,
        parent_event_id: null,
        role: "user",
        content: "Explain Article 21",
        metadata: {},
        created_at: "2026-09-15T10:01:00Z",
      };
      const assistantEvent = {
        id: "event_assistant",
        conversation_id: conversation.id,
        parent_event_id: userEvent.id,
        role: "assistant",
        content: "**Article 21** protects life and personal liberty.",
        metadata: { agents: ["legal"] },
        created_at: "2026-09-15T10:01:01Z",
      };
      events = [userEvent, assistantEvent];
      const lifecycle = {
        content: "",
        is_final: false,
        metadata: {
          status: "working",
          phase: "planning_and_research",
        },
      };
      const completion = {
        content: assistantEvent.content,
        is_final: true,
        metadata: {
          status: "complete",
          citations: [
            {
              title: "Constitution of India",
              source: "Article 21",
              reference: "Art. 21",
              page: 12,
              snippet: "No person shall be deprived of his life or personal liberty.",
            },
          ],
          sources: [
            {
              title: "Constitution of India",
              uri: "https://legislative.gov.in/constitution-of-india/",
              type: "statute",
            },
          ],
          usage: {
            prompt_tokens: 20,
            completion_tokens: 30,
            total_tokens: 50,
          },
          response_metadata: { agents: ["legal"], workflow: "research" },
          conversation_id: conversation.id,
          user_event_id: userEvent.id,
          assistant_event_id: assistantEvent.id,
        },
      };
      await route.fulfill({
        status: 200,
        contentType: "text/event-stream",
        headers: { "x-request-id": "req-e2e-stream" },
        body: [
          `event: message\ndata: ${JSON.stringify(lifecycle)}\n\n`,
          `event: complete\ndata: ${JSON.stringify(completion)}\n\n`,
        ].join(""),
      });
      return;
    }

    await route.fulfill({ status: 404, body: "Unhandled mock route" });
  });

  await page.goto("/app");
  await page.getByRole("button", { name: "New chat" }).click();
  await expect(page).toHaveURL(new RegExp(`/app/c/${conversation.id}$`, "u"));

  await page.getByLabel("Legal question").fill("Explain Article 21");
  await page.getByRole("button", { name: "Send" }).click();

  const citation = page.getByRole("button", {
    name: "Open citation 1: Constitution of India",
  });
  await expect(citation).toBeVisible();
  await citation.click();

  await expect(page.getByRole("dialog", { name: "Sources" })).toBeVisible();
  await expect(
    page.getByText(
      "No person shall be deprived of his life or personal liberty.",
    ),
  ).toBeVisible();
  await expect(page.getByRole("link", { name: "Open source" })).toHaveAttribute(
    "rel",
    "noopener noreferrer",
  );

  await page.keyboard.press("Escape");
  await expect(page.getByRole("dialog", { name: "Sources" })).toHaveCount(0);
  await expect(citation).toBeFocused();
});

test("approves an inline action and appends the resumed event", async ({
  page,
}) => {
  await authenticate(page);
  const approvalEvent = {
    id: "event_approval",
    conversation_id: conversation.id,
    parent_event_id: null,
    role: "assistant",
    content: "I need your approval before taking this action.",
    metadata: {
      agents: ["legal"],
      approval: {
        approval_id: "approval_e2e",
        status: "waiting",
        expires_at: "2099-01-01T00:00:00Z",
      },
    },
    created_at: "2026-09-15T10:02:00Z",
  };
  const resumedEvent = {
    id: "event_resumed",
    conversation_id: conversation.id,
    parent_event_id: approvalEvent.id,
    role: "assistant",
    content: "The approved action completed.",
    metadata: {},
    created_at: "2026-09-15T10:02:02Z",
  };

  let decided = false;
  await page.route("**/api/backend/**", async (route) => {
    const request = route.request();
    const url = new URL(request.url());
    const path = url.pathname.replace("/api/backend", "");

    if (path === "/conversations") {
      await fulfillJson(route, conversationPage([conversation]));
      return;
    }
    if (path === `/conversations/${conversation.id}`) {
      await fulfillJson(route, conversation);
      return;
    }
    if (path === `/conversations/${conversation.id}/messages`) {
      await fulfillJson(
        route,
        eventPage(
          decided
            ? [
                {
                  ...approvalEvent,
                  metadata: {
                    ...approvalEvent.metadata,
                    approval: {
                      approval_id: "approval_e2e",
                      status: "approved",
                      expires_at: "2099-01-01T00:00:00Z",
                    },
                  },
                },
                resumedEvent,
              ]
            : [approvalEvent],
        ),
      );
      return;
    }
    if (path === "/approvals/approval_e2e" && request.method() === "POST") {
      decided = true;
      await fulfillJson(route, {
        approval_id: "approval_e2e",
        agent_action_id: "action_e2e",
        requested_by: user.id,
        status: "approved",
        created_at: "2026-09-15T10:02:00Z",
        expires_at: "2099-01-01T00:00:00Z",
        resume_status: "resumed",
      });
      return;
    }

    await route.fulfill({ status: 404, body: "Unhandled mock route" });
  });

  await page.goto(`/app/c/${conversation.id}`);
  await expect(
    page.getByRole("heading", { name: "Approval required" }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Approve" }).click();

  await expect(page.getByText("Approved", { exact: true })).toBeVisible();
  await expect(page.getByText("The approved action completed.")).toBeVisible();
});

test("shows distinct rate-limit and token-quota banners", async ({ page }) => {
  await authenticate(page);
  let chatCalls = 0;

  await page.route("**/api/backend/**", async (route) => {
    const request = route.request();
    const url = new URL(request.url());
    const path = url.pathname.replace("/api/backend", "");

    if (path === "/conversations") {
      await fulfillJson(route, conversationPage([conversation]));
      return;
    }
    if (path === `/conversations/${conversation.id}`) {
      await fulfillJson(route, conversation);
      return;
    }
    if (path === `/conversations/${conversation.id}/messages`) {
      await fulfillJson(route, eventPage([]));
      return;
    }
    if (path === "/chat/stream" && request.method() === "POST") {
      chatCalls += 1;
      const code =
        chatCalls === 1 ? "RATE_LIMIT_EXCEEDED" : "TOKEN_QUOTA_EXCEEDED";
      const message =
        chatCalls === 1
          ? "Too many requests this minute. Wait and try again."
          : "Daily token quota reached. Try again tomorrow.";
      await route.fulfill({
        status: 429,
        contentType: "application/json",
        body: JSON.stringify({
          success: false,
          error: { code, message },
          metadata: { request_id: `req-quota-${chatCalls}` },
        }),
      });
      return;
    }

    await route.fulfill({ status: 404, body: "Unhandled mock route" });
  });

  await page.goto(`/app/c/${conversation.id}`);
  await page.getByLabel("Legal question").fill("Explain Article 21");
  await page.getByRole("button", { name: "Send" }).click();

  await expect(
    page.getByText("Too many requests this minute. Wait and try again."),
  ).toBeVisible();

  await page.getByRole("button", { name: "Send" }).click();
  await expect(
    page.getByText("Daily token quota reached. Try again tomorrow."),
  ).toBeVisible();
});

test("shows permission denied for another user's conversation", async ({
  page,
}) => {
  await authenticate(page);
  await page.route("**/api/backend/**", async (route) => {
    const request = route.request();
    const url = new URL(request.url());
    const path = url.pathname.replace("/api/backend", "");
    if (path === "/conversations" && request.method() === "GET") {
      await fulfillJson(route, conversationPage([]));
      return;
    }
    await route.fulfill({
      status: 403,
      contentType: "application/json",
      body: JSON.stringify({
        success: false,
        error: {
          code: "FORBIDDEN",
          message: "Not permitted to access this conversation.",
        },
        metadata: {},
      }),
    });
  });

  await page.goto(`/app/c/${conversation.id}`);
  await expect(
    page.getByRole("heading", { name: "Could not load conversation" }),
  ).toBeVisible();
});

test("memory settings load from the API", async ({ page }) => {
  await authenticate(page);
  await page.route("**/api/backend/**", async (route) => {
    const request = route.request();
    const url = new URL(request.url());
    const path = url.pathname.replace("/api/backend", "");
    if (path === "/conversations") {
      await fulfillJson(route, conversationPage([]));
      return;
    }
    if (path === "/memory/settings") {
      await fulfillJson(route, {
        enabled: true,
        consent_updated_at: "2026-09-15T10:00:00Z",
      });
      return;
    }
    if (path === "/memory/items") {
      await fulfillJson(route, {
        items: [
          {
            id: "mem_1",
            kind: "preference",
            content: "Prefers Indian Constitution citations",
            status: "active",
            confidence: 0.9,
            last_used_at: "2026-09-15T10:00:00Z",
            created_at: "2026-09-15T09:00:00Z",
          },
        ],
        pagination: { offset: 0, limit: 20, total: 1, has_more: false },
      });
      return;
    }
    await route.fulfill({ status: 404, body: "Unhandled mock route" });
  });

  await page.goto("/settings/memory");
  await expect(page.getByText("Prefers Indian Constitution citations")).toBeVisible();
});
