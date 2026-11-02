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


async def edge_audio(text):
    import edge_tts
    data=bytearray()
    async def collect():
        async for packet in edge_tts.Communicate(text, EDGE_VOICE, rate='-5%').stream():
            if packet['type']=='audio':
                data.extend(packet['data'])
    await asyncio.wait_for(collect(),timeout=12)
    if not data:
        raise ValueError('Edge returned no audio')
    return bytes(data)


def play(data, stop):
    import pygame
    pygame.mixer.init()
    try:
        pygame.mixer.music.load(io.BytesIO(data), namehint='mp3')
        pygame.mixer.music.play()
        while pygame.mixer.music.get_busy() and not stop.wait(.05):
            pass
        pygame.mixer.music.stop()
        pygame.mixer.music.unload()
    finally:
        pygame.mixer.quit()


def windows_speak(text, stop, preferred_voice=''):
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
    try:
        engine.say(text)
        engine.startLoop(False)
        while engine.isBusy() and not stop.is_set():
            engine.iterate()
            time.sleep(.02)
        engine.stop()
    finally:
        try:engine.endLoop()
        except RuntimeError:pass


def speak_reply(text, allow_online, stop, send, preferred_voice=''):
    provider='windows'
    fallback=None
    if not allow_online:
        if not stop.is_set():
            send({'phase':'speaking','message':'Using an allowed installed Windows SAPI voice.'})
            windows_speak(' '.join(chunks(text)),stop,preferred_voice)
        return {'provider':'windows','fallback_reason':None,'cancelled':stop.is_set()}
    online_available=True
    for chunk in chunks(text):
        if stop.is_set():break
        if online_available:
            try:
                send({'phase':'speaking','message':'Edge TTS: '+EDGE_VOICE+' (reply text sent to Microsoft).'})
                audio=asyncio.run(edge_audio(chunk))
                if stop.is_set():break
                play(audio,stop)
                provider='edge'
                continue
            except Exception as exc:
                fallback=type(exc).__name__
                online_available=False
        if stop.is_set():break
        send({'phase':'speaking','message':'Using an allowed installed Windows SAPI voice.'})
        windows_speak(chunk,stop,preferred_voice)
        provider='windows'
    return {'provider':provider,'fallback_reason':fallback,'cancelled':stop.is_set()}
