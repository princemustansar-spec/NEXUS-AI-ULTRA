"""One optional native floating avatar. No downloads, model or extra browser."""
import threading
import sys
import logging


def apply_form_cutout(form, key_color, transparent_color):
    """Edge's alpha background must reveal a keyed native form, not Control white."""
    form.AllowTransparency = True
    form.BackColor = key_color
    form.TransparencyKey = key_color
    form.webview.BackColor = key_color
    form.webview.DefaultBackgroundColor = transparent_color
    form.Invalidate()


def native_move_loop(user32, handle):
    # Do not enter a modal move loop after a short click has already been released.
    if not user32.GetAsyncKeyState(0x01) & 0x8000:return False
    user32.ReleaseCapture()
    user32.SendMessageW(handle,0x00A1,2,0)  # WM_NCLBUTTONDOWN / HTCAPTION
    return True


class FloatingAvatar:
    def __init__(self):
        self.host = self.main = self.window = None
        self.url = ''
        self.lock = threading.RLock()
        self.cutout_ready = False

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
                    apply_form_cutout(form,Color.FromArgb(1,2,3),Color.Transparent)
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
        from System import Action
        import ctypes
        window=self.window;form=window.native
        user32=ctypes.WinDLL('user32',use_last_error=True)
        user32.GetAsyncKeyState.argtypes=[ctypes.c_int];user32.GetAsyncKeyState.restype=ctypes.c_short
        user32.ReleaseCapture.argtypes=[];user32.ReleaseCapture.restype=ctypes.c_int
        user32.SendMessageW.argtypes=[ctypes.c_void_p,ctypes.c_uint,ctypes.c_size_t,ctypes.c_ssize_t]
        user32.SendMessageW.restype=ctypes.c_ssize_t
        def begin():
            if self.window is window:native_move_loop(user32,form.Handle.ToInt64())
        form.BeginInvoke(Action(begin))
        return {'requested':True}

    def close(self):
        with self.lock:
            window, self.window = self.window, None
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
