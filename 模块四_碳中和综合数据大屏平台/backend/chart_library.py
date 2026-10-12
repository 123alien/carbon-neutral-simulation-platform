"""Declarative chart registry exposed by the BFF.

Definitions describe how normalized BFF fields bind to reusable chart types.
They contain no business values and therefore remain stable across refreshes.
"""
SCHEMA_VERSION = "1.0"

DEFINITIONS = [
    {"id":"simulation_interval","title":"仿真预测分位区间","type":"line","data_path":"visualizations.prediction","unit":"tCO₂e",
     "bindings":{"x":"x","series":[{"field":"p10","name":"P10"},{"field":"p50","name":"P50"},{"field":"p90","name":"P90"}]},
     "refresh_seconds":30,"interactions":["tooltip","legend","downstream"],"data_class":"DEMO_MODEL_INTERVAL"},
    {"id":"building_emission_ranking","title":"建筑碳排排行","type":"bar","data_path":"visualizations.building_ranking","unit":"tCO₂e",
     "bindings":{"category":"name","value":"value"},"refresh_seconds":30,"interactions":["tooltip","downstream"],"data_class":"DEMO_SIMULATION"},
    {"id":"renewable_ratio","title":"可再生能源占比","type":"gauge","data_path":"visualizations.renewable_ratio","unit":"%",
     "bindings":{"value":"$value"},"refresh_seconds":30,"interactions":["tooltip"],"data_class":"DEMO_SIMULATION"},
    {"id":"campus_energy_flow","title":"校园能源流向","type":"sankey","data_path":"visualizations.energy_flow","unit":"kWh",
     "bindings":{"nodes":"nodes","links":"links","source":"source","target":"target","value":"value"},
     "refresh_seconds":30,"interactions":["tooltip","highlight"],"data_class":"DEMO_SIMULATION"},
    {"id":"upstream_health","title":"上游接入健康度","type":"radar","data_path":"visualizations.system_health","unit":"分",
     "bindings":{"indicator":"name","value":"value","maximum":100},"refresh_seconds":30,"interactions":["tooltip"],"data_class":"DERIVED_STATUS"},
]


def library():
    allowed={"line","bar","gauge","sankey","radar"}
    assert all(item["type"] in allowed and item.get("data_path") and item.get("bindings") for item in DEFINITIONS)
    return {"schema_version":SCHEMA_VERSION,"definitions":DEFINITIONS,
            "contract_notice":"图表定义只描述组件和字段绑定；业务数值由/api/bff/overview提供。"}
