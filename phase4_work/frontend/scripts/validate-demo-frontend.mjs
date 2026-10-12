import { chromium } from '@playwright/test'
import { mkdir, writeFile } from 'node:fs/promises'
import { resolve } from 'node:path'

const baseURL = process.env.DEMO_FRONTEND_URL || 'http://127.0.0.1:5173'
const outputDir = resolve('../qa_report/full_case')
await mkdir(outputDir, { recursive: true })

const browser = await chromium.launch({ headless: true })
const page = await browser.newPage({ viewport: { width: 1600, height: 1000 } })
const consoleErrors = []
page.on('console', message => {
  if (message.type() === 'error') consoleErrors.push({ url: page.url(), message: message.text() })
})
page.on('pageerror', error => consoleErrors.push({ url: page.url(), message: error.message }))

const routes = [
  ['/dashboard', 'dashboard'],
  ['/data', 'data'],
  ['/carbon', 'carbon'],
  ['/simulation?scenario_version=4', 'simulation'],
  ['/recommendations?run=1', 'recommendations'],
  ['/scenarios?scenario=4', 'scenarios'],
  ['/carbon-market?scenario_version=4&task=4', 'carbon-market'],
  ['/risks?scenario_version=4&task=4', 'risks'],
  ['/reports?scenario_version=4&task=4', 'reports'],
  ['/system', 'system'],
  ['/screen', 'screen'],
  ['/3d', '3d'],
]
const results = []

for (const [path, name] of routes) {
  const response = await page.goto(`${baseURL}${path}`, { waitUntil: 'networkidle', timeout: 30000 })
  await page.waitForTimeout(800)
  const body = (await page.locator('body').innerText()).replace(/\s+/g, ' ').trim()
  const headings = await page.locator('h1, h2, h3').allTextContents()
  const fatal = ['页面加载失败', '系统发生错误', 'Failed to fetch'].filter(text => body.includes(text))
  const item = {
    route: path,
    http_status: response?.status() ?? null,
    title: await page.title(),
    headings: headings.slice(0, 12),
    body_length: body.length,
    has_demo_site: body.includes('碳中和示范园区'),
    fatal,
    canvas_count: await page.locator('canvas').count(),
  }
  if (name === 'data') {
    const steps = ['园区/站点', '建筑与能源系统', '设备与计量点', '数据源配置', '数据导入', '数据质量']
    item.data_steps = {}
    for (const label of steps) {
      const matches = page.getByText(label, { exact: true })
      item.data_steps[label] = await matches.count()
    }
  }
  if (name === 'reports') {
    item.docx_visible = body.includes('DOCX') || body.includes('Word')
    item.pdf_visible = body.includes('PDF')
    item.checksum_visible = body.includes('SHA-256') || body.includes('checksum')
  }
  if (name === '3d') {
    item.building_names_visible = ['综合办公楼', '科研实验楼', '数据中心', '综合服务楼'].filter(x => body.includes(x))
  }
  await page.screenshot({ path: resolve(outputDir, `${name}.png`), fullPage: name !== 'screen' && name !== '3d' })
  results.push(item)
}

const output = { baseURL, checked_at: new Date().toISOString(), results, console_errors: consoleErrors }
await writeFile(resolve('../demo_data/frontend_validation_result.json'), JSON.stringify(output, null, 2), 'utf8')
console.log(JSON.stringify(output, null, 2))
await browser.close()

if (results.some(result => result.http_status !== 200 || result.fatal.length)) process.exitCode = 1
