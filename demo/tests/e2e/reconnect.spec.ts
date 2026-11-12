import { test, expect, type Page } from "@playwright/test";

// Keeps every control WebSocket and RTCPeerConnection reachable from the test.
async function instrument(page: Page) {
  await page.addInitScript(() => {
    const w = window as any;
    w.__controlSockets = [];
    w.__testConnections = [];
    const OriginalSocket = window.WebSocket;
    window.WebSocket = class extends OriginalSocket {
      constructor(url: string | URL, protocols?: string | string[]) {
        super(url, protocols);
        if (/\/ws\/rooms\/[^/]+$/.test(String(url)))
          w.__controlSockets.push(this);
      }
    } as typeof WebSocket;
    const OriginalPeer = window.RTCPeerConnection;
    window.RTCPeerConnection = class extends OriginalPeer {
      constructor(config?: RTCConfiguration) {
        super(config);
        w.__testConnections.push(this);
      }
    };
  });
}

async function join(page: Page, mode: string) {
  await page.goto("/");
  await page.getByRole("button", { name: "既存ルームに参加" }).click();
  await page
    .locator(`input[name="mode"][value="${mode}"]`)
    .check({ force: true });
  await page.getByLabel("入力方法").selectOption("text");
  await page.getByLabel("ルームID", { exact: true }).fill("reconnect-room");
  await page.getByLabel("パスワード", { exact: true }).fill("e2e-password");
  await page.getByRole("button", { name: "会話に参加" }).click();
  await page.getByRole("button", { name: "文字表示で参加" }).click();
  await expect(page.getByText("接続中", { exact: true })).toBeVisible();
  await page.getByRole("button", { name: "カメラ OFF" }).click();
  await expect(page.getByRole("button", { name: "カメラ ON" })).toBeVisible();
}

/** Passes only while new remote video frames are being decoded, not merely while a stale track exists. */
function remoteVideoFlowing(page: Page) {
  const decoded = () =>
    page.evaluate(async () => {
      let frames = 0;
      for (const pc of (window as any)
        .__testConnections as RTCPeerConnection[]) {
        if (pc.connectionState !== "connected") continue;
        (await pc.getStats()).forEach((report) => {
          if (report.type === "inbound-rtp" && report.kind === "video")
            frames += report.framesDecoded ?? 0;
        });
      }
      return frames;
    });
  return expect
    .poll(
      async () => {
        const first = await decoded();
        await page.waitForTimeout(700);
        return (await decoded()) > first;
      },
      { timeout: 10000, intervals: [100] },
    )
    .toBe(true);
}

/**
 * Simulates a network blip the server does not notice: the client gives up on its socket and
 * reconnects while the server still holds the old one, so only `participant.joined` is broadcast.
 */
async function silentlyDropControlSocket(page: Page) {
  const before = await page.evaluate(
    () => (window as any).__testConnections.length,
  );
  await page.evaluate(() => {
    const sockets = (window as any).__controlSockets as WebSocket[];
    const socket = sockets[sockets.length - 1];
    const onclose = socket.onclose!;
    socket.onclose = null;
    socket.onmessage = null;
    onclose.call(socket, new CloseEvent("close", { code: 1006 }));
  });
  await expect(page.getByText("接続中", { exact: true })).toBeVisible({
    timeout: 15000,
  });
  await expect
    .poll(() => page.evaluate(() => (window as any).__testConnections.length))
    .toBeGreaterThan(before);
}

test("remote video recovers after an unnoticed control reconnect on either side", async ({
  browser,
}) => {
  const errors: string[] = [];
  const pages: Page[] = [];
  try {
    for (const mode of ["standard", "hearing_support"]) {
      const context = await browser.newContext({
        permissions: ["camera", "microphone"],
      });
      const page = await context.newPage();
      page.on("pageerror", (e) => errors.push(e.message));
      await instrument(page);
      pages.push(page);
      await join(page, mode);
    }
    const [a, b] = pages;
    await remoteVideoFlowing(a);
    await remoteVideoFlowing(b);

    // Each side reconnects once, so both the initial offerer and the answerer are covered.
    for (const reconnecting of [a, b]) {
      await silentlyDropControlSocket(reconnecting);
      await remoteVideoFlowing(a);
      await remoteVideoFlowing(b);
    }
    for (const page of pages)
      await expect(
        page.getByText(/映像接続が不安定|映像接続を確立できません/),
      ).toHaveCount(0);
    expect(errors).toEqual([]);
  } finally {
    // Leave explicitly so repeated runs do not fill the four-person room.
    for (const page of pages) {
      await page
        .getByRole("button", { name: "会話終了" })
        .click({ timeout: 2000 })
        .catch(() => {});
      await page.context().close();
    }
  }
});
