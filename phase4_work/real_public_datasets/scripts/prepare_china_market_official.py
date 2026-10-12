"""Normalize explicitly published annual China ETS, CCER and GEC statistics."""
from __future__ import annotations
import hashlib,json
from pathlib import Path
import pandas as pd

ROOT=Path(__file__).resolve().parents[1];BASE=ROOT/'china_market';RAW=BASE/'raw';OUT=BASE/'normalized'
URLS={
 'ETS_2024':'https://www.mee.gov.cn/ywgz/ydqhbh/syqhbh/202501/t20250105_1099975.shtml',
 'ETS_CCER_2025':'https://www.mee.gov.cn/ywgz/ydqhbh/wsqtkz/202601/t20260101_1139528.shtml',
 'GEC_2024':'https://www.nea.gov.cn/download/zglsdlzsfzbg2024.pdf',
 'GEC_2025':'https://www.nea.gov.cn/20260522/a6cedbcbc2764b80abc85836ee862461/c.html'}
FILES={'ETS_2024':'mee_national_ets_2024.html','ETS_CCER_2025':'mee_national_ets_ccer_2025.html','GEC_2024':'nea_green_certificate_report_2024.pdf','GEC_2025':'nea_green_certificate_2025.html'}
def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def main():
 OUT.mkdir(parents=True,exist_ok=True)
 rows=[
  {'market':'NATIONAL_ETS','period':'2024','timestamp':'2024-12-31T00:00:00Z','carbon_price_per_t':97.49,'price_basis':'year-end closing price','trading_volume_t':189_000_000,'trading_amount_yuan':18_114_000_000,'source_key':'ETS_2024'},
  {'market':'NATIONAL_ETS','period':'2025','timestamp':'2025-12-31T00:00:00Z','carbon_price_per_t':62.36,'price_basis':'annual average price','year_end_price_per_t':74.63,'trading_volume_t':235_000_000,'trading_amount_yuan':14_630_000_000,'source_key':'ETS_CCER_2025'},
  {'market':'NATIONAL_CCER','period':'2025','timestamp':'2025-12-31T00:00:00Z','ccer_price_per_t':70.76,'price_basis':'annual average price','ccer_volume_t':9_219_400,'ccer_trading_amount_yuan':650_000_000,'source_key':'ETS_CCER_2025'},
  {'market':'NATIONAL_GEC','period':'2024','timestamp':'2024-12-31T00:00:00Z','green_certificate_issued_count':4_734_000_000,'green_certificate_traded_count':446_000_000,'green_certificate_volume':446_000_000,'green_certificate_price':5.59,'price_basis':'annual standalone-trade average','source_key':'GEC_2024'},
  {'market':'NATIONAL_GEC','period':'2025','timestamp':'2025-12-31T00:00:00Z','green_certificate_issued_count':2_947_000_000,'green_certificate_traded_count':930_000_000,'green_certificate_volume':930_000_000,'green_certificate_price':5.57,'price_basis':'2025 production-year certificate average','source_key':'GEC_2025'},
 ]
 frame=pd.DataFrame(rows);frame['region']='中国全国市场';frame['data_class']='REAL_PUBLIC_OFFICIAL';frame.to_csv(OUT/'china_market_statistics.csv',index=False)
 manifest={'data_class':'REAL_PUBLIC_OFFICIAL','record_count':len(rows),'original_granularity':'ANNUAL','records_by_market':frame.groupby('market').size().to_dict(),'sources':{k:{'url':URLS[k],'file':FILES[k],'sha256':digest(RAW/FILES[k])} for k in URLS},'limitations':['national aggregate statistics, not enterprise transactions or holdings','CCER has one annual observation; no synthetic trend','no interpolation or conversion to daily/monthly frequency']}
 (BASE/'manifest.json').write_text(json.dumps(manifest,indent=2,ensure_ascii=False),encoding='utf-8');print(json.dumps(manifest,indent=2,ensure_ascii=False))
if __name__=='__main__':main()
