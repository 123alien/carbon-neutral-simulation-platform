"""Import normalized official national market statistics through FastAPI."""
from __future__ import annotations
import json
from pathlib import Path
import httpx,pandas as pd
ROOT=Path(__file__).resolve().parents[1];BASE=ROOT/'china_market';API='http://127.0.0.1:8000'
FIELDS=('carbon_price_per_t','trading_volume_t','trading_amount_yuan','ccer_volume_t','ccer_price_per_t','ccer_trading_amount_yuan','green_certificate_volume','green_certificate_price','green_certificate_issued_count','green_certificate_traded_count')
SOURCES={
 'ETS_2024':'REAL_PUBLIC_OFFICIAL | 生态环境部 | 2024年全国碳排放权交易市场配额交易及清缴工作顺利结束',
 'ETS_CCER_2025':'REAL_PUBLIC_OFFICIAL | 生态环境部 | 2025年全国碳市场平稳有序运行',
 'GEC_2024':'REAL_PUBLIC_OFFICIAL | 国家能源局 | 中国绿色电力证书发展报告（2024）',
 'GEC_2025':'REAL_PUBLIC_OFFICIAL | 国家能源局 | 中国绿色电力证书发展报告（2025）'}
def checked(r):
 if not r.is_success:raise RuntimeError(f'{r.request.method} {r.request.url}: {r.status_code} {r.text[:1000]}')
 return r.json()
def main():
 frame=pd.read_csv(BASE/'normalized'/'china_market_statistics.csv')
 with httpx.Client(base_url=API,timeout=60,trust_env=False) as c:
  existing=checked(c.get('/api/carbon-market/statistics',params={'region':'中国全国市场'}))['records']
  existing_keys={(x['timestamp'][:10],x['source']) for x in existing};items=[]
  for row in frame.to_dict('records'):
   source=f"{SOURCES[row['source_key']]} | market={row['market']} | {row['price_basis']} | period={row['period']}"
   if (row['timestamp'][:10],source) in existing_keys:continue
   payload={'region':'中国全国市场','timestamp':row['timestamp'],'source':source}
   for field in FIELDS:
    if row.get(field) is not None and not pd.isna(row[field]):payload[field]=float(row[field])
   items.append(payload)
  inserted=checked(c.post('/api/carbon-market/indicators/bulk',json={'items':items}))['inserted'] if items else 0
  stats=checked(c.get('/api/carbon-market/statistics',params={'region':'中国全国市场'}))
  result={'inserted':inserted,'record_count':stats['record_count'],'statistics':stats,'data_class':'REAL_PUBLIC_OFFICIAL'}
  (BASE/'import_result.json').write_text(json.dumps(result,indent=2,ensure_ascii=False),encoding='utf-8');print(json.dumps({'inserted':inserted,'record_count':stats['record_count']},indent=2))
if __name__=='__main__':main()
