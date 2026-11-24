"""Real pinned Hermes + real router HTTP tests against controlled local providers.

No paid service, user microphone, personal messages or provider credentials are used.
Set HERMES_TEST_PYTHON, HERMES_TEST_ROOT, HERMES_TEST_HOME for SDK acceptance.
"""
import asyncio
import importlib
import json
import os
from pathlib import Path
import shutil
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from contextlib import contextmanager

import httpx
import pytest

from nexus.hermes_agent import HermesAgent
from nexus.hermes_worker import BUILD
from nexus.providers import Providers
from nexus.store import Store
from nexus.tools import Tools


def tool_call(name, args, ident='call_1'):
    return dict(role='assistant', content=None, tool_calls=[dict(id=ident, type='function',
        function=dict(name=name, arguments=json.dumps(args)))])


@contextmanager
def endpoint(reply):
    requests = []
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass
        def do_GET(self):
            body = {'data': [{'id': 'fixture-model'}]}
            self.send_response(200); self.end_headers(); self.wfile.write(json.dumps(body).encode())
        def do_POST(self):
            payload = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
            requests.append(payload)
            status, message = reply(payload, len(requests))
            body = {'model': 'fixture-model', 'choices': [{'message': message}]}
            self.send_response(status)
            if status == 429:self.send_header('Retry-After', '75')
            self.end_headers()
            try:self.wfile.write(json.dumps(body).encode())
            except BrokenPipeError:pass
    server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True);thread.start()
    try:yield 'http://127.0.0.1:%d/v1' % server.server_port, requests
    finally:server.shutdown();server.server_close();thread.join()


def configure(store, urls):
    store.set('providers', [dict(id='fixture-'+str(i), name='Fixture '+str(i), base=url,
        model='fixture-model', kind='openai', paid=False, enabled=True) for i,url in enumerate(urls)])
    store.set('preferred_provider', 'fixture-0')


@pytest.fixture
def runtime(tmp_path):
    values = [os.getenv(k) for k in ('HERMES_TEST_PYTHON','HERMES_TEST_ROOT','HERMES_TEST_HOME')]
    if not all(values):pytest.skip('Exact Hermes runtime not supplied; SDK acceptance not claimed')
    base = tmp_path/'installation';(base/'nexus').mkdir(parents=True)
    shutil.copyfile(Path(__file__).parents[1]/'nexus/hermes_worker.py',base/'nexus/hermes_worker.py')
    (base/'hermes_runtime.json').write_text(json.dumps(dict(zip(
        ('python','root','runtime_home'), values),build=BUILD)))
    return base


@pytest.mark.parametrize('failure',[429,503,'timeout'])
def test_actual_http_fallback_preserves_context(runtime,tmp_path,failure):
    def broken(body,count):
        if failure=='timeout':time.sleep(6.3)
        return (503 if failure=='timeout' else failure),{}
    with endpoint(broken) as (first,one),endpoint(lambda b,n:(200,dict(role='assistant',content='Router recovered.'))) as (second,two):
        store=Store(tmp_path/'data/db');configure(store,[first,second]);providers=Providers(store)
        async def no_tool(name,args):raise AssertionError('No action requested')
        agent=HermesAgent(runtime,tmp_path/'data',providers,no_tool,lambda:False)
        messages=[dict(role='system',content='You are NEXUS AI ULTRA. Reply briefly.'),
                  dict(role='user',content='Remember fixture context 8472')]
        async def run():
            try:return await agent.run(messages,[])
            finally:await agent.close()
        result=asyncio.run(run())
        assert result['text']=='Router recovered.' and result['provider']=='Fixture 1'
        assert one and two and one[0]['messages']==two[0]['messages']
        assert '8472' in json.dumps(two[0]['messages'])
        if failure==429:assert providers.cooldowns['fixture-0']>time.monotonic()+60


def test_tool_receipt_survives_switch_and_duplicate_calls(runtime,tmp_path):
    target=tmp_path/'created.txt';args=dict(path=str(target),text='Approved once')
    def first(body,count):
        return (200,tool_call('create_text',args)) if count==1 else (429,{})
    def second(body,count):
        return (200,tool_call('create_text',args,'different_id')) if count==1 else (200,dict(role='assistant',content='Approval is pending.'))
    with endpoint(first) as (one,requests_one),endpoint(second) as (two,requests_two):
        store=Store(tmp_path/'data/db');store.set('roots',[str(tmp_path)]);configure(store,[one,two])
        tools=Tools(store);pending={}
        async def queue(name,arguments):
            assert name=='create_text'
            pending['real-approval']=arguments
            return dict(approval_required=True,id='real-approval',name=name,args=arguments)
        providers=Providers(store);agent=HermesAgent(runtime,tmp_path/'data',providers,queue,lambda:False)
        async def run():
            try:return await agent.run([dict(role='system',content='You are NEXUS. Never repeat an action.'),dict(role='user',content='Create the approved file.')],tools.schemas())
            finally:await agent.close()
        result=asyncio.run(run());assert result['text']=='Approval is pending.'
        assert len(pending)==1 and not target.exists()
        receipts=[json.loads(m['content']) for m in requests_two[-1]['messages'] if m['role']=='tool']
        assert len(receipts)==2 and receipts[0]['id']==receipts[1]['id']=='real-approval'
        assert all({t['function']['name'] for t in request['tools']}=={t['function']['name'] for t in tools.schemas()}
                   for request in requests_one+requests_two)
        tools.execute('create_text',pending.pop('real-approval'))
        assert target.read_text()=='Approved once'
        ledger=json.loads(next((tmp_path/'data/hermes-tasks').glob('*.json')).read_text())
        assert len(ledger)==1 and next(iter(ledger.values()))['receipt']['id']=='real-approval'


def test_selected_account_failure_uses_router_fallback(tmp_path,monkeypatch):
    with endpoint(lambda b,n:(200,dict(role='assistant',content='fallback'))) as (url,calls):
        store=Store(tmp_path/'db');configure(store,[url]);store.set('account_providers',{'chatgpt-account':True})
        store.set('preferred_provider','chatgpt-account');providers=Providers(store)
        async def unavailable(*args):raise ValueError('Account unavailable')
        monkeypatch.setattr(providers.accounts,'request',unavailable)
        result=asyncio.run(providers.request([dict(role='user',content='hi')],fallback_accounts=True))
        assert result[0]['content']=='fallback' and len(calls)==1
        assert providers.cooldowns['chatgpt-account']>time.monotonic()


def test_gui_voice_approvals_stop_and_settings_use_same_main(runtime,tmp_path,monkeypatch):
    monkeypatch.setenv('NEXUS_DATA_DIR',str(tmp_path/'appdata'))
    import nexus.app
    app=importlib.reload(nexus.app)
    app.hermes=HermesAgent(runtime,app.DATA,app.providers,app.queue_tool,lambda:app.emergency)
    target=tmp_path/'voice-created.txt';args=dict(path=str(target),text='voice approval')
    def respond(body,count):
        if count==1:return 200,dict(role='assistant',content='Hello from NEXUS.')
        if count==2:return 200,tool_call('create_text',args)
        return 200,dict(role='assistant',content='Please approve the file.')
    with endpoint(respond) as (url,calls):
        configure(app.store,[url]);app.store.set('roots',[str(tmp_path)])
        app.store.set('name','NEXUS personal name');app.store.add('memory',{'text':'fixture memory'})
        async def run():
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app.app),base_url='http://127.0.0.1',headers={'x-nexus-token':app.session_token}) as client:
                result=(await client.post('/api/chat',json={'text':'Hello'})).json()
                assert result['agent']=='Hermes' and result['text']=='Hello from NEXUS.'
                warm_pid=app.hermes.process.pid
                voice=await app._auto_chat('Create my file',False)
                assert voice['agent']=='Hermes' and not target.exists() and len(app.pending)==1
                assert app.hermes.process.pid==warm_pid
                spoken=[]
                async def say(text):spoken.append(text)
                monkeypatch.setattr(app.handsfree,'_say',say)
                monkeypatch.setattr(app.handsfree,'_next_approval',lambda:asyncio.sleep(0))
                ident=next(iter(app.pending))
                assert (await client.post('/api/approvals/'+ident,json={'approve':True})).status_code==200
                assert target.read_text()=='voice approval'
                assert (await client.post('/api/approvals/'+ident,json={'approve':True})).status_code==400
                await app.handsfree._reply('Explain the completed file')
                assert spoken==['Please approve the file.']
                await client.post('/api/safety',json={'stop':True})
                assert (await client.post('/api/chat',json={'text':'do something'})).status_code==400
                assert app.hermes.process is None
                assert app.store.get('name')=='NEXUS personal name'
                assert app.store.list('memory')[0]['text']=='fixture memory'
        asyncio.run(run())
        assert 'Current message input source: voice' in calls[1]['messages'][0]['content']


def test_no_config_fails_closed_without_legacy_brain(tmp_path):
    agent=HermesAgent(tmp_path,tmp_path,None,None,lambda:False)
    with pytest.raises(ValueError,match='not configured'):agent.config()


def test_exhausted_router_does_not_restart_or_replay(runtime,tmp_path):
    with endpoint(lambda b,n:(503,{})) as (one,calls_one),endpoint(lambda b,n:(503,{})) as (two,calls_two):
        store=Store(tmp_path/'db');configure(store,[one,two]);providers=Providers(store)
        async def no_tool(*args):raise AssertionError('No tool authorized')
        agent=HermesAgent(runtime,tmp_path/'data',providers,no_tool,lambda:False)
        async def run():
            with pytest.raises(ValueError,match='HTTP 503'):
                await agent.run([dict(role='system',content='You are NEXUS.'),dict(role='user',content='hello')],[])
            assert agent.process is None
            await asyncio.sleep(.15)
        asyncio.run(run());assert len(calls_one)==len(calls_two)==1


def test_existing_explicit_command_runs_inside_hermes_prelude(runtime,tmp_path,monkeypatch):
    monkeypatch.setenv('NEXUS_DATA_DIR',str(tmp_path/'data'))
    import nexus.app
    app=importlib.reload(nexus.app)
    app.hermes=HermesAgent(runtime,app.DATA,app.providers,app.queue_tool,lambda:app.emergency)
    with endpoint(lambda b,n:(200,dict(role='assistant',content='Your routine is ready.'))) as (url,calls):
        configure(app.store,[url])
        async def run():
            try:return await app._auto_chat('routine batao',False)
            finally:await app.hermes.close()
        result=asyncio.run(run())
        assert result['agent']=='Hermes' and calls
        receipt=next(json.loads(m['content']) for m in calls[0]['messages'] if m['role']=='tool')
        assert 'result' in receipt and 'text' in receipt['result']


def test_stop_cancels_inflight_main_agent_without_actions(runtime,tmp_path,monkeypatch):
    monkeypatch.setenv('NEXUS_DATA_DIR',str(tmp_path/'data'))
    import nexus.app
    app=importlib.reload(nexus.app)
    app.hermes=HermesAgent(runtime,app.DATA,app.providers,app.queue_tool,lambda:app.emergency)
    started=threading.Event()
    def slow(body,count):
        started.set();time.sleep(1)
        return 200,dict(role='assistant',content='too late')
    with endpoint(slow) as (url,calls):
        configure(app.store,[url])
        async def run():
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app.app),base_url='http://127.0.0.1',headers={'x-nexus-token':app.session_token}) as client:
                task=asyncio.create_task(client.post('/api/chat',json={'text':'Wait for a response'}))
                assert await asyncio.to_thread(started.wait,15)
                response=await client.post('/api/safety',json={'stop':True})
                assert response.status_code==200
                assert (await task).status_code==409
                assert app.hermes.process is None and not app.pending
        asyncio.run(run());assert len(calls)==1
