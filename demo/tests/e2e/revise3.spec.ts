import { test, expect, type Page } from "@playwright/test";

async function synth(page: Page) {
  await page.addInitScript(() => {
    const w = window as any;
    w.__spoken = [];
    Object.defineProperty(window, "SpeechSynthesisUtterance", {
      configurable: true,
      value: class {
        constructor(public text: string) {}
      },
    });
    Object.defineProperty(window, "speechSynthesis", {
      configurable: true,
      value: {
        getVoices: () => [{ lang: "ja-JP" }],
        speak: (u: any) => {
          w.__spoken.push(u);
          queueMicrotask(() => u.onstart?.());
        },
        cancel: () => w.__spoken.at(-1)?.onerror?.({ error: "canceled" }),
        pause: () => {},
        resume: () => {},
        addEventListener: () => {},
        removeEventListener: () => {},
      },
    });
    const Socket = window.WebSocket;
    w.__controlSockets = [];
    window.WebSocket = class extends Socket {
      constructor(url: string | URL, protocols?: string | string[]) {
        super(url, protocols);
        if (!String(url).endsWith("/media")) w.__controlSockets.push(this);
      }
    };
  });
}
async function event(page: Page, type: string, payload: object) {
  await page.evaluate(
    ({ type, payload }) => {
      (window as any).__controlSockets
        .at(-1)
        .dispatchEvent(
          new MessageEvent("message", {
            data: JSON.stringify({
              version: 1,
              type,
              event_id: crypto.randomUUID(),
              payload,
            }),
          }),
        );
    },
    { type, payload },
  );
}
async function spoken(page: Page) {
  return page.evaluate(() => (window as any).__spoken.map((u: any) => u.text));
}

test("independent output modes control real remote audio and reading of recognized events", async ({
  page,
  browser,
}) => {
  await synth(page);
  await page.goto("/");
  await page
    .getByRole("button", { name: "新規ルームを作成", exact: true })
    .click();
  await page.getByLabel("表示名", { exact: true }).fill("受信者");
  await page.getByLabel("入力方法").selectOption("text");
  await page.getByLabel("ルームID", { exact: true }).fill("output-room");
  await page.getByLabel("パスワード", { exact: true }).fill("e2e-password");
  await page
    .getByRole("button", { name: "ルームを作成して参加", exact: true })
    .click();
  await page
    .getByRole("button", { name: "文字表示で参加", exact: true })
    .click();
  await expect(page.getByText("接続中", { exact: true })).toBeVisible();
  const context = await browser.newContext({
    permissions: ["microphone", "camera"],
  });
  try {
    const other = await context.newPage();
    await synth(other);
    await other.goto("/");
    await other.getByLabel("表示名", { exact: true }).fill("送信者");
    await other.getByLabel("入力方法").selectOption("text");
    await other.getByLabel("ルームID", { exact: true }).fill("output-room");
    await other.getByLabel("パスワード", { exact: true }).fill("e2e-password");
    await other
      .getByRole("button", { name: "会話に参加", exact: true })
      .click();
    await other
      .getByRole("button", { name: "文字表示で参加", exact: true })
      .click();
    await expect(other.getByText("接続中", { exact: true })).toBeVisible();
    await other
      .getByLabel("文字で伝える", { exact: true })
      .fill("字幕だけの発言");
    await other.getByRole("button", { name: "送信", exact: true }).click();
    await expect(page.locator(".utterance")).toContainText("字幕だけの発言");
    expect(await spoken(page)).toEqual([]);
    await expect(
      page.getByRole("button", { name: "音声を開始", exact: true }),
    ).toBeDisabled();
    const snapshot = await page.request
      .get("/api/rooms/output-room/snapshot")
      .then((r) => r.json());
    const sender = snapshot.participants.find(
      (p: any) => p.display_name === "送信者",
    );
    const utterance = (id: string, source = "speech") => ({
      utterance_id: id,
      participant_id: sender.id,
      display_name: sender.display_name,
      source,
      text: id,
      revision: 1,
      created_at: new Date().toISOString(),
    });
    await page.getByLabel("出力", { exact: true }).selectOption("ai");
    await event(page, "participant.activity", {
      id: sender.id,
      speaking: true,
      recognizing: true,
    });
    const tile = page
      .locator(".participant-tile")
      .filter({ hasText: "送信者" });
    await expect(tile.locator(".speaking-indicator")).toHaveText("発話中");
    await expect(tile.locator(".recognizing-indicator")).toHaveText("認識中");
    await event(page, "utterance.final", utterance("発声をAIで読む"));
    await expect.poll(() => spoken(page)).toContain("送信者。発声をAIで読む");
    await expect(page.locator(".utterance.reading")).toContainText(
      "読み上げ中",
    );
    await page.getByLabel("出力", { exact: true }).selectOption("captions");
    await expect(page.locator(".utterance.reading")).toHaveCount(0);
    await event(page, "participant.activity", {
      id: sender.id,
      speaking: false,
      recognizing: false,
    });
    await expect(tile.locator(".participant-activity > span")).toHaveCount(0);
    await page.getByLabel("出力", { exact: true }).selectOption("original");
    const count = (await spoken(page)).length;
    await event(page, "utterance.final", utterance("生音声の字幕"));
    await expect(page.locator(".utterance").last()).toContainText(
      "生音声の字幕",
    );
    expect((await spoken(page)).length).toBe(count);
    await event(page, "utterance.final", utterance("手話の字幕", "sign"));
    await expect.poll(() => spoken(page)).toContain("送信者。手話の字幕");
    await expect(other.getByLabel("出力", { exact: true })).toHaveValue(
      "captions",
    );
    await page.getByLabel("出力", { exact: true }).selectOption("ai");
    const config = await other.request.get("/api/config").then((r) => r.json());
    if (config.capabilities.speech.available) {
      await other.getByLabel("入力", { exact: true }).selectOption("speech");
      await other.getByRole("button", { name: /マイク.*OFF/ }).click();
      await expect
        .poll(() =>
          page
            .locator("audio")
            .evaluateAll((elements) =>
              elements.some(
                (a) => (a.srcObject as MediaStream)?.getAudioTracks().length,
              ),
            ),
        )
        .toBe(true);
      expect(
        await page
          .locator("audio")
          .evaluateAll((elements) => elements.every((a) => a.muted)),
      ).toBe(true);
      await page.getByLabel("出力", { exact: true }).selectOption("original");
      await expect
        .poll(() =>
          page
            .locator("audio")
            .evaluateAll((elements) => elements.every((a) => !a.muted)),
        )
        .toBe(true);
      await other.getByLabel("出力", { exact: true }).selectOption("ai");
      await expect(
        other.getByRole("button", { name: /マイク.*ON/ }),
      ).toHaveAttribute("aria-pressed", "true");
      await other.getByRole("button", { name: /マイク.*ON/ }).click();
    }
    await page.getByLabel("出力", { exact: true }).selectOption("ai");
    await page.reload();
    await expect(page.getByLabel("出力", { exact: true })).toHaveValue("ai");
    await page.getByRole("button", { name: "会話を開始", exact: true }).click();
    await expect(page.getByText("接続中", { exact: true })).toBeVisible();
    expect(await spoken(page)).toEqual([]);
    await page.getByRole("button", { name: "会話終了", exact: true }).click();
    await other.getByRole("button", { name: "会話終了", exact: true }).click();
  } finally {
    await context.close();
  }
});

test("participant resize handle works by pointer and keyboard without wrapping controls", async ({
  page,
}) => {
  await page.goto("/");
  await page
    .getByRole("button", { name: "新規ルームを作成", exact: true })
    .click();
  await page.getByLabel("入力方法").selectOption("text");
  await page.getByLabel("ルームID", { exact: true }).fill("split-room");
  await page.getByLabel("パスワード", { exact: true }).fill("e2e-password");
  await page
    .getByRole("button", { name: "ルームを作成して参加", exact: true })
    .click();
  await page
    .getByRole("button", { name: "文字表示で参加", exact: true })
    .click();
  const handle = page.getByRole("separator", {
    name: "参加者と発話者の映像サイズ",
  });
  await handle.focus();
  const before = Number(await handle.getAttribute("aria-valuenow"));
  await page.keyboard.press("ArrowDown");
  await expect(handle).toHaveAttribute("aria-valuenow", String(before + 8));
  const rect = (await handle.boundingBox())!;
  await page.mouse.move(rect.x + rect.width / 2, rect.y + rect.height / 2);
  await page.mouse.down();
  await page.mouse.move(rect.x + rect.width / 2, rect.y + rect.height / 2 + 30);
  await page.mouse.up();
  expect(Number(await handle.getAttribute("aria-valuenow"))).toBeGreaterThan(
    before + 20,
  );
  for (const locale of ["ja", "en"]) {
    await page.locator(".language-select select").selectOption(locale);
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
      await expect
        .poll(() =>
          page.evaluate(
            () =>
              document.documentElement.scrollHeight <= innerHeight &&
              document.documentElement.scrollWidth <= innerWidth,
          ),
        )
        .toBe(true);
      const controls = await page
        .locator(".conversation-controls button span")
        .evaluateAll((elements) =>
          elements.map((el) => {
            const range = document.createRange();
            range.selectNodeContents(el);
            return {
              whiteSpace: getComputedStyle(el).whiteSpace,
              lines: range.getClientRects().length,
              width: el.getBoundingClientRect().width,
              parent: el.parentElement!.clientWidth,
            };
          }),
        );
      for (const control of controls) {
        expect(control.whiteSpace).toBe("nowrap");
        expect(control.width).toBeLessThanOrEqual(control.parent);
      }
      await page.screenshot({
        path: `../.cache/revise3-${locale}-${width}.png`,
        fullPage: true,
      });
    }
  }
  await page.getByRole("button", { name: "Leave", exact: true }).click();
});
