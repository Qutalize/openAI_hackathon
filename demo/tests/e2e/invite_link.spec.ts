import { expect, test } from "@playwright/test";

test("first visit starts on create, and a room link opens the join form with the room filled in", async ({
  page,
}) => {
  await page.goto("/");
  await expect(
    page.getByRole("button", { name: "新規ルームを作成", exact: true }),
  ).toHaveAttribute("aria-pressed", "true");
  await page.goto("/rooms/shared-room");
  await expect(
    page.getByRole("button", { name: "既存ルームに参加", exact: true }),
  ).toHaveAttribute("aria-pressed", "true");
  await expect(page.getByLabel("ルームID", { exact: true })).toHaveValue(
    "shared-room",
  );
  await expect(page.getByText(/招待されたルームです/)).toBeVisible();
});
