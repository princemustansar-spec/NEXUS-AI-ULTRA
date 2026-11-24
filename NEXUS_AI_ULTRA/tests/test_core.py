import asyncio
import importlib
import json
from datetime import datetime, timedelta, timezone
import httpx
import pytest
from fastapi.testclient import TestClient
from nexus.store import Store
from nexus.tools import Tools
from nexus.providers import Providers

@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv('NEXUS_DATA_DIR',str(tmp_path/'data'))
    import nexus.app
    m=importlib.reload(nexus.app)
    with TestClient(m.app) as c:
        c.headers['x-nexus-token']=c.get('/api/state').json()['token']
        yield c,m

def test_store_persistence(tmp_path):
    s=Store(tmp_path/'db.sqlite3');ident=s.add('memory',{'text':'hello'})
    s.set('name','Custom');s.db.close()
    again=Store(tmp_path/'db.sqlite3')
    assert again.list('memory')[0]['text']=='hello'
    assert again.get('name')=='Custom'
    again.delete('memory',ident);assert not again.list('memory')

def test_monitor_real(tmp_path):
    t=Tools(Store(tmp_path/'db'))
    m=t.monitor()
    assert 0<=m['cpu']<=100 and m['ram_total']>0 and m['app_rss']>0

def test_paths_no_overwrite(tmp_path):
    s=Store(tmp_path/'db');s.set('roots',[str(tmp_path/'allowed')]);(tmp_path/'allowed').mkdir()
    t=Tools(s);p=tmp_path/'allowed'/'a.txt'
    t.execute('create_text',{'path':str(p),'text':'real'})
    assert t.execute('read_document',{'path':str(p)})=='real'
    with pytest.raises(FileExistsError): t.execute('create_text',{'path':str(p),'text':'bad'})
    with pytest.raises(ValueError): t.path(str(tmp_path/'secret'))
    (tmp_path/'allowed'/'escape').symlink_to(tmp_path)
    with pytest.raises(ValueError): t.path(str(tmp_path/'allowed'/'escape'/'secret'))

def test_copy_move(tmp_path):
    s=Store(tmp_path/'db');s.set('roots',[str(tmp_path)]);t=Tools(s)
    p=tmp_path/'a';p.write_text('data')
    t.execute('copy_file',{'source':str(p),'destination':str(tmp_path/'b')})
    assert p.exists() and (tmp_path/'b').read_text()=='data'
    t.execute('move_file',{'source':str(tmp_path/'b'),'destination':str(tmp_path/'c')})
    assert not (tmp_path/'b').exists() and (tmp_path/'c').read_text()=='data'

def test_security(client):
    c,m=client
    assert c.post('/api/safety',json={},headers={'x-nexus-token':'wrong'}).status_code==403
    assert c.get('/api/state',headers={'host':'evil.com'}).status_code==403
    assert c.get('/api/state',headers={'origin':'https://evil.com'}).status_code==403
    assert 'frame-ancestors' in c.get('/').headers['content-security-policy']

def test_approvals_one_use_and_stop(client,tmp_path):
    c,m=client
    assert c.post('/api/settings',json={'roots':[str(tmp_path)]}).status_code==200
    p=tmp_path/'output.txt'
    r=c.post('/api/tools/create_text',json={'path':str(p),'text':'approved'}).json()
    assert r['approval_required'] and not p.exists()
    assert c.post('/api/approvals/'+r['id'],json={'approve':True}).status_code==200
    assert p.read_text()=='approved'
    assert c.post('/api/approvals/'+r['id'],json={'approve':True}).status_code==400
    r=c.post('/api/tools/create_text',json={'path':str(tmp_path/'other'),'text':'x'}).json()
    c.post('/api/safety',json={'stop':True})
    assert c.post('/api/approvals/'+r['id'],json={'approve':True}).status_code==400
    assert c.post('/api/tools/system_info',json={}).status_code==400
    assert not (tmp_path/'other').exists()

def test_denial_expiry_permissions(client):
    c,m=client
    r=c.post('/api/tools/open_app',json={'app':'notepad'}).json()
    assert c.post('/api/approvals/'+r['id'],json={'approve':False}).json()['denied']
    r=c.post('/api/tools/open_app',json={'app':'notepad'}).json();m.pending[r['id']]['expires']=0
    assert c.post('/api/approvals/'+r['id'],json={'approve':True}).status_code==400
    c.post('/api/safety',json={'denied_tools':['system_info']})
    assert c.post('/api/tools/system_info',json={}).status_code==400

def test_reminder_delivery_and_restart(client):
    c,m=client
    due=(datetime.now(timezone.utc)+timedelta(hours=1)).isoformat()
    assert c.post('/api/records/reminder',json={'title':'Meeting','due':due}).status_code==200
    assert c.post('/api/records/reminder',json={'title':'Bad','due':'2020-01-01'}).status_code==400
    r=m.store.list('reminder')[0]
    m.store.update('reminder',r['id'],dict(title='Meeting',due='2020-01-01T00:00:00+00:00',done=False))
    asyncio.run(m.scheduler_tick());asyncio.run(m.scheduler_tick())
    assert len(m.store.list('notification'))==1
    assert m.store.list('reminder')[0]['done']
    reopened=Store(m.DATA/'nexus.sqlite3');assert reopened.list('reminder')[0]['done']

def test_memory_and_settings(client):
    c,m=client
    assert c.post('/api/settings',json={'name':'MY NEXUS'}).status_code==200
    ident=c.post('/api/records/memory',json={'text':'Prefer Roman Urdu'}).json()['id']
    s=c.get('/api/state').json()
    assert s['name']=='MY NEXUS' and s['memory'][0]['text']=='Prefer Roman Urdu'
    c.delete('/api/records/memory/'+str(ident))
    assert not c.get('/api/state').json()['memory']

def test_provider_missing_and_https(client,configured_hermes):
    c,m=client
    r=c.post('/api/chat',json={'text':'Hello'})
    assert r.status_code==400 and 'No enabled provider' in r.json()['detail']
    p=dict(id='test',name='Test',base='http://remote.example/v1',model='x',kind='openai',paid=True,enabled=True)
    assert c.post('/api/settings',json={'providers':[p]}).status_code==400

def test_provider_tool_loop(client,monkeypatch,configured_hermes):
    c,m=client
    calls=[]
    async def request(messages,tools=None,allow_paid=False,**kwargs):
        calls.append(messages.copy())
        if len(calls)==1:
            return {'role':'assistant','content':None,'tool_calls':[{'id':'call1','type':'function','function':{'name':'system_info','arguments':'{}'}}]},'Test transport','test-model'
        assert json.loads(messages[-1]['content'])['result']['ram_total']>0
        return {'role':'assistant','content':'Measured your RAM using the tool.'},'Test transport','test-model'
    monkeypatch.setattr(m.providers,'request',request)
    r=c.post('/api/chat',json={'text':'Check RAM'})
    assert r.status_code==200 and r.json()['model']=='test-model'
    assert len(calls)==2 and len(m.store.list('chat'))==2

def test_provider_http_transport(tmp_path,monkeypatch):
    s=Store(tmp_path/'db');p=Providers(s)
    s.set('providers',[dict(id='test',name='Test',base='http://127.0.0.1:1000/v1',model='actual-model',enabled=True,paid=False,kind='openai')])
    real=httpx.AsyncClient
    def handler(req):
        if req.url.path.endswith('/models'): return httpx.Response(200,json={'data':[{'id':'actual-model'}]})
        body=json.loads(req.content);assert body['model']=='actual-model'
        return httpx.Response(200,json={'model':'actual-model','choices':[{'message':{'role':'assistant','content':'test response'}}]})
    monkeypatch.setattr(httpx,'AsyncClient',lambda **kw:real(transport=httpx.MockTransport(handler),**kw))
    assert asyncio.run(p.probe('test'))['models']==['actual-model']
    assert asyncio.run(p.request([{'role':'user','content':'hi'}]))[0]['content']=='test response'

def test_paid_guard_and_rate_limit(tmp_path,monkeypatch):
    s=Store(tmp_path/'db');p=Providers(s)
    config=dict(id='test',name='Test',base='https://example.com/v1',model='m',enabled=True,paid=True,kind='openai')
    s.set('providers',[config]);requests=[];real=httpx.AsyncClient
    def handler(req): requests.append(req);return httpx.Response(429)
    monkeypatch.setattr(httpx,'AsyncClient',lambda **kw:real(transport=httpx.MockTransport(handler),**kw))
    with pytest.raises(ValueError,match='approval'):asyncio.run(p.request([],allow_paid=False))
    assert not requests
    with pytest.raises(ValueError,match='429'):asyncio.run(p.request([],allow_paid=True))
    with pytest.raises(ValueError,match='cooldown'):asyncio.run(p.request([],allow_paid=True))
    assert len(requests)==1

def test_provider_fallback(tmp_path,monkeypatch):
    s=Store(tmp_path/'db');p=Providers(s)
    s.set('providers',[dict(id=n,name=n,base='https://'+n+'.example/v1',model='m',enabled=True,paid=False,kind='openai') for n in ('first','second')])
    real=httpx.AsyncClient
    def handler(req):
        if req.url.host=='first.example':return httpx.Response(401)
        return httpx.Response(200,json={'model':'m','choices':[{'message':{'role':'assistant','content':'ok'}}]})
    monkeypatch.setattr(httpx,'AsyncClient',lambda **kw:real(transport=httpx.MockTransport(handler),**kw))
    assert asyncio.run(p.request([]))[1]=='second'

def test_image_payment_guard(client):
    c,m=client
    assert c.post('/api/image',json={'provider':'missing','prompt':'test'}).status_code==400

def test_tool_input_validation(client):
    c,m=client
    assert c.post('/api/tools/system_info',json={'unexpected':'argument'}).status_code==400
    assert c.post('/api/tools/unknown',json={}).status_code==400

def test_cancel_inflight(client,monkeypatch,configured_hermes):
    c,m=client
    async def scenario():
        started=asyncio.Event()
        async def slow(*args,**kwargs):
            started.set()
            await asyncio.sleep(60)
        monkeypatch.setattr(m.providers,'request',slow)
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=m.app),base_url='http://127.0.0.1:8765',headers={'x-nexus-token':m.session_token}) as h:
            task=asyncio.create_task(h.post('/api/chat',json={'text':'slow'}))
            await asyncio.wait_for(started.wait(),15)
            response=await h.post('/api/cancel',json={})
            assert response.status_code==200
            cancelled=await asyncio.wait_for(task,2)
            assert cancelled.status_code==409
            assert not m.active
    asyncio.run(scenario())

def test_secure_key_not_in_config(tmp_path,monkeypatch):
    s=Store(tmp_path/'db');p=Providers(s);saved={}
    monkeypatch.setattr('nexus.providers.keyring.set_password',lambda service,key,value:saved.update({key:value}))
    config=dict(id='example',name='Example',base='https://example.com/v1',model='m',enabled=False,paid=True,kind='openai',key='test-secret-not-real')
    p.save([config])
    assert saved['example']=='test-secret-not-real'
    assert 'test-secret-not-real' not in json.dumps(s.get('providers'))

def test_image_transport(tmp_path,monkeypatch):
    s=Store(tmp_path/'db');p=Providers(s)
    s.set('providers',[dict(id='image',name='Image',base='https://example.com/v1',model='image-model',enabled=True,paid=True,kind='openai')])
    real=httpx.AsyncClient
    def handler(req):
        assert req.url.path=='/v1/images/generations'
        assert json.loads(req.content)['model']=='image-model'
        return httpx.Response(200,json={'data':[{'b64_json':'fixture'}]})
    monkeypatch.setattr(httpx,'AsyncClient',lambda **kw:real(transport=httpx.MockTransport(handler),**kw))
    with pytest.raises(ValueError,match='approval'):asyncio.run(p.image('image','test'))
    assert asyncio.run(p.image('image','test',True))[0]['b64_json']=='fixture'

def test_sensitive_ai_call_queues_without_execution(client,monkeypatch,tmp_path,configured_hermes):
    c,m=client;m.store.set('roots',[str(tmp_path)]);count=0
    async def request(*args,**kwargs):
        nonlocal count
        count+=1
        if count==1:return {'role':'assistant','content':None,'tool_calls':[{'id':'a','type':'function','function':{'name':'create_text','arguments':json.dumps({'path':str(tmp_path/'never-created'),'text':'a'})}}]},'Test','test-model'
        return {'role':'assistant','content':'Review the pending approval.'},'Test','test-model'
    monkeypatch.setattr(m.providers,'request',request)
    assert c.post('/api/chat',json={'text':'create file'}).status_code==200
    assert len(m.pending)==1 and not (tmp_path/'never-created').exists()

def test_missing_approved_folder_is_clear_error(client,tmp_path):
    c,m=client
    r=c.post('/api/settings',json={'roots':[str(tmp_path/'does-not-exist')]})
    assert r.status_code==400 and 'Filesystem operation failed' in r.json()['detail']
