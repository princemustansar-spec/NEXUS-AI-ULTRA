import asyncio
from datetime import datetime,timedelta,timezone
from email.utils import format_datetime
import importlib
import json
from pathlib import Path
from unittest.mock import Mock
import os
import httpx
import pytest
from fastapi.testclient import TestClient
from nexus.personal import Personal,News,validate_profile,validate_routine,personal_intent
from nexus.store import Store
from nexus.providers import Providers

def test_profile_validation_and_saved_style(tmp_path):
    store=Store(tmp_path/'test.db');p=Personal(store)
    assert p.profile()['welcome_enabled'] and not p.profile()['news_on_start']
    p.save({'preferred_name':'Friend','tone':'calm','emotions':False})
    p.react('thanks!');assert p.mood()=='neutral' and 'calm' in p.context()
    with pytest.raises(ValueError):p.save({'speak_welcome':'yes'})
    with pytest.raises(ValueError):validate_profile({'unknown':True})
    assert Personal(store).profile()['preferred_name']=='Friend';store.db.close()

@pytest.mark.parametrize('data',[{'title':'x','time':'24:00'},{'title':'','time':'08:00'},{'title':'x','time':'08:00','days':[]},{'title':'x','time':'08:00','days':[True]}])
def test_routine_rejects_invalid_times_and_days(data):
    with pytest.raises(ValueError):validate_routine(data)

def test_routine_daily_notifications_are_persistent_and_once_per_day(tmp_path):
    store=Store(tmp_path/'test.db');p=Personal(store);p.add_routine({'title':'Walk','time':'08:00','days':[0,1,2,3,4,5,6]})
    now=datetime(2026,11,4,9,tzinfo=timezone.utc);p.tick(now);p.tick(now)
    assert len(store.list('notification'))==1
    Personal(store).tick(now);assert len(store.list('notification'))==1
    p.tick(now+timedelta(days=1));assert len(store.list('notification'))==2
    p.news.get=Mock(side_effect=AssertionError('No network on ordinary briefing'))
    assert 'Walk' in p.briefing(False,now)['text'];p.news.get.assert_not_called();store.db.close()

def test_news_parser_requires_recent_date_and_public_source_links():
    now=datetime.now(timezone.utc)
    def row(title,url,date):return '<item><title>'+title+'</title><link>'+url+'</link><pubDate>'+date+'</pubDate></item>'
    fresh=format_datetime(now);old=format_datetime(now-timedelta(days=4))
    feed='<rss><channel>'+row('&lt;script&gt;Bad&lt;/script&gt; title','https://www.dawn.com/news/1',fresh)+row('Old','https://www.dawn.com/news/2',old)+row('Wrong domain','https://evil.test/a',fresh)+row('Undated','https://www.dawn.com/news/3','')+'</channel></rss>'
    items=News.parse(feed.encode(),'pakistan',now)
    assert len(items)==1 and '<' not in items[0]['title'] and items[0]['source']=='Dawn · Pakistan'
    with pytest.raises(ValueError):News.parse(b'<!DOCTYPE rss><rss/>','pakistan',now)

def test_news_failure_does_not_relabel_cached_old_news_as_current(monkeypatch):
    news=News();news.cache['pakistan']=(-10000,[{'title':'old'}])
    monkeypatch.setattr(httpx.Client,'stream',Mock(side_effect=httpx.ConnectError('fixture unavailable')))
    data=news.get('pakistan');assert data['items']==[] and data['warnings']

@pytest.mark.parametrize('text',['pc lock mat karo','do not lock my pc','news nahi chahiye'])
def test_direct_intents_do_not_match_negated_commands(text):assert personal_intent(text) is None

def app_fixture(tmp_path,monkeypatch):
    monkeypatch.setenv('NEXUS_DATA_DIR',str(tmp_path))
    import nexus.app
    module=importlib.reload(nexus.app)
    module.store.set('voice_muted',True)
    return module

def test_settings_routine_briefing_and_lock_confirmation_routes(tmp_path,monkeypatch):
    app=app_fixture(tmp_path,monkeypatch)
    execute=app.tools.execute;locked=Mock(return_value={'lock_requested':True})
    monkeypatch.setattr(app.tools,'execute',lambda name,args:locked() if name=='pc_lock' else execute(name,args))
    with TestClient(app.app) as c:
        assert c.post('/api/personal/settings',json={'preferred_name':'Friend'}).status_code==403
        c.headers['x-nexus-token']=app.session_token
        assert c.post('/api/personal/settings',json={'preferred_name':'Friend'}).status_code==200
        assert c.post('/api/personal/routines',json={'title':'Study','time':'23:59'}).status_code==200
        brief=c.post('/api/personal/briefing',json={'news':False,'speak':True}).json()
        assert 'Friend' in brief['text'] and not brief['spoken']
        response=c.post('/api/chat',json={'text':'pc lock karo'}).json()
        assert 'confirmation' in response['text'];locked.assert_not_called()
        ident=next(iter(app.pending));c.post('/api/approvals/'+ident,json={'approve':True});locked.assert_called_once()
        assert c.post('/api/approvals/'+ident,json={'approve':True}).status_code==400
    app.store.db.close()

def test_startup_is_once_per_backend_and_respects_mute(tmp_path,monkeypatch):
    app=app_fixture(tmp_path,monkeypatch);speak=Mock(side_effect=AssertionError('Muted welcome must not speak'))
    monkeypatch.setattr(app.tts,'start',speak)
    with TestClient(app.app) as c:
        c.headers['x-nexus-token']=app.session_token
        first=c.post('/api/personal/startup',json={}).json();again=c.post('/api/personal/startup',json={}).json()
        assert first==again and not first['spoken'];assert len(app.store.list('notification'))==1
        speak.assert_not_called()
    app.store.db.close()

def test_spoken_startup_completes_once_and_does_not_start_microphone(tmp_path,monkeypatch):
    app=app_fixture(tmp_path,monkeypatch);app.store.set('voice_muted',False);started=[]
    def start(*args,**kwargs):started.append(kwargs);return {'job_id':'welcome'}
    monkeypatch.setattr(app.tts,'start',start)
    monkeypatch.setattr(app.tts,'status',lambda:{'job_id':'welcome','phase':'done' if started else 'idle'})
    monkeypatch.setattr(app.voice,'status',lambda:{'phase':'idle'})
    with TestClient(app.app) as c:
        c.headers['x-nexus-token']=app.session_token
        assert c.post('/api/personal/startup',json={}).json()['spoken']
        assert c.post('/api/personal/startup',json={}).json()['spoken']
        assert len(started)==1 and not app.handsfree.running and not started[0]['allow_online']
    app.store.db.close()

def test_switching_back_from_local_restores_primary_account(tmp_path,monkeypatch):
    app=app_fixture(tmp_path,monkeypatch)
    async def catalog():return {'available':True,'models':[{'name':'llama3.2:latest'}]}
    monkeypatch.setattr('nexus.ollama_local.inspect',catalog)
    app.store.set('preferred_provider','chatgpt-account')
    with TestClient(app.app) as c:
        c.headers['x-nexus-token']=app.session_token
        assert c.post('/api/personal/ollama',json={'action':'configure','model':'llama3.2:latest','mode':'local'}).status_code==200
        assert app.store.get('preferred_provider')=='ollama'
        assert c.post('/api/personal/ollama',json={'action':'configure','model':'llama3.2:latest','mode':'fallback'}).status_code==200
        assert app.store.get('preferred_provider')=='chatgpt-account' and app.store.get('ollama_fallback')
    app.store.db.close()

def test_ollama_uses_native_local_api_without_unsupported_tools_or_remote_fallback(tmp_path,monkeypatch):
    store=Store(tmp_path/'local.db');providers=Providers(store)
    store.set('providers',[dict(id='ollama',name='Ollama',base='http://127.0.0.1:11434/v1',model='llama3.2:latest',kind='openai',paid=False,enabled=True)])
    store.set('preferred_provider','ollama');calls=[];real=httpx.AsyncClient
    def handler(req):
        assert req.url.host=='127.0.0.1';calls.append(req.url.path)
        if req.url.path=='/api/show':return httpx.Response(200,json={'capabilities':['completion']})
        body=json.loads(req.content);assert 'tools' not in body and body['options']['num_ctx']==4096 and body['keep_alive']=='2m'
        return httpx.Response(200,json={'model':'llama3.2:latest','message':{'role':'assistant','content':'hello'}})
    monkeypatch.setattr(httpx,'AsyncClient',lambda **kwargs:real(transport=httpx.MockTransport(handler),**kwargs))
    result=asyncio.run(providers.request([{'role':'user','content':'hello'}],[{'type':'function'}]))
    assert result[0]['content']=='hello' and calls==['/api/show','/api/chat'];store.db.close()

def test_ollama_local_failure_never_falls_back_to_cloud(tmp_path,monkeypatch):
    store=Store(tmp_path/'local.db');providers=Providers(store)
    store.set('providers',[dict(id='ollama',name='Ollama',base='http://127.0.0.1:11434/v1',model='llama3.2:latest',kind='openai',paid=False,enabled=True)])
    store.set('preferred_provider','ollama');remote=Mock(side_effect=AssertionError('Must stay local'));monkeypatch.setattr(providers,'_request_remote',remote)
    async def fail(*args,**kwargs):raise httpx.ConnectError('fixture down')
    monkeypatch.setattr('nexus.ollama_local.request',fail)
    with pytest.raises(ValueError,match='Local Ollama'):asyncio.run(providers.request([]))
    remote.assert_not_called();store.db.close()

def test_startup_shortcut_uses_environment_values_and_current_user_folder(tmp_path,monkeypatch):
    from nexus import startup
    monkeypatch.setattr(startup.sys,'platform','win32');monkeypatch.setenv('APPDATA',str(tmp_path/'roaming'))
    root=tmp_path/'NEXUS project';(root/'.venv/Scripts').mkdir(parents=True);(root/'.venv/Scripts/pythonw.exe').touch();(root/'run.py').touch()
    run=Mock();monkeypatch.setattr(startup.subprocess,'run',run)
    startup.set_startup(root,True)
    args=run.call_args;assert str(root) not in args.args[0][-1] and args.kwargs['env']['NEXUS_LOGIN_TARGET'].endswith('pythonw.exe')
    startup.set_startup(root,False)

def test_avatar_emotions_can_be_disabled_and_expire(tmp_path):
    store=Store(tmp_path/'emotion.db');p=Personal(store);p.react('I am sad');assert p.mood()=='caring'
    p.emotion_until=0;assert p.mood()=='neutral'
    p.react('thanks');assert p.mood()=='happy'
    p.save({'emotions':False});assert p.mood()=='neutral';store.db.close()

@pytest.mark.skipif(os.name!='nt',reason='Actual Windows COM shortcut check')
def test_real_windows_startup_shortcut_in_disposable_profile(tmp_path,monkeypatch):
    from nexus import startup
    monkeypatch.setenv('APPDATA',str(tmp_path/'disposable-profile'))
    root=tmp_path/'NEXUS source';(root/'.venv/Scripts').mkdir(parents=True)
    (root/'.venv/Scripts/pythonw.exe').touch();(root/'run.py').touch()
    assert startup.set_startup(root,True)['enabled'] is True
    assert startup.startup_path().is_file()
    assert startup.set_startup(root,False)['enabled'] is False
