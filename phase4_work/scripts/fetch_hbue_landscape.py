"""Read-only OSM landscape download; emit GeoJSON, never invent locations."""
import hashlib
import json
from pathlib import Path
import xml.etree.ElementTree as ET
import httpx
from fetch_hbue_roads import inside

def main():
    root=Path(__file__).resolve().parents[1]
    ring=json.loads((root/'spatial_data/hbue/hbue_campus_boundary.geojson').read_text(encoding='utf-8'))['features'][0]['geometry']['coordinates'][0]
    bbox=','.join(map(str,[min(p[0] for p in ring),min(p[1] for p in ring),max(p[0] for p in ring),max(p[1] for p in ring)]))
    response=httpx.get('https://www.openstreetmap.org/api/0.6/map',params={'bbox':bbox},headers={'User-Agent':'HBUE-Campus-Landscape/1.0'},timeout=40)
    response.raise_for_status()
    tree=ET.fromstring(response.content)
    nodes={n.attrib['id']:[float(n.attrib['lon']),float(n.attrib['lat'])] for n in tree.findall('node')}
    features=[]
    for way in tree.findall('way'):
        tags={t.attrib['k']:t.attrib['v'] for t in way.findall('tag')}
        kind='water' if tags.get('natural')=='water' or tags.get('water') in ('lake','pond','reservoir') else 'sport' if tags.get('leisure') in ('pitch','track') else 'paving' if tags.get('highway')=='pedestrian' and tags.get('area')=='yes' else 'green' if tags.get('landuse') in ('grass','forest') or tags.get('leisure')=='garden' else None
        if not kind:continue
        coords=[nodes[n.attrib['ref']] for n in way.findall('nd') if n.attrib['ref'] in nodes]
        if len(coords)<4 or coords[0]!=coords[-1] or not all(inside(p,ring) for p in coords[:-1]):continue
        features.append({'type':'Feature','properties':{'campus_id':'HBUE','osm_id':'way/'+way.attrib['id'],'name':tags.get('name'),'landscape_type':kind,'tags':tags,'source':'OpenStreetMap contributors','presentation_only':True},'geometry':{'type':'Polygon','coordinates':[coords]}})
    print(json.dumps({'type':'FeatureCollection','metadata':{'crs':'EPSG:4326','source_url':'https://www.openstreetmap.org/copyright','license':'ODbL 1.0','raw_sha256':hashlib.sha256(response.content).hexdigest(),'notice':'仅保留完整位于既有校园边界内的OSM环境面；颜色为展示示意，不包含业务指标'},'features':features},ensure_ascii=True))

if __name__=='__main__':main()
