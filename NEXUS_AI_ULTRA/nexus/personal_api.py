import asyncio
import time
from fastapi import Request
from .personal import validate_profile
from .startup import set_startup,startup_status
from . import ollama_local

def register(app,store,providers,tools,voice,tts,handsfree,stopped,base):
    personal=tools.personal

    async def speak(text):
        if stopped() or store.get('voice_muted',False):return {'spoken':False,'reason':'Voice muted or Emergency Stop active.'}
        if handsfree.running or any(s.status()['phase'] not in ('idle','done','error','cancelled') for s in (voice,tts)):
            return {'spoken':False,'reason':'Voice is busy; briefing is available as text.'}
        job=await asyncio.to_thread(tts.start,'tts',text=text[:1400],allow_online=store.get('handsfree_online_tts',False))
        deadline=time.monotonic()+90
        while time.monotonic()<deadline:
            state=tts.status()
            if state.get('job_id')!=job['job_id']:return {'spoken':False,'reason':'Voice operation changed.'}
            if state['phase']=='done':return {'spoken':True}
            if state['phase'] in ('cancelled','error'):return {'spoken':False,'reason':state.get('error') or 'Voice cancelled.'}
            if stopped() or store.get('voice_muted',False):await asyncio.to_thread(tts.cancel);return {'spoken':False,'reason':'Voice stopped.'}
            await asyncio.sleep(.15)
        await asyncio.to_thread(tts.cancel)
        return {'spoken':False,'reason':'Voice timed out.'}

    @app.get('/api/personal')
    def snapshot():return dict(profile=personal.profile(),routines=personal.routines(),startup=startup_status(),ollama_fallback=store.get('ollama_fallback',False))

    @app.post('/api/personal/settings')
    async def settings(request:Request):
        body=await request.json()
        if not isinstance(body,dict):raise ValueError('Personal settings must be an object.')
        return dict(profile=personal.save(body))

    @app.post('/api/personal/startup-mode')
    async def startup_mode(request:Request):
        if stopped():raise ValueError('Emergency Stop active.')
        body=await request.json()
        return await asyncio.to_thread(set_startup,base,body.get('enabled'))

    @app.post('/api/personal/routines')
    async def routine(request:Request):return {'id':personal.add_routine(await request.json())}

    @app.delete('/api/personal/routines/{ident}')
    def delete_routine(ident:int):store.delete('routine',ident);return {'deleted':True}

    @app.post('/api/personal/briefing')
    async def briefing(request:Request):
        if stopped():raise ValueError('Emergency Stop active.')
        body=await request.json()
        if any(type(body.get(k,False)) is not bool for k in ('news','speak')):raise ValueError('news and speak must be true or false.')
        result=await asyncio.to_thread(personal.briefing,body.get('news',False))
        if body.get('speak'):result.update(await speak(result['speech_text']))
        return result

    async def welcome():
        profile=personal.profile()
        if not profile['welcome_enabled'] or stopped():return {'skipped':True}
        result=await asyncio.to_thread(personal.briefing,profile['news_on_start'])
        if stopped():return {'skipped':True}
        store.add('notification',{'text':result['text']});personal.react('Welcome back!')
        if profile['speak_welcome']:result.update(await speak(result['speech_text']))
        return result

    @app.post('/api/personal/startup')
    async def startup():
        # Refreshes and the native floating bootstrap await the same one-shot task.
        if personal.startup_task is None:personal.startup_task=asyncio.create_task(welcome())
        return await asyncio.shield(personal.startup_task)

    @app.get('/api/personal/ollama')
    async def inspect():return await ollama_local.inspect()

    @app.post('/api/personal/ollama')
    async def configure_ollama(request:Request):
        if stopped():raise ValueError('Emergency Stop active.')
        body=await request.json();action=body.get('action')
        if action=='test':
            try:message,_,model=await ollama_local.request(providers,[{'role':'user','content':'Reply with: NEXUS local model ready.'}],test=True)
            except Exception as exc:raise ValueError('Local test failed: '+providers.error(exc)) from None
            return dict(verified=True,model=model,text=message.get('content',''),tools_supported=providers.status['ollama'].get('tools_supported',False))
        if action!='configure':raise ValueError('Choose configure or test.')
        model=body.get('model','');mode=body.get('mode','')
        if mode not in ('local','fallback','disabled'):raise ValueError('Choose local, fallback or disabled.')
        if mode!='disabled':
            catalog=await ollama_local.inspect()
            if not catalog['available'] or model not in [m['name'] for m in catalog['models']]:raise ValueError('Choose an installed model; NEXUS does not download models automatically.')
        configs=[dict(p) for p in providers.configs() if p.get('kind')!='account']
        p=next((p for p in configs if p['id']=='ollama'),None)
        if p is None:
            from .providers import DEFAULTS
            p=dict(next(p for p in DEFAULTS if p['id']=='ollama'));configs.append(p)
        p.update(base=ollama_local.BASE+'/v1',model=model,enabled=mode!='disabled',paid=False)
        providers.save(configs);store.set('ollama_fallback',mode=='fallback')
        if mode=='local':
            previous=store.get('preferred_provider','')
            if previous!='ollama':store.set('ollama_previous_provider',previous)
            store.set('preferred_provider','ollama')
        elif store.get('preferred_provider')=='ollama':store.set('preferred_provider',store.get('ollama_previous_provider',''))
        return dict(saved=True,mode=mode,model=model)
