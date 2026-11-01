"""Control only NEXUS's own YouTube WebView2 window; no browser/CDP download."""
import re
import threading
import time
from urllib.parse import urlencode, urlparse, parse_qs

STATE_JS = """(() => {const v=document.querySelector('video');return {
 url:location.href,title:(document.querySelector('h1 yt-formatted-string')?.textContent||document.title).trim(),
 has_video:!!v,paused:v?v.paused:true,ended:v?v.ended:false,time:v?v.currentTime:0,
 ready:v?v.readyState:0,src:v?v.currentSrc:'',ad:!!document.querySelector('.ad-showing')};})()"""
FIRST_JS = """(() => {const a=document.querySelector('ytd-video-renderer a#video-title[href*="/watch?"]');
 if(!a)return false; a.click();return true;})()"""
PLAY_JS = """(() => {const v=document.querySelector('video');if(!v)return false;
 if(v.ended)v.currentTime=0;v.play().catch(()=>{});return true;})()"""
PAUSE_JS = """(() => {const v=document.querySelector('video');if(!v)return false;v.pause();return true;})()"""
NEXT_JS = """(() => {const b=document.querySelector('.ytp-next-button');
 if(!b||b.getAttribute('aria-disabled')==='true')return false;b.click();return true;})()"""


def media_intent(text):
    text = re.sub(r'\bkro\b', 'karo', text.strip(), flags=re.I)
    if re.search(r"\b(?:mat|nahi|nahin|don't|do not)\b", text, re.I):
        return None
    controls = {
        'next': r'(?:next|agla)\s+(?:song|gana|gaana|video)(?:\s+(?:play karo|chalao|lagao))?',
        'pause': r'(?:(?:song|gana|gaana)\s+)?pause(?:\s+karo)?',
        'resume': r'(?:(?:song|gana|gaana)\s+)?resume(?:\s+karo)?',
        'play': r'(?:(?:jo\s+(?:gana|gaana|song)\s+search\s+kiya(?:\s+(?:hai|hin))?\s+(?:use|usy|usay))|(?:pehla\s+(?:song|gana|gaana))|(?:song|gana|gaana))?\s*play(?:\s+karo)?',
    }
    for action, pattern in controls.items():
        if re.fullmatch(pattern, text, re.I):
            return {'action':action, 'query':''}
    match = re.fullmatch(r'(?:youtube\s+(?:open karo|kholo|par)\s+)?(.+?)\s+(?:lagao|chalao|play karo)', text, re.I)
    if not match:
        match = re.fullmatch(r'(?:open youtube and )?play\s+(.+)', text, re.I)
    if match:
        query = match.group(1).strip()
        if query and len(query) <= 300:
            return {'action':'play','query':query}
    return None


class YouTubePlayer:
    def __init__(self, clock=time.monotonic, sleep=time.sleep):
        self.clock, self.sleep = clock, sleep
        self.host = self.window = None
        self.lock = threading.Lock()
        self.stopped = threading.Event()

    def attach(self, host):
        if host is None:
            self.host = None
            self.close()
            return
        self.host = host
        if host:
            self.stopped.clear()

    def close(self):
        self.stopped.set()
        window, self.window = self.window, None
        if window:
            try:
                window.destroy()
            except Exception:
                pass

    def _wait(self, predicate, timeout=20):
        deadline = self.clock()+timeout
        while self.clock() < deadline:
            if self.stopped.is_set():
                raise ValueError('YouTube window closed or NEXUS is shutting down.')
            result = predicate()
            if result:
                return result
            self.sleep(.15)
        raise ValueError('YouTube player did not become ready. Check the NEXUS YouTube window for consent, sign-in, network or playback restrictions.')

    def _check_url(self):
        url = self.window.get_current_url() if self.window else ''
        parsed = urlparse(url or '')
        if parsed.scheme != 'https' or parsed.hostname not in ('www.youtube.com','youtube.com','m.youtube.com'):
            raise ValueError('Media controls work only inside the NEXUS YouTube window on youtube.com.')
        return url

    def _state(self):
        self._check_url()
        return self.window.evaluate_js(STATE_JS) or {}

    def _search(self, query):
        if not self.host:
            raise ValueError('YouTube playback requires the native NEXUS Windows app. Launch START_UPDATED_NEXUS.bat; headless mode cannot control media.')
        url = 'https://www.youtube.com/results?'+urlencode({'search_query':query})
        if self.window is None:
            window = self.host.create_window('NEXUS YouTube', url, width=1050, height=720, min_size=(640,480), js_api=None)
            self.window = window
            if self.stopped.is_set():
                self.close()
                raise ValueError('NEXUS is shutting down.')
            if window is None:
                raise ValueError('Could not create the NEXUS YouTube window.')
            def closed():
                if self.window is window:
                    self.window = None
            window.events.closed += closed
        else:
            self.window.load_url(url)
        # Native page creation is asynchronous; wait before reading its DOM.
        self._wait(lambda: self.window and parse_qs(urlparse(self.window.get_current_url() or '').query).get('search_query') == [query])
        def results_ready():
            self._check_url()
            return self.window.evaluate_js("!!document.querySelector('ytd-video-renderer a#video-title[href*=\"/watch?\"]')")
        self._wait(results_ready)

    def command(self, action, query=''):
        if action not in ('search','play','pause','resume','next') or not isinstance(query,str) or len(query)>300:
            raise ValueError('Choose search/play/pause/resume/next and a query of at most 300 characters.')
        if action=='search' and not query.strip():
            raise ValueError('Enter a song or artist to search.')
        if not self.lock.acquire(timeout=1):
            raise ValueError('A YouTube operation is already running. Try again after it finishes.')
        try:
            if self.host and self.window is None:
                self.stopped.clear()
            if query.strip() and action in ('search','play'):
                self._search(query.strip())
            if self.window is None:
                raise ValueError('No NEXUS YouTube session yet. Say: sad song play karo. An ordinary browser tab cannot be controlled.')
            before = self._state()
            if action=='search':
                return {**before,'status':'search_ready'}
            if before.get('ad'):
                return {**before,'status':'blocked','message':'YouTube is showing an ad. Song playback has not been verified.'}
            if action=='pause':
                self.window.evaluate_js(PAUSE_JS)
                state = self._state()
                if not state.get('has_video') or not state.get('paused'):
                    raise ValueError('Could not verify paused playback.')
                return {**state,'status':'paused'}
            if action=='next':
                if not self.window.evaluate_js(NEXT_JS):
                    raise ValueError('YouTube has no available Next video control in this session.')
            elif '/results?' in before.get('url',''):
                if not self.window.evaluate_js(FIRST_JS):
                    raise ValueError('No playable YouTube video result found.')
            # Observe a real media element; .play() alone does not prove playback.
            if action=='next':
                def new_video():
                    state=self._state()
                    if state.get('has_video') and state.get('url')!=before.get('url') and (state.get('src')!=before.get('src') or state.get('time',0)<before.get('time',0)):
                        return state
                    return None
                self._wait(new_video)
            self._wait(lambda:self._state().get('has_video'))
            self.window.evaluate_js(PLAY_JS)
            observed = self._state()
            def playing():
                state = self._state()
                if state.get('ad'):
                    return {**state,'status':'blocked','message':'YouTube is showing an ad; requested song playback is not yet verified.'}
                changed = action!='next' or (state.get('url'),state.get('src')) != (before.get('url'),before.get('src'))
                if changed and not state.get('paused',True) and not state.get('ended') and state.get('ready',0)>=2 and state.get('time',0)>observed.get('time',0)+.03:
                    return {**state,'status':'playing'}
                return None
            return self._wait(playing,15)
        except ValueError:
            raise
        except Exception as exc:
            raise ValueError('YouTube control failed. Check the NEXUS YouTube window: '+type(exc).__name__) from exc
        finally:
            self.lock.release()


player = YouTubePlayer()
