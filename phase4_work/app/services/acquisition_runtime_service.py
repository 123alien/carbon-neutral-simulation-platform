import asyncio
import json
import logging
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from time import perf_counter
from sqlalchemy import select
from app.database import SessionLocal
from app.models import DataSource, DataSourceRuntimeState, Device
from app.adapters import AdapterRegistry, ExtractedRecord
from app.services import data_source_service
from app.utils.secrets import decrypt_credentials

log=logging.getLogger("acquisition")
INTERVALS={15,30,60,360,1440}

def state(db,source_id):
    row=db.scalars(select(DataSourceRuntimeState).where(DataSourceRuntimeState.data_source_id==source_id)).first()
    if row is None:row=DataSourceRuntimeState(data_source_id=source_id);db.add(row);db.flush()
    return row
def read_runtime(db,source_id):
    source=data_source_service.get(db,source_id);row=state(db,source_id);db.commit();db.refresh(row)
    return {"data_source_id":source.id,"source_type":source.source_type,"collection_mode":source.collection_mode,"schedule_enabled":source.schedule_enabled,"interval_minutes":source.interval_minutes,"runtime_status":row.runtime_status,"connected":row.connected,"subscribed":row.subscribed,"last_started_at":row.last_started_at,"last_success_at":row.last_success_at,"last_failure_at":row.last_failure_at,"next_run_at":row.next_run_at,"last_connected_at":row.last_connected_at,"last_disconnected_at":row.last_disconnected_at,"last_message_at":row.last_message_at,"last_received_count":row.last_received_count,"last_persisted_count":row.last_persisted_count,"last_rejected_count":row.last_rejected_count,"received_count":row.received_count,"persisted_count":row.persisted_count,"rejected_count":row.rejected_count,"dropped_count":row.dropped_count,"reconnect_count":row.reconnect_count,"consecutive_failures":row.consecutive_failures,"current_topic":row.current_topic,"last_error":row.last_error,"incremental_mode":str((source.config_json or {}).get("incremental_mode","NONE")).upper(),"current_window_start":row.current_window_start,"current_window_end":row.current_window_end,"last_success_watermark":row.last_success_watermark,"requested_pages":row.requested_pages,"successful_pages":row.successful_pages,"failed_page":row.failed_page,"pages_fetched":row.pages_fetched,"records_fetched":row.records_fetched,"duplicates_skipped":row.duplicates_skipped}

def _utc_naive(value):
    parsed=datetime.fromisoformat(str(value).replace("Z","+00:00"))
    if parsed.tzinfo is None:parsed=parsed.replace(tzinfo=ZoneInfo("UTC"))
    return parsed.astimezone(ZoneInfo("UTC")).replace(tzinfo=None)
def _serialize(value,config):
    zone=ZoneInfo(str(config.get("api_timezone","UTC")));localized=value.replace(tzinfo=ZoneInfo("UTC")).astimezone(zone);fmt=str(config.get("time_format","iso8601"))
    return localized.isoformat() if fmt.lower() in {"iso8601","iso"} else localized.strftime(fmt)
def _fetch_context(source,row,now):
    config=source.config_json or {};mode=str(config.get("incremental_mode","NONE")).upper()
    if mode=="NONE":return None
    if mode!="TIME_WINDOW":raise ValueError(f"incremental_mode {mode} is not implemented")
    if not config.get("start_param") or not config.get("end_param"):raise ValueError("TIME_WINDOW requires start_param and end_param")
    overlap=int(config.get("overlap_minutes",10))
    if not 0<=overlap<=60:raise ValueError("overlap_minutes must be between 0 and 60")
    if row.last_success_watermark:start=row.last_success_watermark-timedelta(minutes=overlap)
    elif config.get("initial_start"):start=_utc_naive(config["initial_start"])
    else:raise ValueError("TIME_WINDOW requires initial_start before the first run")
    return {"window_start":start,"window_end":now,"window_start_serialized":_serialize(start,config),"window_end_serialized":_serialize(now,config)}
def configure(db,source_id,collection_mode,enabled,interval_minutes=None):
    source=data_source_service.get(db,source_id);mode=collection_mode.upper()
    if source.source_type=="REST_API" and mode not in {"MANUAL","INTERVAL"}:raise ValueError("REST collection_mode must be MANUAL or INTERVAL")
    if source.source_type=="MQTT" and mode not in {"MANUAL","PERSISTENT"}:raise ValueError("MQTT collection_mode must be MANUAL or PERSISTENT")
    if mode=="INTERVAL" and interval_minutes not in INTERVALS:raise ValueError(f"interval_minutes must be one of {sorted(INTERVALS)}")
    source.collection_mode=mode;source.schedule_enabled=enabled;source.interval_minutes=interval_minutes if mode=="INTERVAL" else None
    row=state(db,source_id);row.next_run_at=datetime.utcnow() if enabled and mode=="INTERVAL" else None
    if not enabled:row.runtime_status="STOPPED";row.connected=False;row.subscribed=False
    db.commit();return read_runtime(db,source_id)
def _result(source_id,result,duration,status="SUCCESS"):
    log.info("data_source_id=%s operation=automatic_ingest received=%s persisted=%s rejected=%s duration_ms=%.1f status=%s",source_id,result["extracted"],result["inserted"],result["quarantined"],duration*1000,status)
def run_once(source_id,now_override=None):
    started=perf_counter()
    with SessionLocal() as db:
        source=data_source_service.get(db,source_id);row=state(db,source_id);now=now_override or datetime.utcnow();context=_fetch_context(source,row,now);row.runtime_status="RUNNING";row.last_started_at=now
        if context:row.current_window_start=context["window_start"];row.current_window_end=context["window_end"]
        db.commit()
        try:
            result=data_source_service.sync(db,source,context);finished=now_override or datetime.utcnow();row=state(db,source_id);row.runtime_status="RUNNING";row.last_success_at=finished;row.last_received_count=result["extracted"];row.last_persisted_count=result["inserted"];row.last_rejected_count=result["quarantined"];row.received_count+=result["extracted"];row.persisted_count+=result["inserted"];row.rejected_count+=result["quarantined"];row.duplicates_skipped+=result.get("duplicates_skipped",0);row.consecutive_failures=0;row.last_error=None
            for key in ("requested_pages","successful_pages","failed_page","pages_fetched","records_fetched"):setattr(row,key,result.get(key,getattr(row,key)))
            if context:row.last_success_watermark=context["window_end"]
            if source.collection_mode=="INTERVAL" and source.interval_minutes:row.next_run_at=finished+timedelta(minutes=source.interval_minutes)
            db.commit();_result(source_id,result,perf_counter()-started);return result
        except Exception as exc:
            db.rollback();row=state(db,source_id);row.runtime_status="DEGRADED";row.last_failure_at=now_override or datetime.utcnow();row.consecutive_failures+=1;row.last_error=f"{type(exc).__name__}: {str(exc)[:400]}"
            metadata=getattr(exc,"run_metadata",{})
            for key in ("requested_pages","successful_pages","failed_page","pages_fetched","records_fetched"):setattr(row,key,metadata.get(key,getattr(row,key)))
            db.commit();log.warning("data_source_id=%s operation=automatic_ingest status=FAILED duration_ms=%.1f error_type=%s",source_id,(perf_counter()-started)*1000,type(exc).__name__);raise

class DataSourceSchedulerService:
    def __init__(self):self.task=None;self.running=False;self.locks={};self.semaphore=asyncio.Semaphore(4)
    async def start(self):
        if self.running:return
        self.running=True;self.task=asyncio.create_task(self._loop(),name="rest-data-source-scheduler")
    async def stop(self):
        self.running=False
        if self.task:self.task.cancel();await asyncio.gather(self.task,return_exceptions=True);self.task=None
    async def _loop(self):
        while self.running:
            now=datetime.utcnow()
            with SessionLocal() as db:
                ids=list(db.scalars(select(DataSource.id).where(DataSource.source_type=="REST_API",DataSource.schedule_enabled.is_(True),DataSource.collection_mode=="INTERVAL",DataSource.status=="ACTIVE")).all())
                due=[]
                for source_id in ids:
                    row=state(db,source_id)
                    if row.next_run_at is None or row.next_run_at<=now:due.append(source_id)
                db.commit()
            for source_id in due:asyncio.create_task(self.trigger(source_id))
            await asyncio.sleep(2)
    async def trigger(self,source_id):
        lock=self.locks.setdefault(source_id,asyncio.Lock())
        if lock.locked():return None
        async with lock,self.semaphore:
            try:return await asyncio.wait_for(asyncio.to_thread(run_once,source_id),timeout=120)
            except Exception:return None
    def health(self):return {"status":"RUNNING" if self.running else "STOPPED","active_rest_jobs":sum(x.locked() for x in self.locks.values())}

class MqttSubscriptionManager:
    def __init__(self):self.loop=None;self.clients={};self.queues={};self.consumers={};self.stopping=set();self.running=False;self.max_queue=1000
    async def start(self):
        if self.running:return
        self.running=True;self.loop=asyncio.get_running_loop()
        with SessionLocal() as db:ids=list(db.scalars(select(DataSource.id).where(DataSource.source_type=="MQTT",DataSource.schedule_enabled.is_(True),DataSource.collection_mode=="PERSISTENT",DataSource.status=="ACTIVE")).all())
        for source_id in ids:await self.start_source(source_id)
    async def stop(self):
        for source_id in list(self.clients):await self.stop_source(source_id,disable=False)
        self.running=False
    async def start_source(self,source_id):
        await self.stop_source(source_id,disable=False)
        import paho.mqtt.client as mqtt
        with SessionLocal() as db:
            source=data_source_service.get(db,source_id);config=dict(source.config_json or {});credentials=decrypt_credentials(source.credentials_encrypted);row=state(db,source_id);row.runtime_status="STARTING";row.last_started_at=datetime.utcnow();row.current_topic=str(config.get("topic", ""));db.commit()
        queue=asyncio.Queue(maxsize=self.max_queue);client=mqtt.Client(mqtt.CallbackAPIVersion.VERSION2);username=credentials.get("username");password=credentials.get("password")
        if username:client.username_pw_set(username,password)
        if config.get("tls",True):
            import ssl
            client.tls_set(ca_certs=config.get("ca_certs"),certfile=credentials.get("certfile"),keyfile=credentials.get("keyfile"),cert_reqs=ssl.CERT_REQUIRED if config.get("verify_tls",True) else ssl.CERT_NONE)
            if not config.get("verify_tls",True):client.tls_insecure_set(True)
        client.reconnect_delay_set(min_delay=1,max_delay=60)
        def update(fn):
            with SessionLocal() as db:fn(state(db,source_id));db.commit()
        def on_connect(c,_u,_f,reason,_p):
            if not reason.is_failure:
                update(lambda r:(setattr(r,"runtime_status","STARTING"),setattr(r,"connected",True),setattr(r,"subscribed",False),setattr(r,"last_connected_at",datetime.utcnow()),setattr(r,"consecutive_failures",0),setattr(r,"last_error",None)))
                c.subscribe(config.get("topic"))
            else:update(lambda r:(setattr(r,"runtime_status","DEGRADED"),setattr(r,"connected",False),setattr(r,"subscribed",False),setattr(r,"last_error",f"MQTT connect reason {reason}")))
        def on_subscribe(_c,_u,_mid,reason_codes,_p):
            failed=any(reason.is_failure for reason in reason_codes)
            if failed:update(lambda r:(setattr(r,"runtime_status","DEGRADED"),setattr(r,"subscribed",False),setattr(r,"last_error","MQTT subscription rejected")))
            else:update(lambda r:(setattr(r,"runtime_status","RUNNING"),setattr(r,"subscribed",True),setattr(r,"last_error",None)))
        def on_disconnect(_c,_u,_f,reason,_p):
            reconnecting=self.running and source_id not in self.stopping
            update(lambda r:(setattr(r,"runtime_status","RECONNECTING" if reconnecting else "STOPPED"),setattr(r,"connected",False),setattr(r,"subscribed",False),setattr(r,"last_disconnected_at",datetime.utcnow()),setattr(r,"reconnect_count",r.reconnect_count+1 if reconnecting else r.reconnect_count)))
        def on_message(_c,_u,message):
            try:payload=json.loads(message.payload.decode("utf-8"));self.loop.call_soon_threadsafe(self._enqueue,source_id,payload)
            except Exception as exc:update(lambda r:(setattr(r,"rejected_count",r.rejected_count+1),setattr(r,"last_error",f"payload decode: {type(exc).__name__}")))
        client.on_connect=on_connect;client.on_subscribe=on_subscribe;client.on_disconnect=on_disconnect;client.on_message=on_message
        self.clients[source_id]=client;self.queues[source_id]=queue;self.consumers[source_id]=asyncio.create_task(self._consume(source_id),name=f"mqtt-consumer-{source_id}")
        try:client.connect_async(config.get("host"),int(config.get("port",8883 if config.get("tls",True) else 1883)),int(config.get("keepalive",30)));client.loop_start()
        except Exception as exc:update(lambda r:(setattr(r,"runtime_status","ERROR"),setattr(r,"last_error",f"{type(exc).__name__}: {str(exc)[:300]}")))
    def _enqueue(self,source_id,payload):
        queue=self.queues.get(source_id)
        if not queue:return
        try:queue.put_nowait(payload)
        except asyncio.QueueFull:
            with SessionLocal() as db:row=state(db,source_id);row.dropped_count+=1;row.runtime_status="DEGRADED";row.last_error="MQTT queue overflow";db.commit()
    async def _consume(self,source_id):
        queue=self.queues[source_id]
        while True:
            payload=await queue.get()
            try:await asyncio.to_thread(self._ingest_message,source_id,payload)
            except Exception as exc:
                with SessionLocal() as db:row=state(db,source_id);row.runtime_status="DEGRADED";row.last_failure_at=datetime.utcnow();row.consecutive_failures+=1;row.last_error=f"{type(exc).__name__}: {str(exc)[:300]}";db.commit()
            finally:queue.task_done()
    def _ingest_message(self,source_id,payload):
        with SessionLocal() as db:
            source=data_source_service.get(db,source_id);config=source.config_json or {};metric_fields=config.get("telemetry_fields") or {}
            def read_path(value,path,default=None):
                try:
                    for part in str(path).split("."):
                        value=value[int(part)] if isinstance(value,list) else value[part]
                    return value
                except (KeyError,IndexError,TypeError,ValueError):return default
            received_at=datetime.utcnow().isoformat()+"Z"
            device_code=read_path(payload,config.get("device_code_field","device_code"))
            device_name=config.get("device_name") or read_path(payload,config.get("device_name_field","device_name"))
            timestamp=read_path(payload,config.get("timestamp_field","timestamp")) or received_at
            source_record_id=read_path(payload,config.get("source_record_id_path","message_id"))
            records=[]
            if metric_fields:
                for raw_field,spec in metric_fields.items():
                    spec=spec if isinstance(spec,dict) else {"metric_name":str(spec)}
                    records.append(ExtractedRecord({"device_external_id":device_code,"device_name":device_name,"device_type":config.get("device_type","PV"),"timestamp":timestamp,"metric_name":spec.get("metric_name",raw_field),"value":read_path(payload,raw_field),"unit":spec.get("unit"),"source_record_id":source_record_id,"raw_payload":payload,"received_at":received_at}))
            else:records=[ExtractedRecord(payload)]
            result=data_source_service.ingest_records(db,source,records)
            status_field=config.get("status_field")
            status_value=read_path(payload,status_field) if status_field else None
            if status_value is not None:
                device=db.scalars(select(Device).where(Device.enterprise_id==source.enterprise_id,Device.external_id==str(device_code))).first()
                if device:device.status={"NORMAL":"ACTIVE","ONLINE":"ACTIVE","FAULT":"ERROR","OFFLINE":"INACTIVE"}.get(str(status_value).upper(),str(status_value).upper())
            row=state(db,source_id);row.last_message_at=datetime.utcnow();row.last_success_at=datetime.utcnow();row.last_received_count=1;row.last_persisted_count=result["inserted"];row.last_rejected_count=result["quarantined"];row.received_count+=1;row.persisted_count+=result["inserted"];row.rejected_count+=result["quarantined"];row.consecutive_failures=0;db.commit();_result(source_id,result,0)
    async def stop_source(self,source_id,disable=True):
        self.stopping.add(source_id);client=self.clients.pop(source_id,None)
        if client:client.disconnect();client.loop_stop()
        task=self.consumers.pop(source_id,None)
        if task:task.cancel();await asyncio.gather(task,return_exceptions=True)
        self.queues.pop(source_id,None)
        with SessionLocal() as db:
            source=db.get(DataSource,source_id)
            if source and disable:source.schedule_enabled=False
            if source:row=state(db,source_id);row.runtime_status="STOPPED";row.connected=False;row.subscribed=False;db.commit()
        self.stopping.discard(source_id)
    def health(self):return {"status":"RUNNING" if self.running else "STOPPED","active_mqtt_connections":sum(1 for x in self.clients.values() if x.is_connected()),"managed_mqtt_sources":len(self.clients)}

scheduler=DataSourceSchedulerService();mqtt_manager=MqttSubscriptionManager()
