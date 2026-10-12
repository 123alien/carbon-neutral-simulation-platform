import { expect, test } from "@playwright/test";

test("示范设备自动采集和用水统计真实展示", async ({ page }) => {
  await page.goto("/data");
  const site = page.locator(".context .el-select");
  await site.click();
  await page.getByRole("option", { name: "智慧低碳示范园区" }).click();
  await page.getByRole("button", { name: /配置物联网、标准接口/ }).click();
  for (const name of ["风力发电自动采集", "充电桩自动采集", "储能自动采集", "空调自动采集", "照明自动采集", "第三方能源管理系统接口", "园区用水自动采集"]) {
    await expect(page.getByText(name, { exact: false }).first()).toBeVisible();
  }
  await expect(page.getByText("示范仿真数据", { exact: false }).first()).toBeVisible();
  await expect(page.getByRole("heading", { name: "园区用水趋势" })).toBeVisible();
});

test("校园公共机构区域汇总与标准核算验证", async ({ page }) => {
  await page.goto("/carbon");
  const site = page.locator(".carbon-toolbar .el-select").first();
  await site.click();
  await page.getByRole("option", { name: "绿色校园" }).click();
  await expect(page.getByRole("heading", { name: "区域级碳排放汇总与排名" })).toBeVisible();
  await expect(page.getByText("低碳产业园").first()).toBeVisible();
  await expect(page.getByText("绿色校园").first()).toBeVisible();
  await expect(page.getByText("公共机构示范点").first()).toBeVisible();
  await expect(page.getByRole("heading", { name: /GB\/T 32150-2015/ })).toBeVisible();
  await expect(page.getByText("不代表通过认证", { exact: false })).toBeVisible();
  await expect(page.getByText("可复算示例", { exact: false })).toBeVisible();
});
