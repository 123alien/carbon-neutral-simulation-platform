"""Read-only task video proxy. Fixed upstream paths; no client credentials."""
import os
import re
import httpx
from fastapi import HTTPException
from starlette.responses import StreamingResponse
from backend.adapters import cross_camera_status


async def task_video(task_id, camera, range_header=None):
    if not re.fullmatch(r'[A-Za-z0-9_-]{1,100}', task_id) or camera not in ('cam1','cam2'):
        raise HTTPException(400,'任务编号或摄像头无效')
    tasks=await cross_camera_status('tasks')
    if not any(t['task_id']==task_id for t in tasks):
        raise HTTPException(404,'真实任务不存在或当前账号无权访问')
    base=os.environ.get('CROSS_CAMERA_BASE_URL','http://10.120.203.134:8100').rstrip('/')
    client=httpx.AsyncClient(timeout=30,trust_env=False,follow_redirects=False)
    try:
        response=await client.send(client.build_request('GET',f'{base}/api/v1/tasks/{task_id}/videos/{camera}'),stream=True)
        if response.status_code!=200 or not response.headers.get('content-type','').startswith('video/'):
            await response.aclose();await client.aclose()
            raise HTTPException(502,'任务视频不可用或上游未返回视频')
    except httpx.HTTPError:
        await client.aclose()
        raise HTTPException(502,'视频服务不可达')
    length=int(response.headers.get('content-length','0'))
    start,end,status=0,length-1,200
    headers={'Cache-Control':'private, no-store','X-Content-Type-Options':'nosniff'}
    if length:
        headers['Accept-Ranges']='bytes'
        if range_header:
            match=re.fullmatch(r'bytes=(\d*)-(\d*)',range_header)
            if not match or not any(match.groups()):
                await response.aclose();await client.aclose();raise HTTPException(416,'不支持该Range请求')
            a,b=match.groups()
            start=int(a) if a else max(0,length-int(b))
            end=min(int(b),length-1) if a and b else length-1
            if start>=length or end<start:
                await response.aclose();await client.aclose();raise HTTPException(416,'视频范围超出长度',headers={'Content-Range':f'bytes */{length}'})
            status=206;headers['Content-Range']=f'bytes {start}-{end}/{length}'
        headers['Content-Length']=str(end-start+1)
    async def chunks():
        offset=0
        try:
            async for chunk in response.aiter_raw():
                next_offset=offset+len(chunk)
                if next_offset>start:
                    data=chunk[max(0,start-offset):min(len(chunk),end+1-offset) if length else len(chunk)]
                    if data:yield data
                offset=next_offset
                if length and offset>end:break
        finally:
            await response.aclose();await client.aclose()
    return StreamingResponse(chunks(),status_code=status,headers=headers,media_type=response.headers['content-type'])
