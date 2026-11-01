"""Thin native host for the existing local dashboard; no alternate frontend."""
import http.client
import json
import os
import socket
import sys
import threading
import time
from pathlib import Path

import uvicorn

HOST = '127.0.0.1'
PORT = 8765
URL = f'http://{HOST}:{PORT}'


class LocalBackend:
    """Own one server/socket and wait for the actual application's readiness."""
    def __init__(self, data_dir, port=PORT):
        self.data_dir = Path(data_dir)
        self.port = port
        self.url = f'http://{HOST}:{port}'
        self.sock = None
        self.thread = None
        self.failure = None
        self.server = None
        self.pidfile = self.data_dir / 'server.pid'

    def prepare(self):
        self.data_dir.mkdir(parents=True, exist_ok=True)
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            if sys.platform == 'win32':
                sock.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
            else:
                sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            sock.bind((HOST, self.port))
            self.port = sock.getsockname()[1]
            self.url = f'http://{HOST}:{self.port}'
            sock.listen(128)
        except OSError as exc:
            sock.close()
            raise RuntimeError(f'Local port {self.port} is unavailable. Close the existing NEXUS instance; no other process was stopped.') from exc
        self.sock = sock
        try:
            self.server = uvicorn.Server(uvicorn.Config(
                'nexus.app:app', host=HOST, port=self.port, workers=1,
                log_config=None, access_log=False, timeout_graceful_shutdown=3,
            ))
            self.pidfile.write_text(str(os.getpid()), encoding='ascii')
        except BaseException:
            self.close()
            raise

    def run(self):
        try:
            self.server.run(sockets=[self.sock])
        except BaseException as exc:
            self.failure = exc
        finally:
            # For a headless run there is no enclosing GUI loop to do cleanup.
            if self.thread is None:
                self.close()

    def start(self, timeout=15):
        self.prepare()
        self.thread = threading.Thread(target=self.run, name='NEXUS-local-api', daemon=True)
        self.thread.start()
        return self.wait_ready(timeout)

    def wait_ready(self, timeout):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if self.failure or not self.thread.is_alive():
                raise RuntimeError('NEXUS backend failed during startup. See desktop.log.') from self.failure
            connection = http.client.HTTPConnection(HOST, self.port, timeout=.3)
            try:
                connection.request('GET', '/api/state')
                response = connection.getresponse()
                if response.status == 200:
                    state = json.loads(response.read())
                    if state.get('monitor', {}).get('pid') == os.getpid() and len(state.get('tools', [])) >= 18:
                        return state
            except (OSError, ValueError, http.client.HTTPException):
                pass
            finally:
                connection.close()
            time.sleep(.05)
        raise RuntimeError('NEXUS backend did not become ready within 15 seconds. See desktop.log.')

    def close(self):
        if self.server:
            self.server.should_exit = True
        if self.thread and self.thread.is_alive() and threading.current_thread() is not self.thread:
            self.thread.join(timeout=7)
        if self.sock:
            self.sock.close()
            self.sock = None
        if self.pidfile.exists() and self.pidfile.read_text(encoding='ascii') == str(os.getpid()):
            self.pidfile.unlink()
        if self.thread and self.thread.is_alive():
            raise RuntimeError('Backend shutdown timed out; the desktop process will exit. Completed actions cannot be reversed.')


def load_webview():
    if sys.platform != 'win32':
        raise RuntimeError('The desktop launcher requires Windows 11. Use --headless for cloud/API tests; no browser will be opened.')
    try:
        import webview
    except ImportError as exc:
        raise RuntimeError('pywebview is missing. Run INSTALL.bat, then START_NEXUS.bat.') from exc
    return webview


def run_desktop(backend, webview):
    """Called on the main thread. Closing the only native window stops our API."""
    try:
        state = backend.start()
        # Reuse OS WebView2; no bundled Qt/CEF/Electron or default-browser launch.
        webview.settings['ALLOW_FILE_URLS'] = False
        webview.settings['ALLOW_DOWNLOADS'] = False
        window = webview.create_window(
            state['name'], backend.url, width=1366, height=900,
            min_size=(800, 600), resizable=True, maximized=True,
            background_color='#030d18', text_select=True, js_api=None,
        )
        if window is None:
            raise RuntimeError('Could not create the NEXUS desktop window.')
        from .youtube import player
        player.attach(webview)
        if hasattr(window, 'events'):
            window.events.closed += lambda: player.attach(None)
        webview.start(
            gui='edgechromium', debug=False, http_server=False,
            private_mode=False, storage_path=str(backend.data_dir / 'webview'),
        )
    except Exception as exc:
        raise RuntimeError('Desktop startup failed. Install Microsoft Edge WebView2 Evergreen Runtime if needed. ' + str(exc)) from exc
    finally:
        from .youtube import player
        player.attach(None)
        backend.close()
