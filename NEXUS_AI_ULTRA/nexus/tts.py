"""Reply speech through FreeLLMAPI, Edge, or Windows SAPI."""
import asyncio
import io
import json
import os
import re
import time
from email.utils import parsedate_to_datetime
from urllib.error import HTTPError
from urllib.request import Request, urlopen

EDGE_VOICE = 'en-IN-PrabhatNeural'


def chunks(text):
    words = re.sub(r'\s+', ' ', re.sub(r'\*+', '', text)).strip().split()
    current = []
    for word in words:
        if current and len(' '.join(current+[word])) > 280:
            yield ' '.join(current)
            current=[]
        current.append(word)
    if current:
        yield ' '.join(current)


async def edge_audio(text, with_timing=False):
    import edge_tts
    data=bytearray(); words=[]
    async def collect():
        async for packet in edge_tts.Communicate(text, EDGE_VOICE, rate='-5%', **({'boundary':'WordBoundary'} if with_timing else {})).stream():
            if packet['type']=='audio':
                data.extend(packet['data'])
            elif with_timing and packet['type']=='WordBoundary' and len(words)<300:
                from .avatar_audio import word_shapes
                words.append((int(packet['offset']/10000),int(packet['duration']/10000),word_shapes(packet.get('text',''))))
    await asyncio.wait_for(collect(),timeout=12)
    if not data:
        raise ValueError('Edge returned no audio')
    return (bytes(data),words) if with_timing else bytes(data)


def play(data, stop, animation=None, words=()):
    import pygame
    pygame.mixer.init()
    try:
        levels=[]
        if animation:
            try:
                from .avatar_audio import envelope, word_shape
                sound=pygame.mixer.Sound(file=io.BytesIO(data))
                rate,fmt,channels=pygame.mixer.get_init()
                levels=envelope(sound.get_raw(),rate,fmt,channels)
                del sound
            except Exception:
                pass
        namehint = 'wav' if data[:4] == b'RIFF' and data[8:12] == b'WAVE' else 'mp3'
        pygame.mixer.music.load(io.BytesIO(data), namehint=namehint)
        pygame.mixer.music.play()
        if animation:animation.begin('audio-envelope' if levels else 'unavailable')
        while pygame.mixer.music.get_busy() and not stop.wait(.05):
            if animation and levels:
                position=max(0,pygame.mixer.music.get_pos());index=position//20;cues=[]
                for i in range(index,min(index+8,len(levels))):
                    at=i*20;pose=word_shape(words,at)
                    level=levels[i];cues.append([at,level,pose if level>.06 else 0])
                animation.emit(position_ms=position,cues=cues,
                               openness=levels[index] if index<len(levels) else 0,
                               pose=cues[0][2] if cues else 0)
        pygame.mixer.music.stop()
        pygame.mixer.music.unload()
    finally:
        if animation:animation.end()
        pygame.mixer.quit()


def windows_speak(text, stop, preferred_voice='', animation=None):
    import sys
    if sys.platform!='win32':
        raise ValueError('Windows SAPI output requires Windows.')
    import pyttsx3
    engine=pyttsx3.init('sapi5')
    allowed=[v for v in engine.getProperty('voices') if not re.search('asad|uzma', v.name+' '+v.id, re.I)]
    if not allowed:
        raise ValueError('No allowed Windows voice is installed. Install a voice other than Asad/Uzma.')
    normalize=lambda name: re.sub(r'[^a-z]','',name.lower().replace('desktop',''))
    wanted=normalize(preferred_voice)
    chosen=next((v for v in allowed if wanted and (normalize(v.name)==wanted or wanted in normalize(v.name))),allowed[0])
    engine.setProperty('voice',chosen.id)
    observer=None
    if animation:
        from .avatar_audio import sapi_observer
        observer=sapi_observer(engine,animation,text)
    try:
        engine.say(text)
        engine.startLoop(False)
        while engine.isBusy() and not stop.is_set():
            engine.iterate()
            time.sleep(.02)
        engine.stop()
    finally:
        if animation:animation.end()
        if observer:
            try:observer.disconnect()
            except Exception:pass
        try:engine.endLoop()
        except RuntimeError:pass



def freellmapi_audio(text, voice='echo'):
    """Use the router's configured audio chain and return its served provider."""
    key = os.environ.get('FREELLMAPI_API_KEY', '').strip()
    if not key:
        raise ValueError('key is missing')
    request = Request(
        'http://127.0.0.1:31415/v1/audio/speech',
        data=json.dumps({'model': 'auto', 'input': text, 'response_format': 'mp3', 'voice': voice}).encode(),
        headers={'Authorization': 'Bearer ' + key, 'Content-Type': 'application/json'},
        method='POST',
    )
    with urlopen(request, timeout=35) as response:
        audio = response.read()
        if not audio or not response.headers.get('Content-Type', '').startswith('audio/'):
            raise ValueError('invalid audio response')
        upstream = response.headers.get('X-Provider')
        model = response.headers.get('X-Model')
    return audio, ' / '.join(filter(None, (upstream, model)))


def freellmapi_failure(exc):
    if not isinstance(exc, HTTPError):
        reason = str(exc) if type(exc) is ValueError else type(exc).__name__
        return 'FreeLLMAPI: ' + reason, 30

    status = exc.code
    retry = exc.headers.get('Retry-After', '') if exc.headers else ''
    exc.close()
    delay = 60 if status == 429 else 30
    if retry:
        try:
            delay = max(1, int(retry))
        except ValueError:
            try:
                delay = max(1, parsedate_to_datetime(retry).timestamp() - time.time())
            except (ValueError, TypeError, OverflowError):
                pass
    reason = {
        401: 'authorization failed',
        403: 'access denied',
        429: 'quota or rate limit',
        502: 'audio providers unavailable',
    }.get(status, 'speech request failed')
    return f'FreeLLMAPI HTTP {status} ({reason})', delay


def speak_reply(text, allow_online, stop, send, preferred_voice='', avatar_sync=False,
                freellmapi_backoff=None, online_voice='male'):
    provider = 'windows'
    active = None
    failures = []
    animation = None
    if avatar_sync:
        from .avatar_audio import PlaybackCues
        animation = PlaybackCues(send)

    def report(name, phase, *, pending=False):
        send({'phase': phase, 'active_tts': None if pending else name, 'message': name,
              'fallback_reason': '; '.join(failures) or None})

    def windows(value):
        nonlocal active, provider
        active, provider = 'Windows SAPI', 'windows'
        report(active, 'preparing' if animation else 'speaking')
        if animation:
            windows_speak(value, stop, preferred_voice, animation=animation)
        else:
            windows_speak(value, stop, preferred_voice)

    def result():
        return {'provider': provider, 'active_tts': active,
                'fallback_reason': '; '.join(failures) or None,
                'cancelled': stop.is_set()}

    parts = list(chunks(text))
    if stop.is_set() or not parts:
        return result()
    if not allow_online:
        windows(' '.join(parts))
        return result()

    if freellmapi_backoff:
        failures.append(freellmapi_backoff + ' (retry cooldown)')
    else:
        report('FreeLLMAPI', 'preparing', pending=True)
        try:
            # One synthesis call lets the router walk its configured chain once per reply.
            voice_options = {'voice': 'nova'} if online_voice == 'female' else {}
            audio, served = freellmapi_audio(' '.join(parts), **voice_options)
        except Exception as exc:
            reason, delay = freellmapi_failure(exc)
            failures.append(reason)
            send({'freellmapi_retry': (time.monotonic() + delay, reason)})
        else:
            if stop.is_set():
                return result()
            active = f'FreeLLMAPI ({served})' if served else 'FreeLLMAPI'
            try:
                report(active, 'preparing' if animation else 'speaking')
                play(audio, stop, animation) if animation else play(audio, stop)
            except Exception as exc:
                failures.append(f'FreeLLMAPI playback: {type(exc).__name__}')
            else:
                provider = 'freellmapi'
                return result()

    edge_available = True
    for part in parts:
        if stop.is_set():
            break
        if edge_available:
            try:
                report('Edge TTS: ' + EDGE_VOICE, 'preparing', pending=True)
                if animation:
                    audio, words = asyncio.run(edge_audio(part, with_timing=True))
                else:
                    audio = asyncio.run(edge_audio(part))
                if stop.is_set():
                    break
                active = 'Edge TTS: ' + EDGE_VOICE
                report(active, 'preparing' if animation else 'speaking')
                if animation:
                    play(audio, stop, animation, words)
                else:
                    play(audio, stop)
                provider = 'edge'
                continue
            except Exception as exc:
                failures.append(f'Edge TTS: {type(exc).__name__}')
                edge_available = False
        if not stop.is_set():
            windows(part)
    return result()
