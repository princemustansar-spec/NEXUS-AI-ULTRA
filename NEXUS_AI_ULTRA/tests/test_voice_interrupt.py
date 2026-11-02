import asyncio
import sys
import threading
from types import SimpleNamespace
from unittest.mock import Mock
import numpy as np
import pytest
from test_handsfree import build,fast
from nexus.handsfree import QuietSpeechGate


def setup_hf(mode):
    hf,_=build([],Mock());hf.running=True;hf.options={'interrupt_mode':mode,'allow_online_tts':False}
    hf.interrupt_event=asyncio.Event();cancelled=threading.Event()
    hf.tts.cancel=Mock(side_effect=lambda:cancelled.set())
    async def playing(*a,**k):await asyncio.Future()
    hf._job=playing
    return hf,cancelled


def test_any_speech_stops_audio_before_transcription_and_preserves_complete_new_request(fast):
    async def run():
        hf,cancelled=setup_hf('any');finish=asyncio.Event()
        async def capture(**kwargs):
            assert kwargs['interruption']
            hf.level_event.set()  # Measured quiet-to-speech onset, transcript not ready yet.
            await finish.wait()
            return 'please check my laptop RAM and tell me the result'
        hf._capture=capture
        task=asyncio.create_task(hf._say('An old long reply'))
        assert await asyncio.to_thread(cancelled.wait,2)
        assert not task.done() and hf.phase=='listening'
        finish.set();await asyncio.wait_for(task,2)
        assert hf.queued_text=='please check my laptop RAM and tell me the result'
        assert hf.running and hf.error is None
    asyncio.run(run())


def test_recognized_new_speech_interrupts_without_a_wake_word_and_echo_is_ignored(fast):
    async def run():
        hf,cancelled=setup_hf('any');texts=iter(['this is the original reply','new question about my battery'])
        async def capture(**kwargs):return next(texts)
        hf._capture=capture
        await asyncio.wait_for(hf._say('this is the original reply'),2)
        assert cancelled.is_set() and hf.queued_text=='new question about my battery'
    asyncio.run(run())


def test_optional_wake_mode_ignores_plain_speech_and_keeps_followup(fast):
    async def run():
        hf,cancelled=setup_hf('wake');texts=iter(['background speech','Nexus ruko ab battery check karo'])
        async def capture(**kwargs):return next(texts)
        hf._capture=capture
        await asyncio.wait_for(hf._say('Old reply'),2)
        assert cancelled.is_set() and hf.queued_text=='ab battery check karo'
    asyncio.run(run())


def test_stop_and_listen_button_keeps_auto_voice_running_without_extra_capture_when_off(fast):
    async def run():
        hf,cancelled=setup_hf('off');hf._capture=Mock(side_effect=AssertionError('No continuous interruption capture in Off mode'))
        task=asyncio.create_task(hf._say('old reply'))
        while hf.phase!='speaking':await asyncio.sleep(0)
        assert (await hf.interrupt())['interrupted']
        await asyncio.wait_for(task,2)
        assert cancelled.is_set() and hf.running and hf.queued_text==''
    asyncio.run(run())


def test_quiet_onset_gate_requires_baseline_and_sustained_new_speech():
    gate=QuietSpeechGate()
    def sample(second,level):return gate.observe({'job_id':'clip','phase':'listening','seconds':second,'level_dbfs':level})
    for i in range(4):assert not sample(i*.25,-60)
    assert not sample(1,-20)
    assert not sample(1,-20),'A repeated status poll cannot count as a second loud sample'
    assert sample(1.25,-20)
    speaker=QuietSpeechGate()
    for i in range(8):assert not speaker.observe({'job_id':'speaker','phase':'listening','seconds':i*.25,'level_dbfs':-25})


def test_roman_urdu_converter_is_loaded_once_per_worker(monkeypatch):
    import nexus.voice as voice
    converter=SimpleNamespace(romanize_string=Mock(return_value='mera naam'))
    factory=Mock(return_value=converter)
    monkeypatch.setattr(voice,'_ROMANIZER',None)
    monkeypatch.setitem(sys.modules,'uroman',SimpleNamespace(Uroman=factory))
    assert voice.romanize('میرا نام')=='mera naam'
    assert voice.romanize('میرا نام')=='mera naam'
    factory.assert_called_once()


def test_stopped_interruption_probe_discards_audio_without_recognition(tmp_path,monkeypatch):
    import nexus.voice as voice
    import nexus.voice_online as online
    stop=threading.Event()
    def recorded(*args):stop.set();return np.ones(16000),16000,{'silence':False}
    monkeypatch.setitem(sys.modules,'sounddevice',SimpleNamespace())
    monkeypatch.setattr(voice,'record_audio',recorded)
    recognize=Mock(side_effect=AssertionError('Discarded probe must not upload or transcribe audio'))
    monkeypatch.setattr(online,'google_transcribe',recognize)
    pipe=Mock()
    voice.voice_worker(pipe,stop,'capture',{'device':None,'seconds':8,'engine':'google','language':'ur','discard_on_stop':True},str(tmp_path))
    assert pipe.send.call_args.args[0]['result']['no_speech']
    recognize.assert_not_called()


def test_interrupt_api_requires_session_and_does_not_disable_auto_voice(tmp_path,monkeypatch):
    import importlib
    from unittest.mock import AsyncMock
    from fastapi.testclient import TestClient
    monkeypatch.setenv('NEXUS_DATA_DIR',str(tmp_path))
    import nexus.app
    app=importlib.reload(nexus.app)
    interrupt=AsyncMock(return_value={'interrupted':True});stop=AsyncMock()
    monkeypatch.setattr(app.handsfree,'interrupt',interrupt);monkeypatch.setattr(app.handsfree,'stop',stop)
    with TestClient(app.app) as c:
        assert c.post('/api/handsfree/interrupt',json={}).status_code==403;interrupt.assert_not_called()
        c.headers['x-nexus-token']=app.session_token
        assert c.post('/api/handsfree/interrupt',json={}).json()['interrupted']
        interrupt.assert_awaited_once();stop.assert_not_called()
        assert c.post('/api/settings',json={'handsfree_interrupt_mode':'wake'}).status_code==200
        assert app.store.get('handsfree_interrupt_mode')=='wake'
    app.store.db.close()


def test_original_urdu_wake_phrase_is_retained_when_roman_spelling_differs():
    from unittest.mock import AsyncMock
    hf,_=build([],Mock());hf.running=True
    hf._job=AsyncMock(return_value={'original_text':'نیکسس رکو نئی بات','text':'nks rwkw ny bat'})
    assert asyncio.run(hf._capture(interruption=True))=='nexus ruko نئی بات'
