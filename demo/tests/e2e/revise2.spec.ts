import { test, expect } from "@playwright/test";

test("custom avatar follows the speaker and video labels never cover the image", async ({
  page,
  browser,
}) => {
  const errors: string[] = [];
  page.on("pageerror", (e) => errors.push(e.message));
  await page.goto("/");
  const source = await page.evaluate(() => {
    const canvas = document.createElement("canvas");
    canvas.width = 180;
    canvas.height = 120;
    const ctx = canvas.getContext("2d")!;
    ctx.fillStyle = "#2763da";
    ctx.fillRect(0, 0, 180, 120);
    ctx.fillStyle = "#f5d766";
    ctx.beginPath();
    ctx.arc(90, 60, 36, 0, Math.PI * 2);
    ctx.fill();
    return canvas.toDataURL("image/png");
  });
  await page.getByLabel("アイコン画像を選択").setInputFiles({
    name: "avatar.png",
    mimeType: "image/png",
    buffer: Buffer.from(source.split(",")[1], "base64"),
  });
  const preview = page.locator(".avatar-picker img");
  await expect(preview).toBeVisible();
  expect(
    await preview.evaluate((img: HTMLImageElement) => img.naturalWidth),
  ).toBe(96);
  const avatar = await preview.getAttribute("src");
  await page.getByLabel("アイコン画像を選択").setInputFiles({
    name: "invalid.svg",
    mimeType: "image/svg+xml",
    buffer: Buffer.from("<svg/>"),
  });
  await expect(page.getByRole("alert")).toContainText("5MB以下");
  await expect(preview).toHaveAttribute("src", avatar!);
  await page.reload();
  await expect(preview).toHaveAttribute("src", avatar!);
  await page
    .getByRole("button", { name: "新規ルームを作成", exact: true })
    .click();
  await page.getByLabel("表示名", { exact: true }).fill("アイコンの参加者");
  await page.getByLabel("入力方法").selectOption("text");
  await page.getByLabel("ルームID", { exact: true }).fill("avatar-room");
  await page.getByLabel("パスワード", { exact: true }).fill("e2e-password");
  await page
    .getByRole("button", { name: "ルームを作成して参加", exact: true })
    .click();
  await page
    .getByRole("button", { name: "文字表示で参加", exact: true })
    .click();
  await expect(page.getByText("接続中", { exact: true })).toBeVisible();
  const context = await browser.newContext({
    permissions: ["camera", "microphone"],
  });
  try {
    const other = await context.newPage();
    await other.goto("/");
    await other.getByLabel("入力方法").selectOption("text");
    await other.getByLabel("ルームID", { exact: true }).fill("avatar-room");
    await other.getByLabel("パスワード", { exact: true }).fill("e2e-password");
    await other
      .getByRole("button", { name: "会話に参加", exact: true })
      .click();
    await other
      .getByRole("button", { name: "文字表示で参加", exact: true })
      .click();
    await expect(other.locator(".tile-heading img")).toHaveAttribute(
      "src",
      avatar!,
    );
    await page
      .getByLabel("文字で伝える", { exact: true })
      .fill("アイコン付きの字幕です");
    await page.getByRole("button", { name: "送信", exact: true }).click();
    await expect(other.locator(".utterance.other img")).toHaveAttribute(
      "src",
      avatar!,
    );
    await expect(page.locator(".utterance.own img")).toHaveAttribute(
      "src",
      avatar!,
    );
    await page.getByRole("button", { name: /カメラ.*OFF/ }).click();
    await expect
      .poll(() =>
        other
          .locator(".tile-video video")
          .evaluate((v: HTMLVideoElement) => v.videoWidth),
      )
      .toBeGreaterThan(0);
    for (const [width, height] of [
      [1366, 768],
      [390, 844],
      [320, 568],
    ]) {
      await page.setViewportSize({ width, height });
      await expect(
        page.getByRole("separator", {
          name: /映像と文字おこしのサイズ|Video and transcript size/,
        }),
      ).toHaveAttribute(
        "aria-orientation",
        width <= 760 ? "horizontal" : "vertical",
      );
      await page
        .getByRole("separator", {
          name: /映像と文字おこしのサイズ|Video and transcript size/,
        })
        .focus();
      await page.keyboard.press("Home");
      await expect(page.getByLabel("参加・接続の通知を読み上げる")).toHaveCount(
        0,
      );
      await expect(page.getByLabel("ショートカットを有効にする")).toHaveCount(
        0,
      );
      await expect(page.locator(".modality-label")).toHaveCount(0);
      const tile = page
        .locator(".participant-tile")
        .filter({ hasText: "アイコンの参加者" });
      const header = (await tile.locator(".tile-heading").boundingBox())!;
      const video = (await tile.locator(".tile-video").boundingBox())!;
      const footer = (await tile.locator(".tile-devices").boundingBox())!;
      expect(header.y + header.height).toBeLessThanOrEqual(video.y + 1);
      expect(video.height).toBeGreaterThan(15);
      expect(video.y + video.height).toBeLessThanOrEqual(footer.y + 1);
      await expect(tile.locator('[aria-label="マイク OFF"]')).toBeVisible();
      await expect(tile.locator('[aria-label="カメラ ON"]')).toBeVisible();
      const main = (await page.locator(".main-video").boundingBox())!;
      const mainFooter = (await page.locator(".speaker-footer").boundingBox())!;
      expect(main.y + main.height).toBeLessThanOrEqual(mainFooter.y + 1);
      expect(
        await page.evaluate(
          () =>
            document.documentElement.scrollHeight <= innerHeight &&
            document.documentElement.scrollWidth <= innerWidth,
        ),
      ).toBe(true);
      await page.screenshot({
        path: `../.cache/revise2-${width}.png`,
        fullPage: true,
      });
    }
    const recording = page.waitForEvent("download");
    await page.getByRole("button", { name: "会話終了", exact: true }).click();
    await recording;
    await other.reload();
    await other
      .getByRole("button", { name: "文字表示で参加", exact: true })
      .click();
    await expect(other.locator(".utterance.other img")).toHaveAttribute(
      "src",
      avatar!,
    );
    await other.getByRole("button", { name: "会話終了", exact: true }).click();
    await page
      .getByRole("button", { name: "アイコンを削除", exact: true })
      .click();
    await page.reload();
    await expect(page.locator(".avatar-picker img")).toHaveCount(0);
    await page.getByLabel("表示言語").selectOption("en");
    await expect(
      page.getByRole("button", { name: "Choose image", exact: true }),
    ).toBeVisible();
  } finally {
    await context.close();
  }
  expect(errors).toEqual([]);
});
