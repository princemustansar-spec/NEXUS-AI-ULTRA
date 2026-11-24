"""Preserve the supplied laptop controller while replacing its planning loop.

The user session-store/voice modules are not replaced by this integration.
Store collaborators below test API delegation, not their unpublished internals.
"""
import ast
import asyncio
import hashlib
from pathlib import Path
import sys
import types
from unittest.mock import Mock

import httpx

from nexus.hermes_agent import HermesAgent
from test_hermes_main import runtime, endpoint, configure

COMPAT = Path(__file__).parents[1]/'compatibility/laptop-7931f0'
LAPTOP_HASH = '7931f0dbef329bcddc925547e1a30a47915fb9d9aaae26640bf1dde2f9a05e1d'


def test_exact_laptop_baseline_and_existing_controllers_are_preserved():
    original=(COMPAT/'baseline_app.py').read_bytes()
    assert hashlib.sha256(original).hexdigest()==LAPTOP_HASH
    before=ast.parse(original.decode());after=ast.parse((COMPAT/'app.py').read_text(encoding='utf-8'))
    old={n.name:n for n in before.body if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef))}
    new={n.name:n for n in after.body if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef))}
    assert old.keys()==new.keys()
    # Only these existing controllers change to enter/close the Hermes main loop.
    for name in old.keys()-{'chat','lifespan','safety'}:
        assert ast.dump(old[name])==ast.dump(new[name]),name
    guard=next(n for n in old['chat'].body if isinstance(n,ast.Try))
    old_lock=guard.body[0]
    new_lock=next(n for n in new['chat'].body if isinstance(n,ast.Try)).body[0]
    assert ast.dump(old_lock.body[0])==ast.dump(new_lock.body[0])  # stale chat ID rejection
    assert "tts.online_voice = lambda: store.get('tts_online_voice', 'male')" in (COMPAT/'app.py').read_text(encoding='utf-8')


def test_laptop_variant_enters_real_hermes_and_retains_session_voice_apis(runtime,tmp_path,monkeypatch):
    monkeypatch.setenv('NEXUS_DATA_DIR',str(tmp_path/'data'))
    module=types.ModuleType('nexus.laptop_app')
    module.__package__='nexus'
    module.__file__=str(Path(__file__).parents[1]/'nexus/app.py')
    monkeypatch.setitem(sys.modules,module.__name__,module)
    exec(compile((COMPAT/'app.py').read_text(encoding='utf-8'),module.__file__,'exec'),module.__dict__)
    module.hermes=HermesAgent(runtime,module.DATA,module.providers,module.queue_tool,lambda:module.emergency)
    module.store.set('active_chat','existing-session')
    # The actual laptop already supplies these APIs; their implementation is left untouched.
    module.store.chat_sessions=Mock(return_value=[dict(id='existing-session',title='Saved chat')])
    module.store.create_chat=Mock(return_value={'chat_id':'new-session'})
    module.store.select_chat=Mock(side_effect=lambda ident:module.store.set('active_chat',ident))
    with endpoint(lambda b,n:(200,dict(role='assistant',content='Settings retained.'))) as (url,calls):
        configure(module.store,[url])
        async def run():
            try:
                async with httpx.AsyncClient(transport=httpx.ASGITransport(app=module.app),base_url='http://127.0.0.1',headers={'x-nexus-token':module.session_token}) as client:
                    stale=await client.post('/api/chat',json={'text':'hello','chat_id':'wrong-session'})
                    assert stale.status_code==409 and not calls and not module.store.list('chat')
                    result=await module._auto_chat('hello',False)
                    assert result['agent']=='Hermes' and result['text']=='Settings retained.'
                    assert 'Current message input source: voice' in calls[0]['messages'][0]['content']
                    saved=await client.post('/api/tts/settings',json={'online_voice':'female'})
                    assert saved.status_code==200 and module.tts.online_voice()=='female'
                    assert (await client.post('/api/tts/settings',json={'online_voice':'unknown'})).status_code==400
                    state=(await client.get('/api/state')).json()
                    assert state['active_chat']=='existing-session' and state['chat_sessions'][0]['title']=='Saved chat'
                    assert (await client.post('/api/chats/new')).json()['chat_id']=='new-session'
                    module.store.create_chat.assert_called_once()
                    assert (await client.post('/api/chats/select',json={'chat_id':'existing-session'})).status_code==200
                    module.store.select_chat.assert_called_once_with('existing-session')
                    async with module.chat_lock:
                        assert (await client.post('/api/chats/new')).status_code==409
            finally:await module.hermes.close()
        asyncio.run(run())
    module.store.db.close()
