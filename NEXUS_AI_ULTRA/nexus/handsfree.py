"""Session-scoped half-duplex voice conversation through the existing chat/tools."""
import asyncio
import json
import re
import time
from .voice_online import recognition_locale

YES = {'yes approve','haan approve','han approve','approve karo','manzoor hai'}
NO = {'no','nahi','nahin','cancel','cancel karo','nahi cancel','no cancel'}
STOP = {'mic band karo','microphone band karo','maik band karo','voice band karo','stop listening','stop voice'}


def normalized(text):
    value=re.sub(r'\s+', ' ', re.sub(r'[^\w\s]', '', text.lower())).strip()
    return re.sub(r'^(?:nexus|niks|nikss|nexis|نیکسس|نکسس)\s+', '', value)


class HandsFree:
    def __init__(self, store, voice, tts, chat, approve, pending, emergency):
        self.store,self.voice,self.tts=store,voice,tts
        self.chat,self.approve,self.pending,self.emergency=chat,approve,pending,emergency
        self.task=None;self.running=False;self.phase='off';self.error=None
        self.confirmation=None;self.options={};self.failures=0

    def status(self):
        return {'active':self.running, 'phase':('approval' if self.confirmation and self.phase!='speaking' else self.phase),
                'awaiting':self.confirmation.get('kind') if self.confirmation else None, 'error':self.error}

    async def start(self, consent=False, online_consent=False, allow_online_tts=False):
        if consent is not True:raise ValueError('Consent to continuous microphone capture and automatic transcript submission is required.')
        if self.emergency():raise ValueError('Emergency Stop active. Resume in Safety Center.')
        if self.store.get('voice_muted',False):raise ValueError('Voice is muted. Unmute before starting auto voice.')
        if self.running:return self.status()
        settings={**{'device':None,'language':'ur','seconds':8,'engine':'google','locale':'auto','silence_timeout':.8,'start_timeout':5},**self.store.get('voice_settings',{})}
        if settings['engine']=='google' and online_consent is not True:
            raise ValueError('Consent to sending captured clips to Google is required for auto voice.')
        for service in (self.voice,self.tts):
            status=await asyncio.to_thread(service.status)
            if status['phase'] not in ('idle','done','error','cancelled'):
                raise ValueError('Finish the current voice operation before starting auto voice.')
        settings['locale']=recognition_locale(settings['language'],settings.get('locale','auto'))
        settings['silence_timeout']=settings.get('silence_timeout') or .8
        self.options={k:settings[k] for k in ('device','language','seconds','engine','locale','silence_timeout','start_timeout')}
        self.options['allow_online_tts']=allow_online_tts is True
        self.error=None;self.failures=0;self.confirmation=None;self.running=True;self.phase='starting'
        self.task=asyncio.create_task(self._run(),name='NEXUS-auto-voice')
        return self.status()

    async def stop(self):
        self.running=False
        task=self.task
        if task and task is not asyncio.current_task() and not task.done():
            task.cancel()
            await asyncio.gather(task,return_exceptions=True)
        self.task=None;self.confirmation=None
        if self.phase!='error':self.phase='off'
        return self.status()

    async def _job(self, service, job):
        deadline=time.monotonic()+125
        while self.running and not self.emergency() and time.monotonic()<deadline:
            status=await asyncio.to_thread(service.status)
            if status.get('job_id')!=job['job_id']:raise ValueError('Auto voice operation changed; session stopped.')
            if status['phase']=='done':return status.get('result',{})
            if status['phase'] in ('error','cancelled'):
                raise ValueError(status.get('error') or 'Voice operation cancelled.')
            await asyncio.sleep(.15)
        raise ValueError('Auto voice stopped or timed out.')

    async def _say(self, text):
        if not self.running or self.emergency():raise asyncio.CancelledError()
        self.phase='speaking'
        clean=re.sub(r'[*#`]', '', str(text)).strip()
        for offset in range(0,len(clean),1400):
            job=await asyncio.to_thread(self.tts.start,'tts',text=clean[offset:offset+1400],allow_online=self.options.get('allow_online_tts',False))
            await self._job(self.tts,job)
        # No capture while speaking; allow the final speaker audio to decay.
        await asyncio.sleep(.4)

    async def _capture(self):
        self.phase='listening'
        args={k:v for k,v in self.options.items() if k!='allow_online_tts'}
        job=await asyncio.to_thread(self.voice.start,'capture',**args)
        try:
            result=await self._job(self.voice,job)
        except ValueError as exc:
            if 'No speech detected' in str(exc):return ''
            raise
        original=normalized(str(result.get('original_text','')))
        if original in {'مائیک بند کرو','میک بند کرو','مائیک بند کر دو','مائیکروفون بند کرو'}:
            return 'mic band karo'
        if self.confirmation:
            if original in {'ہاں منظور','ہاں اپروو','جی ہاں منظور'}:return 'haan approve'
            if original in {'نہیں','نہیں کینسل','کینسل کرو'}:return 'nahi cancel'
        return str(result.get('text','')).strip()

    async def _next_approval(self):
        if self.confirmation:return
        items=self.pending()
        if not items:return
        item=items[0]
        details=json.dumps(item['args'],ensure_ascii=False)
        if len(details)>1100:
            await self._say('Is action ki details lambi hain. Safety Center mein review karein. Auto voice pause kar raha hoon.')
            self.running=False;return
        self.confirmation={'kind':'tool',**item}
        await self._say('Approval chahiye. Action: '+item['name']+'. Details: '+details+'. Karna hai to haan approve kahein, warna nahi cancel kahein.')

    async def _confirmed(self, text):
        answer=normalized(text)
        if answer not in YES|NO:
            await self._say('Pehle pending action ka jawab dein: haan approve, ya nahi cancel.')
            return
        confirmation=self.confirmation;self.confirmation=None
        if confirmation['kind']=='paid':
            if answer in NO:await self._say('Paid request cancel kar di.');return
            await self._reply(confirmation['text'],allow_paid=True)
            return
        result=await self.approve(confirmation['id'],answer in YES)
        message='Action cancel kar diya.' if answer in NO else 'Tool ka result: '+json.dumps(result,ensure_ascii=False,default=str)
        self.store.add('chat',{'role':'assistant','text':message,'provider':'NEXUS voice approval','model':'local tool'})
        await self._say(message)
        await self._next_approval()

    async def _reply(self, text, allow_paid=False):
        self.phase='thinking'
        try:
            result=await self.chat(text,allow_paid)
        except ValueError as exc:
            if 'paid request requires' in str(exc).lower() and not allow_paid:
                self.confirmation={'kind':'paid','text':text}
                await self._say('Free provider se jawab nahi mila. Is request ke liye paid API istemal karne se charges lag sakte hain. Sirf is turn ke liye haan approve kahein, warna nahi cancel.')
                return
            raise
        if not isinstance(result,dict) or 'text' not in result:
            raise ValueError('Voice chat did not complete. Request may have been cancelled.')
        if not self.pending():await self._say(result['text'])
        await self._next_approval()

    async def _run(self):
        try:
            await self._say('Auto voice on hai. Baat karne ke baad rukain, main jawab dunga. Mic band karo keh kar rok sakte hain.')
            await self._next_approval()
            while self.running and not self.emergency():
                try:
                    text=await self._capture()
                    if not text:continue
                    if normalized(text) in STOP:
                        await self._say('Auto voice band kar di.');break
                    if self.confirmation:await self._confirmed(text)
                    else:await self._reply(text)
                    self.failures=0
                except ValueError as exc:
                    self.failures+=1
                    if self.failures>=3:raise
                    await self._say('Kaam complete nahi hua: '+str(exc))
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            self.error=str(exc)[:300];self.phase='error'
        finally:
            self.running=False;self.confirmation=None
            await asyncio.to_thread(self.voice.cancel)
            await asyncio.to_thread(self.tts.cancel)
            if self.phase!='error':self.phase='off'
