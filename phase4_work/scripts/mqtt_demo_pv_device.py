"""智慧低碳示范园区光伏逆变器 MQTT 遥测模拟器（仅发送非敏感 Demo 数据）。"""
from __future__ import annotations

import argparse
import json
import math
import random
import time
from datetime import datetime, timezone

import paho.mqtt.client as mqtt

DEFAULT_TOPIC = "carbon-demo/cn-platform-7f3a/DEMO-PARK-001/pv/PV-INV-001/telemetry"


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description="模拟光伏逆变器通过 MQTT 连续上报遥测")
    result.add_argument("--host", default="broker.emqx.io")
    result.add_argument("--port", type=int, default=8883)
    result.add_argument("--topic", default=DEFAULT_TOPIC)
    result.add_argument("--interval", type=float, default=7.0)
    result.add_argument("--no-tls", action="store_true", help="开发环境改用 1883 明文端口")
    result.add_argument("--abnormal", action="store_true", help="每 12 条依次发送缺功率、负功率、过温、重复时间戳")
    result.add_argument("--count", type=int, default=0, help="0 表示持续发送")
    return result


def main() -> None:
    args = parser().parse_args()
    if args.no_tls and args.port == 8883:
        args.port = 1883
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=f"cn-demo-pv-publisher-{random.randint(1000,9999)}")
    if not args.no_tls:
        client.tls_set()
    client.connect(args.host, args.port, 30)
    client.loop_start()
    generation = 1850.3
    last_timestamp: str | None = None
    index = 0
    try:
        while args.count <= 0 or index < args.count:
            now = datetime.now(timezone.utc)
            daylight = max(0.0, math.sin(math.pi * (now.hour + now.minute / 60 - 6) / 12))
            base_power = 430.0 * daylight
            power = max(0.0, base_power + 8 * math.sin(index / 5) + random.uniform(-2.5, 2.5))
            generation += power * args.interval / 3600
            timestamp = now.isoformat().replace("+00:00", "Z")
            payload = {"device_code":"PV-INV-001","timestamp":timestamp,"power_kw":round(power,2),"generation_kwh":round(generation,3),"voltage_v":round(380+1.8*math.sin(index/8),2),"current_a":round(power*1000/(math.sqrt(3)*380),2),"temperature_c":round(28+daylight*14+1.2*math.sin(index/10),2),"status":"NORMAL"}
            if args.abnormal and index and index % 12 in {1,2,3,4}:
                case=index%12
                if case==1:payload.pop("power_kw")
                elif case==2:payload["power_kw"]=-20
                elif case==3:payload["temperature_c"]=125
                else:payload["timestamp"]=last_timestamp or timestamp
            info=client.publish(args.topic,json.dumps(payload,ensure_ascii=False),qos=1)
            info.wait_for_publish();print(json.dumps(payload,ensure_ascii=False),flush=True)
            last_timestamp=payload["timestamp"];index+=1;time.sleep(args.interval)
    finally:
        client.disconnect();client.loop_stop()


if __name__ == "__main__":
    main()
