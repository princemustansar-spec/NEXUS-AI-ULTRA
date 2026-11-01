import threading
from types import SimpleNamespace
from unittest.mock import Mock
import numpy as np
import pytest
import nexus.voice as voice
from test_jarvis_voice import SpeechInput


def test_a_single_click_does_not_count_as_sustained_speech():
    class ClickInput(SpeechInput):
        def read(self,n):
            self.count+=1
            return np.full((n,1),.1 if self.count==12 else .0001,dtype=np.float32),False
    with pytest.raises(voice.NoSpeechError,match='No speech detected'):
        voice.record_audio(ClickInput(),None,8,threading.Event(),Mock(),.8,2)


def test_google_unintelligible_clip_is_idle_not_network_failure(monkeypatch):
    import speech_recognition as sr
    from nexus.voice_online import google_transcribe
    monkeypatch.setattr(sr.Recognizer,'recognize_google',Mock(side_effect=sr.UnknownValueError()))
    with pytest.raises(voice.NoSpeechError):google_transcribe(np.zeros(16000),16000,'ur-PK',True,Mock())


def test_worker_labels_silent_audio_without_calling_recognizers(tmp_path,monkeypatch):
    import sys
    import nexus.voice_online as online
    monkeypatch.setitem(sys.modules,'sounddevice',SimpleNamespace())
    monkeypatch.setattr(voice,'record_audio',lambda *a,**k:(np.zeros(16000),16000,{'silence':True}))
    google=Mock();offline=Mock()
    monkeypatch.setattr(online,'google_transcribe',google);monkeypatch.setattr(voice,'transcribe_audio',offline)
    pipe=Mock()
    voice.voice_worker(pipe,threading.Event(),'capture',{'engine':'google','device':None,'language':'ur','seconds':8},str(tmp_path))
    assert pipe.send.call_args.args[0]['error_code']=='no_speech'
    google.assert_not_called();offline.assert_not_called()
