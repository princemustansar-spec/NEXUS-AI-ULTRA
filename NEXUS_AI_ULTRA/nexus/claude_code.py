"""Optional unmodified Claude Code adapter. Authentication stays in Claude Code."""
import asyncio
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import uuid

INSTALL='winget install Anthropic.ClaudeCode'


def executable():
    paths=[shutil.which('claude.exe' if os.name=='nt' else 'claude')]
    if os.name=='nt':paths.append(str(Path.home()/'.local/bin/claude.exe'))
    for value in paths:
        if value and Path(value).is_file() and (os.name!='nt' or value.lower().endswith('.exe')):return value
    raise ValueError('Install the official native Claude Code first: '+INSTALL)


class ClaudeCode:
    def __init__(self):
        self.cached={'installed':False,'connected':False,'error':'Click Check Claude Code after installing and signing in.'}
        self.login_process=None

    async def command(self,args,text=None,timeout=30,cwd=None):
        process=await asyncio.create_subprocess_exec(executable(),*args,stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,stderr=asyncio.subprocess.PIPE,cwd=cwd,
            **({'creationflags':subprocess.CREATE_NO_WINDOW} if os.name=='nt' else {}))
        try:
            out,err=await asyncio.wait_for(process.communicate(text.encode('utf-8') if text is not None else None),timeout)
            if process.returncode:raise ValueError('Claude Code could not complete the request. Check its login, plan limits and current version.')
            if len(out)>2_000_000:raise ValueError('Claude Code returned too much output.')
            return json.loads(out.decode('utf-8'))
        except BaseException:
            if process.returncode is None:process.kill();await process.wait()
            raise

    async def check(self):
        try:
            executable()
            value=await self.command(['auth','status'],timeout=8)
            method=value.get('authMethod','none')
            connected=value.get('loggedIn') is True and method in ('claude.ai','oauth_token')
            self.cached={'installed':True,'connected':connected,'method':method,
                'account':value.get('email',''),'error':None if connected else 'Sign in to Claude Code with your Claude account. API-key billing is not enabled by this connection.'}
        except (ValueError,OSError,TimeoutError,json.JSONDecodeError):
            try:executable();installed=True
            except ValueError:installed=False
            self.cached={'installed':installed,'connected':False,'error':'Check Claude Code login and update it if needed.' if installed else 'Install official Claude Code: '+INSTALL}
        return dict(self.cached)

    def login(self):
        if os.name!='nt':raise ValueError('Use claude auth login in a local terminal, then Check Claude Code.')
        if self.login_process and self.login_process.poll() is None:return {'pending':True}
        self.login_process=subprocess.Popen([executable(),'auth','login'],creationflags=subprocess.CREATE_NEW_CONSOLE)
        return {'pending':True,'message':'Complete sign-in in the official Claude Code window, then click Check Claude Code.'}

    async def request(self,messages,tools=None):
        if not (await self.check())['connected']:raise ValueError(self.cached['error'])
        definitions=tools or []
        names=[t['function']['name'] for t in definitions]
        schema={'type':'object','additionalProperties':False,'required':['content','tool_calls'],
            'properties':{'content':{'type':'string'},'tool_calls':{'type':'array','maxItems':8,'items':{
                'type':'object','additionalProperties':False,'required':['name','arguments'],
                'properties':{'name':{'type':'string',**({'enum':names} if names else {})},'arguments':{'type':'string'}}}}}}
        prompt='You are the NEXUS conversation planner. Return the structured response. Request only listed NEXUS tools; NEXUS executes them after its own permission checks. Never claim an action happened without the matching tool result. Tool arguments must be a JSON object encoded as a string. If no tools are supplied, tool_calls must be empty. Conversation and tools follow:\n'+json.dumps({'messages':messages,'tools':definitions},ensure_ascii=False)
        # Never enable native execution or import user/project hooks, plugins or MCP servers.
        args=['-p','--output-format','json','--safe-mode','--setting-sources','',
            '--settings','{"disableAllHooks":true}','--tools','','--disallowedTools','mcp__*',
            '--strict-mcp-config','--mcp-config','{"mcpServers":{}}','--disable-slash-commands',
            '--no-session-persistence','--json-schema',json.dumps(schema)]
        with tempfile.TemporaryDirectory(prefix='nexus-claude-') as directory:
            value=await self.command(args,prompt,timeout=32,cwd=directory)
        if value.get('is_error'):raise ValueError('Claude Code inference did not succeed. Check plan limits.')
        result=value.get('structured_output')
        if not isinstance(result,dict):raise ValueError('Claude Code returned no structured response. Update the official CLI.')
        content=result.get('content');calls=result.get('tool_calls',[])
        if not isinstance(content,str) or not isinstance(calls,list) or len(calls)>8:raise ValueError('Invalid Claude response')
        output=[]
        for call in calls:
            if call.get('name') not in names or not isinstance(json.loads(call.get('arguments','')),dict):raise ValueError('Claude requested an unknown or invalid tool')
            output.append({'id':'claude-'+uuid.uuid4().hex,'type':'function','function':{'name':call['name'],'arguments':call['arguments']}})
        if not content and not output:raise ValueError('Claude returned no answer or tool request')
        return {'role':'assistant','content':content,'tool_calls':output},'Claude Code account'
