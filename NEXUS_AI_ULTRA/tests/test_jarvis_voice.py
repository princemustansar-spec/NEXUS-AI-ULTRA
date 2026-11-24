import json
import threading
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock
import numpy as np
import pytest
import nexus.voice as v
from nexus import tts


def test_google_en_in_https_and_roman_conversion(monkeypatch):
    import speech_recognition as sr
    call={}
    def recognize(self,audio,**kwargs):
        call.update(kwargs);assert self.operation_timeout==6 and audio.sample_rate==16000
        return 'میرا نام علی ہے'
    monkeypatch.setattr(sr.Recognizer,'recognize_google',recognize)
    from nexus.voice_online import google_transcribe
    result=google_transcribe(np.full(16000,.1),16000,'en-IN',True,Mock())
    assert call['language']=='en-IN' and call['endpoint'].startswith('https://')
    assert result['romanized'] and not result['offline']


class SpeechInput:
    def __init__(self,speech=True):self.count=0;self.speech=speech
    def query_devices(self,*a):return {'default_samplerate':16000,'max_input_channels':1}
    def check_input_settings(self,**k):pass
    def InputStream(self,**k):return self
    def __enter__(self):return self
    def __exit__(self,*a):pass
    def read(self,n):
        self.count+=1
        # Half-second calibration, then speech, then trailing silence.
        level=.1 if self.speech and 10<=self.count<=20 else .0001
        return np.full((n,1),level,dtype=np.float32),False


def test_speech_detection_finishes_before_maximum():
    send=Mock();audio,rate,metrics=v.record_audio(SpeechInput(),None,8,threading.Event(),send,.4,5)
    assert .5<metrics['seconds']<3
    assert any(c.args[0]['phase']=='listening' for c in send.call_args_list)


def test_no_speech_timeout():
    with pytest.raises(ValueError,match='No speech detected'):
        v.record_audio(SpeechInput(False),None,8,threading.Event(),Mock(),.8,2)


def test_google_failure_falls_back_to_same_captured_audio(tmp_path,monkeypatch):
    import sys
    import nexus.voice_online as online
    monkeypatch.setitem(sys.modules,'sounddevice',SimpleNamespace())
    monkeypatch.setattr(v,'model_manifest',lambda *a,**k:True)
    pcm=np.full(16000,.1)
    monkeypatch.setattr(v,'record_audio',lambda *a,**k:(pcm,16000,{'silence':False}))
    monkeypatch.setattr(online,'google_transcribe',Mock(side_effect=RuntimeError('network')))
    offline=Mock(return_value={'text':'fallback fixture','offline':True});monkeypatch.setattr(v,'transcribe_audio',offline)
    pipe=Mock();v.voice_worker(pipe,threading.Event(),'capture',{'engine':'google','device':None,'language':'ur','seconds':8},str(tmp_path))
    assert offline.call_args.args[0] is pcm
    assert pipe.send.call_args.args[0]['result']['fallback_reason']=='RuntimeError'


def test_google_success_does_not_require_or_load_whisper(tmp_path,monkeypatch):
    import sys
    import nexus.voice_online as online
    monkeypatch.setitem(sys.modules,'sounddevice',SimpleNamespace())
    monkeypatch.setattr(v,'model_manifest',Mock(side_effect=AssertionError('should not inspect offline model')))
    monkeypatch.setattr(v,'record_audio',lambda *a,**k:(np.full(16000,.1),16000,{'silence':False}))
    monkeypatch.setattr(online,'google_transcribe',lambda *a,**k:{'text':'Google fixture','offline':False})
    offline=Mock();monkeypatch.setattr(v,'transcribe_audio',offline)
    pipe=Mock();v.voice_worker(pipe,threading.Event(),'capture',{'engine':'google','device':None,'language':'ur','seconds':8},str(tmp_path))
    assert pipe.send.call_args.args[0]['phase']=='done';offline.assert_not_called()


def test_offline_model_reused_between_calls(tmp_path,monkeypatch):
    import sys
    v._WHISPER_CACHE.clear()
    factory=Mock(return_value=SimpleNamespace(transcribe=lambda *a,**k:([SimpleNamespace(text='fixture')],SimpleNamespace(language='en'))))
    monkeypatch.setitem(sys.modules,'faster_whisper',SimpleNamespace(WhisperModel=factory))
    for _ in range(2):v.transcribe_audio(np.zeros(16000,dtype=np.float32),16000,tmp_path,'en',Mock())
    assert factory.call_count==1
    v._WHISPER_CACHE.clear()


def test_edge_voice_and_windows_fallback(monkeypatch):
    async def fail(text):raise RuntimeError('offline')
    monkeypatch.setattr(tts,'edge_audio',fail)
    windows=Mock();monkeypatch.setattr(tts,'windows_speak',windows)
    result=tts.speak_reply('Hello boss',True,threading.Event(),Mock())
    assert result['provider']=='windows' and tts.EDGE_VOICE=='en-IN-PrabhatNeural'
    windows.assert_called_once()


def test_no_online_tts_without_opt_in(monkeypatch):
    edge=Mock();monkeypatch.setattr(tts,'edge_audio',edge)
    monkeypatch.setattr(tts,'windows_speak',Mock())
    tts.speak_reply('Hello',False,threading.Event(),Mock());edge.assert_not_called()


def test_cancelled_tts_does_not_speak(monkeypatch):
    stop=threading.Event();stop.set();windows=Mock();monkeypatch.setattr(tts,'windows_speak',windows)
    assert tts.speak_reply('Hello',True,stop,Mock())['cancelled'];windows.assert_not_called()


def test_recent_capture_worker_is_reused(tmp_path):
    import time
    service=v.VoiceService(tmp_path,context=Mock())
    service.process=Mock();service.process.is_alive.return_value=True
    service.commands=Mock();service.stop_event=threading.Event()
    service.state={'phase':'done','operation':'capture','job_id':'old'};service.started=time.monotonic()
    result=service.start('capture',engine='google',seconds=8)
    assert result['job_id']!='old'
    service.commands.send.assert_called_once()
    service.context.Process.assert_not_called()
    service.process=None;service.commands=None


def test_forbidden_voice_is_rejected(tmp_path):
    for name in ['ur-PK-AsadNeural','Microsoft Uzma']:
        with pytest.raises(ValueError,match='other than Asad/Uzma'):
            v.VoiceService(tmp_path).start('tts',text='Hello',preferred_voice=name)


def test_online_consent_and_mute_gate_recording_not_text_chat(tmp_path,monkeypatch,configured_hermes):
    import importlib
    from fastapi.testclient import TestClient
    import nexus.app
    monkeypatch.setenv('NEXUS_DATA_DIR',str(tmp_path));m=importlib.reload(nexus.app)
    start=Mock(return_value={'job_id':'fixture','phase':'starting'});monkeypatch.setattr(m.voice,'start',start)
    with TestClient(m.app) as client:
        client.headers['x-nexus-token']=client.get('/api/state').json()['token']
        assert client.post('/api/voice/start',json={'consent':True,'engine':'google'}).status_code==400
        start.assert_not_called()
        assert client.post('/api/voice/start',json={'consent':True,'engine':'google','online_consent':True}).status_code==200
        assert start.call_args.kwargs['locale']=='en-IN'
        assert client.post('/api/voice/mute',json={'muted':True}).status_code==200
        assert client.post('/api/voice/start',json={'consent':True}).status_code==400
        assert client.post('/api/voice/test',json={'consent':True}).status_code==400
        assert client.post('/api/tts/speak',json={'text':'hello'}).status_code==400
        # Existing text chat remains callable; its missing-provider error is not mute-related.
        reply=client.post('/api/chat',json={'text':'Hello'})
        assert reply.status_code==400 and 'provider' in reply.json()['detail'].lower()
