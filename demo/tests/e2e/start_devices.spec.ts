import { test, expect } from "@playwright/test";

test("starting from the all-off setup screen turns on the microphone that speech input needs", async ({
  page,
}) => {
  await page.goto("/");
  await page.getByRole("button", { name: "既存ルームに参加" }).click();
  const config = await page.request.get("/api/config").then((r) => r.json());
  test.skip(
    !config.capabilities.speech.available,
    "The optional speech model is not installed",
  );
  await page.getByLabel("入力方法").selectOption("speech");
  await page.getByLabel("ルームID", { exact: true }).fill("voice-room");
  await page.getByLabel("パスワード", { exact: true }).fill("e2e-password");
  await page.getByRole("button", { name: "会話に参加" }).click();
  await expect(page.getByRole("button", { name: "マイクをON" })).toBeVisible();
  await page.getByRole("button", { name: "会話を開始" }).click();
  await expect(page.getByText("接続中", { exact: true })).toBeVisible();
  await expect(page.getByRole("button", { name: /マイク.*ON/ })).toBeVisible();
  await expect(page.getByRole("alert")).toHaveCount(0);
});
