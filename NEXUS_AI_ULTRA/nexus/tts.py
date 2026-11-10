"""Adapted JARVIS Edge/Windows output approach; no Gemini/key-file component."""
import asyncio
import io
import re
import time

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
        pygame.mixer.music.load(io.BytesIO(data), namehint='mp3')
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


def speak_reply(text, allow_online, stop, send, preferred_voice='', avatar_sync=False):
    provider='windows'
    fallback=None
    animation=None
    if avatar_sync:
        from .avatar_audio import PlaybackCues
        animation=PlaybackCues(send)
    def windows(value):
        if animation:windows_speak(value,stop,preferred_voice,animation=animation)
        else:windows_speak(value,stop,preferred_voice)
    if not allow_online:
        if not stop.is_set():
            send({'phase':'preparing' if animation else 'speaking','message':'Using an allowed installed Windows SAPI voice.'})
            windows(' '.join(chunks(text)))
        return {'provider':'windows','fallback_reason':None,'cancelled':stop.is_set()}
    online_available=True
    for chunk in chunks(text):
        if stop.is_set():break
        if online_available:
            try:
                send({'phase':'preparing' if animation else 'speaking','message':'Edge TTS: '+EDGE_VOICE+' (reply text sent to Microsoft).'})
                if animation:audio,words=asyncio.run(edge_audio(chunk,with_timing=True))
                else:audio=asyncio.run(edge_audio(chunk))
                if stop.is_set():break
                if animation:play(audio,stop,animation,words)
                else:play(audio,stop)
                provider='edge'
                continue
            except Exception as exc:
                fallback=type(exc).__name__
                online_available=False
        if stop.is_set():break
        send({'phase':'preparing' if animation else 'speaking','message':'Using an allowed installed Windows SAPI voice.'})
        windows(chunk)
        provider='windows'
    return {'provider':provider,'fallback_reason':fallback,'cancelled':stop.is_set()}
