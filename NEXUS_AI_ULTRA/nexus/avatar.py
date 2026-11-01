"""One optional native floating avatar. No downloads, model or extra browser."""
import threading


class FloatingAvatar:
    def __init__(self):
        self.host = self.main = self.window = None
        self.url = ''
        self.lock = threading.RLock()

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
                'NEXUS Floating AI', self.url, width=310, height=370,
                min_size=(260,310), frameless=True, transparent=True, on_top=True,
                resizable=False, easy_drag=True, shadow=False, js_api=None,
                background_color='#030d18', focus=False,
            )
            if window is None:
                raise ValueError('Could not create the floating avatar window.')
            self.window = window
            def closed():
                if self.window is window:
                    self.window = None
            window.events.closed += closed
            return {'visible':True}

    def close(self):
        with self.lock:
            window, self.window = self.window, None
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
