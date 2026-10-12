import {expect,test} from '@playwright/test';

test('统一工作台展示从数据接入到报告输出的完整闭环',async({page})=>{
  await page.goto('/carbon-neutral-simulation');
  const flow=page.getByRole('navigation',{name:'碳中和完整业务流程'});
  await expect(flow).toBeVisible();
  for(const step of ['数据接入','碳排放核算','当前基准状态','目标与约束','路径推荐','全过程仿真','场景结果对比','情景参数调整','综合分析','碳市场评估','报告输出']){
    await expect(flow.getByRole('button',{name:new RegExp(step)})).toBeVisible();
  }
  await expect(page.getByRole('main').getByText('示范仿真数据',{exact:true})).toBeVisible();
  await flow.getByRole('button',{name:/报告输出/}).click();
  await expect(page.getByRole('heading',{name:'碳中和可行性与风险评估报告',level:1})).toBeVisible();
  await expect(page.getByText('DOCX / PDF 文件',{exact:true})).toBeVisible();
});
