import { expect, test } from '@playwright/test';

test('join page fits common desktop viewports without page scrolling', async ({ page }) => {
  await page.goto('/');

  for (const locale of ['ja', 'en']) {
    await page.getByLabel(/表示言語|Display language/).selectOption(locale);
    for (const [width, height] of [
      [1366, 768],
      [1236, 834],
    ]) {
      await page.setViewportSize({ width, height });
      await expect(page.locator('.join-page')).toBeVisible();
      await expect
        .poll(() =>
          page.evaluate(
            () =>
              document.documentElement.scrollHeight <= innerHeight &&
              document.documentElement.scrollWidth <= innerWidth,
          ),
        )
        .toBe(true);
      await expect(page.locator('.join-button + .join-footnote')).toBeInViewport();
    }
  }
});
