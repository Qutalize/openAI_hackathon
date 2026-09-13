import { test, expect, type Page } from "@playwright/test";

async function instrument(page: Page) {
  await page.addInitScript(() => {
    const Original = window.RTCPeerConnection;
    (window as any).__testConnections = [];
    (window as any).__testMediaLogs = [];
    const originalStop = MediaStreamTrack.prototype.stop;
    MediaStreamTrack.prototype.stop = function () {
      (window as any).__testMediaLogs.push({
        event: "stop",
        label: this.label,
        stack: new Error().stack,
      });
      return originalStop.call(this);
    };
    const originalMedia = navigator.mediaDevices.getUserMedia.bind(
      navigator.mediaDevices,
    );
    navigator.mediaDevices.getUserMedia = async (constraints) => {
      const stream = await originalMedia(constraints);
      for (const track of stream.getTracks()) {
        (window as any).__testMediaLogs.push({
          event: "acquired",
          label: track.label,
          settings: track.getSettings(),
        });
        track.addEventListener("ended", () =>
          (window as any).__testMediaLogs.push({ event: "ended" }),
        );
      }
      return stream;
    };
    window.RTCPeerConnection = class extends Original {
      constructor(c?: RTCConfiguration) {
        super(c);
        (window as any).__testConnections.push(this);
      }
    };
  });
}

async function join(page: Page, mode = "standard", room = "e2e-room") {
  await page.goto("/");
  await page
    .locator(`input[name="mode"][value="${mode}"]`)
    .check({ force: true });
  await page.getByLabel("入力方法").selectOption("text");
  await page.getByLabel("ルームID", { exact: true }).fill(room);
  await page.getByLabel("パスワード", { exact: true }).fill("e2e-password");
  await page.getByRole("button", { name: "会話に参加" }).click();
  await expect(
    page.getByRole("heading", { name: "カメラと音声を確認" }),
  ).toBeVisible();
  await page.getByRole("button", { name: "文字表示で参加" }).click();
  await expect(page.getByText("接続中", { exact: true })).toBeVisible();
}

test("layout, two participants, captions, correction, camera, reconnect and leave", async ({
  browser,
  page,
}) => {
  const errors: string[] = [];
  page.on("pageerror", (e) => errors.push(e.message));
  await instrument(page);
  await page.goto("/");
  await expect(
    page.getByRole("heading", { name: "ことばリンク" }),
  ).toBeVisible();
  await page.screenshot({
    path: "../.cache/title-implemented.png",
    fullPage: true,
  });
  await join(page);
  const second = await browser.newContext({
    permissions: ["camera", "microphone"],
  });
  const other = await second.newPage();
  other.on("pageerror", (e) => errors.push(e.message));
  await instrument(other);
  await join(other, "hearing_support");
  await page
    .getByRole("textbox", { name: "文字で伝える" })
    .fill("こんにちは。手話と文字で会話できます。");
  await page.getByRole("button", { name: "送信", exact: true }).click();
  await expect(
    other
      .locator(".utterance")
      .getByText("こんにちは。手話と文字で会話できます。"),
  ).toBeVisible();
  await page
    .locator(".utterance")
    .getByRole("button", { name: "修正", exact: true })
    .click();
  await page
    .getByRole("textbox", { name: "発言の修正" })
    .fill("こんにちは。文字で会話できました。");
  await page.getByRole("button", { name: "修正を送信" }).click();
  await expect(
    other.locator(".utterance").getByText("こんにちは。文字で会話できました。"),
  ).toBeVisible();
  await page.getByRole("button", { name: /カメラ.*OFF/ }).click();
  await expect(page.getByRole("button", { name: /カメラ.*ON/ })).toBeVisible();
  try {
    await expect
      .poll(
        () =>
          other
            .locator("video")
            .evaluateAll((v) =>
              v.some((x) => (x as HTMLVideoElement).videoWidth > 0),
            ),
        { timeout: 15000 },
      )
      .toBe(true);
  } catch (error) {
    for (const target of [page, other]) {
      const debug = await target.evaluate(() => ({
        peers: (window as any).__testConnections.map(
          (p: RTCPeerConnection) => ({
            connection: p.connectionState,
            ice: p.iceConnectionState,
            signaling: p.signalingState,
            transceivers: p.getTransceivers().map((t) => ({
              direction: t.currentDirection,
              sender: t.sender.track
                ? {
                    kind: t.sender.track.kind,
                    label: t.sender.track.label,
                    state: t.sender.track.readyState,
                  }
                : null,
              receiver: {
                kind: t.receiver.track.kind,
                state: t.receiver.track.readyState,
                muted: t.receiver.track.muted,
              },
            })),
          }),
        ),
        mediaLogs: (window as any).__testMediaLogs,
        videos: [...document.querySelectorAll("video")].map((v) => ({
          width: v.videoWidth,
          state: v.readyState,
        })),
      }));
      console.log(JSON.stringify(debug));
    }
    throw error;
  }
  await page.screenshot({
    path: "../.cache/talk-implemented.png",
    fullPage: true,
  });
  await other.reload();
  await other.getByRole("button", { name: "文字表示で参加" }).click();
  await expect(
    other.locator(".utterance").getByText("こんにちは。文字で会話できました。"),
  ).toBeVisible();
  await expect(page.getByRole("button", { name: "簡略画面へ" })).toHaveCount(0);
  await expect(
    other
      .locator(".utterance.other")
      .getByRole("button", { name: "修正", exact: true }),
  ).toHaveCount(0);
  await expect(page.locator(".utterance.own")).toHaveCount(1);
  await page.getByRole("button", { name: "名前を変更" }).click();
  await page.getByRole("textbox", { name: "表示名", exact: true }).fill("Yuki");
  await page.getByRole("button", { name: "名前を保存" }).click();
  await expect(other.locator(".utterance b")).toHaveText("Yuki");
  await expect(
    other.locator(".participant-tile").filter({ hasText: "Yuki" }),
  ).toBeVisible();
  const divider = page.getByRole("separator", {
    name: /映像と文字おこしのサイズ|Video and transcript size/,
  });
  await divider.focus();
  await page.keyboard.press("ArrowLeft");
  await expect(divider).toHaveAttribute("aria-valuenow", "60");
  const before = await page.locator(".video-column").boundingBox();
  const handle = await divider.boundingBox();
  await page.mouse.move(handle!.x + handle!.width / 2, handle!.y + 20);
  await page.mouse.down();
  await page.mouse.move(handle!.x - 100, handle!.y + 20);
  await page.mouse.up();
  expect(
    (await page.locator(".video-column").boundingBox())!.width,
  ).toBeLessThan(before!.width);
  const dialogCount = await page.getByRole("dialog").count();
  await page.getByRole("button", { name: /参加者/ }).click();
  await expect(page.getByRole("dialog")).toHaveCount(dialogCount);
  await page.getByLabel("表示言語").selectOption("en");
  await expect(
    page.getByRole("heading", { name: "Transcript", exact: true }),
  ).toBeVisible();
  await expect(
    page.getByRole("button", { name: "Leave", exact: true }),
  ).toBeVisible();
  await page.getByLabel("Display language").selectOption("ja");
  await expect(
    page.getByText("自分のカメラを録画中", { exact: true }),
  ).toBeVisible();
  await page.getByRole("button", { name: /カメラ.*ON/ }).click();
  await expect(page.getByText("録画待機", { exact: true })).toBeVisible();
  await page.getByRole("button", { name: /カメラ.*OFF/ }).click();
  await expect(
    page.getByText("自分のカメラを録画中", { exact: true }),
  ).toBeVisible();
  const downloadPromise = page.waitForEvent("download");
  await page.getByRole("button", { name: "会話終了" }).click();
  const download = await downloadPromise;
  expect(download.suggestedFilename()).toMatch(
    /^kotoba-e2e-room-.*\.(webm|mp4)$/,
  );
  expect(await download.failure()).toBeNull();
  await download.saveAs("../.cache/camera-recording.webm");
  await expect(
    page.getByRole("heading", { name: "ことばリンク" }),
  ).toBeVisible();
  await other.getByRole("button", { name: "会話終了" }).click();
  await second.close();
  expect(errors).toEqual([]);
});

test("permission-free text fallback and responsive keyboard navigation", async ({
  page,
}) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await join(page, "standard", "mobile-room");
  await page
    .getByRole("textbox", { name: "文字で伝える" })
    .fill("スマートフォン幅で送信");
  await page.keyboard.press("Tab");
  await page.keyboard.press("Enter");
  await expect(
    page.locator(".utterance").getByText("スマートフォン幅で送信"),
  ).toBeVisible();
  expect(
    await page.evaluate(
      () =>
        document.documentElement.scrollWidth <= window.innerWidth &&
        document.documentElement.scrollHeight <= window.innerHeight,
    ),
  ).toBe(true);
  for (const name of ["会話終了", "送信", "読み上げ停止", "未読を再生"]) {
    const box = await page
      .getByRole("button", { name, exact: true })
      .boundingBox();
    expect(box!.y + box!.height).toBeLessThanOrEqual(844);
  }
  await page.screenshot({
    path: "../.cache/mobile-implemented.png",
    fullPage: true,
  });
  await page.getByRole("button", { name: "会話終了" }).click();
});

test("speech input sends PCM from an AudioWorklet and stops its microphone", async ({
  page,
}) => {
  const errors: string[] = [];
  page.on("pageerror", (e) => errors.push(e.message));
  let packets = 0;
  page.on("websocket", (ws) => {
    if (ws.url().endsWith("/media"))
      ws.on("framesent", (e) => {
        if (e.payload.length > 6400) packets++;
      });
  });
  await page.goto("/");
  const capabilities = await page.request
    .get("/api/config")
    .then((r) => r.json());
  test.skip(
    !capabilities.capabilities.speech.available,
    "The optional speech model is not installed",
  );
  await page.getByLabel("入力方法").selectOption("speech");
  await page.getByLabel("ルームID", { exact: true }).fill("voice-room");
  await page.getByLabel("パスワード", { exact: true }).fill("e2e-password");
  await page.getByRole("button", { name: "会話に参加" }).click();
  await page.getByRole("button", { name: "マイクをON" }).click();
  await page.getByRole("button", { name: "会話を開始" }).click();
  await expect(page.getByText("接続中", { exact: true })).toBeVisible();
  await expect
    .poll(() => packets, { timeout: 10000 })
    .toBeGreaterThanOrEqual(5);
  await page.getByRole("button", { name: /マイク.*ON/ }).click();
  await expect(page.getByRole("button", { name: /マイク.*OFF/ })).toBeVisible();
  await expect(page.getByRole("alert")).toHaveCount(0);
  await page.getByRole("button", { name: "会話終了" }).click();
  expect(errors).toEqual([]);
});

test("four participants form a mesh and the fifth cannot join", async ({
  browser,
}) => {
  const contexts = [];
  try {
    const pages: Page[] = [];
    for (let i = 0; i < 4; i++) {
      const context = await browser.newContext();
      contexts.push(context);
      const page = await context.newPage();
      pages.push(page);
      await instrument(page);
      await join(page, "standard", "four-room");
    }
    for (const page of pages)
      await expect
        .poll(
          () =>
            page.evaluate(
              () =>
                (window as any).__testConnections.filter(
                  (p: RTCPeerConnection) => p.connectionState === "connected",
                ).length,
            ),
          { timeout: 15000 },
        )
        .toBe(3);
    const fifth = await browser.newContext();
    contexts.push(fifth);
    const page = await fifth.newPage();
    await page.goto("/");
    await page.getByLabel("入力方法").selectOption("text");
    await page.getByLabel("ルームID", { exact: true }).fill("four-room");
    await page.getByLabel("パスワード", { exact: true }).fill("e2e-password");
    await page.getByRole("button", { name: "会話に参加" }).click();
    await expect(page.getByRole("alert")).toContainText("満員");
    for (const member of pages)
      await member.getByRole("button", { name: "会話終了" }).click();
  } finally {
    for (const context of contexts) await context.close();
  }
});
