import os
import platform
import re
import shutil
import subprocess
import time
import webbrowser
from pathlib import Path
from urllib.parse import quote, urlencode
import psutil

CATALOG = {
 'system_info': ('Live CPU, RAM, disk, OS information', False, {}),
 'processes': ('List running processes', False, {}),
 'windows': ('List visible Windows desktop windows', False, {}),
 'list_files': ('List files under approved folders', False, {'path':'string'}),
 'search_files': ('Search filenames in an approved folder, limited to 200 results', False, {'path':'string','query':'string'}),
 'read_document': ('Read a UTF-8 text document in an approved folder', True, {'path':'string'}),
 'create_text': ('Create a new text file without overwriting', True, {'path':'string','text':'string'}),
 'copy_file': ('Copy a file without overwriting', True, {'source':'string','destination':'string'}),
 'move_file': ('Move a file without overwriting', True, {'source':'string','destination':'string'}),
 'open_app': ('Open an allowlisted Windows app: notepad, calculator, paint', True, {'app':'string'}),
 'open_folder': ('Open an approved folder', True, {'path':'string'}),
 'web_search': ('Open a web search in the default browser automatically; no extra approval', False, {'query':'string'}),
 'open_url': ('Open an HTTPS public URL in the default browser automatically; no extra approval', False, {'url':'string'}),
 'whatsapp_draft': ('Open a WhatsApp draft; user must manually send', True, {'phone':'string','message':'string'}),
 'screenshot': ('Capture the desktop to an approved PNG path', True, {'path':'string'}),
 'reminder': ('Create a persistent reminder with an ISO timestamp including timezone', True, {'title':'string','due':'string'}),
 'save_memory': ('Save user-approved long-term memory', True, {'text':'string'}),
 'maintenance_report': ('Inspect memory pressure and disk space; never kill programs', False, {}),
}

def explicit_youtube_request(text):
    """Recognize direct browser commands only, never infer playback or execution."""
    if re.search(r"\b(?:mat|nahi|nahin|don't|do not)\b", text, re.I):
        return None
    patterns = (
        r"(?:please\s+)?(?:youtube|you tube)\s+(?:ko\s+)?(?:open\s+(?:karo|kar do)|kholo|khol do)(?:\s+(.+?))?[.!?]?",
        r"(?:please\s+)?open\s+youtube(?:\s+(?:and\s+)?(?:search(?: for)?|play)\s+(.+?))?[.!?]?",
    )
    for pattern in patterns:
        match = re.fullmatch(pattern, text.strip(), re.I)
        if match:
            query = (match.group(1) or '').strip()
            query = re.sub(r"\s+(?:lagao|laga do|chalao|chala do|play karo)$", '', query, flags=re.I).strip()
            return {'url': 'https://www.youtube.com/' + ('results?' + urlencode({'search_query':query}) if query else '')}
    return None


class Tools:
    def __init__(self, store):
        self.store = store
        self.last_net = (time.monotonic(), psutil.net_io_counters())

    def schemas(self):
        return [dict(type='function', function=dict(name=n, description=d, parameters=dict(type='object', properties={k:dict(type=v) for k,v in args.items()}, required=list(args), additionalProperties=False))) for n,(d,_,args) in CATALOG.items()]

    def roots(self):
        defaults = [str(p) for p in (Path.home()/'Downloads', Path.home()/'Documents') if p.is_dir()]
        return self.store.get('roots', defaults)

    def path(self, value):
        p = Path(value).expanduser().resolve()
        roots = [Path(r).expanduser().resolve() for r in self.roots()]
        if not any(p == r or r in p.parents for r in roots):
            raise ValueError('Path is outside approved folders. Add a folder in Settings first.')
        return p

    def monitor(self):
        vm = psutil.virtual_memory()
        disk = psutil.disk_usage(Path.home().anchor)
        net = psutil.net_io_counters()
        now = time.monotonic()
        before, prev = self.last_net
        elapsed = max(now-before, .001)
        self.last_net = now, net
        try:
            battery = psutil.sensors_battery()
        except (OSError, AttributeError, NotImplementedError):
            battery = None
        return dict(cpu=psutil.cpu_percent(), ram_percent=vm.percent, ram_used=vm.used, ram_total=vm.total, ram_available=vm.available,
                    disk_percent=disk.percent, disk_free=disk.free, disk_total=disk.total,
                    upload=max(0,net.bytes_sent-prev.bytes_sent)/elapsed, download=max(0,net.bytes_recv-prev.bytes_recv)/elapsed,
                    battery=dict(percent=battery.percent, plugged=battery.power_plugged) if battery else None,
                    os=platform.platform(), python=platform.python_version(), pid=os.getpid(), app_rss=psutil.Process().memory_info().rss)

    def execute(self, name, args):
        if name not in CATALOG:
            raise ValueError('Unknown tool')
        expected = CATALOG[name][2]
        if set(args) != set(expected) or any(not isinstance(v, str) for v in args.values()):
            raise ValueError('Tool arguments do not match the schema')
        if name in ('system_info','maintenance_report'):
            return self.monitor()
        if name == 'processes':
            return [p.info for p in psutil.process_iter(['pid','name','memory_info'])][:200]
        if name == 'windows':
            if os.name != 'nt':
                raise ValueError('Visible desktop windows require Windows.')
            import ctypes
            from ctypes import wintypes
            user32 = ctypes.windll.user32
            callback_type = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
            user32.EnumWindows.argtypes = [callback_type, wintypes.LPARAM]
            user32.EnumWindows.restype = wintypes.BOOL
            user32.IsWindowVisible.argtypes = [wintypes.HWND]
            user32.IsWindowVisible.restype = wintypes.BOOL
            user32.GetWindowTextW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
            user32.GetWindowTextW.restype = ctypes.c_int
            titles = []
            def callback(hwnd, _):
                if user32.IsWindowVisible(hwnd):
                    buf = ctypes.create_unicode_buffer(512)
                    user32.GetWindowTextW(hwnd, buf, 512)
                    if buf.value: titles.append(buf.value)
                return True
            cb = callback_type(callback)
            if not user32.EnumWindows(cb, 0): raise OSError('Window enumeration failed')
            return titles
        if name in ('list_files','search_files'):
            p = self.path(args['path'])
            found = []
            iterator = p.iterdir() if name == 'list_files' else p.rglob('*')
            for i, f in enumerate(iterator):
                if i >= 10000: break
                if name == 'search_files' and args['query'].casefold() not in f.name.casefold(): continue
                try:
                    self.path(str(f))
                    found.append(dict(name=f.name, path=str(f), directory=f.is_dir(), bytes=f.stat().st_size))
                except (OSError, ValueError): continue
                if len(found) >= 200: break
            return found
        if name == 'read_document':
            p = self.path(args['path'])
            if p.stat().st_size > 1_000_000: raise ValueError('Text documents are limited to 1 MB.')
            return p.read_text(encoding='utf-8')
        if name == 'create_text':
            p = self.path(args['path'])
            with p.open('x', encoding='utf-8') as f: f.write(args['text'])
            return dict(created=str(p), bytes=p.stat().st_size)
        if name in ('copy_file','move_file'):
            source, dest = self.path(args['source']), self.path(args['destination'])
            if not source.is_file(): raise ValueError('Source must be a regular file.')
            with source.open('rb') as src, dest.open('xb') as out: shutil.copyfileobj(src, out)
            if name == 'move_file': source.unlink()
            return dict(destination=str(dest), bytes=dest.stat().st_size)
        if name == 'open_app':
            if os.name != 'nt': raise ValueError('Application launching requires Windows.')
            apps = dict(notepad='notepad.exe', calculator='calc.exe', paint='mspaint.exe')
            app = apps.get(args['app'].lower())
            if not app: raise ValueError('App is not allowlisted.')
            p = subprocess.Popen([str(Path(os.environ['SystemRoot']) / 'System32' / app)], shell=False)
            return dict(launched=True, pid=p.pid)
        if name == 'open_folder':
            p = self.path(args['path'])
            if not p.is_dir(): raise ValueError('Folder does not exist.')
            if os.name != 'nt': raise ValueError('Folder launching requires Windows.')
            os.startfile(p)
            return dict(requested=True, path=str(p))
        if name in ('web_search','open_url','whatsapp_draft'):
            if name == 'web_search': url = 'https://www.google.com/search?' + urlencode({'q':args['query']})
            elif name == 'whatsapp_draft':
                if not args['phone'].isdigit(): raise ValueError('Phone must use international digits only.')
                url = 'https://wa.me/' + args['phone'] + '?text=' + quote(args['message'])
            else:
                from urllib.parse import urlparse
                import ipaddress
                u = urlparse(args['url'])
                if u.scheme != 'https' or not u.hostname or u.username or u.password: raise ValueError('Use a public HTTPS URL.')
                if u.hostname in ('localhost',) or '.' not in u.hostname: raise ValueError('Local URLs are restricted.')
                try:
                    if not ipaddress.ip_address(u.hostname).is_global: raise ValueError('Private addresses are restricted.')
                except ValueError as exc:
                    if 'restricted' in str(exc): raise
                url = args['url']
            opened = webbrowser.open(url)
            return dict(browser_requested=bool(opened), url=url, sent=False)
        if name == 'screenshot':
            if os.name != 'nt': raise ValueError('Screenshots require the Windows desktop and Pillow optional dependency.')
            from PIL import ImageGrab
            p = self.path(args['path'])
            if p.suffix.lower() != '.png' or p.exists(): raise ValueError('Choose a new PNG filename.')
            ImageGrab.grab().save(p, 'PNG')
            return dict(saved=str(p))
        if name == 'reminder':
            from datetime import datetime, timezone
            if not args['title'].strip(): raise ValueError('Reminder title is required.')
            due = datetime.fromisoformat(args['due'])
            if due.tzinfo is None or due <= datetime.now(timezone.utc): raise ValueError('Use a future timestamp including timezone.')
            return dict(id=self.store.add('reminder', dict(title=args['title'], due=due.isoformat(), done=False)))
        if name == 'save_memory':
            return dict(id=self.store.add('memory', dict(text=args['text'])))
