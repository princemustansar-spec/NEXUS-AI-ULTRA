"""One optional native floating avatar. No downloads, model or extra browser."""
import threading
import sys
import logging


def extend_native_glass(handle):
    import ctypes
    class Margins(ctypes.Structure):
        _fields_=[('left',ctypes.c_int),('right',ctypes.c_int),('top',ctypes.c_int),('bottom',ctypes.c_int)]
    dwm=ctypes.WinDLL('dwmapi',use_last_error=True)
    extend=dwm.DwmExtendFrameIntoClientArea
    extend.argtypes=[ctypes.c_void_p,ctypes.POINTER(Margins)];extend.restype=ctypes.c_long
    result=extend(handle,ctypes.byref(Margins(-1,-1,-1,-1)))
    if result:raise OSError('Windows desktop transparency could not be initialized: '+str(result))


def apply_form_cutout(form, black, transparent, empty):
    """DWM glass retains HWND input; a keyed parent makes the WebView click-through."""
    form.AllowTransparency = True
    form.TransparencyKey = empty
    form.BackColor = black
    form.webview.BackColor = black
    form.webview.DefaultBackgroundColor = transparent
    extend_native_glass(form.Handle.ToInt64())
    form.Invalidate()


class CursorDrag:
    """Move one HWND in physical screen pixels, independent of WebView mouse capture."""
    def __init__(self, user32, handle):
        import ctypes
        from ctypes.wintypes import POINT, RECT
        self.user32,self.handle=user32,handle
        self.point,self.rect=POINT(),RECT()
        if not user32.GetAsyncKeyState(0x01) & 0x8000:
            raise ValueError('Hold the left mouse button on the avatar to drag.')
        if not user32.GetCursorPos(ctypes.byref(self.point)) or not user32.GetWindowRect(handle,ctypes.byref(self.rect)):
            raise OSError('Could not read avatar screen position.')
        self.origin=(self.point.x,self.point.y)
        self.last=(self.rect.left,self.rect.top)

    def step(self):
        import ctypes
        if not self.user32.GetAsyncKeyState(0x01) & 0x8000 or not self.user32.IsWindow(self.handle):return False
        if not self.user32.GetCursorPos(ctypes.byref(self.point)):raise OSError('Could not read mouse position.')
        position=(self.rect.left+self.point.x-self.origin[0],self.rect.top+self.point.y-self.origin[1])
        if position!=self.last:
            # NOSIZE | NOZORDER | NOACTIVATE | ASYNCWINDOWPOS: no caption/modal loop.
            if not self.user32.SetWindowPos(self.handle,None,*position,0,0,0x4015):
                raise OSError('Could not move floating avatar.')
            self.last=position
        return True


def native_drag_api():
    import ctypes
    from ctypes.wintypes import HWND, POINT, RECT, BOOL
    user32=ctypes.WinDLL('user32',use_last_error=True)
    signatures={
        'GetAsyncKeyState':([ctypes.c_int],ctypes.c_short),
        'GetCursorPos':([ctypes.POINTER(POINT)],BOOL),
        'GetWindowRect':([HWND,ctypes.POINTER(RECT)],BOOL),
        'IsWindow':([HWND],BOOL),
        'SetWindowPos':([HWND,HWND,ctypes.c_int,ctypes.c_int,ctypes.c_int,ctypes.c_int,ctypes.c_uint],BOOL),
    }
    for name,(args,result) in signatures.items():
        fn=getattr(user32,name);fn.argtypes=args;fn.restype=result
    return user32


class FloatingAvatar:
    def __init__(self):
        self.host = self.main = self.window = None
        self.url = ''
        self.lock = threading.RLock()
        self.cutout_ready = False
        self.drag_session = None
        self.drag_error = None

    def attach(self, host, main=None, url=''):
        with self.lock:
            if host is None:
                self.host = self.main = None
                self.close()
            else:
                self.host, self.main, self.url = host, main, url

    def available(self):
        return self.host is not None

    def show(self):
        with self.lock:
            if not self.host:
                raise ValueError('Floating avatar requires the native Windows app. Launch START_UPDATED_NEXUS.bat.')
            if self.window:
                self.window.show()
                return {'visible':True}
            window = self.host.create_window(
                'NEXUS Floating AI', self.url, width=280, height=290,
                min_size=(240,250), frameless=True, transparent=True, on_top=True,
                resizable=False, easy_drag=False, shadow=False, js_api=None,
                background_color='#010203', focus=False,
            )
            if window is None:
                raise ValueError('Could not create the floating avatar window.')
            self.window = window
            def closed():
                if self.window is window:
                    self.window = None
                    self.drag_session = None
                    self.cutout_ready = False
                    if self.main:
                        self.main.show()
                        self.main.restore()
            window.events.closed += closed
            def cutout():self.configure_cutout(window)
            if hasattr(window.events,'shown'):window.events.shown += cutout
            if hasattr(window.events,'loaded'):window.events.loaded += cutout
            cutout()
            return {'visible':True}

    def configure_cutout(self, window):
        if sys.platform!='win32':return False
        form=getattr(window,'native',None)
        if form is None:return False
        try:
            from System import Action
            from System.Drawing import Color
            def apply():
                try:
                    if self.window is not window:return
                    apply_form_cutout(form,Color.Black,Color.Transparent,Color.Empty)
                    self.cutout_ready=True
                except Exception:
                    logging.exception('Floating avatar native transparency failed')
            if form.InvokeRequired:form.BeginInvoke(Action(apply))
            else:apply()
            return True
        except Exception:
            logging.exception('Floating avatar native transparency unavailable')
            return False

    def can_native_drag(self):
        return sys.platform=='win32' and self.window is not None and getattr(self.window,'native',None) is not None

    def drag(self):
        if not self.can_native_drag():raise ValueError('Native avatar dragging requires the Windows floating window.')
        with self.lock:
            if self.drag_session is not None:return {'requested':True}
            window=self.window
            # Keep HWND, cursor and rectangle in native physical pixels, including negative monitors.
            tracker=CursorDrag(native_drag_api(),window.native.Handle.ToInt64())
            session=object();self.drag_session=session;self.drag_error=None
            delay=threading.Event()
            def follow():
                try:
                    while self.window is window and self.drag_session is session and tracker.step():
                        delay.wait(1/60)
                except Exception as exc:
                    self.drag_error=str(exc)
                    logging.exception('Floating avatar cursor drag failed')
                finally:
                    with self.lock:
                        if self.drag_session is session:self.drag_session=None
            threading.Thread(target=follow,name='NEXUS-avatar-drag',daemon=True).start()
            return {'requested':True}

    def close(self):
        with self.lock:
            window, self.window = self.window, None
            self.drag_session = None
            self.cutout_ready = False
            if window:
                window.destroy()
            return {'visible':False}

    def dashboard(self):
        with self.lock:
            if not self.main:
                raise ValueError('NEXUS desktop window is unavailable.')
            self.main.show()
            self.main.restore()
            return {'requested':True}


avatar = FloatingAvatar()
