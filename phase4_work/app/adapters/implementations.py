import json
import ssl
import time
from urllib.parse import urljoin
from pathlib import Path
import httpx
from app.utils.load_import import read_tabular_file
from .base import DataSourceAdapter, ExtractedRecord

class ManualAdapter(DataSourceAdapter):
    def test_connection(self): return {"success": True, "message": "manual source ready"}
    def extract(self): return [ExtractedRecord(dict(row)) for row in self.config.get("records", [])]

class FileAdapter(DataSourceAdapter):
    def test_connection(self):
        path=Path(self.config.get("path", "")); return {"success": path.is_file(), "message": "file available" if path.is_file() else "file not found"}
    def extract(self):
        path=Path(self.config.get("path", ""))
        if not path.is_file(): raise ValueError("configured file not found")
        _, rows=read_tabular_file(path.name, path.read_bytes()); return [ExtractedRecord(row) for row in rows]

class RestApiAdapter(DataSourceAdapter):
    def __init__(self, config, credentials=None):
        super().__init__(config, credentials)
        self.run_metadata={"requested_pages":0,"successful_pages":0,"failed_page":None,"pages_fetched":0,"records_fetched":0}
    @staticmethod
    def _path(value, path, default=None):
        if not path:return value
        keys=path.split(".") if isinstance(path,str) else path
        try:
            for key in keys:value=value[int(key)] if isinstance(value,list) else value[key]
            return value
        except (KeyError,IndexError,TypeError,ValueError):return default
    def _request(self, url=None, params=None):
        url=str(url or self.config.get("url", ""))
        if not url.startswith("https://") and not self.config.get("allow_insecure", False): raise ValueError("REST_API requires HTTPS")
        headers=dict(self.config.get("headers", {})); headers.update(self.credentials.get("headers", {}))
        if self.credentials.get("token"): headers["Authorization"]=f"Bearer {self.credentials['token']}"
        with httpx.Client(timeout=float(self.config.get("timeout_seconds",10)),verify=bool(self.config.get("verify_tls",True)),trust_env=bool(self.config.get("trust_env",True))) as client:
            return client.request(self.config.get("method","GET"),url,headers=headers,params=params)
    def test_connection(self):
        response=self._request(); return {"success": response.is_success, "status_code": response.status_code, "message": "connected" if response.is_success else "remote error"}
    def extract(self):
        mode=str(self.config.get("pagination_mode","NONE")).upper();url=str(self.config.get("url", ""));params=dict(self.config.get("query_params",{}));records=[];seen_requests=set();max_pages=int(self.config.get("max_pages",100));max_records=self.config.get("max_records_per_run")
        if mode not in {"NONE","LINK_NEXT"}:raise ValueError(f"pagination_mode {mode} is not implemented")
        if not 1<=max_pages<=1000:raise ValueError("max_pages must be between 1 and 1000")
        context=self.config.get("_fetch_context") or {}
        if context:
            params[str(self.config["start_param"])]=context["window_start_serialized"]
            params[str(self.config["end_param"])]=context["window_end_serialized"]
        page=0
        while url:
            page+=1
            if page>max_pages:raise RuntimeError("MAX_PAGES_EXCEEDED")
            self.run_metadata["requested_pages"]+=1
            try:response=self._request(url,params=params);response.raise_for_status();payload=response.json()
            except Exception:
                self.run_metadata["failed_page"]=page;raise
            request_url=str(response.request.url)
            if request_url in seen_requests:raise RuntimeError(f"PAGINATION_LOOP: {request_url}")
            seen_requests.add(request_url);self.run_metadata["successful_pages"]+=1;self.run_metadata["pages_fetched"]+=1
            data=self._path(payload,self.config.get("data_path",[]))
            if not isinstance(data,list):raise ValueError("REST payload data must be a list")
            for row in data:
                if not isinstance(row,dict):raise ValueError("REST record must be an object")
                records.append(ExtractedRecord(dict(row)))
                if max_records is not None and len(records)>int(max_records):raise RuntimeError("MAX_RECORDS_PER_RUN_EXCEEDED")
            self.run_metadata["records_fetched"]=len(records)
            if mode=="NONE":break
            next_value=self._path(payload,self.config.get("next_path","_links.next.href"))
            if not next_value:break
            next_url=str(next_value.get("href")) if isinstance(next_value,dict) else str(next_value)
            url=urljoin(url,next_url);params=None
        return records

class MqttAdapter(DataSourceAdapter):
    def _client(self, records):
        import paho.mqtt.client as mqtt
        client=mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
        username=self.credentials.get("username"); password=self.credentials.get("password")
        if username: client.username_pw_set(username, password)
        if self.config.get("tls", True):
            client.tls_set(ca_certs=self.config.get("ca_certs"), certfile=self.credentials.get("certfile"), keyfile=self.credentials.get("keyfile"), cert_reqs=ssl.CERT_REQUIRED if self.config.get("verify_tls", True) else ssl.CERT_NONE)
            if not self.config.get("verify_tls", True): client.tls_insecure_set(True)
        def on_message(_client, _userdata, message): records.append(json.loads(message.payload.decode("utf-8")))
        client.on_message=on_message; return client
    def _collect(self, collect):
        records=[]; client=self._client(records); host=self.config.get("host"); port=int(self.config.get("port", 8883 if self.config.get("tls", True) else 1883))
        client.connect(host, port, int(self.config.get("keepalive", 30)))
        if collect:
            client.subscribe(self.config.get("topic")); client.loop_start(); time.sleep(min(float(self.config.get("collect_seconds", 1)), 10)); client.loop_stop()
        client.disconnect(); return records
    def test_connection(self): self._collect(False); return {"success": True, "message": "MQTT connected with configured TLS/authentication"}
    def extract(self): return [ExtractedRecord(row) for row in self._collect(True)]
