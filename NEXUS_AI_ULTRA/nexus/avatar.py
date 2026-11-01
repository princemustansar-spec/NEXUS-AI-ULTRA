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
                resizable=False, easy_drag=True, shadow=False, js_api=None,
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
