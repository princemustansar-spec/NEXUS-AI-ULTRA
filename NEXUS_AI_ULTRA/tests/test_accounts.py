import asyncio
import base64
import hashlib
import importlib
import json
import threading
import time
from types import SimpleNamespace
from unittest.mock import Mock,AsyncMock
from urllib.parse import urlsplit,parse_qs,urlencode
from urllib.request import urlopen
from urllib.error import HTTPError
import pytest
from nexus import chatgpt_signin as login
from nexus.account_providers import AccountProviders
from nexus.claude_code import ClaudeCode
from nexus.store import Store


@pytest.fixture
def local_session(tmp_path,monkeypatch):
    monkeypatch.setattr(login,'ROOT',tmp_path)
    monkeypatch.setattr(login,'HOST_PATH',tmp_path/'host.json')
    monkeypatch.setattr(login,'CREDS_PATH',tmp_path/'session.dpapi')
    monkeypatch.setattr(login,'_protect',lambda b:b'cipher:'+base64.b64encode(b))
    monkeypatch.setattr(login,'_unprotect',lambda b:base64.b64decode(b.removeprefix(b'cipher:')))
    login._LOGIN.update(pending=False,error='')
    return tmp_path


def test_pkce_browser_callback_rejects_wrong_state_then_validates_issued_client(local_session,monkeypatch):
    sent={};threads=[]
    def browser(url):
        params=parse_qs(urlsplit(url).query);sent.update(params)
        assert params['client_id']==['dynamic_agent_client']
        assert params['agent_name_hint']==['NEXUS AI ULTRA']
        def callbacks():
            redirect=params['redirect_uri'][0]
            try:urlopen(redirect+'?'+urlencode({'state':'wrong','code':'wrong'}),timeout=5)
            except HTTPError as exc:assert exc.code==400
            with urlopen(redirect+'?'+urlencode({'state':params['state'][0],'client_id':'oaiapp_test','code':'test-code'}),timeout=5) as r:assert r.status==200
        t=threading.Thread(target=callbacks);threads.append(t);t.start();return True
    def post(url,data,timeout):
        assert url==login.AUTH+'/api/accounts/oauth/token'
        assert data['client_id']=='oaiapp_test' and data['code']=='test-code'
        assert login._b64url(hashlib.sha256(data['code_verifier'].encode()).digest())==sent['code_challenge'][0]
        assert data['redirect_uri']==sent['redirect_uri'][0]
        return SimpleNamespace(is_success=True,json=lambda:{'id_token':'id-secret','access_token':'access-secret','refresh_token':'refresh-secret','scope':login.SCOPES,'expires_in':3600})
    monkeypatch.setattr(login.webbrowser,'open',browser)
    monkeypatch.setattr(login,'requests',SimpleNamespace(post=post))
    verify=Mock(side_effect=lambda token,client,nonce:({'sub':'account-one','email':'owner@example.test'} if nonce==sent['nonce'][0] else {}))
    monkeypatch.setattr(login,'_verify_id_token',verify)
    login._login_worker()
    for t in threads:t.join(5)
    assert not login._LOGIN['error']
    assert login.status()['connected']
    public=json.dumps(login.status());assert all(secret not in public for secret in ('id-secret','access-secret','refresh-secret'))
    assert b'access-secret' not in login.CREDS_PATH.read_bytes()
    assert login._load_session()['client_id']=='oaiapp_test'


def test_id_token_signature_audience_expiry_and_nonce(monkeypatch):
    import jwt
    from cryptography.hazmat.primitives.asymmetric import rsa
    key=rsa.generate_private_key(public_exponent=65537,key_size=2048)
    monkeypatch.setattr(jwt,'PyJWKClient',lambda *a,**k:SimpleNamespace(get_signing_key_from_jwt=lambda token:SimpleNamespace(key=key.public_key())))
    claims={'iss':login.AUTH,'aud':'client','sub':'one','exp':int(time.time())+60,'iat':int(time.time()),'nonce':'nonce'}
    token=jwt.encode(claims,key,algorithm='RS256')
    assert login._verify_id_token(token,'client','nonce')['sub']=='one'
    with pytest.raises(RuntimeError,match='nonce'):login._verify_id_token(token,'client','wrong')
    with pytest.raises(jwt.InvalidAudienceError):login._verify_id_token(token,'other','nonce')
    with pytest.raises(jwt.ExpiredSignatureError):login._verify_id_token(jwt.encode({**claims,'exp':1},key,algorithm='RS256'),'client','nonce')


def test_refresh_rotates_tokens_preserves_identity_and_checks_scope(local_session,monkeypatch):
    login._save_session({'client_id':'client','sub':'one','scopes':login.SCOPES.split(),'expires_at':0,'refresh_token':'old'})
    post=Mock(return_value=SimpleNamespace(is_success=True,json=lambda:{'access_token':'new','refresh_token':'rotated','expires_in':3600,'scope':login.SCOPES}))
    monkeypatch.setattr(login,'requests',SimpleNamespace(post=post))
    assert login._refresh_if_needed()['refresh_token']=='rotated'
    assert login._load_session()['sub']=='one'
    login._save_session({**login._load_session(),'expires_at':0})
    post.return_value.json=lambda:{'access_token':'new','scope':'openid','expires_in':3600}
    with pytest.raises(RuntimeError,match='revoked'):login._refresh_if_needed()


def sse(events):return SimpleNamespace(iter_lines=lambda:iter('data: '+json.dumps(e) for e in events))


def test_stream_requires_completion_and_keeps_text_and_tools():
    events=[{'type':'response.output_text.delta','output_index':0,'delta':'Done'},
        {'type':'response.output_item.added','output_index':1,'item':{'type':'function_call','call_id':'call-one','name':'system_info','arguments':''}},
        {'type':'response.function_call_arguments.delta','output_index':1,'delta':'{}'},
        {'type':'response.completed','response':{'output':[{'type':'function_call','call_id':'call-one','name':'system_info','arguments':'{}'}]}}]
    msg=login._chat_result(login._sse_completed(sse(events)))['choices'][0]['message']
    assert msg['content']=='Done' and msg['tool_calls'][0]['id']=='call-one'
    with pytest.raises(RuntimeError,match='before response.completed'):login._sse_completed(sse(events[:-1]))
    with pytest.raises(RuntimeError,match='failed'):login._sse_completed(sse([{'type':'response.failed'}]))


def test_responses_request_uses_fixed_endpoint_and_input_history(local_session,monkeypatch):
    login._save_session({'model':'account-model','access_token':'secret','expires_at':time.time()+3600,'scopes':login.SCOPES.split()})
    stream=sse([{'type':'response.completed','response':{'output':[{'type':'message','content':[{'type':'output_text','text':'OK'}]}]}}]);stream.is_success=True
    class Context:
        def __enter__(self):return stream
        def __exit__(self,*a):pass
    transport=Mock(return_value=Context());monkeypatch.setattr(login,'requests',SimpleNamespace(stream=transport))
    result=login.request_chatgpt([{'role':'user','content':'hello'},{'role':'tool','tool_call_id':'call','content':'result'}],[{'type':'function','function':{'name':'system_info','parameters':{'type':'object'}}}])
    args=transport.call_args;body=args.kwargs['json']
    assert args.args==('POST','https://api.openai.com/v1/responses')
    assert body['store'] is False and body['stream'] is True
    assert body['input'][0]['type']=='additional_tools'
    assert body['input'][-1]['type']=='function_call_output'
    assert result['choices'][0]['message']['content']=='OK'


def test_claude_adapter_disables_native_execution_and_maps_nexus_tools(monkeypatch):
    cli=ClaudeCode();cli.check=AsyncMock(return_value={'connected':True})
    cli.command=AsyncMock(return_value={'structured_output':{'content':'Checking','tool_calls':[{'name':'system_info','arguments':'{}'}]}})
    msg,model=asyncio.run(cli.request([{'role':'user','content':'RAM?'}],[{'type':'function','function':{'name':'system_info'}}]))
    assert msg['tool_calls'][0]['function']['name']=='system_info'
    args=cli.command.call_args.args[0]
    assert args[args.index('--tools')+1]=='' and args[args.index('--disallowedTools')+1]=='mcp__*'
    assert '--safe-mode' in args and '--strict-mcp-config' in args and '--no-session-persistence' in args
    assert '--dangerously-skip-permissions' not in args
    cli.command.return_value={'structured_output':{'content':'','tool_calls':[{'name':'Bash','arguments':'{}'}]}}
    with pytest.raises(ValueError,match='unknown'):asyncio.run(cli.request([],[]))


def test_claude_api_key_is_not_silently_used_as_account_subscription(monkeypatch):
    import nexus.claude_code as module
    monkeypatch.setattr(module,'executable',lambda:'/official/claude')
    cli=ClaudeCode();cli.command=AsyncMock(return_value={'loggedIn':True,'authMethod':'api_key','email':'owner'})
    assert not asyncio.run(cli.check())['connected']
    cli.command.return_value={'loggedIn':True,'authMethod':'claude.ai'}
    assert asyncio.run(cli.check())['connected']


def test_account_routes_require_token_usage_consent_and_successful_test(tmp_path,monkeypatch):
    from fastapi.testclient import TestClient
    monkeypatch.setenv('NEXUS_DATA_DIR',str(tmp_path))
    import nexus.app
    app=importlib.reload(nexus.app)
    monkeypatch.setattr(login,'request_chatgpt',Mock(return_value={'choices':[{'message':{'content':'OK'}}]}))
    with TestClient(app.app) as c:
        assert c.post('/api/accounts/chatgpt/enable',json={'consent':True}).status_code==403
        c.headers['x-nexus-token']=app.session_token
        assert c.post('/api/accounts/chatgpt/enable',json={'consent':True}).status_code==400
        assert c.post('/api/accounts/chatgpt/test',json={}).status_code==400
        login.request_chatgpt.assert_not_called()
        assert c.post('/api/accounts/chatgpt/test',json={'consent':True}).json()['verified']
        assert c.post('/api/accounts/chatgpt/enable',json={'consent':True}).json()['enabled']
        assert app.store.get('preferred_provider')=='chatgpt-account'
        assert app.providers.configs()[-1]['kind']=='account'
        assert c.post('/api/accounts/chatgpt/disable',json={}).status_code==200
        assert app.store.get('preferred_provider')==''
    app.store.db.close()


def test_account_selection_does_not_silently_send_to_other_providers(tmp_path,monkeypatch):
    from nexus.providers import Providers
    store=Store(tmp_path/'store.sqlite');store.set('preferred_provider','chatgpt-account')
    providers=Providers(store);providers.accounts.request=AsyncMock(side_effect=ValueError('Sign in again'))
    with pytest.raises(ValueError,match='Sign in again'):asyncio.run(providers.request([{'role':'user','content':'hi'}]))
    store.db.close()


@pytest.mark.skipif(__import__('os').name!='nt',reason='Windows DPAPI')
def test_windows_credentials_are_encrypted_and_round_trip():
    from nexus.account_secrets import protect,unprotect
    value=b'access and refresh token test payload'*400
    protected=protect(value)
    assert protected!=value and value not in protected and unprotect(protected)==value


def test_claude_subprocess_transport_and_timeout_kills_its_worker(monkeypatch):
    import sys
    import nexus.claude_code as module
    monkeypatch.setattr(module,'executable',lambda:sys.executable)
    cli=ClaudeCode()
    result=asyncio.run(cli.command(['-c','import sys,json; print(json.dumps({"input":sys.stdin.read()}))'],'hello'))
    assert result=={'input':'hello'}
    original=asyncio.create_subprocess_exec;children=[]
    async def spawn(*args,**kwargs):
        p=await original(*args,**kwargs);children.append(p);return p
    monkeypatch.setattr(module.asyncio,'create_subprocess_exec',spawn)
    with pytest.raises(TimeoutError):asyncio.run(cli.command(['-c','import time; time.sleep(30)'],timeout=.05))
    assert children[0].returncode is not None


def test_account_provider_cannot_be_used_as_an_image_endpoint(tmp_path):
    from nexus.providers import Providers
    store=Store(tmp_path/'store.sqlite');store.set('account_providers',{'chatgpt-account':True})
    with pytest.raises(ValueError,match='image API'):asyncio.run(Providers(store).image('chatgpt-account','robot',True))
    store.db.close()
