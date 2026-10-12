"""Create new HBUE simulation records through module one's public APIs only."""
import argparse
import json
from pathlib import Path

import httpx

TAG = '模块四展示联调 / 示范仿真数据 / HBUE-PATH-1'


def measure(kind, year, **parameters):
    return dict(measure_type=kind, start_year=year, parameters_json={**parameters, 'parameter_source': 'FUNCTION_PARAMETER_ONLY'})


LOW = [
    measure('HVAC', 2026, load_share=.35, saving_rate=.15, capex=900000),
    measure('LIGHTING', 2026, load_share=.12, saving_rate=.3, capex=600000),
    measure('PV', 2027, capacity_kw=1200, annual_yield_kwh_per_kw=1100, performance_ratio=.82, capex=4200000),
    measure('STORAGE', 2028, capacity_kwh=400, max_charge_kw=80, max_discharge_kw=80, capex=800000),
    measure('GREEN_POWER', 2030, purchase_share=.35, premium_per_kwh=.08),
]


def call(client, method, url, **kwargs):
    response = client.request(method, url, **kwargs)
    if not response.is_success:
        raise RuntimeError(f'{method} {url}: HTTP {response.status_code} {response.text[:300]}')
    return response.json()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--base-url', default='http://127.0.0.1:8000')
    parser.add_argument('--execute', action='store_true', help='Create new scenario/task/run records; never overwrite old records')
    args = parser.parse_args()
    if not args.execute:
        print('仅预览：基准路径、低碳路径、强化情景。传入 --execute 创建新的运行记录。')
        return
    outputs = []
    with httpx.Client(base_url=args.base_url, timeout=180, trust_env=False) as client:
        site = next(s for s in call(client, 'GET', '/api/sites') if s['code'] == 'HBUE')
        existing = call(client, 'GET', f'/api/scenarios?enterprise_id={site["enterprise_id"]}')
        runs = call(client, 'GET', f'/api/simulation/long-term/runs?enterprise_id={site["enterprise_id"]}&limit=100')
        plans = [('校园基准路径', 'BASELINE', []), ('校园低碳路径', 'BALANCED', LOW)]
        for name, kind, measures in plans:
            scenario = next((s for s in existing if s['name'] == name and s.get('description') == TAG), None)
            if scenario is None:
                scenario = call(client, 'POST', '/api/scenarios', json=dict(
                    enterprise_id=site['enterprise_id'], name=name, description=TAG, base_year=2024, start_year=2024,
                    end_year=2060, target_peak_year=2030, target_neutral_year=2060,
                    baseline_growth_json={'electricity': .01, 'natural_gas': .01}, scenario_type=kind, measures=measures))
            version = scenario['current_version_id']
            run = next((r for r in runs if r['scenario_version_id'] == version and r['status'] == 'SUCCESS' and
                        r['input_snapshot_json'].get('site_id') == site['id'] and not r['input_snapshot_json'].get('source_run_id')), None)
            if run is None:
                baseline = call(client, 'POST', '/api/simulation/hourly/run', json=dict(site_id=site['id'], scenario_id=scenario['id'],
                    scenario_version_id=version, year=2024, temporary_measures=[], store_hourly_results=False))
                run = call(client, 'POST', '/api/simulation/long-term/run', json=dict(site_id=site['id'], scenario_version_id=version,
                    baseline_task_id=baseline['summary']['task_id'], start_year=2024, end_year=2060,
                    target_peak_year=2030, target_neutral_year=2060, annual_load_growth_rate=.01,
                    annual_grid_factor_change_rate=-.015, carbon_quota_t=10000, annual_quota_change_rate=-.01,
                    electricity_price_per_kwh=.57, annual_price_change_rate=.02, carbon_price_per_t=85,
                    neutrality_threshold_t=1, measures=measures))
            outputs.append(run)
        low = outputs[-1]
        strengthened = next((r for r in runs if r['input_snapshot_json'].get('source_run_id') == low['id']), None)
        if strengthened is None:
            strengthened = call(client, 'POST', f'/api/simulation/long-term/{low["id"]}/strengthen', json=dict(
                pv_annual_addition_kw=100, storage_expansion_year=2034, storage_expansion_kwh=600,
                additional_hvac_saving_rate=.03, additional_lighting_saving_rate=.02,
                green_power_ratio=.95, annual_ccer_t=2500, annual_grid_factor_change_rate=-.025))
        outputs.append(strengthened)
    checksums = {r['input_snapshot_json']['unified_baseline']['checksum'] for r in outputs}
    if len(checksums) != 1:
        raise RuntimeError('三个路径基准校验码不一致，请勿并列比较')
    # Output only non-sensitive simulation IDs and computed summary results.
    for name, run in zip(('基准路径', '低碳路径', '强化情景'), outputs):
        result = run['result_snapshot_json']
        print(json.dumps(dict(name=name, run_id=run['id'], scenario_version_id=run['scenario_version_id'],
            years=len(result['annual']), actual_peak_year=result['actual_peak_year'],
            actual_neutral_year=result['actual_neutral_year'], emission_at_end_t=result['emission_at_end_t'],
            cumulative_investment=result['cumulative_investment'], data_notice='示范仿真数据'), ensure_ascii=False))


if __name__ == '__main__':
    main()
