from types import SimpleNamespace
from unittest.mock import Mock
import importlib
from fastapi.testclient import TestClient
from nexus.avatar import native_move_loop


def test_drag_uses_native_own_window_move_message_only_while_button_held():
    user32=SimpleNamespace(GetAsyncKeyState=Mock(return_value=0x8000),ReleaseCapture=Mock(),SendMessageW=Mock())
    assert native_move_loop(user32,12345)
    user32.ReleaseCapture.assert_called_once()
    user32.SendMessageW.assert_called_once_with(12345,0x00A1,2,0)
    user32.GetAsyncKeyState.return_value=0;user32.SendMessageW.reset_mock()
    assert not native_move_loop(user32,12345)
    user32.SendMessageW.assert_not_called()


def test_native_drag_route_requires_session_and_targets_avatar_only(tmp_path,monkeypatch):
    monkeypatch.setenv('NEXUS_DATA_DIR',str(tmp_path))
    import nexus.app
    m=importlib.reload(nexus.app)
    drag=Mock(return_value={'requested':True})
    monkeypatch.setattr(m.avatar,'drag',drag)
    with TestClient(m.app) as c:
        assert c.post('/api/avatar/drag').status_code==403;drag.assert_not_called()
        c.headers['x-nexus-token']=m.session_token
        assert c.post('/api/avatar/drag').json()['requested']
        drag.assert_called_once_with()
    m.store.db.close()
