from collections import Counter
from datetime import datetime, timezone, timedelta
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from app.adapters import AdapterRegistry
from app.models import DataSource, DataSourceRuntimeState, DataValidationLog, Device, DeviceMetric, Enterprise, ExternalRecordDedup, MeteringPoint, Site, Building
from app.utils.load_import import normalize_timestamp
from app.utils.secrets import decrypt_credentials, encrypt_credentials

SOURCE_TYPES={"FILE","REST_API","MQTT","THIRD_PARTY","MANUAL"}
DEVICE_TYPES={"ELECTRIC_METER","WATER_METER","GAS_METER","PV","WIND","EV_CHARGER","STORAGE","HVAC","LIGHTING"}
UNIT_RULES={
    "power_kw": ({"w":.001,"kw":1,"mw":1000}, "kW", True),
    "energy_kwh": ({"wh":.001,"kwh":1,"mwh":1000}, "kWh", True),
    "water_m3": ({"l":.001,"m3":1}, "m3", True),
    "gas_m3": ({"l":.001,"m3":1}, "m3", True),
    "temperature_c": ({"c":1,"°c":1}, "C", False),
    "humidity_pct": ({"%":1,"pct":1}, "%", True),
    "irradiance_w_m2": ({"w/m2":1,"w/m²":1}, "W/m2", True),
    "poa_irradiance_w_m2": ({"w/m2":1,"w/m²":1}, "W/m2", False),
    "ambient_temperature_c": ({"c":1,"°c":1}, "C", False),
    "module_temperature_c": ({"c":1,"°c":1}, "C", False),
    "ac_power_kw": ({"w":.001,"kw":1,"mw":1000}, "kW", False),
    "dc_power_kw": ({"w":.001,"kw":1,"mw":1000}, "kW", False),
    "ac_energy_kwh": ({"wh":.001,"kwh":1,"mwh":1000}, "kWh", False),
    "dc_energy_kwh": ({"wh":.001,"kwh":1,"mwh":1000}, "kWh", False),
    "hvac_power_kw": ({"w":.001,"kw":1,"mw":1000}, "kW", False),
    "hvac_condenser_power_kw": ({"w":.001,"kw":1,"mw":1000}, "kW", False),
    "hvac_fan_power_kw": ({"w":.001,"kw":1,"mw":1000}, "kW", False),
    "wind_speed_m_s": ({"m/s":1,"mps":1}, "m/s", True),
    "active_power_kw": ({"w":.001,"kw":1,"mw":1000}, "kW", False),
    "wind_direction_deg": ({"deg":1,"°":1}, "deg", False),
    "rotor_speed_rpm": ({"rpm":1,"r/min":1}, "rpm", True),
    "soc_pct": ({"%":1,"pct":1}, "%", True),
    "storage_charge_kw": ({"w":.001,"kw":1,"mw":1000}, "kW", True),
    "storage_discharge_kw": ({"w":.001,"kw":1,"mw":1000}, "kW", True),
    "voltage_v": ({"v":1,"kv":1000}, "V", True),
    "current_a": ({"a":1,"ma":.001}, "A", True),
    "phase_a_voltage_v": ({"v":1,"kv":1000}, "V", True),
    "phase_b_voltage_v": ({"v":1,"kv":1000}, "V", True),
    "phase_c_voltage_v": ({"v":1,"kv":1000}, "V", True),
    "phase_a_current_a": ({"a":1,"ma":.001}, "A", True),
    "phase_b_current_a": ({"a":1,"ma":.001}, "A", True),
    "phase_c_current_a": ({"a":1,"ma":.001}, "A", True),
    "device_temperature_c": ({"c":1,"°c":1}, "C", False),
}

def _sanitize(value):
    sensitive={"password","token","secret","authorization","api_key","apikey","username","certfile","keyfile"}
    if isinstance(value,dict): return {key:("***" if key.lower() in sensitive else _sanitize(item)) for key,item in value.items()}
    if isinstance(value,list): return [_sanitize(item) for item in value]
    return value

def _read(obj):
    return {"id":obj.id,"enterprise_id":obj.enterprise_id,"site_id":obj.site_id,"building_id":obj.building_id,"device_id":obj.device_id,"metering_point_id":obj.metering_point_id,"data_nature":obj.data_nature,"name":obj.name,"source_type":obj.source_type,"config_json":_sanitize(obj.config_json),"status":obj.status,"has_credentials":bool(obj.credentials_encrypted),"collection_mode":obj.collection_mode,"schedule_enabled":obj.schedule_enabled,"interval_minutes":obj.interval_minutes,"last_sync_at":obj.last_sync_at,"created_at":obj.created_at,"updated_at":obj.updated_at}

def _validate_binding(db,enterprise_id,site_id=None,building_id=None,device_id=None,metering_point_id=None):
    site=db.get(Site,site_id) if site_id else None
    building=db.get(Building,building_id) if building_id else None
    device=db.get(Device,device_id) if device_id else None
    meter=db.get(MeteringPoint,metering_point_id) if metering_point_id else None
    if site_id and (not site or site.enterprise_id!=enterprise_id):raise ValueError("园区不属于所选企业或不存在")
    resolved_site_id=site_id
    for label,obj,obj_site_id in (("建筑",building,building.site_id if building else None),("计量点",meter,meter.site_id if meter else None)):
        if (building_id if label=="建筑" else metering_point_id) and not obj:raise ValueError(f"{label}不存在")
        if obj and resolved_site_id and obj_site_id!=resolved_site_id:raise ValueError(f"{label}不属于所选园区")
        if obj and not resolved_site_id:resolved_site_id=obj_site_id
    if device_id and (not device or device.enterprise_id!=enterprise_id):raise ValueError("设备不属于所选企业或不存在")
    if meter and device_id and meter.device_id not in (None,device_id):raise ValueError("计量点不属于所选设备")
    if resolved_site_id and db.get(Site,resolved_site_id).enterprise_id!=enterprise_id:raise ValueError("关联对象不属于同一企业")

def create(db:Session,data):
    source_type=data.source_type.upper()
    if source_type not in SOURCE_TYPES: raise ValueError(f"source_type must be one of {sorted(SOURCE_TYPES)}")
    if db.get(Enterprise,data.enterprise_id) is None: raise LookupError("enterprise not found")
    _validate_binding(db,data.enterprise_id,data.site_id,data.building_id,data.device_id,data.metering_point_id)
    nature=data.data_nature.upper() if data.data_nature else None
    if nature and nature not in {"MEASURED","SIMULATED","HISTORICAL"}:raise ValueError("data_nature must be MEASURED, SIMULATED or HISTORICAL")
    if source_type!="FILE" and nature:raise ValueError("data_nature is only available for FILE data sources")
    obj=DataSource(enterprise_id=data.enterprise_id,site_id=data.site_id,building_id=data.building_id,device_id=data.device_id,metering_point_id=data.metering_point_id,data_nature=nature,name=data.name,source_type=source_type,config_json=data.config_json,credentials_encrypted=encrypt_credentials(data.credentials),status=data.status,collection_mode=data.collection_mode,schedule_enabled=data.schedule_enabled,interval_minutes=data.interval_minutes)
    db.add(obj);db.commit();db.refresh(obj);return _read(obj)

def list_all(db,enterprise_id=None,site_id=None):
    stmt=select(DataSource)
    if enterprise_id is not None: stmt=stmt.where(DataSource.enterprise_id==enterprise_id)
    if site_id is not None: stmt=stmt.where(DataSource.site_id==site_id)
    return [_read(obj) for obj in db.scalars(stmt.order_by(DataSource.id)).all()]

def get(db,source_id):
    obj=db.get(DataSource,source_id)
    if obj is None: raise LookupError("data source not found")
    return obj

def update(db,obj,data):
    values=data.model_dump(exclude_unset=True)
    if "credentials" in values: obj.credentials_encrypted=encrypt_credentials(values.pop("credentials"))
    binding={key:values.get(key,getattr(obj,key)) for key in ("site_id","building_id","device_id","metering_point_id")}
    _validate_binding(db,obj.enterprise_id,**binding)
    if "data_nature" in values and values["data_nature"]:
        values["data_nature"]=values["data_nature"].upper()
        if obj.source_type!="FILE" or values["data_nature"] not in {"MEASURED","SIMULATED","HISTORICAL"}:raise ValueError("invalid file data nature")
    for key,value in values.items(): setattr(obj,key,value)
    db.commit();db.refresh(obj);return _read(obj)

def assert_deletable(db,obj):
    device_count=db.scalar(select(func.count()).select_from(Device).where(Device.data_source_id==obj.id)) or 0
    metric_count=db.scalar(select(func.count()).select_from(DeviceMetric).where(DeviceMetric.data_source_id==obj.id)) or 0
    if device_count or metric_count:
        raise ValueError(f"data source contains {device_count} bound device(s) and {metric_count} fact record(s); deletion is blocked to protect real data")

def delete(db,obj):
    assert_deletable(db,obj)
    db.delete(obj);db.commit()

def adapter(obj,config_override=None): return AdapterRegistry.create(obj.source_type,config_override or obj.config_json,decrypt_credentials(obj.credentials_encrypted))
def test_connection(obj): return adapter(obj).test_connection()

def create_device(db,data):
    if data.device_type.upper() not in DEVICE_TYPES: raise ValueError(f"unsupported device_type: {data.device_type}")
    if db.get(Enterprise,data.enterprise_id) is None: raise LookupError("enterprise not found")
    obj=Device(**data.model_dump(exclude={"device_type"}),device_type=data.device_type.upper());db.add(obj);db.commit();db.refresh(obj);return obj

def list_devices(db,enterprise_id=None,source_id=None):
    stmt=select(Device)
    if enterprise_id is not None: stmt=stmt.where(Device.enterprise_id==enterprise_id)
    if source_id is not None: stmt=stmt.where(Device.data_source_id==source_id)
    return list(db.scalars(stmt.order_by(Device.id)).all())

def metrics(db,device_id,start=None,end=None,metric_name=None):
    stmt=select(DeviceMetric).where(DeviceMetric.device_id==device_id)
    if start: stmt=stmt.where(DeviceMetric.timestamp>=start)
    if end: stmt=stmt.where(DeviceMetric.timestamp<end)
    if metric_name: stmt=stmt.where(DeviceMetric.metric_name==metric_name)
    return list(db.scalars(stmt.order_by(DeviceMetric.timestamp)).all())

def _mapped(raw,config):
    mapping=config.get("field_mapping",{})
    def read_path(path,default=None):
        value=raw
        try:
            for part in str(path).split("."):value=value[int(part)] if isinstance(value,list) else value[part]
            return value
        except (KeyError,IndexError,TypeError,ValueError):return default
    def field(name, default=None):return read_path(mapping.get(name,name),default)
    source_path=config.get("source_record_id_path") or mapping.get("source_record_id")
    return {"device_external_id":field("device_external_id"),"device_name":field("device_name"),"device_type":field("device_type"),"timestamp":field("timestamp"),"metric_name":field("metric_name"),"value":field("value"),"unit":field("unit"),"source_record_id":read_path(source_path) if source_path else None}

def _log(db,source_id,raw,stage,code,message,level="ERROR",timestamp=None):
    db.add(DataValidationLog(data_source_id=source_id,device_external_id=raw.get("device_external_id"),timestamp=timestamp,level=level,validation_stage=stage,code=code,message=message,raw_json=raw))

def ingest_records(db:Session,obj:DataSource,records):
    inserted=quarantined=warnings=duplicates_skipped=0; seen_metrics=set();seen_external=set()
    for extracted in records:
        raw=dict(extracted.payload); mapped=_mapped(raw,obj.config_json)
        # L1: structural validation.
        required=["device_external_id","device_type","timestamp","metric_name","value","unit"]
        missing=[name for name in required if mapped.get(name) in (None,"")]
        if missing: _log(db,obj.id,mapped,"L1_SCHEMA","MISSING_FIELDS",f"missing fields: {', '.join(missing)}"); quarantined+=1; continue
        try:
            device_type=str(mapped["device_type"]).upper()
            if device_type not in DEVICE_TYPES: raise ValueError("unsupported device type")
            timestamp=normalize_timestamp(mapped["timestamp"],obj.config_json.get("timezone","UTC")); value=float(mapped["value"])
        except (TypeError,ValueError) as exc: _log(db,obj.id,mapped,"L1_SCHEMA","INVALID_STRUCTURE",str(exc));quarantined+=1;continue
        # L2: canonical unit and physical range.
        metric=str(mapped["metric_name"]); rule=UNIT_RULES.get(metric); unit=str(mapped["unit"]).lower().replace(" ","")
        if rule is None or unit not in rule[0]: _log(db,obj.id,mapped,"L2_SEMANTIC","UNSUPPORTED_UNIT",f"unsupported unit {mapped['unit']} for {metric}",timestamp=timestamp);quarantined+=1;continue
        value*=rule[0][unit]; canonical_unit=rule[1]
        configured_range=(obj.config_json or {}).get("semantic_ranges",{}).get(metric,{})
        below=configured_range.get("min") is not None and value<float(configured_range["min"])
        above=configured_range.get("max") is not None and value>float(configured_range["max"])
        if rule[2] and value<0 or metric in {"humidity_pct","soc_pct"} and value>100 or below or above: _log(db,obj.id,mapped,"L2_SEMANTIC","OUT_OF_RANGE",f"invalid canonical value {value}",timestamp=timestamp);quarantined+=1;continue
        device=db.scalars(select(Device).where(Device.enterprise_id==obj.enterprise_id,Device.external_id==str(mapped["device_external_id"]))).first()
        if device is None:
            device=Device(enterprise_id=obj.enterprise_id,data_source_id=obj.id,external_id=str(mapped["device_external_id"]),name=str(mapped.get("device_name") or mapped["device_external_id"]),device_type=device_type,metadata_json={});db.add(device);db.flush()
        # L3: third-party identity has priority; temporal uniqueness remains the fallback.
        source_record_id=mapped.get("source_record_id")
        if source_record_id not in (None,""):
            external_key=(str(source_record_id),metric)
            external_duplicate=external_key in seen_external or db.scalars(select(ExternalRecordDedup.id).where(ExternalRecordDedup.data_source_id==obj.id,ExternalRecordDedup.source_record_id==str(source_record_id),ExternalRecordDedup.metric_name==metric)).first()
            if external_duplicate:duplicates_skipped+=1;continue
        metric_key=(device.id,timestamp,metric)
        duplicate=metric_key in seen_metrics or db.scalars(select(DeviceMetric.id).where(DeviceMetric.device_id==device.id,DeviceMetric.timestamp==timestamp,DeviceMetric.metric_name==metric)).first()
        if duplicate: _log(db,obj.id,mapped,"L3_TEMPORAL","DUPLICATE","metric timestamp already exists",timestamp=timestamp);quarantined+=1;continue
        if timestamp>datetime.utcnow()+timedelta(minutes=5): _log(db,obj.id,mapped,"L3_TEMPORAL","FUTURE_TIMESTAMP","timestamp is in the future",timestamp=timestamp);quarantined+=1;continue
        quality="VALID"; limit=obj.config_json.get("max_value_change_ratio")
        previous=db.scalars(select(DeviceMetric).where(DeviceMetric.device_id==device.id,DeviceMetric.metric_name==metric).order_by(DeviceMetric.timestamp.desc())).first()
        if limit is not None and previous and previous.value and abs(value-previous.value)/abs(previous.value)>float(limit):
            quality="WARNING";warnings+=1;_log(db,obj.id,mapped,"L3_TEMPORAL","RATE_OF_CHANGE","value change exceeds configured ratio",level="WARNING",timestamp=timestamp)
        db.add(DeviceMetric(device_id=device.id,data_source_id=obj.id,timestamp=timestamp,metric_name=metric,value=value,unit=canonical_unit,quality=quality,raw_json={**raw,"source_record_id":source_record_id} if source_record_id not in (None,"") else raw));seen_metrics.add(metric_key)
        if source_record_id not in (None,""):
            db.add(ExternalRecordDedup(data_source_id=obj.id,source_record_id=str(source_record_id),metric_name=metric));seen_external.add((str(source_record_id),metric))
        inserted+=1
    obj.last_sync_at=datetime.utcnow();db.commit();return {"extracted":len(records),"inserted":inserted,"quarantined":quarantined,"warnings":warnings,"duplicates_skipped":duplicates_skipped}

def sync(db:Session,obj:DataSource,fetch_context=None):
    config=dict(obj.config_json or {})
    if fetch_context:config["_fetch_context"]=fetch_context
    source_adapter=adapter(obj,config)
    try:records=source_adapter.extract()
    except Exception as exc:
        setattr(exc,"run_metadata",getattr(source_adapter,"run_metadata",{}));raise
    result=ingest_records(db,obj,records)
    result.update(getattr(source_adapter,"run_metadata",{}));return result

def quality(db,source_id):
    valid=db.scalar(select(func.count()).select_from(DeviceMetric).where(DeviceMetric.data_source_id==source_id)) or 0
    logs=list(db.scalars(select(DataValidationLog).where(DataValidationLog.data_source_id==source_id)).all()); quarantined=sum(log.level=="ERROR" for log in logs); warnings=sum(log.level=="WARNING" for log in logs); stages=Counter(log.validation_stage for log in logs);total=valid+quarantined
    return {"data_source_id":source_id,"total_records":total,"valid_records":valid,"quarantined_records":quarantined,"warning_records":warnings,"quality_rate":valid/total if total else 0,"by_stage":dict(stages)}

def _security(obj):
    config=obj.config_json or {}; source_type=obj.source_type
    if source_type in {"REST_API","THIRD_PARTY"}:
        url=str(config.get("url", "")); transport="HTTPS" if url.startswith("https://") else "HTTP"
        secure=url.startswith("https://") and bool(config.get("verify_tls",True))
        return {"transport":transport,"secure_transport_enabled":secure,"tls_verification":bool(config.get("verify_tls",True)) if url.startswith("https://") else False,"authentication":config.get("authentication","凭证/请求头") if obj.credentials_encrypted else "未配置","credentials_configured":bool(obj.credentials_encrypted),"ca_configured":None,"client_certificate_configured":None}
    if source_type=="MQTT":
        tls=bool(config.get("tls",True))
        return {"transport":"MQTTS" if tls else "MQTT","secure_transport_enabled":tls,"tls_verification":bool(config.get("verify_tls",True)) if tls else False,"authentication":"用户名/密码或客户端证书" if obj.credentials_encrypted else "未配置","credentials_configured":bool(obj.credentials_encrypted),"ca_configured":bool(config.get("ca_certs")),"client_certificate_configured":bool(obj.credentials_encrypted)}
    return {"transport":"本地文件/应用内部","secure_transport_enabled":None,"tls_verification":None,"authentication":"不适用","credentials_configured":bool(obj.credentials_encrypted),"ca_configured":None,"client_certificate_configured":None}

def _capability(source_type):
    modes={"FILE":"文件人工导入","REST_API":"手动 API 同步","MQTT":"手动触发的短时 MQTT 采集","THIRD_PARTY":"手动触发的第三方接口/交换","MANUAL":"人工录入"}
    return {"acquisition_mode":modes[source_type],"connection_test":True,"manual_sync":True,"scheduled_sync":source_type=="REST_API","realtime_listener":source_type=="MQTT","automatic_reconnect":source_type=="MQTT","field_mapping":True,"validation_pipeline":["L1_SCHEMA","L2_SEMANTIC","L3_TEMPORAL"],"runtime_status":"AVAILABLE" if source_type in {"REST_API","MQTT"} else "NOT_APPLICABLE","limitation":({"THIRD_PARTY":"自动运行需按实际传输类型配置为 REST_API 或 MQTT"}.get(source_type))}

def capabilities():
    return [{"source_type":source_type,**_capability(source_type)} for source_type in sorted(SOURCE_TYPES)]

def validation_logs(db,source_id,limit=100):
    get(db,source_id)
    rows=db.scalars(select(DataValidationLog).where(DataValidationLog.data_source_id==source_id).order_by(DataValidationLog.created_at.desc()).limit(limit)).all()
    return [{"id":x.id,"data_source_id":x.data_source_id,"device_external_id":x.device_external_id,"timestamp":x.timestamp,"level":x.level,"validation_stage":x.validation_stage,"code":x.code,"message":x.message,"raw_json":_sanitize(x.raw_json),"created_at":x.created_at,"disposition":"隔离" if x.level=="ERROR" else "带警告入库"} for x in rows]

def details(db,source_id):
    obj=get(db,source_id); devices=list(db.scalars(select(Device).where(Device.data_source_id==obj.id).order_by(Device.id)).all())
    meters=list(db.scalars(select(MeteringPoint).where(MeteringPoint.data_source_id==obj.id).order_by(MeteringPoint.id)).all())
    valid=db.scalar(select(func.count()).select_from(DeviceMetric).where(DeviceMetric.data_source_id==obj.id)) or 0
    latest=db.scalar(select(func.max(DeviceMetric.timestamp)).where(DeviceMetric.data_source_id==obj.id))
    recent=db.scalar(select(func.count()).select_from(DeviceMetric).where(DeviceMetric.data_source_id==obj.id,DeviceMetric.timestamp>=datetime.utcnow()-timedelta(hours=24))) or 0
    logs=validation_logs(db,source_id,100)
    latest_rows=list(db.scalars(select(DeviceMetric).where(DeviceMetric.data_source_id==obj.id).order_by(DeviceMetric.timestamp.desc(),DeviceMetric.id.desc()).limit(30)).all())
    return {"source":_read(obj),"protocol":_security(obj)["transport"],"capability":_capability(obj.source_type),"security":_security(obj),"binding":{"device_count":len(devices),"metering_point_count":len(meters),"devices":[{"id":x.id,"external_id":x.external_id,"name":x.name,"device_type":x.device_type,"status":x.status} for x in devices],"metering_points":[{"id":x.id,"code":x.code,"name":x.name,"metric_type":x.metric_type,"energy_type":x.energy_type,"unit":x.unit,"device_id":x.device_id} for x in meters]},"status":{"last_received_at":latest,"received_last_24h":recent,"cumulative_accepted":valid,"last_error":next((x for x in logs if x["level"]=="ERROR"),None)},"mapping":(obj.config_json or {}).get("field_mapping",{}),"validation":quality(db,source_id),"validation_logs":logs,"latest_records":[{"id":x.id,"device_id":x.device_id,"timestamp":x.timestamp,"metric_name":x.metric_name,"value":x.value,"unit":x.unit,"quality":x.quality} for x in latest_rows]}

def acquisition_overview(db,enterprise_id=None,site_id=None):
    stmt=select(DataSource)
    if enterprise_id is not None:stmt=stmt.where(DataSource.enterprise_id==enterprise_id)
    if site_id is not None:stmt=stmt.where(DataSource.site_id==site_id)
    sources=list(db.scalars(stmt).all());ids=[x.id for x in sources]
    if not ids:return {"source_count":0,"normal_source_count":0,"abnormal_source_count":0,"by_type":{},"received_last_24h":None,"last_success_sync_at":None,"last_failure_at":None,"validation":{"L1_SCHEMA":{"rejected":0,"passed":None},"L2_SEMANTIC":{"rejected":0,"passed":None},"L3_TEMPORAL":{"rejected":0,"warnings":0,"passed":None}},"quarantined":0,"quality_rate":None,"latest_data_at":None,"automatic_acquisition_running":False}
    logs=list(db.scalars(select(DataValidationLog).where(DataValidationLog.data_source_id.in_(ids))).all())
    accepted=db.scalar(select(func.count()).select_from(DeviceMetric).where(DeviceMetric.data_source_id.in_(ids))) or 0
    recent=db.scalar(select(func.count()).select_from(DeviceMetric).where(DeviceMetric.data_source_id.in_(ids),DeviceMetric.timestamp>=datetime.utcnow()-timedelta(hours=24))) or 0
    latest=db.scalar(select(func.max(DeviceMetric.timestamp)).where(DeviceMetric.data_source_id.in_(ids)))
    errors=[x for x in logs if x.level=="ERROR"]; warnings=[x for x in logs if x.level=="WARNING"]
    by_type=Counter(x.source_type for x in sources); total=accepted+len(errors);runtime=list(db.scalars(select(DataSourceRuntimeState).where(DataSourceRuntimeState.data_source_id.in_(ids))).all())
    return {"source_count":len(sources),"normal_source_count":sum(x.status in {"ACTIVE","OK","SUCCESS"} and x.last_sync_at is not None for x in sources),"abnormal_source_count":sum(x.status not in {"ACTIVE","OK","SUCCESS"} for x in sources),"never_run_count":sum(x.last_sync_at is None for x in sources),"by_type":dict(by_type),"received_last_24h":recent,"last_success_sync_at":max((x.last_sync_at for x in sources if x.last_sync_at),default=None),"last_failure_at":max((x.created_at for x in errors),default=None),"validation":{"L1_SCHEMA":{"rejected":sum(x.validation_stage=="L1_SCHEMA" and x.level=="ERROR" for x in logs),"passed":None},"L2_SEMANTIC":{"rejected":sum(x.validation_stage=="L2_SEMANTIC" and x.level=="ERROR" for x in logs),"passed":None},"L3_TEMPORAL":{"rejected":sum(x.validation_stage=="L3_TEMPORAL" and x.level=="ERROR" for x in logs),"warnings":sum(x.validation_stage=="L3_TEMPORAL" and x.level=="WARNING" for x in logs),"passed":None}},"quarantined":len(errors),"quality_rate":accepted/total if total else None,"latest_data_at":latest,"automatic_acquisition_running":any(x.runtime_status in {"RUNNING","STARTING","RECONNECTING"} for x in runtime),"automatic_source_count":sum(x.schedule_enabled for x in sources),"running_automatic_source_count":sum(x.runtime_status=="RUNNING" for x in runtime),"rest_interval_count":sum(x.source_type=="REST_API" and x.schedule_enabled for x in sources),"mqtt_listener_count":sum(x.source_type=="MQTT" and x.schedule_enabled for x in sources)}
