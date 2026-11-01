import importlib
from unittest.mock import AsyncMock
from fastapi.testclient import TestClient


def test_auto_voice_routes_require_session_consent_and_visible_avatar(tmp_path,monkeypatch):
    monkeypatch.setenv('NEXUS_DATA_DIR',str(tmp_path))
    import nexus.app
    m=importlib.reload(nexus.app)
    # No real audio in this transport test; consent validation itself is tested on HandsFree.
    start=AsyncMock(return_value={'active':True});stop=AsyncMock(return_value={'active':False})
    monkeypatch.setattr(m.handsfree,'start',start);monkeypatch.setattr(m.handsfree,'stop',stop)
    monkeypatch.setattr(m.avatar,'window',None)
    with TestClient(m.app) as c:
        assert c.post('/api/handsfree/start',json={'consent':True,'online_consent':True}).status_code==403
        c.headers['x-nexus-token']=m.session_token
        assert c.post('/api/handsfree/start',json={'consent':True}).status_code==400;start.assert_not_called()
        monkeypatch.setattr(m.avatar,'window',object())
        assert c.post('/api/handsfree/start',json={'consent':True,'online_consent':True}).status_code==200
        start.assert_awaited_once_with(True,True,False)
        assert c.post('/api/handsfree/stop').status_code==200;stop.assert_awaited_once()
        assert c.post('/api/handsfree/arbitrary').status_code==400
    m.store.db.close()


def test_avatar_close_stops_auto_voice_before_returning_dashboard(tmp_path,monkeypatch):
    monkeypatch.setenv('NEXUS_DATA_DIR',str(tmp_path))
    import nexus.app
    m=importlib.reload(nexus.app);events=[]
    async def stop():events.append('mic stopped');return {'active':False}
    monkeypatch.setattr(m.handsfree,'stop',stop)
    monkeypatch.setattr(m.avatar,'available',lambda:True)
    monkeypatch.setattr(m.avatar,'close',lambda:events.append('closed') or {'visible':False})
    monkeypatch.setattr(m.avatar,'dashboard',lambda:events.append('dashboard') or {'requested':True})
    with TestClient(m.app) as c:
        c.headers['x-nexus-token']=m.session_token
        assert c.post('/api/avatar/close').status_code==200
        assert events[:3]==['mic stopped','closed','dashboard']
    m.store.db.close()


def test_online_speaker_preference_is_saved_only_after_explicit_start(tmp_path,monkeypatch):
    monkeypatch.setenv('NEXUS_DATA_DIR',str(tmp_path))
    import nexus.app
    m=importlib.reload(nexus.app);start=AsyncMock(return_value={'active':True})
    monkeypatch.setattr(m.handsfree,'start',start);monkeypatch.setattr(m.avatar,'window',object())
    with TestClient(m.app) as c:
        c.headers['x-nexus-token']=m.session_token
        body={'consent':True,'online_consent':True,'allow_online_tts':True}
        assert c.post('/api/handsfree/start',json=body).status_code==200
        start.assert_awaited_with(True,True,True)
        assert m.store.get('handsfree_online_tts') is True
        assert c.post('/api/handsfree/start',json={'consent':True,'online_consent':True}).status_code==200
        start.assert_awaited_with(True,True,True)
        body['allow_online_tts']=False;c.post('/api/handsfree/start',json=body)
        assert m.store.get('handsfree_online_tts') is False
    m.store.db.close()


def test_only_explicit_true_unmute_flag_is_forwarded(tmp_path,monkeypatch):
    monkeypatch.setenv('NEXUS_DATA_DIR',str(tmp_path))
    import nexus.app
    m=importlib.reload(nexus.app);start=AsyncMock(return_value={'active':True})
    monkeypatch.setattr(m.handsfree,'start',start);monkeypatch.setattr(m.avatar,'window',object())
    with TestClient(m.app) as c:
        c.headers['x-nexus-token']=m.session_token
        assert c.post('/api/handsfree/start',json={'consent':True,'online_consent':True,'unmute':True}).status_code==200
        start.assert_awaited_with(True,True,False,unmute=True)
        assert c.post('/api/handsfree/start',json={'consent':True,'online_consent':True,'unmute':'true'}).status_code==200
        start.assert_awaited_with(True,True,False)
    m.store.db.close()
