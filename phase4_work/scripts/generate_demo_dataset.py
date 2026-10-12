"""Generate deterministic DEVELOPMENT/DEMO/VALIDATION files for P3-1.

This script only writes demo_data. It never opens or mutates a database.
"""
from __future__ import annotations

import csv
import json
import math
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "demo_data"
INVALID = OUT / "invalid"
START = datetime(2024, 1, 1)
HOURS = 8784


def write_json(name: str, value: object) -> None:
    (OUT / name).write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


def write_csv(path: Path, fields: list[str], rows: list[dict]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def load_components(ts: datetime) -> tuple[float, dict[str, float]]:
    h, doy = ts.hour, ts.timetuple().tm_yday
    weekday = ts.weekday() < 5
    occupied = 1.0 if weekday and 8 <= h < 19 else 0.30 if 7 <= h < 22 else 0.12
    summer = max(0.0, math.sin(math.pi * (doy - 130) / 180))
    winter = max(0.0, math.cos(2 * math.pi * (doy - 15) / 366))
    smooth = 1 + 0.025 * math.sin(doy * 0.73 + h * 1.31)
    ev = (8 + (68 if weekday and (8 <= h < 10 or 17 <= h < 20) else 24 if 10 <= h < 22 else 0)) * smooth
    parts = {
        "b01_office_a_kw": (55 + 300 * occupied + 110 * summer * occupied + 42 * winter * occupied) * smooth,
        "b02_office_b_kw": (48 + 255 * occupied + 92 * summer * occupied + 36 * winter * occupied) * smooth,
        "b03_lab_kw": (92 + 265 * (0.45 + 0.55 * occupied) + 78 * summer) * smooth,
        "b04_service_kw": ((45 + 160 * (0.35 + 0.65 * occupied) + 58 * summer) + ev) * smooth,
        "ev_charging_kw": ev * 0.58,
    }
    parts = {k: v * 0.58 if k != "ev_charging_kw" else v for k, v in parts.items()}
    total = sum(v for k,v in parts.items() if k != "ev_charging_kw")
    return round(total, 3), {k: round(v, 3) for k, v in parts.items()}


def weather(ts: datetime) -> dict[str, float]:
    doy, h = ts.timetuple().tm_yday, ts.hour
    seasonal = 17 + 12 * math.sin(2 * math.pi * (doy - 105) / 366)
    temperature = seasonal + 5 * math.sin(2 * math.pi * (h - 8) / 24)
    humidity = max(28, min(92, 68 - 0.9 * (temperature - 18) + 6 * math.sin(doy * 0.17)))
    daylight = max(0.0, math.sin(math.pi * (h - 6) / 13))
    cloud = max(5, min(92, 38 + 22 * math.sin(doy * 0.31) + 10 * math.sin(h * 0.77)))
    clear = 1 - 0.0065 * cloud
    ghi = max(0.0, 880 * daylight * clear * (0.82 + 0.18 * math.sin(2 * math.pi * (doy - 80) / 366)))
    dni = max(0.0, ghi * (0.72 + 0.12 * clear))
    dhi = max(0.0, ghi - dni * 0.72)
    wind = max(0.4, 4.8 + 1.7 * math.sin(doy * 0.19 + h * 0.41) + 0.7 * math.cos(doy * 0.07))
    return {"temperature_c": round(temperature, 2), "humidity_pct": round(humidity, 2), "ghi_w_m2": round(ghi, 2), "dni_w_m2": round(dni, 2), "dhi_w_m2": round(dhi, 2), "wind_speed_m_s": round(wind, 2), "cloud_cover_pct": round(cloud, 2)}


def main() -> None:
    OUT.mkdir(exist_ok=True)
    INVALID.mkdir(exist_ok=True)
    write_json("site.json", {"data_classification":"DEMO_SIMULATION","code":"DEMO-PARK-001","name":"智慧低碳示范园区","site_type":"PARK","timezone":"Asia/Shanghai","address":"示范园区仿真场景（非真实企业）","area_m2":33800,"population":1580,"position_json":{"coordinate_system":"LOCAL","x":0,"y":0,"z":0}})
    buildings = [
        ("B01","办公楼A","OFFICE",9800,12,520,-38,0,-22),
        ("B02","办公楼B","OFFICE",8200,9,430,25,0,-25),
        ("B03","实验楼","LAB",8800,8,390,48,0,22),
        ("B04","综合服务楼","SERVICE",7000,6,240,-24,0,36),
    ]
    write_json("buildings.json", [{"code":c,"name":n,"building_type":t,"area_m2":a,"floor_count":f,"population":p,"position_json":{"coordinate_system":"LOCAL","x":x,"y":y,"z":z}} for c,n,t,a,f,p,x,y,z in buildings])
    write_json("devices.json", {"data_classification":"DEMO_SIMULATION","energy_systems":[{"code":"ES-ELEC","name":"园区电网系统","system_type":"ELECTRICITY"},{"code":"ES-PV","name":"分布式光伏系统","system_type":"PV"},{"code":"ES-WIND","name":"风力发电系统","system_type":"WIND"},{"code":"ES-STORAGE","name":"储能系统","system_type":"STORAGE"},{"code":"ES-HVAC","name":"空调系统","system_type":"HVAC"},{"code":"ES-LIGHT","name":"照明系统","system_type":"LIGHTING"},{"code":"ES-EV","name":"充电桩系统","system_type":"EV_CHARGING"}],"devices":[{"code":"METER-MAIN","name":"园区总电表","type":"ELECTRIC_METER","system":"ES-ELEC","position":[0,1,0]}]+[{"code":f"METER-{b[0]}","name":f"{b[1]}电表","type":"ELECTRIC_METER","building":b[0],"system":"ES-ELEC","position":[2,1,2]} for b in buildings]+[{"code":"PV-INV-01","name":"屋顶光伏系统","type":"PV","building":"B01","system":"ES-PV","position":[0,14,0],"capacity_kw":420},{"code":"WIND-AGG-01","name":"园区风电机组","type":"WIND","building":"B04","system":"ES-WIND","position":[15,1,10],"capacity_kw":120},{"code":"BESS-01","name":"园区储能系统","type":"STORAGE","building":"B03","system":"ES-STORAGE","position":[-8,1,5]},{"code":"HVAC-B01","name":"办公楼A空调系统","type":"HVAC","building":"B01","system":"ES-HVAC","position":[-4,1,-4]},{"code":"HVAC-B02","name":"办公楼B空调系统","type":"HVAC","building":"B02","system":"ES-HVAC","position":[4,1,-4]},{"code":"LIGHT-AGG","name":"园区照明系统","type":"LIGHTING","building":"B04","system":"ES-LIGHT","position":[0,1,0]},{"code":"EV-AGG-20","name":"园区充电桩（20台）","type":"EV_CHARGER","building":"B04","system":"ES-EV","position":[0,1,8]}]})

    loads, weather_rows, prices, factors, device_metrics = [], [], [], [], []
    soc_kwh = 240.0
    for i in range(HOURS):
        ts = START + timedelta(hours=i)
        total, parts = load_components(ts); meteo = weather(ts)
        pv_kw = max(0.0, 420 * meteo["ghi_w_m2"] / 1000 * .82 * (1 - .004 * max(0, meteo["temperature_c"] - 25)))
        wind = meteo["wind_speed_m_s"]
        wind_kw = min(120.0, 120 * (((wind - 3) / 7) ** 3 if 3 <= wind < 10 else 1 if 10 <= wind < 25 else 0))
        charge_kw = min(100.0, max(0.0, pv_kw + wind_kw - total), (432 - soc_kwh) / .95) if ts.hour < 16 else 0.0
        discharge_kw = min(100.0, max(0.0, total - pv_kw - wind_kw), (soc_kwh - 48) * .95) if 17 <= ts.hour < 21 else 0.0
        soc_kwh = min(432.0, max(48.0, soc_kwh + charge_kw * .95 - discharge_kw / .95))
        grid_kw = max(0.0, total + charge_kw - discharge_kw - pv_kw - wind_kw)
        stamp = ts.isoformat(sep=" ")
        loads.append({"timestamp":stamp,"load_kw":total,**parts,"data_classification":"DEMO_SIMULATION"})
        device_metrics.append({"device_external_id":"METER-MAIN","device_name":"园区总电表","device_type":"ELECTRIC_METER","timestamp":stamp,"metric_name":"power_kw","value":round(grid_kw,3),"unit":"kW"})
        for code,key in [("METER-B01","b01_office_a_kw"),("METER-B02","b02_office_b_kw"),("METER-B03","b03_lab_kw"),("METER-B04","b04_service_kw")]:
            device_metrics.append({"device_external_id":code,"device_name":code,"device_type":"ELECTRIC_METER","timestamp":stamp,"metric_name":"power_kw","value":parts[key],"unit":"kW"})
        device_metrics.extend([
            {"device_external_id":"PV-INV-01","device_name":"屋顶光伏系统","device_type":"PV","timestamp":stamp,"metric_name":"power_kw","value":round(pv_kw,3),"unit":"kW"},
            {"device_external_id":"WIND-AGG-01","device_name":"园区风电机组","device_type":"WIND","timestamp":stamp,"metric_name":"power_kw","value":round(wind_kw,3),"unit":"kW"},
            {"device_external_id":"BESS-01","device_name":"园区储能系统","device_type":"STORAGE","timestamp":stamp,"metric_name":"soc_pct","value":round(soc_kwh/480*100,3),"unit":"%"},
            {"device_external_id":"BESS-01","device_name":"园区储能系统","device_type":"STORAGE","timestamp":stamp,"metric_name":"charge_power_kw","value":round(charge_kw,3),"unit":"kW"},
            {"device_external_id":"BESS-01","device_name":"园区储能系统","device_type":"STORAGE","timestamp":stamp,"metric_name":"discharge_power_kw","value":round(discharge_kw,3),"unit":"kW"},
            {"device_external_id":"EV-AGG-20","device_name":"园区充电桩（20台）","device_type":"EV_CHARGER","timestamp":stamp,"metric_name":"power_kw","value":parts["ev_charging_kw"],"unit":"kW"},
            {"device_external_id":"HVAC-B01","device_name":"办公楼A空调系统","device_type":"HVAC","timestamp":stamp,"metric_name":"power_kw","value":round(parts["b01_office_a_kw"]*.36,3),"unit":"kW"},
            {"device_external_id":"HVAC-B02","device_name":"办公楼B空调系统","device_type":"HVAC","timestamp":stamp,"metric_name":"power_kw","value":round(parts["b02_office_b_kw"]*.34,3),"unit":"kW"},
            {"device_external_id":"LIGHT-AGG","device_name":"园区照明系统","device_type":"LIGHTING","timestamp":stamp,"metric_name":"power_kw","value":round((parts["b01_office_a_kw"]+parts["b02_office_b_kw"]+parts["b04_service_kw"])*.14,3),"unit":"kW"},
        ])
        weather_rows.append({"timestamp":stamp,**meteo,"source":"DEMO_SIMULATION"})
        price = 1.10 if (10 <= ts.hour < 12 or 17 <= ts.hour < 21) else 0.40 if (0 <= ts.hour < 7 or ts.hour >= 23) else 0.72
        prices.append({"timestamp":stamp,"purchase_price_per_kwh":price,"feed_in_tariff_per_kwh":0.38,"source":"SYNTHETIC_DEVELOPMENT"})
        ef = 0.56 + 0.045 * math.cos(2 * math.pi * (ts.hour - 2) / 24) - 0.025 * max(0, math.sin(math.pi * (ts.hour - 6) / 13))
        factors.append({"timestamp":stamp,"factor_kg_per_kwh":round(max(0,ef),5),"source":"SYNTHETIC_DEVELOPMENT","version":"DEMO-2024-HOURLY"})
    write_csv(OUT/"hourly_load_2024.csv",list(loads[0]),loads)
    write_csv(OUT/"device_metrics_2024.csv",list(device_metrics[0]),device_metrics)
    write_csv(OUT/"weather_2024.csv",list(weather_rows[0]),weather_rows)
    write_csv(OUT/"electricity_price_2024.csv",list(prices[0]),prices)
    write_csv(OUT/"grid_emission_factor_2024.csv",list(factors[0]),factors)
    gas=[{"month":f"2024-{m:02d}-01","natural_gas_m3":round(12000+5000*max(0,math.cos(2*math.pi*(m-1)/12)),2),"scope":"SCOPE_1","source":"SYNTHETIC_DEVELOPMENT"} for m in range(1,13)]
    write_csv(OUT/"natural_gas_2024.csv",list(gas[0]),gas)
    market=[{"timestamp":f"2024-{m:02d}-01 00:00:00","carbon_price_per_t":round(78+6*math.sin(m*.7),2),"trading_volume_t":50000+m*1700,"carbon_quota_t":2200,"ccer_price_per_t":round(52+3*math.cos(m*.5),2),"green_certificate_price":6.5,"source":"SYNTHETIC_DEVELOPMENT"} for m in range(1,13)]
    write_csv(OUT/"carbon_market_2024.csv",list(market[0]),market)
    write_csv(INVALID/"duplicate_timestamp.csv",["timestamp","load_kw"],[{"timestamp":"2024-01-01 00:00:00","load_kw":500},{"timestamp":"2024-01-01 00:00:00","load_kw":510}])
    write_csv(INVALID/"missing_interval.csv",["timestamp","load_kw"],[{"timestamp":"2024-01-01 00:00:00","load_kw":500},{"timestamp":"2024-01-01 02:00:00","load_kw":520}])
    write_csv(INVALID/"invalid_unit.csv",["timestamp","load"],[{"timestamp":"2024-01-01 00:00:00","load":"not-a-number"}])
    write_csv(INVALID/"out_of_range.csv",["timestamp","temperature_c","humidity_pct","ghi_w_m2"],[{"timestamp":"2024-01-01 12:00:00","temperature_c":99,"humidity_pct":140,"ghi_w_m2":-5}])
    write_csv(INVALID/"future_timestamp.csv",["timestamp","load_kw"],[{"timestamp":"2099-01-01 00:00:00","load_kw":500}])
    annual=sum(x["load_kw"] for x in loads); peak=max(x["load_kw"] for x in loads)
    (OUT/"README.md").write_text(f"""# 碳中和示范园区开发验证数据\n\n- 性质：DEVELOPMENT / DEMO / VALIDATION；非真实企业实测数据。\n- 时区：Asia/Shanghai；时间范围：2024-01-01 00:00 至 2024-12-31 23:00。\n- 小时数：{HOURS}（闰年）；年负荷：{annual/1_000_000:.3f} GWh；峰值：{peak:.3f} kW。\n- 电价：谷 0.40、平 0.72、峰 1.10 元/kWh；上网 0.38 元/kWh。\n- 电网因子：kgCO2e/kWh，版本 DEMO-2024-HOURLY。\n- 所有 CSV 均含字段名和单位语义；invalid 目录只能 Preview，不得 Confirm。\n""",encoding="utf-8")
    readme=OUT/"README.md"
    readme.write_text(readme.read_text(encoding="utf-8").replace("碳中和示范园区开发验证数据","智慧低碳示范园区统一演示数据").replace("DEVELOPMENT / DEMO / VALIDATION；非真实企业实测数据","DEMO_SIMULATION（示范仿真数据）；非真实企业实测或结算数据"),encoding="utf-8")
    print(json.dumps({"hours":HOURS,"annual_load_gwh":round(annual/1_000_000,4),"peak_kw":peak,"output":str(OUT)},ensure_ascii=False))


if __name__ == "__main__":
    main()
