"""Small playback cues. Optional observers must never interrupt voice output."""
from array import array
import math
import re
import time

def word_pose(word):
    word = re.sub('[^a-z]', '', str(word).lower())
    return 2 if re.search('[ou]', word) else 3 if re.search('[a]', word) else 1

def viseme_pose(value):
    value = int(value)
    if value in (0, 21): return 0
    if value in (3, 7, 8, 10): return 2
    if value in (1, 2, 9, 11, 12, 20): return 3
    return 1

def envelope(raw, rate, sample_format, channels, step_ms=20):
    """Downsample only amplitude analysis, not playback. Bounded to one TTS chunk."""
    if sample_format != -16 or rate <= 0 or channels not in (1, 2): return []
    samples = array('h'); samples.frombytes(raw[:len(raw)//2*2])
    block = max(1, int(rate * channels * step_ms / 1000)); levels = []
    for start in range(0, min(len(samples), rate*channels*40), block):
        values = samples[start:start+block:8]
        levels.append(math.sqrt(sum(v*v for v in values)/max(1,len(values)))/32768)
    peak = sorted(levels)[int(len(levels)*.90)] if levels else 0
    scale = max(.025, peak)
    return [0.0 if v < .004 else round(min(1.0, math.sqrt(v/scale)), 3) for v in levels]

class PlaybackCues:
    def __init__(self, send):
        self.send = send; self.serial = 0; self.segment = 0; self.started = 0; self.mode = 'unavailable'; self.active = False

    def emit(self, **value):
        self.serial += 1
        packet = dict(serial=self.serial, segment=self.segment, playing=self.active,
                      mode=self.mode, position_ms=max(0,int((time.monotonic()-self.started)*1000)) if self.started else 0,
                      emitted_at=time.monotonic(), openness=0, pose=0, cues=[])
        packet.update(value)
        try: self.send({'phase':'speaking' if self.active else 'preparing', 'animation':packet})
        except (OSError, EOFError, ValueError): pass

    def begin(self, mode):
        self.segment += 1; self.started = time.monotonic(); self.mode = mode; self.active = True; self.emit()

    def end(self):
        self.active = False; self.emit()

    def word(self, text, length):
        if not self.active or self.mode == 'viseme': return
        position = max(0,int((time.monotonic()-self.started)*1000)); duration = max(70,min(350,int(length)*45))
        pose = word_pose(text)
        self.emit(pose=pose,openness=.65,cues=[[position,.65,pose],[position+duration,0,0]])

    def viseme(self, value, duration):
        if not self.active: return
        self.mode = 'viseme'; position = max(0,int((time.monotonic()-self.started)*1000)); pose = viseme_pose(value)
        self.emit(pose=pose,openness=0 if not pose else .8,
                  cues=[[position,0 if not pose else .8,pose],[position+max(30,min(500,int(duration))),0,0]])

def sapi_observer(engine, bridge, text):
    """Keep pyttsx3's own event sink intact; attach a second optional SAPI sink."""
    connection = None
    def start(*_): bridge.begin('word-boundary')
    def word(_name, location, length): bridge.word(text[int(location):int(location)+int(length)], length)
    def end(*_): bridge.end()
    try:
        for event, callback in [('started-utterance',start),('started-word',word),('finished-utterance',end),('error',end)]:
            engine.connect(event,callback)
    except (AttributeError,TypeError,RuntimeError):
        return None
    try:
        from comtypes.client import GetEvents
        from comtypes.gen import SpeechLib
        native = engine.proxy._driver._tts
        class Sink:
            def _ISpeechVoiceEvents_Viseme(self, _stream, _position, duration, _next, _feature, current):
                bridge.viseme(current,duration)
        native.EventInterests |= SpeechLib.SVEViseme
        connection = GetEvents(native, Sink())
    except Exception:
        # Some installed voices expose word callbacks only. Quality is reported.
        pass
    return connection
