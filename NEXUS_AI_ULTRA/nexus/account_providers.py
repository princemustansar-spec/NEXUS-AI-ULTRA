"""Account providers are opt-in and route tools through the normal NEXUS planner."""
import asyncio
from . import chatgpt_signin as chatgpt
from .claude_code import ClaudeCode

IDS=('chatgpt-account','claude-account')
NAMES={'chatgpt-account':'ChatGPT account','claude-account':'Claude Code account'}


class AccountProviders:
    def __init__(self,store):self.store=store;self.claude=ClaudeCode()

    def configs(self):
        enabled=self.store.get('account_providers',{})
        return [dict(id=i,name=NAMES[i],kind='account',base='https://api.openai.com/v1' if i==IDS[0] else 'http://127.0.0.1',
            model='Account default',paid=False,enabled=True) for i in IDS if enabled.get(i) is True]

    def status(self):
        return {'chatgpt':chatgpt.status(),'claude':dict(self.claude.cached),'enabled':self.store.get('account_providers',{})}

    async def models(self,ident):
        if ident==IDS[0]:return [m['slug'] for m in await asyncio.to_thread(chatgpt.models)]
        if ident==IDS[1]:
            status=await self.claude.check()
            if not status['connected']:raise ValueError(status['error'])
            return ['Claude Code account default']
        raise ValueError('Unknown account provider')

    async def request(self,ident,messages,tools=None):
        if not self.store.get('account_providers',{}).get(ident):raise ValueError('Account plan usage has not been enabled in Settings.')
        if ident==IDS[1]:return await self.claude.request(messages,tools)
        if ident!=IDS[0]:raise ValueError('Unknown account provider')
        result=await asyncio.to_thread(chatgpt.request_chatgpt,messages,tools)
        return result['choices'][0]['message'],chatgpt.status().get('model') or 'ChatGPT account'

    def disable(self,ident):
        values=self.store.get('account_providers',{});values[ident]=False;self.store.set('account_providers',values)
        if self.store.get('preferred_provider')==ident:self.store.set('preferred_provider','')
