"""Real WebView2 avatar + Win32 mouse input regression; no microphone/provider calls."""
import ctypes
from ctypes.wintypes import HWND, POINT, RECT
import json
import os
from pathlib import Path
import sys
import tempfile
import time
import traceback
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))


def main():
    import webview
    from nexus.desktop import LocalBackend
    from nexus.avatar import avatar,native_drag_api
    api=native_drag_api()
    api.SetCursorPos.argtypes=[ctypes.c_int,ctypes.c_int];api.SetCursorPos.restype=ctypes.c_int
    api.mouse_event.argtypes=[ctypes.c_uint,ctypes.c_uint,ctypes.c_uint,ctypes.c_uint,ctypes.c_size_t]
    api.WindowFromPoint.argtypes=[POINT];api.WindowFromPoint.restype=HWND
    api.GetAncestor.argtypes=[HWND,ctypes.c_uint];api.GetAncestor.restype=HWND
    saved=POINT();api.GetCursorPos(ctypes.byref(saved))
    result={};failures=[]
    with tempfile.TemporaryDirectory(prefix='nexus-avatar-mouse-') as directory:
        os.environ['NEXUS_DATA_DIR']=directory
        backend=LocalBackend(directory);backend.start()
        main_window=webview.create_window('NEXUS mouse regression',html='<html><body style="margin:0;background:rgb(230,40,180)"></body></html>',x=100,y=100,width=700,height=550,frameless=True)
        avatar.attach(webview,main_window,backend.url+'/static/avatar.html')
        def rect(window):
            value=RECT();assert api.GetWindowRect(window.native.Handle.ToInt64(),ctypes.byref(value));return value
        def run():
            try:
                avatar.show();window=avatar.window
                assert window.events.loaded.wait(30),'Avatar page did not load'
                deadline=time.monotonic()+15
                while time.monotonic()<deadline:
                    if window.evaluate_js("document.querySelector('#phase').textContent")=='READY':break
                    time.sleep(.1)
                else:raise AssertionError('Avatar telemetry did not become ready')
                window.move(220,180)
                window.evaluate_js("window.mouseProbe={pointer:0,mouse:0};document.addEventListener('pointerdown',()=>mouseProbe.pointer++,true);document.addEventListener('mousedown',()=>mouseProbe.mouse++,true);")
                time.sleep(.3)
                api.GetDC.argtypes=[HWND];api.GetDC.restype=ctypes.c_void_p
                api.ReleaseDC.argtypes=[HWND,ctypes.c_void_p]
                gdi=ctypes.WinDLL('gdi32');gdi.GetPixel.argtypes=[ctypes.c_void_p,ctypes.c_int,ctypes.c_int];gdi.GetPixel.restype=ctypes.c_uint
                screen=api.GetDC(None)
                box=rect(window);corner=gdi.GetPixel(screen,box.left+3,box.top+3)
                api.ReleaseDC(None,screen)
                result['corner_rgb']=[corner&255,(corner>>8)&255,(corner>>16)&255]
                print(json.dumps(result),flush=True)
                assert result['corner_rgb']==[230,40,180],'Avatar blank corner must reveal underlying desktop, not a backing rectangle'
                for delta in (100,-80):
                    before=rect(window);x=(before.left+before.right)//2;y=(before.top+before.bottom)//2
                    assert api.SetCursorPos(x,y),'Interactive cursor could not be positioned'
                    time.sleep(.3)
                    point=POINT();api.GetCursorPos(ctypes.byref(point))
                    assert (point.x,point.y)==(x,y),'Runner has no interactive cursor desktop'
                    hit=api.WindowFromPoint(point);root=api.GetAncestor(hit,2)
                    result['hit_avatar']=int(root or 0)==window.native.Handle.ToInt64()
                    api.mouse_event(2,0,0,0,0);time.sleep(.3)
                    for offset in range(10,abs(delta)+1,10):
                        api.SetCursorPos(x+(offset if delta>0 else -offset),y+20);time.sleep(.025)
                    time.sleep(.3);api.mouse_event(4,0,0,0,0);time.sleep(.2)
                    after=rect(window)
                    result.update(delta=[after.left-before.left,after.top-before.top],events=window.evaluate_js('window.mouseProbe'),detail=window.evaluate_js("document.querySelector('#detail').textContent"),drag_error=avatar.drag_error,cutout=avatar.cutout_ready)
                    print(json.dumps(result),flush=True)
                    assert abs((after.left-before.left)-delta)<=3 and abs((after.top-before.top)-20)<=3,'Actual avatar did not follow physical mouse input'
                    api.SetCursorPos(x+delta+50,y+70);time.sleep(.2);released=rect(window)
                    assert (released.left,released.top)==(after.left,after.top),'Avatar kept moving after mouse release'
                print('Real transparent WebView2 avatar dragged left and right and stopped on release',flush=True)
            except BaseException:
                failures.append(traceback.format_exc());print(failures[-1],flush=True)
            finally:
                api.mouse_event(4,0,0,0,0)
                api.SetCursorPos(saved.x,saved.y)
                avatar.close();main_window.destroy()
        try:webview.start(run,gui='edgechromium',debug=False,private_mode=True)
        finally:
            avatar.attach(None);backend.close()
            from nexus.app import store
            store.db.close()
    if failures:raise SystemExit(1)


if __name__=='__main__':main()
