import { test, expect } from "@playwright/test";
import { readFile } from "node:fs/promises";

test("English settings persist and meeting controls fit desktop and mobile screens", async ({
  page,
}) => {
  const downloads: string[] = [];
  page.on("download", (d) => downloads.push(d.suggestedFilename()));
  await page.goto("/");
  await page.getByLabel("表示言語").selectOption("en");
  await page.reload();
  await expect(
    page.getByRole("heading", { name: "Kotoba Link", exact: true }),
  ).toBeVisible();
  await page
    .getByRole("button", { name: "Create a room", exact: true })
    .click();
  await page.getByLabel("Display name", { exact: true }).fill("Alex");
  await page.getByLabel("Input method", { exact: true }).selectOption("text");
  await page.getByLabel("Room ID", { exact: true }).fill("revise-layout");
  await page.getByLabel("Password", { exact: true }).fill("e2e-password");
  await page
    .getByRole("button", { name: "Create and join", exact: true })
    .click();
  await page.getByRole("button", { name: "Change name", exact: true }).click();
  await page.getByLabel("Display name", { exact: true }).fill("Alex Example");
  await page.getByRole("button", { name: "Save name", exact: true }).click();
  await page
    .getByRole("button", { name: "Join with text", exact: true })
    .click();
  await expect(page.getByText("Connected", { exact: true })).toBeVisible();
  await page
    .getByLabel("Type a message", { exact: true })
    .fill("Hello! This is a conversation in English.");
  await page.getByRole("button", { name: "Send", exact: true }).click();
  for (const [width, height] of [
    [1366, 768],
    [1280, 720],
    [1024, 768],
    [390, 844],
    [320, 568],
  ]) {
    await page.setViewportSize({ width, height });
    const separator = page.getByRole("separator", {
      name: /映像と文字おこしのサイズ|Video and transcript size/,
    });
    await expect(separator).toHaveAttribute(
      "aria-orientation",
      width <= 760 ? "horizontal" : "vertical",
    );
    await separator.focus();
    await page.keyboard.press("Home");
    await expect
      .poll(
        async () => (await page.locator(".video-column").boundingBox())!.height,
      )
      .toBeGreaterThanOrEqual(119);
    for (const selector of [
      ".composer",
      ".conversation-controls",
      ".meeting-utilities",
      ".panel-divider",
    ]) {
      for (const element of await page.locator(selector).all()) {
        const box = await element.boundingBox();
        expect(box!.y).toBeGreaterThanOrEqual(0);
        expect(box!.y + box!.height).toBeLessThanOrEqual(height + 1);
        expect(box!.x + box!.width).toBeLessThanOrEqual(width + 1);
      }
    }
    expect(
      await page.evaluate(
        () =>
          document.documentElement.scrollHeight <= innerHeight &&
          document.documentElement.scrollWidth <= innerWidth,
      ),
    ).toBe(true);
    const box = await page
      .getByRole("button", { name: "Send", exact: true })
      .boundingBox();
    expect(box!.y + box!.height).toBeLessThanOrEqual(height);
    await page.screenshot({
      path: `../.cache/revise-${width}-en.png`,
      fullPage: true,
    });
  }
  await page.getByRole("button", { name: "Leave", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: "Kotoba Link", exact: true }),
  ).toBeVisible();
  expect(downloads).toEqual([]);
  await expect(page.getByLabel("Display name", { exact: true })).toHaveValue(
    "Alex Example",
  );
});

test("camera enabled before joining records a playable local video across camera toggles", async ({
  page,
}) => {
  const errors: string[] = [];
  page.on("pageerror", (e) => errors.push(e.message));
  await page.addInitScript(() => {
    const Recorder = window.MediaRecorder;
    (window as any).__recordingStreams = [];
    window.MediaRecorder = class extends Recorder {
      constructor(stream: MediaStream, options?: MediaRecorderOptions) {
        super(stream, options);
        (window as any).__recordingStreams.push(
          stream.getTracks().map((t) => t.kind),
        );
      }
    };
  });
  await page.goto("/");
  await page
    .getByRole("button", { name: "新規ルームを作成", exact: true })
    .click();
  await page.getByLabel("入力方法").selectOption("text");
  await page.getByLabel("ルームID", { exact: true }).fill("revise-recording");
  await page.getByLabel("パスワード", { exact: true }).fill("e2e-password");
  await page
    .getByRole("button", { name: "ルームを作成して参加", exact: true })
    .click();
  await page.getByRole("button", { name: "カメラをON", exact: true }).click();
  await page.getByRole("button", { name: "会話を開始", exact: true }).click();
  await expect(
    page.getByText("自分のカメラを録画中", { exact: true }),
  ).toBeVisible();
  await expect
    .poll(() =>
      page
        .locator(".participant-tile video")
        .evaluate((v: HTMLVideoElement) => v.currentTime),
    )
    .toBeGreaterThan(1);
  await page.getByRole("button", { name: /カメラ.*ON/ }).click();
  await expect(page.getByText("録画待機", { exact: true })).toBeVisible();
  await page.getByRole("button", { name: /カメラ.*OFF/ }).click();
  await expect(
    page.getByText("自分のカメラを録画中", { exact: true }),
  ).toBeVisible();
  await expect
    .poll(() =>
      page
        .locator(".participant-tile video")
        .evaluate((v: HTMLVideoElement) => v.currentTime),
    )
    .toBeGreaterThan(1);
  expect(await page.evaluate(() => (window as any).__recordingStreams)).toEqual(
    [["video"]],
  );
  const downloadPromise = page.waitForEvent("download");
  await page.getByRole("button", { name: "会話終了", exact: true }).click();
  const download = await downloadPromise;
  const bytes = await readFile((await download.path())!);
  expect(bytes.length).toBeGreaterThan(1000);
  const decoded = await page.evaluate(
    (bytes) =>
      new Promise<{ width: number; height: number }>((resolve, reject) => {
        const video = document.createElement("video");
        const url = URL.createObjectURL(
          new Blob([new Uint8Array(bytes)], { type: "video/webm" }),
        );
        video.muted = true;
        const timeout = setTimeout(() => {
          URL.revokeObjectURL(url);
          reject(new Error("Video decoding timed out"));
        }, 10000);
        video.onloadeddata = () => {
          clearTimeout(timeout);
          const result = { width: video.videoWidth, height: video.videoHeight };
          video.removeAttribute("src");
          video.load();
          URL.revokeObjectURL(url);
          resolve(result);
        };
        video.onerror = () => {
          clearTimeout(timeout);
          URL.revokeObjectURL(url);
          reject(new Error("Recorded video cannot be decoded"));
        };
        video.src = url;
        video.load();
      }),
    [...bytes],
  );
  expect(decoded.width).toBeGreaterThan(0);
  expect(decoded.height).toBeGreaterThan(0);
  expect(errors).toEqual([]);
});
