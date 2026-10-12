"""Fetch OSM roads clipped to the existing campus boundary; JSON on stdout."""
import hashlib
import json
from pathlib import Path
import httpx
import xml.etree.ElementTree as ET
ROOT=Path(__file__).resolve().parents[1]
def inside(point,ring):
    x,y=point;result=False
    for a,b in zip(ring,ring[1:]):
        if (a[1]>y)!=(b[1]>y) and x<(b[0]-a[0])*(y-a[1])/(b[1]-a[1])+a[0]:result=not result
    return result
def clip(a,b,ring):
    dx,dy=b[0]-a[0],b[1]-a[1];cuts=[0,1]
    for c,d in zip(ring,ring[1:]):
        ex,ey=d[0]-c[0],d[1]-c[1];den=dx*ey-dy*ex
        if abs(den)<1e-16:continue
        t=((c[0]-a[0])*ey-(c[1]-a[1])*ex)/den
        u=((c[0]-a[0])*dy-(c[1]-a[1])*dx)/den
        if 0<=t<=1 and 0<=u<=1:cuts.append(t)
    cuts=sorted(set(cuts));result=[]
    for start,end in zip(cuts,cuts[1:]):
        mid=(start+end)/2
        if inside((a[0]+dx*mid,a[1]+dy*mid),ring):result.append([[a[0]+dx*start,a[1]+dy*start],[a[0]+dx*end,a[1]+dy*end]])
    return result
def main():
    boundary=json.loads((ROOT/'spatial_data/hbue/hbue_campus_boundary.geojson').read_text(encoding='utf-8'))
    ring=boundary['features'][0]['geometry']['coordinates'][0]
    west,south,east,north=min(p[0] for p in ring),min(p[1] for p in ring),max(p[0] for p in ring),max(p[1] for p in ring)
    query=f'[out:json][timeout:20];way[highway]({south},{west},{north},{east});out tags geom;'
    response=None
    ways=[]
    for endpoint in ['https://www.openstreetmap.org/api/0.6/map']:
        try:
            r=httpx.get(endpoint,params={'bbox':f'{west},{south},{east},{north}'},headers={'User-Agent':'HBUE-Campus-Visualization/1.0'},timeout=40)
            r.raise_for_status();response=r
            tree=ET.fromstring(r.content);nodes={n.attrib['id']:{'lon':float(n.attrib['lon']),'lat':float(n.attrib['lat'])} for n in tree.findall('node')}
            for w in tree.findall('way'):
                tags={t.attrib['k']:t.attrib['v'] for t in w.findall('tag')}
                if 'highway' in tags:ways.append({'id':w.attrib['id'],'tags':tags,'geometry':[nodes[n.attrib['ref']] for n in w.findall('nd') if n.attrib['ref'] in nodes]})
            break
        except httpx.HTTPError:continue
    if response is None:raise RuntimeError('公开道路获取失败，未生成虚构道路')
    features=[]
    for way in ways:
        coords=[(p['lon'],p['lat']) for p in way.get('geometry',[])]
        if len(coords)<2:continue
        lines=[]
        for a,b in zip(coords,coords[1:]):
            for part in clip(a,b,ring):
                if lines and lines[-1][-1]==part[0]:lines[-1].append(part[1])
                else:lines.append(part)
        for index,line in enumerate(lines):
            tags=way['tags'];features.append({'type':'Feature','properties':{'campus_id':'HBUE','osm_id':str(way['id']),'segment_index':index,'name':tags.get('name'),'highway':tags['highway'],'source':'OpenStreetMap API','width_source':'MODEL_DEFAULT','tags':tags},'geometry':{'type':'LineString','coordinates':line}})
    print(json.dumps({'type':'FeatureCollection','metadata':{'crs':'EPSG:4326','source':'OpenStreetMap contributors','license':'ODbL 1.0','source_url':'https://www.openstreetmap.org/copyright','raw_sha256':hashlib.sha256(response.content).hexdigest(),'query':query,'notice':'真实道路中心线，展示宽度与路缘为示意；道路已裁剪至现有校园边界'},'features':features},ensure_ascii=True))
if __name__=='__main__':main()
