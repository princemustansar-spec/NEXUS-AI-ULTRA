"""Session-scoped interruptible voice conversation through existing chat/tools."""
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


class QuietSpeechGate:
    """Fast onset only after quiet input is established; not acoustic echo cancellation."""
    def __init__(self):self.samples=[];self.last=None;self.armed=None;self.loud=0
    def observe(self,status):
        level=status.get('level_dbfs');key=(status.get('job_id'),status.get('seconds'))
        if status.get('phase')!='listening' or not isinstance(level,(int,float)) or key==self.last:return False
        self.last=key
        if self.armed is None:
            self.samples.append(level)
            if len(self.samples)>=4:self.armed=max(self.samples)<-48
            return False
        if not self.armed:return False
        self.loud=self.loud+1 if level>-34 else 0
        return self.loud>=2


class VoiceJobError(ValueError):
    def __init__(self, message, code=None):
        super().__init__(message);self.code=code


class SpeechOutputError(ValueError):
    pass


class HandsFree:
    def __init__(self, store, voice, tts, chat, approve, pending, emergency):
        self.store,self.voice,self.tts=store,voice,tts
        self.chat,self.approve,self.pending,self.emergency=chat,approve,pending,emergency
        self.task=None;self.running=False;self.phase='off';self.error=None
        self.confirmation=None;self.options={};self.failures=0
        self.interrupt_event=None;self.queued_text='';self.probe_job=None;self.interrupt_error=None;self.level_event=None;self.speech_gate=None

    def status(self):
        return {'active':self.running, 'phase':('approval' if self.confirmation and self.phase!='speaking' else self.phase),
                'interrupt_mode':self.options.get('interrupt_mode','off'),'interrupt_error':self.interrupt_error,
                'awaiting':self.confirmation.get('kind') if self.confirmation else None, 'error':self.error}

    async def start(self, consent=False, online_consent=False, allow_online_tts=False, unmute=False, interrupt_mode='off'):
        if interrupt_mode not in ('off','wake','any'):raise ValueError('Choose Off, Nexus ruko, or Any speech interruption.')
        if consent is not True:raise ValueError('Consent to continuous microphone capture and automatic transcript submission is required.')
        if self.emergency():raise ValueError('Emergency Stop active. Resume in Safety Center.')
        if self.store.get('voice_muted',False) and unmute is not True:raise ValueError('Voice is muted. Unmute before starting auto voice.')
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
        self.options['interrupt_mode']=interrupt_mode
        self.interrupt_event=asyncio.Event();self.queued_text='';self.probe_job=None;self.interrupt_error=None
        # Only an explicit mic click may clear saved mute, after every start precondition passes.
        if unmute is True:self.store.set('voice_muted',False)
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

    async def _job(self, service, job, on_status=None):
        deadline=time.monotonic()+125
        while self.running and not self.emergency() and time.monotonic()<deadline:
            status=await asyncio.to_thread(service.status)
            if status.get('job_id')!=job['job_id']:raise ValueError('Auto voice operation changed; session stopped.')
            if on_status:on_status(status)
            if status['phase']=='done':return status.get('result',{})
            if status['phase'] in ('error','cancelled'):
                raise VoiceJobError(status.get('error') or 'Voice operation cancelled.',status.get('error_code'))
            await asyncio.sleep(.15)
        raise ValueError('Auto voice stopped or timed out.')

    async def _say(self, text, interruptible=True):
        if not self.running or self.emergency():raise asyncio.CancelledError()
        if self.interrupt_event:self.interrupt_event.clear()
        self.level_event=asyncio.Event();self.speech_gate=QuietSpeechGate()
        self.phase='speaking'
        clean=re.sub(r'[*#`]', '', str(text)).strip()
        for offset in range(0,len(clean),1400):
            try:
                job=await asyncio.to_thread(self.tts.start,'tts',text=clean[offset:offset+1400],allow_online=self.options.get('allow_online_tts',False))
                spoken=asyncio.create_task(self._job(self.tts,job))
                watcher=asyncio.create_task(self._watch_interrupt(clean[offset:offset+1400])) if interruptible else None
                onset=asyncio.create_task(self.level_event.wait()) if watcher and self.options.get('interrupt_mode')=='any' else None
                try:
                    done,_=await asyncio.wait([t for t in (spoken,watcher,onset) if t],return_when=asyncio.FIRST_COMPLETED)
                    if onset and onset in done and watcher not in done:
                        self.phase='listening'
                        await asyncio.to_thread(self.tts.cancel)
                        spoken.cancel();await asyncio.gather(spoken,return_exceptions=True)
                        self.queued_text=await watcher
                        return
                    if watcher and watcher in done:
                        self.queued_text=watcher.result()
                        await asyncio.to_thread(self.tts.cancel)
                        spoken.cancel();await asyncio.gather(spoken,return_exceptions=True)
                        await asyncio.sleep(.15)
                        return
                    await spoken
                finally:
                    for task in (spoken,watcher,onset):
                        if task and not task.done():task.cancel()
                    await asyncio.gather(*(t for t in (spoken,watcher,onset) if t),return_exceptions=True)
                    if watcher:await self._finish_probe()
            except ValueError as exc:raise SpeechOutputError(str(exc)) from exc
        # The interruption probe is closed; let the final speaker audio decay.
        await asyncio.sleep(.4)

    async def _capture(self, interruption=False):
        if not interruption:self.phase='listening'
        args={k:v for k,v in self.options.items() if k not in ('allow_online_tts','interrupt_mode')}
        if interruption:args.update(seconds=self.options.get('seconds',8),start_timeout=2,silence_timeout=.4,discard_on_stop=True)
        job=await asyncio.to_thread(self.voice.start,'capture',**args)
        if interruption:self.probe_job=job['job_id']
        try:
            def meter(status):
                if self.options.get('interrupt_mode')=='any' and self.speech_gate and self.speech_gate.observe(status):self.level_event.set()
            result=await self._job(self.voice,job,meter) if interruption else await self._job(self.voice,job)
        except ValueError as exc:
            idle_messages=('no speech detected','no speech was recognized','no microphone signal detected','recording stopped before any audio','unknownvalueerror')
            if getattr(exc,'code',None)=='no_speech' or any(value in str(exc).lower() for value in idle_messages):return ''
            raise
        if result.get('no_speech') or result.get('diagnostics',{}).get('silence'):return ''
        original=normalized(str(result.get('original_text','')))
        if interruption:
            raw_original=re.sub(r'\s+',' ',re.sub(r'[^\w\s]','',str(result.get('original_text','')))).strip()
            for prefix in ('نیکسس رکو','نیکسس روکو','نکسس رکو','نیکسس سٹاپ','نیکسس اسٹاپ'):
                if raw_original.startswith(prefix):return 'nexus ruko '+raw_original[len(prefix):].strip()
        if original in {'مائیک بند کرو','میک بند کرو','مائیک بند کر دو','مائیکروفون بند کرو'}:
            return 'mic band karo'
        if self.confirmation:
            if original in {'ہاں منظور','ہاں اپروو','جی ہاں منظور'}:return 'haan approve'
            if original in {'نہیں','نہیں کینسل','کینسل کرو'}:return 'nahi cancel'
        return str(result.get('text','')).strip()

    async def interrupt(self):
        if not self.running or self.phase!='speaking' or self.interrupt_event is None:
            raise ValueError('No auto-voice reply is speaking right now.')
        self.interrupt_event.set()
        return {'interrupted':True,'message':'Stopping reply and returning to listening.'}

    async def _finish_probe(self):
        if not self.probe_job:return
        try:
            status=await asyncio.to_thread(self.voice.status)
            if status.get('job_id')!=self.probe_job or status['phase'] in ('done','error','cancelled','idle'):return
            await asyncio.to_thread(self.voice.stop_recording)
            deadline=time.monotonic()+2
            while time.monotonic()<deadline:
                status=await asyncio.to_thread(self.voice.status)
                if status['phase'] in ('done','error','cancelled','idle'):return
                await asyncio.sleep(.03)
            await asyncio.to_thread(self.voice.cancel)
        except ValueError:pass
        finally:self.probe_job=None

    async def _watch_interrupt(self,spoken_text):
        async def listen():
            echo_reference=spoken_text
            while self.running:
                try:text=await self._capture(interruption=True)
                except ValueError as exc:
                    self.interrupt_error=str(exc)[:200]
                    if self.level_event and self.level_event.is_set():raise
                    # A probe fault must not repeatedly speak errors or kill a valid reply.
                    await asyncio.Future()
                value=normalized(text)
                if not value:continue
                # Require the wake word in wake mode; plain background speech is ignored.
                wake=re.match(r'^(?:nexus|niks|nikss|nexis)\s+(?:ruko|ru ko|ruk jao|stop)\b[ ,.!؟]*',text.lower())
                if wake:return text[wake.end():].strip()
                if self.options.get('interrupt_mode')=='any':
                    words=set(value.split());spoken=set(normalized(echo_reference).split())
                    if words and len(words & spoken)/len(words)<.65:return text
                    if self.level_event and self.level_event.is_set():echo_reference=''
        manual=asyncio.create_task(self.interrupt_event.wait())
        listener=asyncio.create_task(listen()) if self.options.get('interrupt_mode')!='off' else None
        try:
            done,_=await asyncio.wait([manual,listener] if listener else [manual],return_when=asyncio.FIRST_COMPLETED)
            return listener.result() if listener and listener in done else ''
        finally:
            for task in (manual,listener):
                if task and not task.done():task.cancel()
            await asyncio.gather(*(t for t in (manual,listener) if t),return_exceptions=True)

    async def _next_approval(self):
        if self.confirmation:return
        items=self.pending()
        if not items:return
        item=items[0]
        details=json.dumps(item['args'],ensure_ascii=False)
        if item['name']=='whatsapp_send':
            args=item['args'];details='Contact: '+args.get('recipient','')+('. Number: '+args['recipient_phone'] if args.get('recipient_phone') else '')+'. Message: '+args.get('message','')
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
        if answer in YES and confirmation.get('name')=='whatsapp_send':
            receipt=result.get('result',{})
            who=confirmation.get('args',{}).get('recipient','contact')
            if receipt.get('sent') is True:
                message=who+' ke liye WhatsApp ka message acceptance tick verify ho gaya. '+('Delivery ticks bhi verify ho gayi hain.' if receipt.get('delivery_verified') else 'Recipient ki delivery abhi confirm nahi hui.')
            elif receipt.get('sent') is False:message='WhatsApp message send nahi hua: '+str(receipt.get('reason',receipt.get('status','blocked')))
            else:message='WhatsApp send ka result abhi confirm nahi. Chat check karein; main khud dobara send nahi karunga.'

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
        if not self.pending():await self._say(result.get('speech_text') or result['text'])
        await self._next_approval()

    async def _run(self):
        try:
            while self.running and not self.emergency():
                # Capture failures are visual-only: never speak/retry complaints on an idle timer.
                if self.queued_text:
                    text,self.queued_text=self.queued_text,''
                else:text=await self._capture()
                if not text:
                    await asyncio.sleep(.15)
                    continue
                try:
                    if normalized(text) in STOP:
                        await self._say('Auto voice band kar di.',interruptible=False);break
                    if self.confirmation:await self._confirmed(text)
                    else:await self._reply(text)
                    self.failures=0
                except SpeechOutputError:
                    raise
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
