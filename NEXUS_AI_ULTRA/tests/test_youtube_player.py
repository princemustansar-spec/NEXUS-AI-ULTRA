from types import SimpleNamespace
from unittest.mock import Mock
import importlib
import json
import pytest
from fastapi.testclient import TestClient
from nexus.youtube import YouTubePlayer, media_intent, STATE_JS, FIRST_JS, PLAY_JS, PAUSE_JS, NEXT_JS

class Event:
    def __init__(self):self.handlers=[]
    def __iadd__(self,fn):self.handlers.append(fn);return self

class Window:
    def __init__(self,url):
        self.url=url;self.paused=True;self.time=0;self.src='';self.progress=True;self.ad=False;self.allow_play=True;self.allow_next=True
        self.events=SimpleNamespace(closed=Event());self.destroyed=False
    def get_current_url(self):return self.url
    def load_url(self,url):self.url=url;self.src='';self.time=0;self.paused=True
    def destroy(self):
        self.destroyed=True
        for handler in self.events.closed.handlers:handler()
    def evaluate_js(self,script):
        if script==STATE_JS:
            if not self.paused and self.progress:self.time+=.1
            return dict(url=self.url,title='Fixture',has_video=bool(self.src),paused=self.paused,ended=False,time=self.time,ready=4,src=self.src,ad=self.ad)
        if script.startswith('!!document'):return True
        if script==FIRST_JS:self.url='https://www.youtube.com/watch?v=first';self.src='first';return True
        if script==PLAY_JS:self.paused=not self.allow_play;return True
        if script==PAUSE_JS:self.paused=True;return True
        if script==NEXT_JS:
            if not self.allow_next:return False
            self.url='https://www.youtube.com/watch?v=next';self.src='next';self.time=0;return True
        raise AssertionError(script)

@pytest.fixture
def controller():
    tick=[0]
    def clock():tick[0]+=.1;return tick[0]
    p=YouTubePlayer(clock=clock,sleep=lambda delay:None)
    created=[]
    def create(title,url,**kwargs):
        assert kwargs['js_api'] is None
        w=Window(url);created.append(w);return w
    p.attach(SimpleNamespace(create_window=create))
    yield p,created
    p.close()

@pytest.mark.parametrize('text,args',[
    ('youtube open karo sad song lagao',{'action':'play','query':'sad song'}),
    ('sad song play kro',{'action':'play','query':'sad song'}),
    ('jo gana search kiya hin usy play kro',{'action':'play','query':''}),
    ('next song play kro',{'action':'next','query':''}),
    ('pause karo',{'action':'pause','query':''}),
    ('resume karo',{'action':'resume','query':''}),
])
def test_voice_and_typed_media_commands(text,args):assert media_intent(text)==args

@pytest.mark.parametrize('text',['hello','open youtube','song play mat karo','next song nahi play karo'])
def test_non_commands_do_not_start_media(text):assert media_intent(text) is None


def test_reuses_owned_window_for_play_pause_resume_next(controller):
    p,created=controller
    assert p.command('play','sad song')['status']=='playing'
    assert p.command('pause')['status']=='paused'
    assert p.command('resume')['status']=='playing'
    result=p.command('next');assert result['status']=='playing' and 'v=next' in result['url']
    assert p.command('play','another song')['status']=='playing'
    assert len(created)==1
    p.close();assert created[0].destroyed and p.window is None


def test_follow_up_play_uses_owned_search_results(controller):
    p,created=controller
    assert p.command('search','fixture')['status']=='search_ready'
    assert p.command('play')['status']=='playing'


def test_never_reports_playing_without_time_progress(controller):
    p,created=controller;p.command('search','fixture');created[0].progress=False
    with pytest.raises(ValueError,match='did not become ready'):p.command('play')


def test_autoplay_restriction_and_missing_next_are_truthful(controller):
    p,created=controller;p.command('search','fixture');created[0].allow_play=False
    with pytest.raises(ValueError,match='did not become ready'):p.command('play')
    created[0].allow_play=True;p.command('play');created[0].allow_next=False
    with pytest.raises(ValueError,match='Next video'):p.command('next')


def test_ads_and_external_pages_do_not_get_success_claims(controller):
    p,created=controller;p.command('play','fixture');created[0].ad=True
    assert p.command('next')['status']=='blocked'
    created[0].url='https://example.com/'
    with pytest.raises(ValueError,match='only inside'):p.command('pause')


def test_no_native_session_or_host_does_not_open_a_personal_browser():
    p=YouTubePlayer()
    with pytest.raises(ValueError,match='No NEXUS YouTube'):p.command('next')
    with pytest.raises(ValueError,match='native NEXUS Windows'):p.command('play','fixture')


def test_chat_uses_previous_search_and_media_controls_without_paid_call(tmp_path,monkeypatch):
    monkeypatch.setenv('NEXUS_DATA_DIR',str(tmp_path))
    import nexus.app
    m=importlib.reload(nexus.app)
    m.store.add('chat',dict(role='user',text='youtube open karo sad song'))
    player=Mock(return_value={'status':'playing','title':'Fixture song','url':'https://www.youtube.com/watch?v=fixture'})
    monkeypatch.setattr('nexus.youtube.player.command',player)
    async def no_model(*a,**k):pytest.fail('No model or paid inference needed for media commands')
    monkeypatch.setattr(m.providers,'request',no_model)
    with TestClient(m.app) as client:
        client.headers['x-nexus-token']=m.session_token
        r=client.post('/api/chat',json={'text':'jo gana search kiya hin usy play kro','input_source':'voice'})
        assert r.status_code==200 and 'verify' in r.json()['text']
        player.assert_called_with('play','sad song')
        assert not m.pending
        r=client.post('/api/chat',json={'text':'next song play kro'})
        assert r.status_code==200;player.assert_called_with('next','')
        m.store.set('denied_tools',['youtube_player'])
        before=player.call_count
        assert client.post('/api/chat',json={'text':'pause karo'}).status_code==400
        assert player.call_count==before
    m.store.db.close()


def test_next_does_not_report_old_video_as_next_playing(controller):
    p,created=controller;p.command('play','fixture');w=created[0];original=w.evaluate_js
    def stale_next(script):
        if script==NEXT_JS:return True
        return original(script)
    w.evaluate_js=stale_next
    with pytest.raises(ValueError,match='did not become ready'):p.command('next')


def test_emergency_stop_closes_media_and_cannot_reopen_until_resumed(tmp_path,monkeypatch):
    monkeypatch.setenv('NEXUS_DATA_DIR',str(tmp_path))
    import nexus.app
    m=importlib.reload(nexus.app)
    closed=Mock();command=Mock()
    monkeypatch.setattr(m.youtube_player,'close',closed)
    monkeypatch.setattr(m.youtube_player,'command',command)
    with TestClient(m.app) as client:
        client.headers['x-nexus-token']=m.session_token
        assert client.post('/api/safety',json={'stop':True}).status_code==200
        closed.assert_called_once()
        assert client.post('/api/chat',json={'text':'sad song play karo'}).status_code==400
        command.assert_not_called()
    m.store.db.close()
