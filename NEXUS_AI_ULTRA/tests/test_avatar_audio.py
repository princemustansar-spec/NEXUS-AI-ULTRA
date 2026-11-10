import asyncio
from array import array
import json
from pathlib import Path
from types import SimpleNamespace
import threading
from unittest.mock import Mock
import pytest
from nexus.avatar_audio import PlaybackCues, SHAPE_OPENNESS, VISEME_SHAPE, envelope, sapi_observer, shape_at, viseme_pose, word_cues, word_shape, word_shapes
from nexus import tts

def test_envelope_measures_real_pcm_and_silence_with_bounded_work():
    raw=array('h',[0]*320+[12000,-12000]*160+[0]*320).tobytes()
    result=envelope(raw,16000,-16,1)
    assert result[0]==result[-1]==0 and result[1]>.9
    assert envelope(raw,16000,8,1)==[]
    assert len(envelope(array('h',[100]*700000).tobytes(),16000,-16,1))==2000

def test_cues_come_from_callbacks_and_clear_on_end(monkeypatch):
    clock=[100.0];monkeypatch.setattr('nexus.avatar_audio.time.monotonic',lambda:clock[0]);messages=[];bridge=PlaybackCues(messages.append)
    bridge.begin('word-boundary');clock[0]+=.2;bridge.word('hello',5)
    assert messages[-1]['animation']['cues'][0][0]==200
    bridge.viseme(7,120);assert messages[-1]['animation']['pose']==2 and bridge.mode=='viseme'
    count=len(messages);bridge.word('ignored',7);assert len(messages)==count
    bridge.end();assert not messages[-1]['animation']['playing'] and messages[-1]['animation']['pose']==0
    assert 'hello' not in json.dumps(messages)
    assert viseme_pose(0)==0 and viseme_pose(21)==5 and SHAPE_OPENNESS[5]==0

def test_pygame_timing_starts_after_play_and_tracks_actual_position(monkeypatch):
    import sys
    messages=[];order=[];positions=iter([40,90]);busy=iter([True,True,False]);raw=array('h',[10000,-10000]*8000).tobytes()
    music=SimpleNamespace(load=Mock(),play=lambda:order.append('play'),get_busy=lambda:next(busy),get_pos=lambda:next(positions),stop=Mock(),unload=Mock())
    mixer=SimpleNamespace(init=Mock(),quit=Mock(),music=music,get_init=lambda:(16000,-16,1),Sound=lambda **_:SimpleNamespace(get_raw=lambda:raw))
    monkeypatch.setitem(sys.modules,'pygame',SimpleNamespace(mixer=mixer))
    def send(packet):order.append('active' if packet['animation']['playing'] else 'closed');messages.append(packet)
    tts.play(b'fixture-audio',threading.Event(),PlaybackCues(send),[(0,500,2)])
    active=[m['animation'] for m in messages if m['animation']['playing']]
    assert order.index('play')<order.index('active')
    assert [p['position_ms'] for p in active[1:]]==[40,90]
    assert all(p['cues'][0][2]==2 for p in active[1:])
    assert not messages[-1]['animation']['playing'];music.stop.assert_called_once();mixer.quit.assert_called_once()

def test_optional_decode_failure_keeps_existing_audio_playback(monkeypatch):
    import sys
    music=SimpleNamespace(load=Mock(),play=Mock(),get_busy=lambda:False,stop=Mock(),unload=Mock())
    mixer=SimpleNamespace(init=Mock(),quit=Mock(),music=music,Sound=Mock(side_effect=ValueError('unsupported audio analysis')))
    monkeypatch.setitem(sys.modules,'pygame',SimpleNamespace(mixer=mixer));messages=[]
    tts.play(b'fixture-audio',threading.Event(),PlaybackCues(messages.append))
    music.play.assert_called_once();assert messages[0]['animation']['mode']=='unavailable'

def test_edge_preparation_is_not_playback(monkeypatch):
    messages=[];stages=[]
    async def audio(text,with_timing=False):
        assert with_timing and not any(m.get('animation',{}).get('playing') for m in messages)
        stages.append('download');return b'audio',[(0,100,1)]
    def play(data,stop,animation,words):
        assert stages==['download'];animation.begin('audio-envelope');animation.end()
    monkeypatch.setattr(tts,'edge_audio',audio);monkeypatch.setattr(tts,'play',play)
    result=tts.speak_reply('fixture',True,threading.Event(),messages.append,avatar_sync=True)
    assert messages[0]['phase']=='preparing' and result['provider']=='edge'
    assert any(m.get('animation',{}).get('playing') for m in messages)

def test_additional_sapi_sink_preserves_word_callbacks(monkeypatch):
    import sys
    handlers={};native=SimpleNamespace(EventInterests=32);engine=SimpleNamespace(connect=lambda event,callback:handlers.update({event:callback}),proxy=SimpleNamespace(_driver=SimpleNamespace(_tts=native)))
    sinks=[];connection=SimpleNamespace(disconnect=Mock())
    monkeypatch.setitem(sys.modules,'comtypes.client',SimpleNamespace(GetEvents=lambda source,sink:(sinks.append(sink) or connection)))
    monkeypatch.setitem(sys.modules,'comtypes.gen',SimpleNamespace(SpeechLib=SimpleNamespace(SVEViseme=256)))
    messages=[];bridge=PlaybackCues(messages.append)
    assert sapi_observer(engine,bridge,'Hello') is connection
    handlers['started-word'](name='fixture',location=1,length=0);assert not messages
    sinks[0]._ISpeechVoiceEvents_StartStream(1,0)
    handlers['started-word'](name='fixture',location=0,length=5)
    sinks[0]._ISpeechVoiceEvents_Viseme(1,0,100,0,0,7)
    assert bridge.mode=='viseme' and native.EventInterests==288
    handlers['finished-utterance'](name='fixture',completed=True);assert not messages[-1]['animation']['playing']

def test_terminal_voice_state_discards_old_cues(tmp_path):
    from nexus.voice import VoiceService
    service=VoiceService(tmp_path);service.state=dict(phase='done',job_id='old',animation=dict(playing=True,pose=3,cues=[[0,1,3],[1000,0,0]]))
    assert not service.animation_status()['animation']['playing']
    service.cancel();assert service.animation_status()['animation']['pose']==0

FIXTURE=json.loads((Path(__file__).parent/'fixtures'/'viseme_words.json').read_text())

def test_word_shapes_match_the_browser_tables_in_the_shared_fixture():
    for word,expected in FIXTURE['words'].items():assert list(word_shapes(word))==expected,word
    c=FIXTURE['cues'];assert word_cues(c['position'],c['duration'],word_shapes(c['word']))==c['expected']
    assert {str(k):v for k,v in VISEME_SHAPE.items()}==FIXTURE['visemes']
    assert len(word_shapes('a'*5+'bcdefghijklmnop'))<=12 and word_shapes('')==(1,) and word_shapes('123')==(1,)

def test_every_sapi_viseme_maps_to_a_known_shape_and_unknown_numbers_stay_safe():
    assert set(range(22))==set(VISEME_SHAPE) and set(VISEME_SHAPE.values())<=set(SHAPE_OPENNESS)
    assert viseme_pose(99)==1 and viseme_pose(18)==6 and viseme_pose(21)==5

def test_a_word_moves_through_several_mouth_shapes_and_closes_at_its_end(monkeypatch):
    clock=[50.0];monkeypatch.setattr('nexus.avatar_audio.time.monotonic',lambda:clock[0]);messages=[];bridge=PlaybackCues(messages.append)
    bridge.begin('word-boundary');clock[0]+=.1;bridge.word('hello',5)
    cues=messages[-1]['animation']['cues']
    assert [c[2] for c in cues]==[8,4,1,2,0] and cues[0][0]==100 and cues[-1][1]==0
    assert all(a[0]<b[0] for a,b in zip(cues,cues[1:])) and messages[-1]['animation']['pose']==8
    bridge.viseme(21,80)  # a real viseme stream takes over; pressed lips are closed
    clock[0]+=.2;bridge.word('ignored',7);assert messages[-1]['animation']['pose']==5 and messages[-1]['animation']['openness']==0

def test_word_timeline_accepts_old_single_pose_entries_and_shape_lists():
    assert shape_at((0,100,2),50)==2 and shape_at((0,100,2),100) is None
    shapes=(8,4,1,2);seen=[shape_at((0,300,shapes),at) for at in range(0,300,10)]
    assert seen[0]==8 and seen[-1]==2 and set(seen)==set(shapes) and seen==sorted(seen,key=shapes.index)
    assert word_shape([(0,100,(3,)),(100,100,2)],150)==2 and word_shape([(0,100,3)],500)==1 and shape_at((0,100,()),10)==1

def test_edge_word_boundaries_become_shape_sequences(monkeypatch):
    import sys
    class Fake:
        def __init__(self,*a,**k):pass
        async def stream(self):
            yield dict(type='audio',data=b'x');yield dict(type='WordBoundary',offset=1_000_000,duration=2_000_000,text='Hello')
    monkeypatch.setitem(sys.modules,'edge_tts',SimpleNamespace(Communicate=Fake))
    data,words=asyncio.run(tts.edge_audio('Hello',with_timing=True))
    assert data==b'x' and words==[(100,200,(8,4,1,2))]
