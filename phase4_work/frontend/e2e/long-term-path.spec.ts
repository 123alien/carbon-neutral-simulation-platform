import { expect, test } from "@playwright/test";

test("碳中和仿真工作台执行长期路径推演", async ({ page }) => {
  await page.goto("/simulation?scenario_version=19");
  const section = page.getByTestId("long-term-path");
  await expect(
    section.getByRole("heading", { name: "2024—2060 年长期路径推演" }),
  ).toBeVisible();
  await section.getByRole("button", { name: "执行长期推演" }).click();
  await expect(section.getByText("实际达峰年份")).toBeVisible({
    timeout: 15_000,
  });
  await expect(section.getByText("实际中和年份")).toBeVisible();
  await expect(section.getByText("2060年前未实现碳中和")).toBeVisible();
  await expect(section.locator("tbody tr")).toHaveCount(37);
  const gap = page.getByTestId("target-gap-analysis");
  await expect(gap.getByText("目标存在缺口")).toBeVisible();
  await expect(gap.getByText("达峰延迟")).toBeVisible();
  await expect(
    gap.getByRole("heading", { name: "主要未达标原因" }),
  ).toBeVisible();
  await gap.getByRole("button", { name: "生成并推演强化方案" }).click();
  await expect(
    gap.getByRole("cell", { name: "强化仿真情景" }),
  ).toBeVisible({ timeout: 15_000 });
  await expect(gap.getByRole("cell", { name: "已满足" })).toBeVisible();
  await expect(gap.getByText("不构成真实工程报价", { exact: false })).toBeVisible();
  await expect(gap.getByText("不构成确定性承诺", { exact: false })).toBeVisible();
});
