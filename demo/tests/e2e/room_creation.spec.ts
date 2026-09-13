import { test, expect, type Page } from "@playwright/test";

async function credentials(page: Page, room: string, password: string) {
  await page.getByLabel("入力方法").selectOption("text");
  await page.getByLabel("ルームID", { exact: true }).fill(room);
  await page.getByLabel("パスワード", { exact: true }).fill(password);
}

async function enter(page: Page) {
  await expect(
    page.getByRole("heading", { name: "カメラと音声を確認" }),
  ).toBeVisible();
  await page.getByRole("button", { name: "文字表示で参加" }).click();
  await expect(page.getByText("接続中", { exact: true })).toBeVisible();
}

test("create via 127.0.0.1, reject duplicates, join via localhost and converse", async ({
  page,
  browser,
}) => {
  const room = `created-${Date.now()}`;
  await page.goto("http://127.0.0.1:5173");
  await page
    .getByRole("button", { name: "新規ルームを作成", exact: true })
    .click();
  await credentials(page, room, "e2e-new-password");
  await page
    .getByRole("button", { name: "ルームを作成して参加", exact: true })
    .click();
  await enter(page);
  await expect(page).toHaveURL(new RegExp(`/rooms/${room}`));

  const context = await browser.newContext();
  try {
    const other = await context.newPage();
    await other.goto("/");
    await other
      .getByRole("button", { name: "新規ルームを作成", exact: true })
      .click();
    await credentials(other, room, "wrong-password");
    await other
      .getByRole("button", { name: "ルームを作成して参加", exact: true })
      .click();
    await expect(other.getByRole("alert")).toContainText("既に使われています");
    await other
      .getByRole("button", { name: "既存ルームに参加", exact: true })
      .click();
    await other
      .getByRole("button", { name: "会話に参加", exact: true })
      .click();
    await expect(other.getByRole("alert")).toContainText(
      "ルームIDまたはパスワード",
    );
    await other
      .getByLabel("パスワード", { exact: true })
      .fill("e2e-new-password");
    await other
      .getByRole("button", { name: "会話に参加", exact: true })
      .click();
    await enter(other);
    await page
      .getByRole("textbox", { name: "文字で伝える" })
      .fill("画面で作成したルームに参加できました");
    await page.getByRole("button", { name: "送信", exact: true }).click();
    await expect(other.locator(".utterance")).toContainText(
      "画面で作成したルームに参加できました",
    );
    await other.getByRole("button", { name: "会話終了" }).click();
    await page.getByRole("button", { name: "会話終了" }).click();
  } finally {
    await context.close();
  }
});

test("creation survives a failed join and can retry joining without recreating", async ({
  page,
}) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/");
  await page
    .getByRole("button", { name: "新規ルームを作成", exact: true })
    .click();
  await credentials(page, "retry-created-room", "e2e-new-password");
  await page.route(
    "**/api/rooms/retry-created-room/join",
    (route) => route.abort(),
    { times: 1 },
  );
  await page
    .getByRole("button", { name: "ルームを作成して参加", exact: true })
    .click();
  await expect(page.getByRole("status")).toContainText(
    "ルーム「retry-created-room」を作成しました",
  );
  await expect(page.getByRole("alert")).toBeVisible();
  await expect(
    page.getByRole("button", { name: "既存ルームに参加", exact: true }),
  ).toHaveAttribute("aria-pressed", "true");
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBe(true);
  await page.screenshot({
    path: "../.cache/room-creation-mobile.png",
    fullPage: true,
  });
  await page.getByRole("button", { name: "会話に参加", exact: true }).click();
  await enter(page);
  await page.getByRole("button", { name: "会話終了" }).click();
});
