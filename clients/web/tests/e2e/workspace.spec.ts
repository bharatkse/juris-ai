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

function conversationPage(items: typeof conversation[] = [conversation]) {
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

test.beforeEach(async ({ page }) => {
  await authenticate(page);
  await page.route("**/api/backend/**", async (route) => {
    const request = route.request();
    const url = new URL(request.url());
    const path = url.pathname.replace("/api/backend", "");
    if (path === "/conversations") {
      await fulfillJson(route, conversationPage());
      return;
    }
    if (path === `/conversations/${conversation.id}`) {
      await fulfillJson(route, conversation);
      return;
    }
    if (path === `/conversations/${conversation.id}/messages`) {
      await fulfillJson(route, {
        items: [],
        pagination: { offset: 0, limit: 100, total: 0, has_more: false },
      });
      return;
    }
    if (path === "/memory/settings") {
      await fulfillJson(route, {
        enabled: true,
        consent_updated_at: "2026-09-15T10:00:00Z",
      });
      return;
    }
    if (path === "/memory/items" && request.method() === "GET") {
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
    if (path === "/memory/items/mem_1") {
      await fulfillJson(route, {
        id: "mem_1",
        kind: "preference",
        content: "Prefers Indian Constitution citations",
        status: "active",
        confidence: 0.9,
        last_used_at: "2026-09-15T10:00:00Z",
        created_at: "2026-09-15T09:00:00Z",
      });
      return;
    }
    if (path.startsWith("/memory/items") && request.method() === "POST") {
      await fulfillJson(
        route,
        {
          id: "mem_new",
          kind: "note",
          content: "Remember to cite Article 14",
          status: "active",
          confidence: 1,
          last_used_at: "2026-09-15T10:00:00Z",
          created_at: "2026-09-15T10:00:00Z",
        },
        201,
      );
      return;
    }
    if (path === "/memory/items/mem_1" && request.method() === "DELETE") {
      await route.fulfill({ status: 204, body: "" });
      return;
    }
    if (path === "/health") {
      await fulfillJson(route, { status: "ok", service: "juris-ai" });
      return;
    }
    await route.fulfill({ status: 404, body: "Unhandled mock route" });
  });
});

test("profile menu opens settings and hides admin", async ({ page }) => {
  await page.goto("/app");
  await expect(page.getByRole("link", { name: "Settings" })).toHaveCount(0);
  await expect(page.getByRole("link", { name: "Memory" })).toHaveCount(0);
  await page.getByRole("button", { name: /legal researcher/iu }).click();
  const menu = page.getByRole("menu", { name: "Account" });
  await expect(menu).toBeVisible();
  await expect(menu.getByRole("menuitem", { name: "Admin" })).toHaveCount(0);
  await menu.getByRole("menuitem", { name: "Settings" }).click();
  await expect(page).toHaveURL(/\/settings\/general/u);
  await expect(page.getByRole("link", { name: "Back to chat" })).toBeVisible();
});

test("memory master-detail", async ({ page }) => {
  await page.goto("/settings/memory");
  await expect(
    page.getByRole("heading", { name: "Memory", exact: true }),
  ).toBeVisible();
  await page.getByRole("link", { name: /Prefers Indian Constitution/u }).click();
  await expect(page).toHaveURL(/\/settings\/memory\/mem_1/u);
  await expect(page.getByRole("button", { name: "Copy" })).toBeVisible();
});

test("projects create flow", async ({ page }) => {
  await page.goto("/projects");
  await page.getByRole("button", { name: "New project" }).click();
  await page.getByLabel("Project name").fill("Constitution workspace");
  await page.getByRole("button", { name: "Create" }).click();
  await expect(page).toHaveURL(/\/projects\//u);
  await expect(
    page.getByRole("heading", { name: "Constitution workspace" }),
  ).toBeVisible();
  await expect(page.getByText("Saved on this device")).toBeVisible();
});

test("pin from conversation menu", async ({ page }) => {
  await page.goto("/app");
  await page.getByRole("button", { name: /Actions for Article 21/u }).click();
  await page.getByRole("menuitem", { name: "Pin" }).click();
  await expect(page.getByRole("navigation", { name: "Pinned" }).or(page.getByLabel("Pinned"))).toBeVisible();
});
