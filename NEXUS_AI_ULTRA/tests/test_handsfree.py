import asyncio
import json
from unittest.mock import Mock
import pytest
from nexus.handsfree import HandsFree

class Store:
    def __init__(self):self.records=[];self.settings={}
    def get(self,key,default=None):return self.settings.get(key,default)
    def add(self,kind,value):self.records.append((kind,value))

class Voice:
    def __init__(self,texts,events):self.texts=list(texts);self.events=events;self.job=0;self.phase='idle';self.cancelled=0
    def status(self):
        if not self.job:return {'phase':self.phase}
        if self.text is None:return {'job_id':str(self.job),'phase':'listening'}
        if isinstance(self.text,dict):return {'job_id':str(self.job),**self.text}
        return {'job_id':str(self.job),'phase':'done','result':{'text':self.text}}
    def start(self,operation,**options):
        assert operation=='capture';self.job+=1;self.text=self.texts.pop(0) if self.texts else None
        self.events.append(('capture',self.text));return {'job_id':str(self.job)}
    def cancel(self):self.cancelled+=1;self.phase='cancelled';return {}

class Speaker:
    def __init__(self,events):self.events=events;self.job=0;self.cancelled=0;self.spoken=[]
    def status(self):return {'phase':'done','job_id':'tts'+str(self.job),'result':{}} if self.job else {'phase':'idle'}
    def start(self,operation,**options):
        assert operation=='tts';self.job+=1;self.spoken.append(options['text']);self.events.append(('speak',options['text']))
        assert options['allow_online'] is False
        return {'job_id':'tts'+str(self.job)}
    def cancel(self):self.cancelled+=1;return {}

@pytest.fixture
def fast(monkeypatch):
    original=asyncio.sleep
    async def sleep(delay):await original(0)
    monkeypatch.setattr('nexus.handsfree.asyncio.sleep',sleep)


def build(texts,chat,approve=None,pending=None):
    events=[];store=Store();voice=Voice(texts,events);speaker=Speaker(events)
    async def unused(*args):raise AssertionError('Unexpected approval')
    return HandsFree(store,voice,speaker,chat,approve or unused,pending or (lambda:[]),lambda:False),events


def test_conversation_autosends_then_speaks_and_stops_on_voice(fast):
    calls=[]
    async def chat(text,paid):calls.append((text,paid));return {'text':'Ji, aapki baat mil gai.'}
    hf,events=build(['hello','mic band karo'],chat)
    async def run():
        await hf.start(True,True);await hf.task
    asyncio.run(run())
    assert calls==[('hello',False)] and not hf.running
    assert events[0]==('capture','hello') and events[1][0]=='speak' and events[2]==('capture','mic band karo')
    assert hf.voice.cancelled==1 and hf.tts.cancelled==1


def test_actual_pending_tool_requires_spoken_confirmation(fast):
    items=[];approved=[]
    async def chat(text,paid):
        items.append({'id':'one','name':'create_text','args':{'path':'C:/Docs/note.txt','text':'hi'}})
        return {'text':'Approval required.'}
    async def approve(ident,yes):approved.append((ident,yes));items.clear();return {'result':{'created':'note.txt'}}
    hf,events=build(['note banao','haan','haan lekin file delete mat karo','haan approve','mic band karo'],chat,approve,lambda:list(items))
    async def run():await hf.start(True,True);await hf.task
    asyncio.run(run())
    assert approved==[('one',True)]
    prompt=next(text for kind,text in events if kind=='speak' and 'Details:' in text)
    assert 'create_text' in prompt and 'C:/Docs/note.txt' in prompt
    assert any('Pehle pending' in text for text in hf.tts.spoken)

def test_whatsapp_voice_review_reads_contact_number_and_exact_message(fast):
    items=[]
    async def chat(text,paid):
        items.append({'id':'approval','name':'whatsapp_send','args':{'draft_id':'private-draft-token','recipient':'Nexus Test Contact','recipient_id':'phone:+12025550101','recipient_phone':'+12025550101','message':'Kidhar ho?'}})
        return {'text':'Approval pending.'}
    async def approve(ident,yes):items.clear();return {'result':{'sent':True,'delivery_verified':False}}
    hf,events=build(['message bhejo','haan approve','mic band karo'],chat,approve,lambda:list(items))
    async def run():await hf.start(True,True);await hf.task
    asyncio.run(run())
    prompt=next(text for kind,text in events if kind=='speak' and 'Approval chahiye' in text)
    assert 'Nexus Test Contact' in prompt and '+12025550101' in prompt and 'Kidhar ho?' in prompt and 'private-draft-token' not in prompt


def test_paid_permission_is_for_one_turn_only(fast):
    calls=[]
    async def chat(text,paid):
        calls.append((text,paid))
        if text=='first' and not paid:raise ValueError('Provider: paid request requires your approval')
        return {'text':'Answer'}
    hf,events=build(['first','yes approve','second','mic band karo'],chat)
    async def run():await hf.start(True,True);await hf.task
    asyncio.run(run())
    assert calls==[('first',False),('first',True),('second',False)]


def test_denied_paid_request_never_retries(fast):
    calls=[]
    async def chat(text,paid):calls.append(paid);raise ValueError('paid request requires your approval')
    hf,events=build(['question','nahi cancel','mic band karo'],chat)
    async def run():await hf.start(True,True);await hf.task
    asyncio.run(run());assert calls==[False]


def test_stop_cancels_owned_audio_and_resumes_no_capture(fast):
    async def chat(*args):raise AssertionError('No transcript')
    hf,events=build([],chat)
    async def run():
        await hf.start(True,True)
        for _ in range(20):await asyncio.sleep(0)
        await hf.stop()
        count=len(events)
        for _ in range(10):await asyncio.sleep(0)
        assert len(events)==count
    asyncio.run(run());assert not hf.running and hf.voice.cancelled==1 and hf.tts.cancelled==1


@pytest.mark.parametrize('consent,online',[(False,True),(True,False)])
def test_capture_and_online_consent_required(consent,online):
    async def chat(*args):raise AssertionError()
    hf,events=build([],chat)
    with pytest.raises(ValueError,match='Consent'):
        asyncio.run(hf.start(consent,online))
    assert not events


def test_tts_failure_after_request_stops_without_error_speech_loop(fast):
    async def chat(*args):return {'text':'reply'}
    hf,events=build(['hello'],chat)
    hf.tts.start=Mock(side_effect=ValueError('No speaker installed'))
    async def run():await hf.start(True,True);await hf.task
    asyncio.run(run());assert hf.phase=='error' and 'speaker' in hf.error
    assert [text for kind,text in events if kind=='capture']==['hello']
    hf.tts.start.assert_called_once()


def test_original_urdu_confirmation_and_stop_are_not_lost_to_roman_spelling(fast):
    async def chat(*args):return {'text':'ok'}
    hf,events=build([],chat)
    hf.running=True;hf.confirmation={'kind':'tool'}
    async def job(service,job):return {'text':'han mnzwr','original_text':'ہاں منظور'}
    hf._job=job
    assert asyncio.run(hf._capture())=='haan approve'
    async def stop_job(service,job):return {'text':'myk bnd krw','original_text':'مائیک بند کرو'}
    hf._job=stop_job
    assert asyncio.run(hf._capture())=='mic band karo'
    hf.running=False


def test_spoken_tool_denial_never_approves(fast):
    items=[{'id':'one','name':'move_file','args':{'source':'C:/one','destination':'C:/two'}}];approvals=[]
    async def chat(*args):return {'text':'ok'}
    async def approve(ident,yes):approvals.append((ident,yes));items.clear();return {'denied':True}
    hf,events=build(['hello','nahi cancel','mic band karo'],chat,approve,lambda:list(items))
    async def run():await hf.start(True,True);await hf.task
    asyncio.run(run());assert approvals==[('one',False)]


def test_long_approval_details_are_spoken_in_chunks_without_opening_gui(fast):
    text='approved content '*180
    items=[{'id':'long','name':'create_text','args':{'path':'C:/Docs/long.txt','text':text}}];approved=[]
    async def chat(*args):return {'text':'ok'}
    async def approve(ident,yes):approved.append((ident,yes));items.clear();return {'result':{'created':'long.txt'}}
    hf,events=build(['hello','haan approve','mic band karo'],chat,approve,lambda:list(items))
    async def run():await hf.start(True,True);await hf.task
    asyncio.run(run())
    assert approved==[('long',True)]
    assert all(len(chunk)<=1400 for chunk in hf.tts.spoken)
    all_spoken=''.join(hf.tts.spoken)
    assert text in all_spoken and 'Safety Center' not in all_spoken


@pytest.mark.parametrize('idle',[
    {'phase':'error','error':'quiet capture','error_code':'no_speech'},
    {'phase':'error','error':'No microphone signal detected. Run diagnostics.'},
    {'phase':'error','error':'No speech was recognized. Try again.'},
    {'phase':'error','error':'Google recognition failed (UnknownValueError). Offline fallback missing.'},
    {'phase':'done','result':{'text':''}},
    {'phase':'done','result':{'text':'hallucinated text','diagnostics':{'silence':True}}},
])
def test_quiet_cycles_make_no_ai_requests_or_speech_then_answer_real_request(fast,idle):
    calls=[]
    async def chat(text,paid):calls.append(text);return {'text':'Recognized request answered'}
    hf,events=build([idle]*12+['actual request','mic band karo'],chat)
    async def run():await hf.start(True,True);await hf.task
    asyncio.run(run())
    assert calls==['actual request']
    assert hf.tts.spoken==['Recognized request answered','Auto voice band kar di.']
    assert hf.failures==0


def test_capture_fault_pauses_visually_without_timer_driven_complaints(fast):
    async def chat(*args):raise AssertionError('No recognized request')
    hf,events=build([{'phase':'error','error':'Microphone could not be opened'}],chat)
    async def run():await hf.start(True,True);await hf.task
    asyncio.run(run())
    assert hf.phase=='error' and not hf.running
    assert hf.tts.spoken==[]
    assert hf.voice.cancelled==1


def test_explicit_mic_click_unmutes_and_starts_but_normal_start_respects_mute(fast):
    hf,events=build([],Mock())
    hf.store.settings['voice_muted']=True
    hf.store.set=lambda key,value:hf.store.settings.__setitem__(key,value)
    async def run():
        with pytest.raises(ValueError,match='muted'):await hf.start(True,True)
        assert hf.store.settings['voice_muted'] is True and not hf.running
        await hf.start(True,True,unmute=True)
        assert hf.store.settings['voice_muted'] is False and hf.running
        await hf.stop()
    asyncio.run(run())


@pytest.mark.parametrize('fault',['consent','online','emergency','busy'])
def test_failed_explicit_start_preserves_saved_mute(fast,fault):
    hf,events=build([],Mock());hf.store.settings['voice_muted']=True
    hf.store.set=Mock(side_effect=lambda key,value:hf.store.settings.__setitem__(key,value))
    if fault=='emergency':hf.emergency=lambda:True
    if fault=='busy':hf.voice.phase='transcribing'
    async def run():
        with pytest.raises(ValueError):await hf.start(fault!='consent',fault!='online',unmute=True)
    asyncio.run(run())
    assert hf.store.settings['voice_muted'] is True and not hf.running
    hf.store.set.assert_not_called()
