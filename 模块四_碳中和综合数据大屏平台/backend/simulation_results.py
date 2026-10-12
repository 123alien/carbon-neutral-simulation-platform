"""Campus-isolated, read-only path projection from module-one run snapshots."""
from backend.adapters import get_json
from backend.prediction_interval import build_prediction_interval


def select_paths(runs, scenarios, site_id):
    lookup = {s['current_version_id']: s for s in scenarios if s.get('current_version_id')}
    valid = []
    for run in sorted(runs, key=lambda r: r['id'], reverse=True):
        snapshot = run.get('input_snapshot_json') or {}
        frozen = snapshot.get('unified_baseline') or {}
        provenance = frozen.get('provenance') or {}
        if (run.get('status') != 'SUCCESS' or snapshot.get('site_id') != site_id or
            provenance.get('site_id') != site_id or provenance.get('campus_id') != 'HBUE' or not frozen.get('checksum')):
            continue
        if not run.get('result_snapshot_json', {}).get('annual'):
            continue
        valid.append(run)
    originals = [r for r in valid if not r['input_snapshot_json'].get('source_run_id')]
    selected = next((r for r in originals if lookup.get(r['scenario_version_id'], {}).get('scenario_type') == 'BALANCED'), None)
    selected = selected or next((r for r in originals if lookup.get(r['scenario_version_id'], {}).get('scenario_type') != 'BASELINE'), None)
    selected = selected or (originals[0] if originals else None)
    if selected is None:
        return {'campus_id': 'HBUE', 'paths': [], 'data_notice': '当前校园尚无长期推演结果'}
    checksum = selected['input_snapshot_json']['unified_baseline']['checksum']
    compatible = [r for r in valid if r['input_snapshot_json']['unified_baseline']['checksum'] == checksum]
    baseline = next((r for r in compatible if not r['input_snapshot_json'].get('source_run_id') and
                     lookup.get(r['scenario_version_id'], {}).get('scenario_type') == 'BASELINE'), None)
    strengthened = next((r for r in compatible if r['input_snapshot_json'].get('source_run_id') == selected['id']), None)
    paths = []
    for role, name, run in [('baseline', '基准路径', baseline), ('low_carbon', '低碳路径', selected), ('strengthened', '强化情景', strengthened)]:
        if run is None or (role == 'low_carbon' and baseline and run['id'] == baseline['id']):
            continue
        snapshot = run['input_snapshot_json']
        result = run['result_snapshot_json']
        assumptions = {k: snapshot.get(k) for k in ('start_year','end_year','target_peak_year','target_neutral_year',
                          'annual_load_growth_rate','annual_grid_factor_change_rate','carbon_quota_t','annual_quota_change_rate',
                          'electricity_price_per_kwh','annual_price_change_rate','carbon_price_per_t','neutrality_threshold_t')}
        paths.append({'role': role, 'name': name, 'run_id': run['id'], 'source_run_id': snapshot.get('source_run_id'),
                      'scenario_version_id': run['scenario_version_id'], 'created_at': run['created_at'],
                      'campus_id': 'HBUE', 'site_id': site_id, 'data_class': 'DEMO_SIMULATION',
                      'baseline_checksum': checksum, 'result': result,
                      'prediction_interval': build_prediction_interval(result, assumptions, run['id']),
                      'assumptions': assumptions,
                      'measures': snapshot.get('resolved_measures') or snapshot.get('measures') or []})
    return {'campus_id': 'HBUE', 'site_id': site_id, 'paths': paths, 'selected_run_id': selected['id'],
            'data_notice': '示范仿真数据', 'baseline_checksum': checksum,
            'limitations': ['基于模块一冻结校园小时基准，后续年度为状态演化近似。',
                           '投资为模型仿真假设，不是学校工程报价；中和年份不是确定性承诺。',
                           '95%预测区间由模块四对模型参数进行Monte Carlo传播；当前为演示校准，未使用学校历史预测误差。']}


async def read_paths(client, site):
    runs = await get_json(client, f'/api/simulation/long-term/runs?enterprise_id={site["enterprise_id"]}&limit=100')
    scenarios = await get_json(client, f'/api/scenarios?enterprise_id={site["enterprise_id"]}')
    return select_paths(runs, scenarios, site['id'])
