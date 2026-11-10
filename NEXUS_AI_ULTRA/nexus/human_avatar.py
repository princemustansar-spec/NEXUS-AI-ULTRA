"""Optional portrait profile and audio-only animation telemetry. All assets stay local."""
import asyncio
import copy
import io
import json
import math
from pathlib import Path
import re
import shutil
import struct
import threading
import time
import uuid
import zipfile
import zlib
from fastapi import HTTPException, Request
from fastapi.responses import Response, StreamingResponse

PNG_LIMIT = 1_900_000
PACK_LIMIT = 4_000_000
DEFAULT_RIG = dict(
    eyes=[[0,[.35,.335,.16,.115],[.352,.333,.122,.093]], [0,[.51,.335,.16,.115],[.500,.340,.122,.093]]],
    mouths=[[1,[.35,.475,.30,.157],[.369,.487,.247,.133]], [2,[.35,.475,.30,.157],[.369,.487,.247,.141]], [3,[.35,.475,.30,.157],[.369,.486,.247,.137]]],
    pivot=[.493,.685], neck=[.53,.79])

def validate_png(data):
    if len(data)>PNG_LIMIT or not data.startswith(b'\x89PNG\r\n\x1a\n'):raise ValueError('Choose a transparent PNG smaller than 1.9 MB.')
    offset=8;kinds=[]
    while offset+12<=len(data):
        size,=struct.unpack('>I',data[offset:offset+4]);end=offset+12+size
        if end>len(data):raise ValueError('Incomplete PNG.')
        kind=data[offset+4:offset+8];body=data[offset+8:end-4];crc,=struct.unpack('>I',data[end-4:end])
        if zlib.crc32(kind+body)&0xffffffff!=crc:raise ValueError('Damaged PNG.')
        if not kinds:
            if kind!=b'IHDR' or size!=13:raise ValueError('Invalid PNG header.')
            w,h,depth,color,compression,filtering,interlace=struct.unpack('>IIBBBBB',body)
            if not(64<=w<=2048 and 64<=h<=2048 and depth==8 and color==6 and compression==filtering==interlace==0):
                raise ValueError('Use an 8-bit RGBA, non-interlaced PNG, 64–2048 pixels.')
        elif kind in (b'IHDR',b'acTL'):raise ValueError('Choose a still PNG.')
        kinds.append(kind);offset=end
        if kind==b'IEND':
            if size or offset!=len(data) or b'IDAT' not in kinds:raise ValueError('Invalid PNG ending.')
            return
    raise ValueError('Incomplete PNG.')

def numbers(values,length):
    return isinstance(values,list) and len(values)==length and all(type(n) in (int,float) and math.isfinite(n) for n in values)

OPTIONAL_RIG={'grid','shapes','jaw'}

def validate_rig(value):
    """Original packs: 2x2 sheet, 2 eye patches, 3 mouth patches. Newer packs may add
    `grid` [columns, rows] (up to 12 cells), 3-8 mouth patches, `shapes` (mouth shape id of
    each patch, 1-8) and `jaw` [centre x, centre y, half width, half height] of the mouth."""
    if not isinstance(value,dict) or not set(DEFAULT_RIG)<=set(value)<=set(DEFAULT_RIG)|OPTIONAL_RIG:raise ValueError('Invalid portrait rig.')
    grid=value.get('grid',[2,2])
    if not isinstance(grid,list) or len(grid)!=2 or any(type(n) is not int or not 1<=n<=4 for n in grid) or grid[0]*grid[1]>12:raise ValueError('Invalid expression sheet grid.')
    cells=grid[0]*grid[1]
    for key,low,high in [('eyes',2,2),('mouths',3,8)]:
        if not isinstance(value[key],list) or not low<=len(value[key])<=high:raise ValueError('Invalid facial frames.')
        for row in value[key]:
            if not isinstance(row,list) or len(row)!=3 or type(row[0]) is not int or row[0] not in range(cells):raise ValueError('Invalid frame index.')
            for box in row[1:]:
                if not numbers(box,4) or any(n<0 or n>1 for n in box) or min(box[2:])<=0 or box[0]+box[2]>1 or box[1]+box[3]>1:
                    raise ValueError('Facial frame bounds must stay inside the image.')
                if box[2]*box[3]>.16:raise ValueError('Facial frame regions must remain small.')
    if 'shapes' in value:
        shapes=value['shapes']
        if not isinstance(shapes,list) or len(shapes)!=len(value['mouths']) or any(type(n) is not int or not 1<=n<=8 for n in shapes) or len(set(shapes))!=len(shapes):
            raise ValueError('Invalid mouth shape list.')
    if 'jaw' in value:
        jaw=value['jaw']
        if not numbers(jaw,4) or any(not 0<=n<=1 for n in jaw) or jaw[2]<=0 or jaw[3]<=0 or jaw[2]>.5 or jaw[3]>.5:raise ValueError('Invalid jaw region.')
    if not numbers(value['pivot'],2) or any(not 0<=v<=1 for v in value['pivot']):raise ValueError('Invalid head pivot.')
    if not numbers(value['neck'],2) or not 0<=value['neck'][0]<value['neck'][1]<=1:raise ValueError('Invalid neck transition.')
    return copy.deepcopy(value)

def parse_import(data):
    if len(data)>PACK_LIMIT:raise ValueError('Avatar file is larger than 4 MB.')
    if data.startswith(b'\x89PNG'):
        validate_png(data);return {'portrait.png':data},copy.deepcopy(DEFAULT_RIG)
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            rows=archive.infolist();names=[r.filename for r in rows]
            if len(set(names))!=len(names) or set(names)!={'portrait.png','expressions.png','rig.json'}:raise ValueError('Avatar pack must contain portrait.png, expressions.png and rig.json only.')
            if sum(r.file_size for r in rows)>PACK_LIMIT or any(r.file_size>PNG_LIMIT or r.flag_bits&1 or (r.external_attr>>16)&0o170000==0o120000 for r in rows):raise ValueError('Invalid avatar pack size or entry.')
            files={r.filename:archive.read(r) for r in rows}
        validate_png(files['portrait.png']);validate_png(files['expressions.png'])
        if len(files['rig.json'])>10_000:raise ValueError('Portrait rig is too large.')
        rig=validate_rig(json.loads(files.pop('rig.json')))
        return files,rig
    except (zipfile.BadZipFile,KeyError,UnicodeError,json.JSONDecodeError) as exc:
        raise ValueError('Choose a transparent PNG or a valid local avatar pack.') from exc

class HumanAvatar:
    def __init__(self,directory,store):
        self.directory=Path(directory)/'avatars';self.store=store;self.lock=threading.RLock()

    def status(self):
        with self.lock:
            p=self.store.get('human_avatar',{})
            if not isinstance(p,dict):p={}
            ident=p.get('revision','')
            valid=isinstance(ident,str) and re.fullmatch('[0-9a-f]{32}',ident)
            present=bool(valid and (self.directory/ident/'portrait.png').is_file())
            frames=bool(present and (self.directory/ident/'expressions.png').is_file())
            enabled=present and p.get('enabled') is True
            try:rig=validate_rig(p.get('rig',DEFAULT_RIG))
            except ValueError:rig=copy.deepcopy(DEFAULT_RIG)
            return dict(enabled=enabled,present=present,frames=frames,revision=ident if present else '',
                        photo='/api/human-avatar/assets/portrait.png?v='+ident if present else '',
                        expressions='/api/human-avatar/assets/expressions.png?v='+ident if frames else '',
                        rig=rig,
                        alignment=p.get('alignment',dict(x=0,y=0,scale=1)))

    def import_file(self,data):
        files,rig=parse_import(data)
        with self.lock:
            old=self.status()['revision'];ident=uuid.uuid4().hex;folder=self.directory/ident
            folder.mkdir(parents=True,mode=0o700)
            try:
                for name,body in files.items():(folder/name).write_bytes(body)
                self.store.set('human_avatar',dict(revision=ident,enabled=True,rig=rig,alignment=dict(x=0,y=0,scale=1)))
            except Exception:
                shutil.rmtree(folder,ignore_errors=True);raise
            if old:shutil.rmtree(self.directory/old,ignore_errors=True)
            return self.status()

    def configure(self,body):
        if not isinstance(body,dict) or set(body)-{'enabled','alignment'}:raise ValueError('Unknown avatar setting.')
        with self.lock:
            p=self.store.get('human_avatar',{})
            if not isinstance(p,dict):p={}
            if 'enabled' in body:
                if type(body['enabled']) is not bool:raise ValueError('enabled must be true or false.')
                if body['enabled'] and not self.status()['present']:raise ValueError('Choose an avatar photo first.')
                p['enabled']=body['enabled']
            if 'alignment' in body:
                a=body['alignment']
                if not isinstance(a,dict) or set(a)!={'x','y','scale'} or not numbers([a['x'],a['y'],a['scale']],3) or abs(a['x'])>.15 or abs(a['y'])>.15 or not .7<=a['scale']<=1.3:
                    raise ValueError('Invalid facial alignment.')
                p['alignment']=dict(a)
            self.store.set('human_avatar',p);return self.status()

    def remove(self):
        with self.lock:
            old=self.status()['revision'];self.store.set('human_avatar',{})
            if old:shutil.rmtree(self.directory/old,ignore_errors=True)
            return self.status()

def live_snapshot(profile,voice,tts,handsfree,personal,muted,stopped,thinking):
    v=voice.animation_status();t=tts.animation_status();hf=handsfree.status();animation=t['animation']
    if stopped:phase='emergency'
    elif muted:phase='idle'
    elif animation.get('playing'):phase='speaking'
    elif thinking or hf.get('phase')=='thinking' or v['phase'] in ('calibrating','transcribing') or t['phase'] in ('starting','preparing'):phase='thinking'
    elif v['phase']=='listening' or hf.get('active') and hf.get('phase') in ('listening','approval'):phase='listening'
    else:phase='idle'
    if phase!='speaking':animation=dict(playing=False,pose=0,openness=0,cues=[],mode=animation.get('mode','unavailable'))
    return dict(enabled=profile.status()['enabled'],blocked=bool(muted or stopped),phase=phase,emotion=personal.mood(),job_id=t['job_id'],animation=animation)

def register(app,profile,snapshot):
    @app.get('/api/human-avatar')
    def status():return profile.status()

    @app.post('/api/human-avatar/settings')
    async def settings(request:Request):return profile.configure(await request.json())

    @app.post('/api/human-avatar/import')
    async def import_photo(request:Request):
        data=bytearray()
        async for part in request.stream():
            data.extend(part)
            if len(data)>PACK_LIMIT:raise HTTPException(413,'Avatar file is larger than 4 MB.')
        return profile.import_file(bytes(data))

    @app.delete('/api/human-avatar/photo')
    def remove():return profile.remove()

    @app.get('/api/human-avatar/assets/{name}')
    def asset(name:str):
        if name not in ('portrait.png','expressions.png'):raise HTTPException(404)
        with profile.lock:
            p=profile.status()
            if not p['present']:raise HTTPException(404)
            file=profile.directory/p['revision']/name
            if not file.is_file():raise HTTPException(404)
            return Response(file.read_bytes(),media_type='image/png',headers={'Cache-Control':'no-store','Cross-Origin-Resource-Policy':'same-origin'})

    @app.get('/api/human-avatar/live')
    def live():return snapshot()

    @app.get('/api/human-avatar/events')
    async def events(request:Request):
        async def stream():
            previous=None;heartbeat=time.monotonic()
            while not await request.is_disconnected():
                value=await asyncio.to_thread(snapshot);payload=json.dumps(value,separators=(',',':'))
                if payload!=previous:
                    yield 'data: '+payload+'\n\n';previous=payload;heartbeat=time.monotonic()
                elif time.monotonic()-heartbeat>12:
                    yield ': heartbeat\n\n';heartbeat=time.monotonic()
                if not value['enabled']:return
                await asyncio.sleep(.04 if value['phase']=='speaking' else .20)
        return StreamingResponse(stream(),media_type='text/event-stream',headers={'Cache-Control':'no-store','X-Accel-Buffering':'no'})
