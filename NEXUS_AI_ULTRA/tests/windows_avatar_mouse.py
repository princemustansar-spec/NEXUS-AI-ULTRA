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
                # Hover is physical input too; exercise buttons without JS-dispatched clicks.
                box=rect(window);api.SetCursorPos((box.left+box.right)//2,(box.top+box.bottom)//2);time.sleep(.3)
                assert window.evaluate_js("getComputedStyle(document.querySelector('header')).opacity")=='1','Hover must reveal controls'
                def click_button(name):
                    bounds=window.evaluate_js("(()=>{const r=document.getElementById('"+name+"').getBoundingClientRect();return {x:r.x+r.width/2,y:r.y+r.height/2,w:innerWidth,h:innerHeight};})()")
                    box=rect(window)
                    api.SetCursorPos(round(box.left+bounds['x']*(box.right-box.left)/bounds['w']),round(box.top+bounds['y']*(box.bottom-box.top)/bounds['h']))
                    time.sleep(.2);api.mouse_event(2,0,0,0,0);time.sleep(.1);api.mouse_event(4,0,0,0,0);time.sleep(.3)
                motion=window.evaluate_js("localStorage.getItem('core-motion')")
                click_button('motion')
                assert window.evaluate_js("localStorage.getItem('core-motion')")!=motion,'Motion button must receive actual click'
                main_window.hide();time.sleep(.2);assert not main_window.native.Visible
                click_button('dashboard')
                deadline=time.monotonic()+3
                while not main_window.native.Visible and time.monotonic()<deadline:time.sleep(.1)
                assert main_window.native.Visible,'Open NEXUS must receive actual click and show GUI'
                # Exercise the real mic button and backend consent/mute transition, without audio.
                import asyncio
                from nexus.app import handsfree,store
                async def no_audio_session():await asyncio.sleep(3600)
                handsfree._run=no_audio_session
                store.set('voice_muted',True)
                click_button('mic')
                deadline=time.monotonic()+3
                while not handsfree.running and time.monotonic()<deadline:time.sleep(.1)
                assert handsfree.running and store.get('voice_muted') is False,'Explicit floating mic click must unmute and start'
                handsfree.phase='speaking'
                deadline=time.monotonic()+3
                while window.evaluate_js("document.querySelector('#interrupt').disabled") and time.monotonic()<deadline:time.sleep(.1)
                click_button('interrupt')
                assert handsfree.interrupt_event.is_set(),'Native Stop & listen must dispatch interruption without stopping auto voice'
                handsfree.phase='listening'
                click_button('mic')
                deadline=time.monotonic()+3
                while handsfree.running and time.monotonic()<deadline:time.sleep(.1)
                assert not handsfree.running,'Second mic click must pause listening'
                print('Real transparent WebView2 avatar: drag, release, hover, controls and explicit mic unmute/start/pause passed (no audio)',flush=True)
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
