"""幂等配置示范园区的真实 MQTT 光伏逆变器验证链路。"""
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from sqlalchemy import select
from app.database import SessionLocal
from app.models import DataSource,Device,EnergySystem,MeteringPoint,Site
from app.services.acquisition_runtime_service import state

TOPIC="carbon-demo/cn-platform-7f3a/DEMO-PARK-001/pv/PV-INV-001/telemetry"

def main():
    with SessionLocal() as db:
        site=db.scalar(select(Site).where(Site.name=="智慧低碳示范园区"))
        if not site:raise SystemExit("未找到智慧低碳示范园区，请先运行示范园区初始化脚本")
        system=db.scalar(select(EnergySystem).where(EnergySystem.site_id==site.id,EnergySystem.system_type=="PV"))
        if not system:raise SystemExit("示范园区缺少分布式光伏能源系统")
        source=db.scalar(select(DataSource).where(DataSource.enterprise_id==site.enterprise_id,DataSource.name=="光伏逆变器实时数据"))
        config={"host":"broker.emqx.io","port":8883,"topic":TOPIC,"tls":True,"verify_tls":True,"keepalive":30,"timezone":"UTC","classification":"DEMO_REALTIME_ACQUISITION","device_code_field":"device_code","device_name":"光伏逆变器01","device_type":"PV","timestamp_field":"timestamp","status_field":"status","source_record_id_path":"message_id","telemetry_fields":{"power_kw":{"metric_name":"power_kw","unit":"kW"},"generation_kwh":{"metric_name":"energy_kwh","unit":"kWh"},"voltage_v":{"metric_name":"voltage_v","unit":"V"},"current_a":{"metric_name":"current_a","unit":"A"},"temperature_c":{"metric_name":"device_temperature_c","unit":"C"}},"semantic_ranges":{"power_kw":{"min":0,"max":720},"energy_kwh":{"min":0},"voltage_v":{"min":300,"max":450},"current_a":{"min":0,"max":1200},"device_temperature_c":{"min":-30,"max":90}}}
        if source is None:
            source=DataSource(enterprise_id=site.enterprise_id,site_id=site.id,name="光伏逆变器实时数据",source_type="MQTT",config_json=config,status="ACTIVE",collection_mode="PERSISTENT",schedule_enabled=True);db.add(source);db.flush()
        else:source.site_id=site.id;source.config_json=config;source.status="ACTIVE";source.collection_mode="PERSISTENT";source.schedule_enabled=True
        device=db.scalar(select(Device).where(Device.enterprise_id==site.enterprise_id,Device.external_id=="PV-INV-001"))
        if device is None:
            device=Device(enterprise_id=site.enterprise_id,data_source_id=source.id,external_id="PV-INV-001",name="光伏逆变器01",device_type="PV",status="ACTIVE",metadata_json={"energy_system_id":system.id,"data_class":"DEMO_REALTIME_ACQUISITION"});db.add(device);db.flush()
        else:device.data_source_id=source.id;device.name="光伏逆变器01";device.metadata_json={**(device.metadata_json or {}),"energy_system_id":system.id,"data_class":"DEMO_REALTIME_ACQUISITION"}
        specs=[("PV-INV-001-P","光伏实时功率","POWER","kW"),("PV-INV-001-E","累计发电量","ENERGY","kWh"),("PV-INV-001-U","逆变器电压","VOLTAGE","V"),("PV-INV-001-I","逆变器电流","CURRENT","A"),("PV-INV-001-T","逆变器温度","TEMPERATURE","C")]
        primary=None
        for code,name,metric,unit in specs:
            meter=db.scalar(select(MeteringPoint).where(MeteringPoint.site_id==site.id,MeteringPoint.code==code))
            if meter is None:meter=MeteringPoint(site_id=site.id,energy_system_id=system.id,device_id=device.id,data_source_id=source.id,code=code,name=name,metric_type=metric,energy_type="ELECTRICITY",unit=unit,status="ACTIVE",metadata_json={"data_class":"DEMO_REALTIME_ACQUISITION"});db.add(meter);db.flush()
            else:meter.device_id=device.id;meter.data_source_id=source.id;meter.energy_system_id=system.id
            if metric=="POWER":primary=meter
        source.device_id=device.id;source.metering_point_id=primary.id if primary else None
        runtime=state(db,source.id);runtime.runtime_status="STOPPED";runtime.connected=False;runtime.subscribed=False
        db.commit();print(f"data_source_id={source.id}\ndevice_id={device.id}\ntopic={TOPIC}\ntls=8883")

if __name__=="__main__":main()
