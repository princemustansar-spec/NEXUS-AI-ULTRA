"""Small playback cues. Optional observers must never interrupt voice output."""
from array import array
import math
import re
import time

# Mouth shape ids. static/human_client.js mirrors these tables; tests/fixtures/viseme_words.json
# keeps both sides identical. 0 = lips resting. The three original packs only draw 1-3;
# the renderer maps the other shapes to the nearest frame the pack really has.
#   1 parted (t d n s l th)   2 round (o u w)       3 wide open (a)    4 wide smile (e i)
#   5 lips pressed (m b p)    6 teeth on lip (f v)  7 pursed (sh ch r) 8 mid open (uh h k g)
SHAPE_OPENNESS = {0: 0, 1: .35, 2: .6, 3: .9, 4: .5, 5: 0, 6: .3, 7: .45, 8: .65}
LONG_SHAPES = (2, 3, 4, 8)  # vowel-like shapes stay on screen longer inside a word
LETTER_SHAPE = dict(a=3, e=4, i=4, o=2, u=2, y=4, w=2, m=5, b=5, p=5, f=6, v=6, r=7, j=7,
                    h=8, k=8, g=8, q=8, c=1, s=1, z=1, t=1, d=1, n=1, l=1, x=1)
PAIR_SHAPE = dict(sh=7, ch=7, th=1, ph=6, oo=2, ou=2, ow=2, ee=4, ea=4, ie=4, ai=3, ay=3)
# SAPI viseme number -> shape (0 silence, 21 = p b m)
VISEME_SHAPE = {0: 0, 1: 8, 2: 3, 3: 2, 4: 4, 5: 7, 6: 4, 7: 2, 8: 2, 9: 3, 10: 2, 11: 3, 12: 8,
                13: 7, 14: 1, 15: 1, 16: 7, 17: 1, 18: 6, 19: 1, 20: 8, 21: 5}

def word_pose(word):
    word = re.sub('[^a-z]', '', str(word).lower())
    return 2 if re.search('[ou]', word) else 3 if re.search('[a]', word) else 1

def word_shapes(word, limit=12):
    """Rough letter-to-mouth sequence for one spoken word (English / Roman Urdu spelling)."""
    text = re.sub('[^a-z]', '', str(word).lower()); shapes = []; i = 0
    while i < len(text) and len(shapes) < limit:
        shape = PAIR_SHAPE.get(text[i:i+2]); step = 2
        if shape is None: shape = LETTER_SHAPE.get(text[i], 1); step = 1
        if not shapes or shapes[-1] != shape: shapes.append(shape)
        i += step
    return tuple(shapes) or (1,)

def word_cues(position, duration, shapes):
    """Spread a word's shapes over its duration; vowels get a longer share."""
    weights = [1.5 if s in LONG_SHAPES else 1.0 for s in shapes]; total = sum(weights); at = float(position); cues = []
    for shape, weight in zip(shapes, weights):
        cues.append([int(round(at)), SHAPE_OPENNESS[shape], shape]); at += duration * weight / total
    cues.append([int(round(position + duration)), 0, 0])
    return cues

def shape_at(entry, at):
    """entry = (start_ms, duration_ms, shape | [shapes]); returns the shape playing at `at`, else None."""
    start, duration, value = entry
    if not start <= at < start + duration: return None
    if isinstance(value, int): return value
    shapes = tuple(value)
    if len(shapes) < 2: return shapes[0] if shapes else 1
    weights = [1.5 if s in LONG_SHAPES else 1.0 for s in shapes]; point = (at - start) / max(1, duration) * sum(weights); total = 0
    for shape, weight in zip(shapes, weights):
        total += weight
        if point < total: return shape
    return shapes[-1]

def word_shape(words, at, default=1):
    for entry in words:
        shape = shape_at(entry, at)
        if shape is not None: return shape
    return default

def viseme_pose(value):
    return VISEME_SHAPE.get(int(value), 1)

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
        position = max(0,int((time.monotonic()-self.started)*1000)); duration = max(70,min(420,int(length)*45))
        cues = word_cues(position, duration, word_shapes(text))
        self.emit(pose=cues[0][2],openness=cues[0][1],cues=cues)

    def viseme(self, value, duration):
        if not self.active: return
        self.mode = 'viseme'; position = max(0,int((time.monotonic()-self.started)*1000)); pose = viseme_pose(value)
        openness = SHAPE_OPENNESS[pose]
        self.emit(pose=pose,openness=openness,
                  cues=[[position,openness,pose],[position+max(30,min(500,int(duration))),0,0]])

def sapi_observer(engine, bridge, text):
    """Keep pyttsx3's own event sink intact; attach a second optional SAPI sink."""
    connection = None
    def word(name=None, location=0, length=0, **_):
        if int(length)<=0:return
        if not bridge.active:bridge.begin('word-boundary')
        bridge.word(text[int(location):int(location)+int(length)], length)
    def end(*_, **__): bridge.end()
    try:
        for event, callback in [('started-word',word),('finished-utterance',end),('error',end)]:
            engine.connect(event,callback)
    except (AttributeError,TypeError,RuntimeError):
        return None
    try:
        from comtypes.client import GetEvents
        from comtypes.gen import SpeechLib
        native = engine.proxy._driver._tts
        class Sink:
            def _ISpeechVoiceEvents_StartStream(self, *_args):
                bridge.begin('word-boundary')
            def _ISpeechVoiceEvents_Viseme(self, *args):
                if len(args)<6:return
                duration,current=args[-4],args[-1]
                if not bridge.active:bridge.begin('viseme')
                bridge.viseme(current,duration)
            def _ISpeechVoiceEvents_EndStream(self, *_args):
                bridge.end()
        native.EventInterests |= SpeechLib.SVEViseme
        connection = GetEvents(native, Sink())
    except Exception:
        # Some installed voices expose word callbacks only. Quality is reported.
        pass
    return connection
