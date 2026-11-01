import importlib
from unittest.mock import Mock
import pytest
from fastapi.testclient import TestClient

@pytest.fixture
def client(tmp_path,monkeypatch):
    monkeypatch.setenv('NEXUS_DATA_DIR',str(tmp_path))
    import nexus.app
    m=importlib.reload(nexus.app)
    with TestClient(m.app) as c:
        c.headers['x-nexus-token']=m.session_token
        yield c,m
    m.store.db.close()


def test_desktop_mode_and_auto_voice_are_saved_and_reported(client):
    c,m=client
    options={'desktop_mode':'floating','auto_voice':False}
    assert c.post('/api/settings',json={'avatar_settings':options}).status_code==200
    result=c.get('/api/state').json()['avatar_settings']
    assert result['desktop_mode']=='floating' and result['auto_voice'] is False
    assert m.store.get('desktop_mode')=='floating'
    assert c.post('/api/settings',json={'avatar_settings':{'desktop_mode':'gui','auto_voice':True}}).status_code==200
    assert m.store.get('desktop_mode')=='gui'


@pytest.mark.parametrize('options',[{'desktop_mode':'shell','auto_voice':True},{'desktop_mode':'gui','auto_voice':'yes'},None])
def test_invalid_start_preferences_are_rejected(client,options):
    c,m=client
    assert c.post('/api/settings',json={'avatar_settings':options}).status_code==400
    assert m.store.get('desktop_mode') is None


def test_gui_shortcut_repair_requires_session_and_targets_this_install(client,monkeypatch):
    c,m=client;repair=Mock(return_value={'updated':True})
    monkeypatch.setattr('create_shortcut.repair_source_shortcut',repair)
    assert c.post('/api/desktop/shortcut',headers={'x-nexus-token':'wrong'}).status_code==403
    repair.assert_not_called()
    assert c.post('/api/desktop/shortcut').json()['updated']
    repair.assert_called_once_with(m.BASE)


def test_disabling_auto_voice_stops_current_session(client,monkeypatch):
    from unittest.mock import AsyncMock
    c,m=client;stop=AsyncMock()
    monkeypatch.setattr(m.handsfree,'running',True);monkeypatch.setattr(m.handsfree,'stop',stop)
    assert c.post('/api/settings',json={'avatar_settings':{'desktop_mode':'gui','auto_voice':False}}).status_code==200
    stop.assert_awaited_once()
