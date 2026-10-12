"""Backend-for-frontend contract for the acceptance overview.

The BFF owns orchestration and vocabulary normalization only.  Simulation,
edge collection and cross-camera algorithms remain in their source systems.
"""
from __future__ import annotations

import asyncio
import os
from datetime import datetime, timezone
from urllib.parse import urlencode

from backend import adapters

SCHEMA_VERSION = "1.0"


def _entry(env_name: str, default: str, label: str, params: dict) -> dict:
    base = os.environ.get(env_name, default).strip()
    clean = {key: value for key, value in params.items() if value not in (None, "")}
    separator = "&" if "?" in base else "?"
    return {"label": label, "url": base + (separator + urlencode(clean) if clean else ""), "params": clean}


def _status(source: dict | None, ready: tuple[str, ...]) -> str:
    value = (source or {}).get("status")
    if value in ready:
        return "READY"
    if value in ("NO_OBSERVATIONS", "ON_DEMAND", "DEMO_SIMULATION"):
        return "DEGRADED"
    if value in ("NOT_CONNECTED", "ERROR"):
        return "OFFLINE"
    return "UNCONFIGURED"


def _metric(code: str, name: str, value, unit: str, data_class: str, quality: str = "VALID") -> dict:
    return {"code": code, "name": name, "value": value, "unit": unit,
            "data_class": data_class, "quality_status": quality}


def _simulation(data: dict) -> dict:
    source = next((x for x in data.get("sources", []) if x.get("id") == "simulation"), {})
    paths = (data.get("simulation") or {}).get("paths") or []
    selected = next((p for p in paths if p.get("role") == "low_carbon"), paths[0] if paths else {})
    interval = selected.get("prediction_interval") or {}
    points = [{"x": p.get("year"), "p10": p.get("p10_t"), "p50": p.get("p50_t"), "p90": p.get("p90_t")}
              for p in interval.get("points", [])]
    metric_lookup = {m.get("code"): m for m in data.get("metrics", [])}
    metrics = []
    for code in ("carbon", "renewable", "load"):
        item = metric_lookup.get(code)
        if item:
            metrics.append(_metric(code, item.get("name"), item.get("value"), item.get("unit", ""),
                                   item.get("data_class", "DEMO_SIMULATION"), item.get("quality_status", "SIMULATED")))
    sim = data.get("simulation") or {}
    return {"id": "simulation", "name": "碳仿真推演", "kind": "SIMULATION",
            "status": _status(source, ("OBSERVED", "LIVE_READY")) if not paths else "READY",
            "message": source.get("message") or sim.get("data_notice") or "等待推演结果",
            "observed_at": selected.get("created_at") or data.get("observation_time"),
            "data_class": selected.get("data_class") or "DEMO_SIMULATION", "metrics": metrics,
            "alerts": [], "series": [{"code": "net_emission_p10_p50_p90", "name": "净碳排预测分位区间", "unit": "tCO₂e", "points": points}] if points else [],
            "resources": {"scenario_count": len(paths), "run_id": selected.get("run_id"), "scenario_version_id": selected.get("scenario_version_id")},
            "entry": _entry("SIMULATION_ENTRY_URL", "http://10.120.45.223:5173/dashboard", "进入仿真系统",
                            {"campus_id": "HBUE", "site_id": sim.get("site_id"), "run_id": selected.get("run_id"), "scenario_version_id": selected.get("scenario_version_id")})}


def _edge(payload: dict) -> dict:
    boxes = payload.get("boxes") or []
    online = sum(1 for box in boxes if box.get("online") is True)
    offline = sum(1 for box in boxes if box.get("online") is False)
    algorithms = sum(int(box.get("running_algorithms") or 0) for box in boxes)
    algorithm_alerts = [{"code": "EDGE_ALGORITHM_ALARM", "level": alarm.get("level") or "WARNING", "title": alarm.get("title") or "算法告警",
                         "object_id": alarm.get("box_id"), "occurred_at": alarm.get("occurred_at")} for alarm in payload.get("alarms", [])]
    channel_alerts = [{"code": "EDGE_CHANNEL_OFFLINE", "level": "WARNING",
                       "title": f"摄像头点位 {channel.get('name') or channel.get('channel_id')} 离线",
                       "object_id": str(channel.get("channel_id")), "occurred_at": payload.get("observed_at")}
                      for box in boxes for channel in (box.get("channels") or []) if channel.get("online") is False]
    alerts = algorithm_alerts + channel_alerts
    if not payload.get("configured"):
        status = "UNCONFIGURED"
    elif payload.get("status") == "OFFLINE":
        status = "OFFLINE"
    else:
        status = "READY" if boxes and online > 0 and offline == 0 else "DEGRADED"
    return {"id": "edge", "name": "识别采集", "kind": "EDGE_COLLECTION", "status": status,
            "message": payload.get("message") or "边缘盒子状态与算法告警", "observed_at": payload.get("observed_at"),
            "data_class": "OBSERVED", "metrics": [_metric("edge_box_total", "边缘盒子", len(boxes) if payload.get("configured") else None, "台", "OBSERVED", "UNKNOWN" if not payload.get("configured") else "VALID"),
                _metric("edge_box_online", "在线盒子", online if payload.get("configured") else None, "台", "OBSERVED"),
                _metric("running_algorithms", "已配置算法" if "configured_algorithms" in payload else "运行算法", payload.get("configured_algorithms", algorithms) if payload.get("configured") else None, "项", "OBSERVED"),
                _metric("algorithm_alerts", "算法告警", len(algorithm_alerts) if payload.get("configured") and payload.get("alarms_available", True) else None, "条", "OBSERVED", "UNKNOWN" if not payload.get("alarms_available", True) else "WARNING" if algorithm_alerts else "VALID")],
            "alerts": alerts, "series": [], "resources": {"boxes": boxes, "online": online, "offline": offline},
            "entry": ({"label": "进入边缘盒子系统", "url": "/api/edge-entry", "params": {}}
                      if os.environ.get('EDGE_SHARED_ADMIN_ACCESS', '').lower() == 'true' else
                      _entry("EDGE_ENTRY_URL", os.environ.get("EDGE_BOX_BASE_URL", "http://10.120.45.223:5173/dashboard") + ("/#/login" if os.environ.get("EDGE_BOX_BASE_URL") else ""), "进入边缘盒子系统", {}))}


def _cross_camera(data: dict, tasks: list | None, health: dict | None) -> dict:
    source = next((x for x in data.get("sources", []) if x.get("id") == "cross_camera"), {})
    tasks = tasks or []
    latest = tasks[0] if tasks else {}
    ready = bool((health or {}).get("upstream_reachable") and (health or {}).get("login_success") and (health or {}).get("token_valid"))
    status = "READY" if ready else _status(source, ("LIVE_READY",))
    task_id = latest.get("task_id")
    alerts = [] if ready else [{"code": "CROSS_CAMERA_NOT_READY", "level": "WARNING", "title": (health or {}).get("message") or "跨镜服务未就绪", "object_id": None, "occurred_at": None}]
    return {"id": "cross_camera", "name": "跨镜追踪", "kind": "CROSS_CAMERA", "status": status,
            "message": (health or {}).get("message") or source.get("message") or "真实任务按需读取",
            "observed_at": latest.get("created_at"), "data_class": "OBSERVED", "metrics": [
                _metric("task_count", "可用任务", len(tasks), "个", "OBSERVED"),
                _metric("service_ready", "服务就绪", 1 if ready else 0, "", "OBSERVED", "VALID" if ready else "WARNING")],
            "alerts": alerts, "series": [], "resources": {"task_count": len(tasks), "latest_task_id": task_id},
            "entry": _entry("CROSS_GATEWAY_ENTRY_URL", "/api/cross-entry", "进入跨镜追踪", {"task_id": task_id})
                      if os.environ.get('CROSS_SHARED_ADMIN_ACCESS', '').lower() == 'true' else
                      _entry("CROSS_CAMERA_ENTRY_URL", "http://10.120.203.134:5174/embed/analysis", "进入跨镜追踪",
                            {"campus_id": "HBUE", "task_id": task_id})}


async def overview(force: bool = False) -> dict:
    data = await adapters.dashboard(force)
    task_result, health_result, edge_result = await asyncio.gather(adapters.cross_camera_status("tasks"), adapters.cross_camera_status("health"), adapters.edge_box_overview(), return_exceptions=True)
    tasks = task_result if isinstance(task_result, list) else []
    health = health_result if isinstance(health_result, dict) else {}
    edge = edge_result if isinstance(edge_result, dict) else {'configured': True, 'status': 'OFFLINE', 'message': '边缘盒子接口读取失败'}
    systems = [_simulation(data), _edge(edge), _cross_camera(data, tasks, health)]
    states = {name: sum(1 for s in systems if s["status"] == name) for name in ("READY", "DEGRADED", "OFFLINE", "UNCONFIGURED")}
    current = data.get("current") or {}
    buildings = sorted(data.get("building_results") or [], key=lambda x: float(x.get("emission_t") or 0), reverse=True)[:6]
    renewable = next((m.get("value") for m in data.get("metrics", []) if m.get("code") == "renewable"), None)
    prediction = (systems[0].get("series") or [{}])[0].get("points") or []
    status_score = {"READY": 100, "DEGRADED": 60, "OFFLINE": 0, "UNCONFIGURED": 0}
    visualizations = {
        "prediction": prediction,
        "building_ranking": [{"name": x.get("name"), "value": x.get("emission_t")} for x in buildings],
        "renewable_ratio": renewable,
        "energy_flow": {"nodes": [{"name": name} for name in ("电网", "光伏", "风电", "储能", "校园负荷", "充电桩")],
                        "links": [{"source": "电网", "target": "校园负荷", "value": current.get("grid_power_kwh") or 0},
                                  {"source": "光伏", "target": "校园负荷", "value": current.get("pv_generation_kwh") or 0},
                                  {"source": "风电", "target": "校园负荷", "value": current.get("wind_generation_kwh") or 0},
                                  {"source": "储能", "target": "校园负荷", "value": current.get("storage_discharge_kwh") or 0},
                                  {"source": "校园负荷", "target": "充电桩", "value": current.get("ev_charging_load_kwh") or 0}]},
        "system_health": [{"name": s["name"], "value": status_score[s["status"]], "status": s["status"]} for s in systems],
        "data_notice": "建筑、能源流与占比来自校园示范仿真结果；系统健康度由BFF状态枚举换算，不代表设备性能评分。"
    }
    return {"schema_version": SCHEMA_VERSION, "campus": {"id": "HBUE", "name": data.get("campus_name", "湖北经济学院智慧低碳校园")},
            "generated_at": datetime.now(timezone.utc).isoformat(), "observation_time": data.get("observation_time"),
            "systems": systems, "map": {"building_results": data.get("building_results") or [], "edge_boxes": edge.get("boxes") or []},
            "visualizations": visualizations,
            "summary": {**states, "system_count": len(systems), "alert_count": sum(len(s["alerts"]) for s in systems)},
            "contract_notice": "BFF仅做取数、口径归一和下钻参数编排；算法与业务数据由各上游系统负责。"}
