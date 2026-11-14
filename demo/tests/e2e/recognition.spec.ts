import { test, expect } from "@playwright/test";

for (const kind of ["lipread", "sign"])
  test(`guided ${kind} collection sends only landmarks after consent`, async ({
    page,
  }) => {
    test.setTimeout(60000);
    page.on("console", (message) => {
      if (message.type() === "error") console.log(message.text());
    });
    const bodies: any[] = [];
    page.on("request", (request) => {
      if (request.url().endsWith("/api/training/samples"))
        bodies.push(JSON.parse(request.postData() ?? "{}"));
    });
    await page.goto("/training");
    await page.getByLabel("入力方式").selectOption(kind);
    await page.getByLabel("人物ID（氏名を使用しない）").fill("test-person");
    await page.getByLabel("収集コード").fill("e2e-collection-code");
    await page.getByLabel("1表現あたりの回数").selectOption("1");
    await expect(
      page.getByRole("button", { name: "カメラをON" }),
    ).toBeDisabled();
    await page
      .getByLabel("本人が収集・モデル学習への使用に同意しています")
      .check();
    await page.getByRole("button", { name: "カメラをON" }).click();
    await expect(page.getByText("この人物IDの収録数")).toBeVisible();
    await expect(page.locator(".training-counts li")).toHaveCount(11);
    await page.getByRole("button", { name: "連続撮影を開始" }).click();
    await expect(page.locator(".training-prompt")).toContainText("1 / 13", {
      timeout: 45000,
    });
    await expect(page.locator(".training-phase")).toHaveText("撮影中", {
      timeout: 10000,
    });
    // The fake camera shows no face, so the server rejects the take and the page asks again.
    await expect
      .poll(() => bodies.length, { timeout: 15000 })
      .toBeGreaterThan(0);
    await expect(page.getByRole("status")).toContainText(
      /特徴点が途切れました|顔や手が映っていません/,
    );
    const data = bodies[0];
    expect(data.modality).toBe(kind);
    expect(data.consent).toBe(true);
    expect(data.frames[0]).toHaveLength(kind === "lipread" ? 40 : 100);
    expect(data.frames[0][0]).toHaveLength(4);
    expect(data).not.toHaveProperty("video");
    await page.getByRole("button", { name: "中断" }).click();
    await expect(page.locator(".training-prompt")).toHaveCount(0);
    await page
      .getByLabel("本人が収集・モデル学習への使用に同意しています")
      .uncheck();
    await expect(page.getByRole("status")).toContainText("収集を停止しました");
  });

test("speech output skips replays and replaces an unread correction", async ({
  page,
}) => {
  await page.goto("/");
  const result = await page.evaluate(async () => {
    const spoken: string[] = [];
    const pending: any[] = [];
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
          spoken.push(u.text);
          pending.push(u);
        },
        cancel: () => {},
        pause: () => {},
        resume: () => {},
        addEventListener: () => {},
        removeEventListener: () => {},
      },
    });
    const modulePath = "/src/services/speechOutput.ts";
    const { SpeechOutput } = await import(modulePath);
    const output = new SpeechOutput(
      "self",
      { tts_lang: "ja-JP", tts_rate: 1, tts_queue_limit: 10 },
      () => {},
    );
    const u = {
      utterance_id: "first",
      participant_id: "other",
      display_name: "ユーザーB",
      source: "text",
      text: "最初",
      revision: 1,
    };
    output.utterance(u, "event-1");
    output.utterance(u, "event-1");
    output.utterance(
      { ...u, utterance_id: "queued", text: "古い候補" },
      "event-2",
    );
    output.utterance(
      { ...u, utterance_id: "queued", text: "修正後", revision: 2 },
      "event-3",
      true,
    );
    output.utterance({ ...u, utterance_id: "old", replayed: true }, "event-4");
    output.utterance(
      { ...u, utterance_id: "own", participant_id: "self" },
      "event-5",
    );
    output.utterance(
      { ...u, utterance_id: "speech", source: "speech" },
      "event-6",
    );
    pending[0].onend();
    return spoken;
  });
  expect(result).toEqual(["ユーザーB。最初", "ユーザーB。修正後"]);
});

test("sign features keep hand and face landmarks that report no visibility", async ({
  page,
}) => {
  await page.goto("/");
  const valid = await page.evaluate(async () => {
    const modulePath = "/src/workers/features.ts";
    const { signFeatures } = await import(modulePath);
    const point = (x: number, y: number, visibility?: number) => ({
      x,
      y,
      z: 0,
      visibility,
    });
    const pose = Array.from({ length: 33 }, (_, i) =>
      point(0.5, 0.5 + i / 100, i > 24 ? 0.1 : 0.9),
    );
    pose[11] = point(0.6, 0.6, 0.99);
    pose[12] = point(0.4, 0.6, 0.99);
    // MediaPipe Tasks reports visibility 0 for hand and face landmarks.
    const hand = Array.from({ length: 21 }, (_, i) =>
      point(0.3 + i / 100, 0.5, 0),
    );
    const face = Array.from({ length: 478 }, (_, i) =>
      point(0.5, 0.3 + i / 10000, 0),
    );
    const f = signFeatures(face, pose, [hand], ["Right"]);
    const ok = (a: number, b: number) =>
      f.slice(a, b).filter((p: number[]) => p[3] === 1).length;
    return {
      left: ok(0, 21),
      right: ok(21, 42),
      shoulders: f[53][3] + f[54][3],
      hidden: f[42 + 30][3],
      face: ok(75, 100),
    };
  });
  expect(valid).toEqual({
    left: 0,
    right: 21,
    shoulders: 2,
    hidden: 0,
    face: 25,
  });
});
