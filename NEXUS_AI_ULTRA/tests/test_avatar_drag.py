from types import SimpleNamespace
from unittest.mock import Mock
import importlib
from fastapi.testclient import TestClient
from nexus.avatar import CursorDrag
import pytest


def drag_api(points=((300,200),(330,240))):
    points=iter(points)
    def cursor(ptr):ptr._obj.x,ptr._obj.y=next(points);return True
    def rect(handle,ptr):ptr._obj.left=-600;ptr._obj.top=100;return True
    return SimpleNamespace(GetAsyncKeyState=Mock(return_value=0x8000),GetCursorPos=Mock(side_effect=cursor),
        GetWindowRect=Mock(side_effect=rect),IsWindow=Mock(return_value=True),SetWindowPos=Mock(return_value=True))


def test_drag_moves_actual_window_by_cursor_delta_and_stops_on_release():
    api=drag_api();drag=CursorDrag(api,12345)
    assert drag.step()
    api.SetWindowPos.assert_called_once_with(12345,None,-570,140,0,0,0x4015)
    api.GetAsyncKeyState.return_value=0
    assert not drag.step()
    assert api.SetWindowPos.call_count==1


def test_drag_does_not_start_after_release_or_move_destroyed_window():
    api=drag_api();api.GetAsyncKeyState.return_value=0
    with pytest.raises(ValueError,match='Hold'):CursorDrag(api,12345)
    api.GetCursorPos.assert_not_called()
    api.GetAsyncKeyState.return_value=0x8000;drag=CursorDrag(api,12345)
    api.IsWindow.return_value=False
    assert not drag.step();api.SetWindowPos.assert_not_called()


def test_drag_does_not_move_idle_cursor_and_reports_native_failure():
    api=drag_api(((300,200),(300,200),(340,200)));drag=CursorDrag(api,12345)
    assert drag.step();api.SetWindowPos.assert_not_called()
    api.SetWindowPos.return_value=False
    with pytest.raises(OSError,match='move'):drag.step()


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


@pytest.mark.skipif(__import__('sys').platform!='win32',reason='Real HWND contract needs Windows')
def test_real_windows_handle_is_moved_without_caption_or_mouse_capture():
    import ctypes
    from ctypes.wintypes import HWND, RECT, HINSTANCE
    from nexus.avatar import native_drag_api
    api=native_drag_api()
    create=api.CreateWindowExW
    create.argtypes=[ctypes.c_uint,ctypes.c_wchar_p,ctypes.c_wchar_p,ctypes.c_uint,
        ctypes.c_int,ctypes.c_int,ctypes.c_int,ctypes.c_int,HWND,ctypes.c_void_p,HINSTANCE,ctypes.c_void_p]
    create.restype=HWND
    api.DestroyWindow.argtypes=[HWND];api.DestroyWindow.restype=ctypes.c_int
    handle=create(0,'STATIC','NEXUS drag contract',0x80000000,-400,100,80,80,None,None,None,None)
    assert handle,'Disposable hidden native window must be created'
    try:
        def cursor(ptr):
            ptr._obj.x,ptr._obj.y=next(points);return True
        points=iter(((300,200),(330,240)))
        wrapper=SimpleNamespace(GetAsyncKeyState=lambda key:0x8000,GetCursorPos=cursor,
            GetWindowRect=api.GetWindowRect,IsWindow=api.IsWindow,SetWindowPos=api.SetWindowPos)
        before=RECT();assert api.GetWindowRect(handle,ctypes.byref(before))
        drag=CursorDrag(wrapper,handle);assert drag.step()
        after=RECT();assert api.GetWindowRect(handle,ctypes.byref(after))
        assert (after.left,after.top)==(before.left+30,before.top+40)
        assert (after.right-after.left,after.bottom-after.top)==(before.right-before.left,before.bottom-before.top)
    finally:api.DestroyWindow(handle)
