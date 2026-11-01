from types import SimpleNamespace
from unittest.mock import Mock
import importlib
import pytest
from fastapi.testclient import TestClient
from nexus.avatar import FloatingAvatar

class Event:
    def __init__(self):self.handlers=[]
    def __iadd__(self,fn):self.handlers.append(fn);return self


def test_avatar_is_lazy_reused_draggable_on_top_and_independently_closed():
    a=FloatingAvatar()
    with pytest.raises(ValueError,match='native Windows'):a.show()
    window=SimpleNamespace(events=SimpleNamespace(closed=Event()),destroy=Mock(),show=Mock())
    main=SimpleNamespace(show=Mock(),restore=Mock(),hide=Mock())
    host=SimpleNamespace(create_window=Mock(return_value=window))
    a.attach(host,main,'http://127.0.0.1:8765/static/avatar.html')
    host.create_window.assert_not_called()
    assert a.show()['visible']
    options=host.create_window.call_args.kwargs
    assert options['transparent'] and options['frameless'] and not options['easy_drag'] and options['on_top']
    assert options['js_api'] is None and not options['focus']
    a.show();assert host.create_window.call_count==1;window.show.assert_called_once()
    a.dashboard();main.show.assert_called_once();main.restore.assert_called_once()
    a.close();window.destroy.assert_called_once();assert a.window is None and a.available()
    a.show();assert host.create_window.call_count==2
    a.attach(None);assert not a.available() and a.window is None


def test_user_close_allows_avatar_recreation():
    a=FloatingAvatar();w=SimpleNamespace(events=SimpleNamespace(closed=Event()),destroy=Mock())
    host=SimpleNamespace(create_window=Mock(return_value=w));a.attach(host,None,'http://127.0.0.1:8765/static/avatar.html');a.show()
    w.events.closed.handlers[0]();assert a.window is None
    a.show();assert host.create_window.call_count==2;a.attach(None)


def test_avatar_routes_are_authenticated_and_telemetry_is_minimal(tmp_path,monkeypatch):
    monkeypatch.setenv('NEXUS_DATA_DIR',str(tmp_path))
    import nexus.app
    m=importlib.reload(nexus.app)
    monkeypatch.setattr(m.voice,'status',lambda:{'phase':'listening','level_dbfs':-24,'result':{'text':'private transcript'}})
    monkeypatch.setattr(m.tts,'status',lambda:{'phase':'idle','result':{'text':'private reply'}})
    show=Mock(return_value={'visible':True});close=Mock(return_value={'visible':False})
    monkeypatch.setattr(m.avatar,'show',show);monkeypatch.setattr(m.avatar,'close',close)
    with TestClient(m.app) as client:
        state=client.get('/api/avatar/status').json();token=state.pop('token')
        assert state['voice']=={'phase':'listening','level_dbfs':-24}
        assert state['tts']=={'phase':'idle'}
        assert 'private' not in str(state) and 'chat' not in state
        assert client.post('/api/avatar/show').status_code==403;show.assert_not_called()
        client.headers['x-nexus-token']=token
        assert client.post('/api/avatar/show').json()['visible'];show.assert_called_once()
        assert client.post('/api/avatar/close').status_code==200;close.assert_called_once()
        assert client.post('/api/avatar/arbitrary').status_code==400
        assert client.get('/static/avatar.html').status_code==200
    m.store.db.close()
