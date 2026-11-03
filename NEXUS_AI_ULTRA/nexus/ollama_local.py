"""Bounded native Ollama calls. Never download a model or fall back to a cloud silently."""
import json
import secrets
from urllib.parse import urlparse
import httpx

BASE='http://127.0.0.1:11434'

def local_config(providers):
    p=next((p for p in providers.configs() if p['id']=='ollama'),None)
    if not p or not p['enabled']:raise ValueError('Enable Ollama in Personal Assistant settings first.')
    u=urlparse(p['base'])
    if u.scheme!='http' or u.hostname not in ('127.0.0.1','localhost','::1') or u.port!=11434 or u.username or u.password:raise ValueError('Local Ollama must use this computer on port 11434.')
    return p

async def inspect():
    try:
        async with httpx.AsyncClient(timeout=4,follow_redirects=False,trust_env=False) as client:
            response=await client.get(BASE+'/api/tags');response.raise_for_status()
        return dict(available=True,models=[{'name':m['name'],'bytes':m.get('size',0)} for m in response.json().get('models',[]) if isinstance(m.get('name'),str)][:40])
    except (httpx.HTTPError,ValueError,TypeError,KeyError):return dict(available=False,models=[],error='Ollama local server unavailable. Open Ollama on this computer.')

async def request(providers,messages,tools=None,test=False):
    p=local_config(providers);model=p.get('model') or 'llama3.2:latest'
    if model.upper()=='AUTO':model='llama3.2:latest'
    async with httpx.AsyncClient(timeout=httpx.Timeout(120,connect=3),follow_redirects=False,trust_env=False) as client:
        metadata=await client.post(BASE+'/api/show',json={'model':model});metadata.raise_for_status();capabilities=metadata.json().get('capabilities',[])
        supported='tools' in capabilities
        converted=[]
        for item in messages:
            row={k:v for k,v in item.items() if k in ('role','content','tool_calls')}
            if row.get('tool_calls'):
                row['tool_calls']=[{'function':{'name':c['function']['name'],'arguments':json.loads(c['function']['arguments']) if isinstance(c['function']['arguments'],str) else c['function']['arguments']}} for c in row['tool_calls']]
            converted.append(row)
        if not supported:converted.insert(0,{'role':'system','content':'This local model has no tool-call capability in NEXUS. Answer conversation only. Never claim that you performed desktop actions. The app handles explicit routine, news and lock commands separately.'})
        body={'model':model,'messages':converted,'stream':False,'keep_alive':'2m','options':{'num_ctx':4096,'num_predict':64 if test else 512}}
        if supported and tools:body['tools']=tools
        response=await client.post(BASE+'/api/chat',json=body);response.raise_for_status();data=response.json();message=data.get('message',{})
    if not isinstance(message,dict) or not (message.get('content') or message.get('tool_calls')):raise ValueError('Ollama returned no reply.')
    if message.get('tool_calls') and not supported:raise ValueError('Model returned tool calls without declaring tool support.')
    for call in message.get('tool_calls',[]):
        call['id']='local_'+secrets.token_hex(8);call['type']='function'
        if not isinstance(call['function']['arguments'],str):call['function']['arguments']=json.dumps(call['function']['arguments'])
    providers.active=dict(provider=p['name'],provider_id='ollama',model=data.get('model',model))
    providers.status['ollama']=dict(connected=True,models=[model],tools_supported=supported,error=None)
    return message,p['name'],data.get('model',model)
