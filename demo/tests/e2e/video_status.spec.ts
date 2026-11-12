import { test, expect, type Page } from "@playwright/test";

async function join(page: Page, blockVideo: boolean) {
  if (blockVideo)
    await page.addInitScript(() => {
      // Relay-only without a TURN server gathers no candidates, so this camera never arrives.
      const Original = window.RTCPeerConnection;
      window.RTCPeerConnection = class extends Original {
        constructor(config?: RTCConfiguration) {
          super({ ...config, iceServers: [], iceTransportPolicy: "relay" });
        }
      };
    });
  await page.goto("/");
  await page.getByRole("button", { name: "既存ルームに参加" }).click();
  await page.getByLabel("入力方法").selectOption("text");
  await page.getByLabel("ルームID", { exact: true }).fill("status-room");
  await page.getByLabel("パスワード", { exact: true }).fill("e2e-password");
  await page.getByRole("button", { name: "会話に参加" }).click();
  await page.getByRole("button", { name: "文字表示で参加" }).click();
  await expect(page.getByText("接続中", { exact: true })).toBeVisible();
}

test("a camera that is on but not arriving is not reported as off", async ({
  browser,
}) => {
  const pages: Page[] = [];
  try {
    for (const blockVideo of [false, true]) {
      const context = await browser.newContext({
        permissions: ["camera", "microphone"],
      });
      const page = await context.newPage();
      pages.push(page);
      await join(page, blockVideo);
    }
    const [viewer, blocked] = pages;
    const tile = viewer
      .locator(".participant-tile")
      .filter({ hasNotText: "自分" });
    // Camera off: the honest message is still "camera off".
    await expect(viewer.locator(".tile-placeholder small")).toHaveCount(0);
    await blocked.getByRole("button", { name: "カメラ OFF" }).click();
    await expect(tile.getByText("映像を接続しています")).toBeVisible();
    await expect(viewer.getByText("カメラはOFFです")).toHaveCount(0);
  } finally {
    for (const page of pages) {
      await page
        .getByRole("button", { name: "会話終了" })
        .click({ timeout: 2000 })
        .catch(() => {});
      await page.context().close();
    }
  }
});
