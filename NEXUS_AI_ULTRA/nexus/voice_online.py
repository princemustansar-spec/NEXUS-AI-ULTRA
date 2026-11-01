"""JARVIS V6.7-compatible Google recognizer using NEXUS's existing PCM capture."""

def recognition_locale(language, locale='auto'):
    """Match acoustic recognition to speech language, not Latin output script."""
    if locale not in (None, '', 'auto'):
        if locale not in ('en-IN', 'ur-PK', 'hi-IN', 'en-US', 'en-GB'):
            raise ValueError('Unsupported recognition language locale.')
        return locale
    return 'ur-PK' if language == 'ur' else 'en-IN'


def google_transcribe(audio, rate, locale, roman_output, send):
    import numpy as np
    import speech_recognition as sr
    from .voice import romanize, NoSpeechError
    recognizer = sr.Recognizer()
    recognizer.operation_timeout = 6
    pcm = (np.clip(audio, -1, 1) * 32767).astype('<i2').tobytes()
    send({'phase':'transcribing','message':'Google Speech Recognition: '+locale+'. Audio is sent online; local fallback is available.'})
    audio_data = sr.AudioData(pcm,rate,2)
    if rate != 16000:
        audio_data = sr.AudioData(audio_data.get_raw_data(convert_rate=16000,convert_width=2),16000,2)
    try:
        text = recognizer.recognize_google(audio_data, language=locale,
                    endpoint='https://www.google.com/speech-api/v2/recognize')
    except sr.UnknownValueError as exc:
        raise NoSpeechError('No speech was recognized in this clip.') from exc
    if not text.strip():
        raise NoSpeechError('No speech was recognized in this clip.')
    converted = romanize(text) if roman_output else text
    return {'text':converted,'original_text':text,'romanized':converted!=text,'offline':False,
            'engine':'google','detected_language':locale,'model':'Google Speech Recognition',
            'notice':'Review before Send. Roman Urdu spelling is approximate; compare the original transcript. Select ur-PK for Urdu speech.'}
