from __future__ import annotations


class CarbonCostEngine:
    """Financial overlay only: never mutates physical simulation results."""

    @staticmethod
    def calculate(gross_emission_t: float, params: dict) -> dict:
        gross = max(float(gross_emission_t), 0.0)
        quota = max(float(params.get("carbon_quota_t", 0)), 0.0)
        carbon_price = max(float(params.get("carbon_price_per_t", 0)), 0.0)
        ccer_available = max(float(params.get("ccer_quantity_t", 0)), 0.0)
        ccer_price = max(float(params.get("ccer_price_per_t", 0)), 0.0)
        certificates = max(float(params.get("green_certificate_quantity", 0)), 0.0)
        certificate_price = max(float(params.get("green_certificate_price", 0)), 0.0)
        excess_before = max(gross - quota, 0.0)
        ccer_offset = min(ccer_available, excess_before)
        excess_after = excess_before - ccer_offset
        surplus = max(quota - gross, 0.0)
        result = {
            "gross_emission_t": gross,
            "carbon_quota_t": quota,
            "quota_balance_t": quota - gross,
            "quota_surplus_t": surplus,
            "excess_emission_before_offset_t": excess_before,
            "ccer_offset_t": ccer_offset,
            "ccer_cost": ccer_offset * ccer_price,
            "excess_emission_after_offset_t": excess_after,
            "excess_emission_cost": excess_after * carbon_price,
            "green_certificate_cost": certificates * certificate_price,
            "quota_surplus_value": surplus * carbon_price,
            "net_carbon_emission_t": max(gross - ccer_offset, 0.0),
        }
        result["comprehensive_carbon_cost"] = (
            result["excess_emission_cost"] + result["ccer_cost"]
            + result["green_certificate_cost"] - result["quota_surplus_value"]
        )
        result["physical_energy_balance_changed"] = False
        return result


class RiskAssessmentEngine:
    LEVEL_SCORE = {"LOW": 0, "MEDIUM": 1, "HIGH": 2}

    @classmethod
    def assess(cls, data: dict) -> dict:
        def risk(category, level, value, reason, advice):
            return {"category": category, "level": level, "indicator_value": value,
                    "trigger_reason": reason, "recommendation": advice}

        year = int(data.get("simulation_year", 0) or 0)
        peak = data.get("target_peak_year")
        neutral = data.get("target_neutral_year")
        reduction = float(data.get("reduction_rate", 0) or 0)
        payback = data.get("payback_years")
        price_vol = float(data.get("price_volatility_pct", 0) or 0)
        renewable_vol = float(data.get("renewable_volatility_pct", 0) or 0)
        implementation = float(data.get("technical_implementation_score", 1) or 0)
        peak_level = "HIGH" if peak and year > peak and reduction <= 0 else ("MEDIUM" if peak and peak-year <= 2 and reduction < .1 else "LOW")
        neutral_level = "HIGH" if neutral and year >= neutral and reduction < .9 else ("MEDIUM" if neutral and neutral-year <= 5 and reduction < .5 else "LOW")
        payback_level = "HIGH" if payback is None else ("HIGH" if payback > 10 else "MEDIUM" if payback > 6 else "LOW")
        price_level = "HIGH" if price_vol >= 30 else "MEDIUM" if price_vol >= 15 else "LOW"
        renewable_level = "HIGH" if renewable_vol >= 30 else "MEDIUM" if renewable_vol >= 15 else "LOW"
        tech_level = "HIGH" if implementation < .4 else "MEDIUM" if implementation < .7 else "LOW"
        risks = [
            risk("PEAK_DELAY", peak_level, {"year": year, "target": peak, "reduction_rate": reduction}, "达峰目标窗口与当前减排进度不匹配" if peak_level != "LOW" else "达峰进度处于可控范围", "提高近期节能和可再生能源措施优先级"),
            risk("NEUTRALITY_DELAY", neutral_level, {"year": year, "target": neutral, "reduction_rate": reduction}, "中和目标剩余时间与减排率存在缺口" if neutral_level != "LOW" else "中和路径进度可控", "滚动复核中和里程碑并准备抵消资源"),
            risk("INVESTMENT_PAYBACK", payback_level, payback, "投资回收期过长或无法形成正向节省" if payback_level != "LOW" else "投资回收期可接受", "分期实施并优先配置短回收期措施"),
            risk("PRICE_VOLATILITY", price_level, price_vol, "电价或碳价波动超过风险阈值" if price_level != "LOW" else "价格波动处于可控范围", "开展敏感性分析并设置价格情景区间"),
            risk("RENEWABLE_VOLATILITY", renewable_level, renewable_vol, "可再生能源出力波动较高" if renewable_level != "LOW" else "可再生能源波动可控", "配置储能、需求响应和备用供能"),
            risk("TECHNICAL_IMPLEMENTATION", tech_level, implementation, "技术适配或实施成熟度不足" if tech_level != "LOW" else "技术实施条件较成熟", "先行试点并设置验收与运维保障机制"),
        ]
        overall = max(risks, key=lambda x: cls.LEVEL_SCORE[x["level"]])["level"]
        return {"overall_level": overall, "risks": risks}


class ReportEngine:
    @staticmethod
    def generate(title: str, sources: dict) -> dict:
        batch = sources.get("scenario_batch") or {}
        risks = sources.get("risk_assessments") or []
        return {
            "schema_version": "1.0",
            "title": title,
            "executive_summary": {
                "scenario_count": len((batch.get("comparison_json") or {}).get("items", [])),
                "overall_risk_levels": [r.get("overall_level") for r in risks],
                "purpose": "碳中和可行性与风险评估",
            },
            "carbon_accounting": sources.get("carbon_accounting"),
            "project": sources.get("project"),
            "energy_and_devices": sources.get("energy_and_devices"),
            "path_recommendations": sources.get("path_recommendations"),
            "scenario_analysis": batch or None,
            "long_term_path": sources.get("long_term_path"),
            "carbon_market": sources.get("carbon_market", []),
            "risk_assessment": risks,
            "model_validation": sources.get("model_validation", []),
            "data_provenance": sources.get("data_provenance"),
            "conclusions": {"note": "报告数据已结构化，可由后续 Word/PDF 渲染器消费。"},
            "provenance": sources.get("provenance", {}),
        }
