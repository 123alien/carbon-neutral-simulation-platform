"""Versioned, safe and locally persisted dynamic metric rules for module four."""
from __future__ import annotations

import ast
import json
import os
import threading
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
STORE_PATH = Path(os.environ.get("METRIC_RULES_PATH") or ROOT / "data" / "metric_rules.json")
LOCK = threading.Lock()
ALLOWED_FUNCTIONS = {"abs": abs, "min": min, "max": max, "round": round}
ALLOWED_NODES = (
    ast.Expression, ast.BinOp, ast.UnaryOp, ast.Name, ast.Load, ast.Constant,
    ast.Add, ast.Sub, ast.Mult, ast.Div, ast.Pow, ast.Mod, ast.USub, ast.UAdd,
    ast.Call,
)

DEFAULT_STORE = {
    "active_version": 1,
    "published_at": "2026-09-29T00:00:00+08:00",
    "change_note": "初始动态指标规则",
    "parameters": {"emission_factor_kg_per_kwh": 0.57},
    "rules": [
        {"code": "calculated_emission", "name": "规则核算碳排", "unit": "tCO₂e", "category": "碳核算", "formula": "electricity_kwh * emission_factor_kg_per_kwh / 1000", "precision": 1, "enabled": True},
        {"code": "carbon_intensity", "name": "用电碳排强度", "unit": "kgCO₂e/kWh", "category": "能效评价", "formula": "carbon_t * 1000 / electricity_kwh", "precision": 4, "enabled": True},
        {"code": "renewable_avoidance", "name": "可再生能源减排量", "unit": "tCO₂e", "category": "碳核算", "formula": "renewable_generation_kwh * emission_factor_kg_per_kwh / 1000", "precision": 1, "enabled": True},
        {"code": "renewable_self_sufficiency", "name": "可再生能源自给率", "unit": "%", "category": "能效评价", "formula": "renewable_generation_kwh / electricity_kwh * 100", "precision": 2, "enabled": True},
    ],
    "history": [],
}


class FormulaError(ValueError):
    pass


def _load() -> dict:
    if not STORE_PATH.exists():
        return deepcopy(DEFAULT_STORE)
    try:
        value = json.loads(STORE_PATH.read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else deepcopy(DEFAULT_STORE)
    except (OSError, json.JSONDecodeError):
        return deepcopy(DEFAULT_STORE)


def get_store() -> dict:
    with LOCK:
        return deepcopy(_load())


def _validate_formula(formula: str, variables: set[str]) -> ast.Expression:
    if not formula or len(formula) > 300:
        raise FormulaError("公式不能为空且不得超过300字符")
    try:
        tree = ast.parse(formula, mode="eval")
    except SyntaxError as exc:
        raise FormulaError("公式语法错误") from exc
    for node in ast.walk(tree):
        if not isinstance(node, ALLOWED_NODES):
            raise FormulaError(f"公式包含不允许的语法：{type(node).__name__}")
        if isinstance(node, ast.Name) and node.id not in variables and node.id not in ALLOWED_FUNCTIONS:
            raise FormulaError(f"未知变量：{node.id}")
        if isinstance(node, ast.Call):
            if not isinstance(node.func, ast.Name) or node.func.id not in ALLOWED_FUNCTIONS:
                raise FormulaError("只允许使用 abs、min、max、round 函数")
            if node.keywords:
                raise FormulaError("函数不支持关键字参数")
    return tree


def evaluate_formula(formula: str, variables: dict[str, float]) -> float:
    tree = _validate_formula(formula, set(variables))
    try:
        result = eval(compile(tree, "<metric-rule>", "eval"), {"__builtins__": {}}, {**ALLOWED_FUNCTIONS, **variables})
    except ZeroDivisionError as exc:
        raise FormulaError("公式发生除零") from exc
    except (TypeError, ValueError, OverflowError) as exc:
        raise FormulaError("公式计算失败") from exc
    if not isinstance(result, (int, float)) or isinstance(result, bool):
        raise FormulaError("公式结果必须是数值")
    if result != result or result in (float("inf"), float("-inf")):
        raise FormulaError("公式结果不是有限数值")
    return float(result)


def dashboard_variables(data: dict, parameters: dict | None = None) -> dict[str, float]:
    metrics = {row.get("code"): row.get("value") for row in data.get("metrics", [])}
    current = data.get("current") or {}
    values = {
        "electricity_kwh": float(metrics.get("electricity") or 0),
        "water_m3": float(metrics.get("water") or 0),
        "carbon_t": float(metrics.get("carbon") or 0),
        "renewable_ratio_pct": float(metrics.get("renewable") or 0),
        "load_kw": float(metrics.get("load") or 0),
        "storage_kwh": float(metrics.get("storage") or 0),
        "renewable_generation_kwh": float(current.get("renewable_generation_kwh") or 0),
    }
    values.update({k: float(v) for k, v in (parameters or {}).items()})
    return values


def evaluate_rules(rules: list[dict], parameters: dict, variables: dict) -> list[dict]:
    context = {**variables, **{k: float(v) for k, v in parameters.items()}}
    results = []
    seen = set()
    for rule in rules:
        code = str(rule.get("code") or "").strip()
        if not code or not code.replace("_", "a").isalnum() or code in seen:
            raise FormulaError("指标编码必须唯一且仅包含字母、数字和下划线")
        seen.add(code)
        if not rule.get("enabled", True):
            continue
        precision = max(0, min(6, int(rule.get("precision", 2))))
        try:
            value = round(evaluate_formula(str(rule.get("formula") or ""), context), precision)
            error = None
        except FormulaError as exc:
            value, error = None, str(exc)
        results.append({
            "code": code, "name": str(rule.get("name") or code)[:40], "unit": str(rule.get("unit") or "")[:20],
            "category": str(rule.get("category") or "自定义指标")[:20], "formula": str(rule.get("formula") or ""),
            "precision": precision, "value": value, "error": error,
        })
    return results


def preview(payload: dict, dashboard_data: dict) -> dict:
    rules = payload.get("rules") or []
    parameters = payload.get("parameters") or {}
    variables = dashboard_variables(dashboard_data, parameters)
    return {"variables": variables, "results": evaluate_rules(rules, parameters, variables)}


def publish(payload: dict, dashboard_data: dict) -> dict:
    rules = payload.get("rules") or []
    parameters = payload.get("parameters") or {}
    checked = preview({"rules": rules, "parameters": parameters}, dashboard_data)
    errors = [x for x in checked["results"] if x["error"]]
    if errors:
        raise FormulaError("存在无法发布的公式：" + "；".join(f"{x['name']}：{x['error']}" for x in errors))
    with LOCK:
        old = _load()
        expected = payload.get("expected_version")
        if expected is not None and int(expected) != int(old.get("active_version") or 0):
            raise FormulaError("规则版本已被其他操作更新，请重新加载后再发布")
        now = datetime.now(timezone.utc).isoformat()
        version = int(old.get("active_version") or 0) + 1
        history = list(old.get("history") or [])[-9:]
        history.append({k: deepcopy(old.get(k)) for k in ("active_version", "published_at", "change_note", "parameters", "rules")})
        store = {
            "active_version": version, "published_at": now,
            "change_note": str(payload.get("change_note") or "更新动态指标规则")[:100],
            "parameters": {k: float(v) for k, v in parameters.items()}, "rules": deepcopy(rules), "history": history,
        }
        STORE_PATH.parent.mkdir(parents=True, exist_ok=True)
        temporary = STORE_PATH.with_suffix(".tmp")
        temporary.write_text(json.dumps(store, ensure_ascii=False, indent=2), encoding="utf-8")
        temporary.replace(STORE_PATH)
    return {**store, "preview": checked}


def rollback(target_version: int, expected_version: int, dashboard_data: dict) -> dict:
    with LOCK:
        current = _load()
        active = int(current.get("active_version") or 0)
        if int(expected_version) != active:
            raise FormulaError("规则版本已被其他操作更新，请重新加载后再回滚")
        candidates = list(current.get("history") or [])
        if int(target_version) == active:
            raise FormulaError("目标版本已经是当前生效版本")
        target = next((item for item in candidates if int(item.get("active_version") or -1) == int(target_version)), None)
        if target is None:
            raise FormulaError("目标历史版本不存在或已超出保留范围")
        checked = preview({"rules": target.get("rules") or [], "parameters": target.get("parameters") or {}}, dashboard_data)
        errors = [x for x in checked["results"] if x["error"]]
        if errors:
            raise FormulaError("历史版本当前无法计算，拒绝回滚")
        now = datetime.now(timezone.utc).isoformat()
        history = candidates[-9:]
        history.append({k: deepcopy(current.get(k)) for k in ("active_version", "published_at", "change_note", "parameters", "rules")})
        store = {
            "active_version": active + 1, "published_at": now,
            "change_note": f"回滚至 V{target_version} 的规则内容",
            "parameters": deepcopy(target.get("parameters") or {}), "rules": deepcopy(target.get("rules") or []),
            "history": history,
        }
        STORE_PATH.parent.mkdir(parents=True, exist_ok=True)
        temporary = STORE_PATH.with_suffix(".tmp")
        temporary.write_text(json.dumps(store, ensure_ascii=False, indent=2), encoding="utf-8")
        temporary.replace(STORE_PATH)
    return {**store, "preview": checked, "rolled_back_from": target_version}


def apply_to_dashboard(data: dict) -> None:
    store = get_store()
    variables = dashboard_variables(data, store.get("parameters"))
    data["dynamic_metrics"] = evaluate_rules(store.get("rules") or [], store.get("parameters") or {}, variables)
    data["metric_rule_version"] = store.get("active_version")
    data["metric_rule_published_at"] = store.get("published_at")
