import { expect, test } from "@playwright/test";

test("碳市场统计独立展示并默认定位最近有效评估", async ({ page }) => {
  await page.goto("/carbon-market");
  await expect(
    page.getByRole("heading", { name: "市场指标趋势" }),
  ).toBeVisible();
  await expect(page.getByText("当前评估场景")).toBeVisible();
  await expect(
    page.locator(".context-bar").getByText("仿真任务21 · 已完成"),
  ).toBeVisible();
  await expect(
    page.locator(".market-cards").getByText("配额盈余", { exact: true }),
  ).toBeVisible();
  await expect(page.getByText("carbon market scenario not found")).toHaveCount(
    0,
  );
  await expect(page.getByText("DEMO_REGION")).toHaveCount(0);
  await expect(
    page
      .getByTestId("market-statistics")
      .locator(".el-table__body-wrapper tbody tr"),
  ).toHaveCount(12);
});
