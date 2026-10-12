"""Bind real upstream camera identifiers to explicitly illustrative campus anchors."""
from sqlalchemy import select
from app.database import SessionLocal
from app.models import Site, Building, CameraSpatialMapping
from app.schemas.cross_camera import CameraSpatialMappingCreate
from app.services.cross_camera_adapter_service import create_mapping
from app.services.cross_camera_source_service import demo_cameras

def main():
    anchors={x['camera_id']:x for x in demo_cameras()}
    with SessionLocal() as db:
        site=db.scalar(select(Site).where(Site.code=='HBUE'))
        if site is None:raise RuntimeError('湖北经济学院园区不存在')
        buildings=list(db.scalars(select(Building).where(Building.site_id==site.id)))
        for upstream,anchor in [('cam1','CAM01'),('cam2','CAM02')]:
            if db.scalar(select(CameraSpatialMapping).where(CameraSpatialMapping.campus_id=='HBUE',CameraSpatialMapping.camera_id==upstream)):
                print(upstream,'existing mapping preserved');continue
            c=anchors[anchor]
            building=next(b for b in buildings if (b.metadata_json or {}).get('building_id')==c['building_id'] or b.code==c['building_id'])
            create_mapping(db,CameraSpatialMappingCreate(site_id=site.id,building_id=building.id,campus_id='HBUE',camera_id=upstream,area_id=c['area_id'],longitude=c['longitude'],latitude=c['latitude'],anchor_source='DEMO_PLACEMENT',metadata_json={'camera_name':c['camera_name'],'demo_gis_camera_id':anchor,'notice':'真实算法输出与示范校园空间关联，不代表真实拍摄位置'}))
            print(upstream,'mapped to',c['building_id'],'DEMO_PLACEMENT')

if __name__=='__main__':main()
