from datetime import datetime
from hashlib import sha256
from pathlib import Path
import os,re
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.models import ReportTask,ReportSnapshot,ReportFile
from app.reporting import DocxReportRenderer,PdfReportRenderer
RENDERERS={"DOCX":DocxReportRenderer,"PDF":PdfReportRenderer}
def _task(db,id):
    row=db.get(ReportTask,id)
    if not row:raise LookupError("report task not found")
    return row
def _snapshot(db,id):
    row=db.scalar(select(ReportSnapshot).where(ReportSnapshot.report_task_id==id))
    if not row:raise LookupError("report snapshot not found")
    return row
def _safe(value):return re.sub(r'[<>:"/\\|?*\x00-\x1f]+','_',value).strip(' .')[:100] or "报告"
def _root():return Path(os.getenv("REPORT_STORAGE_PATH","report_files")).resolve()
def files(db,id):
    _task(db,id);return list(db.scalars(select(ReportFile).where(ReportFile.report_task_id==id).order_by(ReportFile.format)).all())
def render(db:Session,id:int,formats:list[str]):
    task=_task(db,id);snapshot=_snapshot(db,id);requested=list(dict.fromkeys(x.upper() for x in formats))
    if not set(requested)<=set(RENDERERS):raise ValueError("formats must contain DOCX and/or PDF")
    task.status="GENERATING";task.failure_reason=None;db.commit()
    frozen={"scenario_version_id":snapshot.scenario_version_id,"simulation_task_id":snapshot.simulation_task_id,"input_snapshot_json":snapshot.input_snapshot_json,"report_data_json":snapshot.report_data_json}
    try:
        folder=_root()/str(task.id);folder.mkdir(parents=True,exist_ok=True);records=[]
        for fmt in requested:
            name=f"碳中和可行性与风险评估报告_{_safe(task.title)}_{task.id}.{fmt.lower()}";path=folder/name;RENDERERS[fmt]().render(frozen,path,task.id,task.title);raw=path.read_bytes();checksum=sha256(raw).hexdigest();row=db.scalar(select(ReportFile).where(ReportFile.report_task_id==task.id,ReportFile.format==fmt))
            if row is None:row=ReportFile(report_task_id=task.id,format=fmt,file_name=name,storage_path=str(path),file_size=len(raw),checksum=checksum,generated_at=datetime.utcnow());db.add(row)
            else:row.file_name=name;row.storage_path=str(path);row.file_size=len(raw);row.checksum=checksum;row.generated_at=datetime.utcnow()
            records.append(row)
        task.status="SUCCESS";task.generated_at=datetime.utcnow();db.commit()
        for row in records:db.refresh(row)
        return records
    except Exception as exc:
        db.rollback();task=_task(db,id);task.status="FAILED";task.failure_reason=f"{type(exc).__name__}: {exc}"[:2000];db.commit();raise ValueError("report rendering failed") from exc
def file_for(db,id,fmt):
    _task(db,id);row=db.scalar(select(ReportFile).where(ReportFile.report_task_id==id,ReportFile.format==fmt.upper()))
    if not row:raise LookupError(f"{fmt.upper()} report file not found")
    path=Path(row.storage_path)
    if not path.is_file():raise LookupError("report file is missing from storage")
    return row,path
