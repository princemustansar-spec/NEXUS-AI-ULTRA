import asyncio
import copy
import importlib
import io
import json
import struct
import time
from types import SimpleNamespace
import zipfile
import zlib
import pytest
from fastapi.testclient import TestClient
from nexus.human_avatar import HumanAvatar,DEFAULT_RIG,parse_import,validate_rig,live_snapshot,register
from nexus.store import Store

def png(w=64,h=64):
    def chunk(kind,data):return struct.pack('>I',len(data))+kind+data+struct.pack('>I',zlib.crc32(kind+data)&0xffffffff)
    return b'\x89PNG\r\n\x1a\n'+chunk(b'IHDR',struct.pack('>IIBBBBB',w,h,8,6,0,0,0))+chunk(b'IDAT',zlib.compress((b'\0'+b'\x88\xaa\xcc\xff'*w)*h))+chunk(b'IEND',b'')

def pack(extra=None):
    data=io.BytesIO()
    with zipfile.ZipFile(data,'w',zipfile.ZIP_DEFLATED) as z:
        for name,value in {'portrait.png':png(),'expressions.png':png(128,128),'rig.json':json.dumps(DEFAULT_RIG).encode(),**(extra or {})}.items():z.writestr(name,value)
    return data.getvalue()

def test_profile_is_opt_in_local_and_switching_preserves_other_settings(tmp_path):
    store=Store(tmp_path/'test.db');store.set('preferred_provider','fixture-provider');profile=HumanAvatar(tmp_path,store)
    assert not profile.status()['enabled']
    status=profile.import_file(pack());assert status['enabled'] and status['frames']
    assert HumanAvatar(tmp_path,store).status()==status
    folder=profile.directory/status['revision'];assert (folder/'portrait.png').read_bytes()==png()
    profile.configure({'enabled':False});assert profile.status()['present'] and (folder/'expressions.png').is_file()
    profile.configure({'enabled':True,'alignment':dict(x=.01,y=-.01,scale=1.1)})
    assert profile.status()['alignment']['scale']==1.1 and store.get('preferred_provider')=='fixture-provider'
    assert 'data:image' not in json.dumps(profile.status()) and str(tmp_path) not in json.dumps(profile.status())
    profile.remove();assert not folder.exists() and not profile.status()['present'];store.db.close()

def test_new_photo_never_reuses_someone_elses_expression_frames(tmp_path):
    store=Store(tmp_path/'test.db');profile=HumanAvatar(tmp_path,store);old=profile.import_file(pack())
    profile.import_file(png());assert not profile.status()['frames'] and not (profile.directory/old['revision']).exists();store.db.close()

@pytest.mark.parametrize('bad',[b'<svg onload="x"/>',png()[:-1],png()+b'extra',png(2049),pack({'../outside.txt':b'unsafe'}),pack({'portrait.png':b'bad'}),pack({'rig.json':b'{bad json'})])
def test_import_validation_keeps_current_avatar_unchanged(tmp_path,bad):
    store=Store(tmp_path/'test.db');profile=HumanAvatar(tmp_path,store);before=profile.import_file(pack())
    with pytest.raises(ValueError):profile.import_file(bad)
    assert profile.status()==before;store.db.close()

def test_rig_and_alignment_bounds(tmp_path):
    rig=copy.deepcopy(DEFAULT_RIG);rig['neck']=[.8,.5]
    with pytest.raises(ValueError):validate_rig(rig)
    rig=copy.deepcopy(DEFAULT_RIG);rig['eyes'][0][2][0]=float('nan')
    with pytest.raises(ValueError):validate_rig(rig)
    store=Store(tmp_path/'test.db');p=HumanAvatar(tmp_path,store)
    for body in [{'enabled':'yes'},{'enabled':True},{'unknown':1},{'alignment':dict(x=2,y=0,scale=1)}]:
        with pytest.raises(ValueError):p.configure(body)
    store.db.close()

def fixture(tmp_path,monkeypatch):
    monkeypatch.setenv('NEXUS_DATA_DIR',str(tmp_path));import nexus.app
    return importlib.reload(nexus.app)

def test_routes_require_session_and_keep_photos_local(tmp_path,monkeypatch):
    app=fixture(tmp_path,monkeypatch);c=TestClient(app.app)
    assert c.post('/api/human-avatar/import',content=pack()).status_code==403
    c.headers['X-Nexus-Token']=app.session_token
    assert c.post('/api/human-avatar/import',content=pack(),headers={'Origin':'https://foreign.invalid'}).status_code==403
    assert c.post('/api/human-avatar/import',content=pack()).json()['frames']
    image=c.get('/api/human-avatar/assets/portrait.png');assert image.content==png() and image.headers['cross-origin-resource-policy']=='same-origin'
    assert c.get('/api/human-avatar/assets/rig.json').status_code==404
    assert c.post('/api/human-avatar/settings',json={'enabled':False}).json()['present']
    assert not c.get('/api/state').json()['human_avatar']['enabled']
    assert c.post('/api/human-avatar/settings',json={'enabled':True}).json()['enabled']
    assert c.delete('/api/human-avatar/photo').status_code==200;assert c.get('/api/human-avatar/assets/portrait.png').status_code==404
    app.store.db.close()

def test_live_states_use_playback_not_preparation_and_stop_at_mute_cancel(tmp_path,monkeypatch):
    app=fixture(tmp_path,monkeypatch);app.human_avatar.import_file(pack());app.store.set('voice_muted',False);c=TestClient(app.app);c.headers['X-Nexus-Token']=app.session_token
    app.tts.state=dict(job_id='current',phase='preparing');assert c.get('/api/human-avatar/live').json()['phase']=='thinking'
    app.tts.state=dict(job_id='current',phase='speaking',animation=dict(playing=True,emitted_at=time.monotonic(),position_ms=50,cues=[[40,.7,2],[180,0,0]],pose=2,openness=.7,mode='audio-envelope'))
    value=c.get('/api/human-avatar/live').json();assert value['phase']=='speaking' and value['animation']['cues'] and 'emitted_at' not in value['animation']
    assert c.post('/api/tts/stop',json={}).status_code==200;assert c.get('/api/human-avatar/live').json()['phase']=='idle'
    app.voice.state=dict(phase='listening',level_dbfs=-25);assert c.get('/api/human-avatar/live').json()['phase']=='listening'
    app.voice.state=dict(phase='transcribing');assert c.get('/api/human-avatar/live').json()['phase']=='thinking'
    app.voice.state=dict(phase='idle');app.store.set('voice_muted',True);value=c.get('/api/human-avatar/live').json();assert value['blocked'] and not value['animation']['playing']
    monkeypatch.setattr(app,'emergency',True);assert c.get('/api/human-avatar/live').json()['phase']=='emergency';app.store.db.close()

def test_event_stream_emits_compact_state_and_finishes_when_disabled():
    from fastapi import FastAPI
    app=FastAPI();calls=[0]
    def snapshot():calls[0]+=1;return dict(enabled=calls[0]==1,phase='idle',animation={})
    register(app,None,snapshot);endpoint=next(r.endpoint for r in app.routes if r.path=='/api/human-avatar/events')
    async def disconnected():return False
    async def check():
        response=await endpoint(SimpleNamespace(is_disconnected=disconnected));rows=[]
        async for row in response.body_iterator:rows.append(row)
        assert len(rows)==2 and all(r.startswith('data: ') for r in rows)
    asyncio.run(check())
