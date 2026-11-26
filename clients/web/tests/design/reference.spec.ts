import { mkdirSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

import { expect, test, type Page, type Route } from "@playwright/test";

const referenceDirectory = fileURLToPath(new URL("./reference", import.meta.url));
const fixedNow = new Date("2026-09-15T12:00:00Z").getTime();

const user = {
  id: "design-user",
  email: "researcher@example.com",
  first_name: "Amit",
  last_name: "Vishvakarma",
  gender: "other",
  phone_number: "+91 98765 43210",
  date_of_birth: "1990-01-02",
  created_at: "2026-09-01T09:00:00Z",
  updated_at: "2026-09-15T10:00:00Z",
};

const conversation = {
  id: "design-thread",
  user_id: user.id,
  title: "Article 21 research",
  is_active: true,
  memory_disabled: false,
  created_at: "2026-09-15T09:00:00Z",
  updated_at: "2026-09-15T10:00:00Z",
};

const longConversation = {
  ...conversation,
  id: "design-long-thread",
  title:
    "Whether a delayed departmental inquiry under Article 311 can proceed after superannuation",
  updated_at: "2026-09-15T09:30:00Z",
};

const userEvent = {
  id: "design-user-event",
  conversation_id: conversation.id,
  parent_event_id: null,
  role: "user",
  content: "Explain Article 21 of the Constitution of India.",
  metadata: {},
  created_at: "2026-09-15T10:00:00Z",
};

const assistantEvent = {
  id: "design-assistant-event",
  conversation_id: conversation.id,
  parent_event_id: userEvent.id,
  role: "assistant",
  content:
    "Article 21 protects **life and personal liberty**. The Supreme Court requires any procedure limiting those rights to be fair, just, and reasonable.",
  metadata: {
    agents: ["legal"],
    citations: [
      {
        title: "Constitution of India",
        source: "Article 21",
        reference: "Art. 21",
        page: null,
        snippet:
          "No person shall be deprived of his life or personal liberty except according to procedure established by law.",
      },
      {
        title: "Maneka Gandhi v. Union of India",
        source: "Supreme Court of India",
        reference: "AIR 1978 SC 597",
        page: 12,
        snippet:
          "The procedure prescribed by law must be fair, just and reasonable.",
      },
    ],
    sources: [
      {
        title: "Constitution of India",
        uri: "https://legislative.gov.in/constitution-of-india/",
        type: "statute",
      },
      {
        title: "Maneka Gandhi v. Union of India",
        uri: "https://indiankanoon.org/doc/1766147/",
        type: "case",
      },
    ],
    usage: {
      prompt_tokens: 310,
      completion_tokens: 532,
      total_tokens: 842,
      latency_ms: 1200,
    },
  },
  created_at: "2026-09-15T10:00:01Z",
};

const approvalEvent = {
  ...assistantEvent,
  id: "design-approval-event",
  content:
    "I drafted the external action and need your approval before it runs.",
  metadata: {
    agents: ["legal"],
    approval: {
      approval_id: "design-approval",
      status: "waiting",
      expires_at: "2026-09-15T12:15:00Z",
      requested_by: user.id,
    },
  },
};

type Scenario = "empty" | "thread" | "hitl" | "quota";

function envelope(data: unknown) {
  return JSON.stringify({ success: true, data, metadata: {} });
}

async function fulfillEnvelope(route: Route, data: unknown) {
  await route.fulfill({
    status: 200,
    contentType: "application/json",
    body: envelope(data),
  });
}

function conversationPage() {
  return {
    items: [conversation, longConversation],
    pagination: {
      offset: 0,
      limit: 20,
      total: 2,
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

async function installMocks(
  page: Page,
  scenario: { current: Scenario },
) {
  await page.addInitScript((timestamp) => {
    Date.now = () => timestamp;
  }, fixedNow);
  await page.route("**/api/auth/me", (route) => fulfillEnvelope(route, user));
  await page.route("**/api/backend/**", async (route) => {
    const request = route.request();
    const url = new URL(request.url());
    const backendPath = url.pathname.replace("/api/backend", "");

    if (backendPath === "/conversations") {
      await fulfillEnvelope(
        route,
        scenario.current === "empty"
          ? {
              items: [],
              pagination: {
                offset: 0,
                limit: 20,
                total: 0,
                has_more: false,
              },
            }
          : conversationPage(),
      );
      return;
    }
    if (backendPath === `/conversations/${conversation.id}`) {
      await fulfillEnvelope(route, conversation);
      return;
    }
    if (backendPath === `/conversations/${longConversation.id}`) {
      await fulfillEnvelope(route, longConversation);
      return;
    }
    if (backendPath === `/conversations/${longConversation.id}/messages`) {
      await fulfillEnvelope(route, eventPage([]));
      return;
    }
    if (backendPath === `/conversations/${conversation.id}/messages`) {
      const events =
        scenario.current === "hitl"
          ? [userEvent, approvalEvent]
          : [userEvent, assistantEvent];
      await fulfillEnvelope(route, eventPage(events));
      return;
    }
    if (backendPath === "/health") {
      await fulfillEnvelope(route, {
        status: "ok",
        service: "juris-ai",
        version: "design",
      });
      return;
    }
    if (backendPath === "/memory/settings") {
      await fulfillEnvelope(route, { enabled: true });
      return;
    }
    if (backendPath === "/memory/items") {
      await fulfillEnvelope(route, {
        items: [],
        pagination: { offset: 0, limit: 20, total: 0, has_more: false },
      });
      return;
    }
    if (
      backendPath === "/chat/stream" &&
      scenario.current === "quota" &&
      request.method() === "POST"
    ) {
      await route.fulfill({
        status: 429,
        contentType: "application/json",
        headers: {
          "retry-after": "30",
          "x-request-id": "design-quota-request",
        },
        body: JSON.stringify({
          success: false,
          error: {
            code: "RATE_LIMIT_EXCEEDED",
            message: "Too many requests this minute. Wait and try again.",
          },
          metadata: { request_id: "design-quota-request" },
        }),
      });
      return;
    }

    await route.fulfill({
      status: 404,
      contentType: "application/json",
      body: JSON.stringify({
        success: false,
        error: { code: "NOT_FOUND", message: "Unhandled design mock." },
      }),
    });
  });
}

async function capture(page: Page, filename: string) {
  mkdirSync(referenceDirectory, { recursive: true });
  await page.addStyleTag({
    content:
      "*,*::before,*::after{animation:none!important;transition:none!important;caret-color:transparent!important}nextjs-portal{display:none!important}",
  });
  await page.evaluate(() => document.fonts.ready);
  await page.screenshot({
    path: path.join(referenceDirectory, filename),
    fullPage: false,
    animations: "disabled",
  });
}

async function authenticate(page: Page) {
  await page.context().addCookies([
    {
      name: "juris_access_token",
      value: "design-only-token",
      domain: "127.0.0.1",
      path: "/",
      httpOnly: true,
      sameSite: "Lax",
    },
  ]);
}

test("capture versioned design references", async ({ page }, testInfo) => {
  const scenario: { current: Scenario } = { current: "empty" };
  const prefix = testInfo.project.name.replace("design-", "");
  const wide = prefix !== "360";
  await installMocks(page, scenario);

  async function applyTheme(theme: "light" | "dark") {
    await page.addInitScript((value) => {
      window.localStorage.setItem("juris-theme", value);
    }, theme);
    await page.evaluate((value) => {
      window.localStorage.setItem("juris-theme", value);
      document.documentElement.classList.remove("light", "dark");
      document.documentElement.classList.add(value);
      document.documentElement.style.colorScheme = value;
    }, theme);
  }

  await page.goto("/");
  await expect(
    page.getByRole("heading", {
      name: "Legal research with sources you can open.",
    }),
  ).toBeVisible();
  await capture(page, `${prefix}-landing.png`);

  await page.goto("/login");
  await expect(page.getByRole("heading", { name: "Sign in" })).toBeVisible();
  await capture(page, `${prefix}-login.png`);

  await authenticate(page);

  for (const theme of ["light", "dark"] as const) {
    await applyTheme(theme);

    scenario.current = "empty";
    await page.goto("/app");
    await expect(
      page.getByRole("heading", { name: "What do you want to work on?" }),
    ).toBeVisible();
    if (theme === "light") {
      const background = await page.locator("body").evaluate((el) =>
        getComputedStyle(el).backgroundColor,
      );
      expect(background).toBe("rgb(255, 255, 255)");
    }
    await capture(page, `${prefix}-${theme}-chat-empty.png`);
    await capture(page, `${prefix}-${theme}-sidebar-expanded.png`);

    if (!wide) {
      await page.getByRole("button", { name: "Open sidebar" }).click();
      await expect(
        page.getByRole("complementary", { name: "Workspace navigation" }),
      ).toBeVisible();
      await capture(page, `${prefix}-${theme}-sidebar-drawer.png`);
      await page.getByRole("button", { name: "Close sidebar" }).click();
    }

    scenario.current = "thread";
    await page.goto(`/app/c/${conversation.id}`);
    await expect(page.getByLabel("Juris AI response")).toBeVisible();
    await capture(page, `${prefix}-${theme}-chat-messages.png`);
    if (!wide) {
      await page.getByRole("button", { name: "Open sidebar" }).click();
    }
    await page
      .getByRole("button", {
        name: /Actions for Whether a delayed departmental inquiry/u,
      })
      .click();
    await expect(page.getByRole("menu")).toBeVisible();
    await capture(page, `${prefix}-${theme}-sidebar-row-menu.png`);
    await page.keyboard.press("Escape");

    if (wide) {
      await page.getByRole("button", { name: "Collapse sidebar" }).click();
      await capture(page, `${prefix}-${theme}-sidebar-collapsed.png`);
      await page
        .getByRole("complementary", { name: "Workspace navigation" })
        .getByRole("button", { name: "Expand sidebar" })
        .click();
    }

    await page
      .getByRole("button", { name: "Open citation 1: Constitution of India" })
      .click();
    await expect(page.getByRole("dialog", { name: "Sources" })).toBeVisible();
    await capture(page, `${prefix}-${theme}-side-panel.png`);
    await page
      .getByRole("dialog", { name: "Sources" })
      .getByRole("button", { name: "Close panel" })
      .click();

    await page.goto("/settings/profile");
    await expect(page.getByRole("heading", { name: "Profile" })).toBeVisible();
    await capture(page, `${prefix}-${theme}-settings.png`);

    await page.goto("/settings/memory");
    await expect(
      page.getByRole("heading", { name: "Memory", exact: true }),
    ).toBeVisible();
    await capture(page, `${prefix}-${theme}-memory.png`);

    await page.goto("/projects");
    await expect(page.getByRole("heading", { name: "Projects" })).toBeVisible();
    await capture(page, `${prefix}-${theme}-projects.png`);

    await page.goto("/app");
    await page.getByRole("button", { name: /Amit Vishvakarma/iu }).click();
    await expect(page.getByRole("menu", { name: "Account" })).toBeVisible();
    await capture(page, `${prefix}-${theme}-profile-menu.png`);
  }

  scenario.current = "hitl";
  await applyTheme("light");
  await page.goto(`/app/c/${conversation.id}`);
  await expect(
    page.getByRole("heading", { name: "Approval required" }),
  ).toBeVisible();
  await capture(page, `${prefix}-hitl-waiting.png`);
});
