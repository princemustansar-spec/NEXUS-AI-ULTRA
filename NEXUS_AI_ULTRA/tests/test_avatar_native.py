"""Real local audio/COM checks; no network, account, microphone or physical speaker."""
import sys
import threading
import time
import pytest

def test_real_pygame_decode_and_playback_clock(monkeypatch):
    monkeypatch.setenv('SDL_AUDIODRIVER','dummy')
    pytest.importorskip('pygame')
    from nexus.tts import play
    from nexus.avatar_audio import PlaybackCues
    import base64
    from pathlib import Path
    audio=base64.b64decode((Path(__file__).parent/'fixtures/avatar-tone.mp3.b64').read_text())
    messages=[];play(audio,threading.Event(),PlaybackCues(messages.append))
    active=[p['animation'] for p in messages if p['animation']['playing']]
    assert any(p['cues'] and p['openness']>.1 and p['position_ms']>=0 for p in active)
    assert not messages[-1]['animation']['playing']

@pytest.mark.skipif(sys.platform!='win32',reason='Native Windows SAPI/COM requires Windows.')
def test_real_sapi_visemes_with_file_output(tmp_path):
    import pyttsx3
    from comtypes import COMError
    from comtypes.client import CreateObject
    from nexus.avatar_audio import PlaybackCues,sapi_observer
    engine=pyttsx3.init('sapi5');native=engine.proxy._driver._tts
    allowed=[v for v in engine.getProperty('voices') if not any(s in (v.name+' '+v.id).lower() for s in ('asad','uzma'))]
    if not allowed:pytest.skip('No allowed Windows SAPI voice installed.')
    engine.setProperty('voice',allowed[0].id)
    destination=tmp_path/'synthetic-sapi.wav';stream=CreateObject('SAPI.SpFileStream');stream.Open(str(destination),3,False)
    previous=None
    try:previous=native.AudioOutputStream
    except COMError:pass  # Hosted Windows runners may have no physical audio endpoint.
    messages=[];bridge=PlaybackCues(messages.append);connection=sapi_observer(engine,bridge,'Hello Nexus. One two three.')
    try:
        native.AudioOutputStream=stream
        engine.say('Hello Nexus. One two three.');engine.startLoop(False);deadline=time.monotonic()+15
        while engine.isBusy() and time.monotonic()<deadline:engine.iterate();time.sleep(.01)
        assert not engine.isBusy(),'Native SAPI synthesis did not complete.'
    finally:
        engine.stop()
        try:engine.endLoop()
        except RuntimeError:pass
        if previous is not None:native.AudioOutputStream=previous
        stream.Close()
        if connection:connection.disconnect()
    assert destination.stat().st_size>44
    assert connection is not None,'Pinned pyttsx3 SAPI event adapter could not attach.'
    assert any(m['animation']['mode']=='viseme' and m['animation']['pose'] for m in messages),'SAPI did not deliver visemes.'
