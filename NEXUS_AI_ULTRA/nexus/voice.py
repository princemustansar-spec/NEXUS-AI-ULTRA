"""Offline microphone STT. Heavy/native packages live only in a short-lived child."""
import hashlib
import importlib.util
import json
import math
import multiprocessing
import os
from pathlib import Path
import re
import shutil
import threading
import time
import uuid

MODEL_REPO = 'Systran/faster-whisper-tiny'  # Multilingual: never tiny.en.
MODEL_NAME = 'tiny'
MAX_SECONDS = 15
VOICE_PACKAGES = ('sounddevice', 'faster_whisper', 'uroman', 'speech_recognition')
_WHISPER_CACHE = {}
_ROMANIZER = None


class NoSpeechError(ValueError):
    """Normal idle/unintelligible capture, distinct from device/network failure."""



def model_manifest(directory, verify=False):
    directory = Path(directory)
    try:
        marker = json.loads((directory / 'verified.json').read_text(encoding='utf-8'))
        files = marker['files']
        if marker['repo'] != MODEL_REPO or not {'model.bin', 'config.json', 'tokenizer.json'}.issubset(files):
            return None
        for name, digest in files.items():
            if Path(name).name != name or not re.fullmatch(r'[a-f0-9]{64}', digest):
                return None
            p = directory / name
            if not p.is_file() or p.is_symlink():
                return None
            if verify and hashlib.sha256(p.read_bytes()).hexdigest() != digest:
                return None
        return marker
    except (OSError, ValueError, KeyError, TypeError):
        return None


def verify_download(path, etag):
    """Verify HF LFS SHA-256 or Git blob SHA-1 against authoritative metadata."""
    data = Path(path).read_bytes()
    expected = (etag or '').strip('"')
    if re.fullmatch(r'[a-fA-F0-9]{64}', expected):
        digest = hashlib.sha256(data).hexdigest()
    elif re.fullmatch(r'[a-fA-F0-9]{40}', expected):
        digest = hashlib.sha1(b'blob ' + str(len(data)).encode() + b'\0' + data).hexdigest()
    else:
        raise ValueError('Model file has no supported authoritative checksum; refusing to install it.')
    if digest.lower() != expected.lower():
        raise ValueError('Model checksum mismatch. Download stopped; no unverified model will be used.')
    return hashlib.sha256(data).hexdigest()


def install_model(directory, send):
    from huggingface_hub import HfApi, get_hf_file_metadata, hf_hub_download, hf_hub_url
    directory = Path(directory)
    if model_manifest(directory, verify=True):
        return {'model': MODEL_NAME, 'already_installed': True}
    if directory.exists():
        raise ValueError('Offline model folder is incomplete or changed. Rename/remove only the voice-models/tiny folder, then reinstall. Your chat database is separate.')
    directory.parent.mkdir(parents=True, exist_ok=True)
    stage = directory.parent / '.tiny-download'
    stage.mkdir(exist_ok=True)
    try:
        # Resolve a real immutable revision, then verify each downloaded artifact.
        info = HfApi().model_info(MODEL_REPO)
        revision = info.sha
        if not revision or not re.fullmatch(r'[a-f0-9]{40}', revision):
            raise ValueError('Could not resolve an immutable model revision.')
        names = [f.rfilename for f in info.siblings if f.rfilename in ('config.json', 'model.bin', 'tokenizer.json', 'preprocessor_config.json') or f.rfilename.startswith('vocabulary.')]
        if not {'config.json', 'model.bin', 'tokenizer.json'}.issubset(names):
            raise ValueError('The official model is missing required files.')
        hashes = {}
        for name in names:
            if Path(name).name != name:
                raise ValueError('Unexpected model filename.')
            send({'phase': 'downloading', 'message': 'Downloading and verifying ' + name})
            metadata = get_hf_file_metadata(hf_hub_url(MODEL_REPO, name, revision=revision))
            path = hf_hub_download(MODEL_REPO, name, revision=revision, local_dir=str(stage))
            hashes[name] = verify_download(path, metadata.etag)
        (stage / 'verified.json').write_text(json.dumps({'repo': MODEL_REPO, 'revision': revision, 'files': hashes}, indent=2), encoding='utf-8')
        stage.rename(directory)
        return {'model': MODEL_NAME, 'revision': revision, 'verified': True}
    finally:
        if stage.exists():
            shutil.rmtree(stage)


def enumerate_inputs(sd):
    devices = sd.query_devices()
    hosts = sd.query_hostapis()
    inputs = []
    for index, d in enumerate(devices):
        if d['max_input_channels'] > 0:
            inputs.append({'id': index, 'name': d['name'], 'host_api': hosts[d['hostapi']]['name'],
                           'sample_rate': int(d['default_samplerate']), 'channels': d['max_input_channels']})
    try:
        default = int(sd.default.device[0])
    except (TypeError, ValueError):
        default = -1
    return {'devices': inputs, 'default_input': default, 'permission_tested': False,
            'guidance': 'Windows Settings > Privacy & security > Microphone: enable microphone access and Let desktop apps access your microphone. Enumeration alone does not prove permission.'}


def record_audio(sd, device, seconds, stop_event, send, silence_timeout=None, start_timeout=5, calibration_seconds=.5):
    import numpy as np
    info = sd.query_devices(device, 'input')
    rate = int(info['default_samplerate'])
    if not 8000 <= rate <= 192000:
        raise ValueError('Microphone reports an unsupported sample rate. Select another input device.')
    sd.check_input_settings(device=device, channels=1, samplerate=rate, dtype='float32')
    chunks, frames, overflows = [], 0, 0
    target = int(rate * (seconds + start_timeout + calibration_seconds)) if silence_timeout else int(rate * seconds)
    noise, threshold, speech_start, last_speech = [], .004, None, 0
    candidate_start = None
    from collections import deque
    preroll = deque(maxlen=max(1, int(rate * .2 / 1024)))
    with sd.InputStream(device=device, samplerate=rate, channels=1, dtype='float32', blocksize=1024) as stream:
        send({'phase': 'calibrating' if silence_timeout else 'listening', 'message': 'Keep quiet for 0.5 seconds while ambient noise is measured.' if silence_timeout else 'Listening locally. Press Stop to transcribe, or Cancel to discard.'})
        last_meter = 0
        while frames < target and not stop_event.is_set():
            data, overflow = stream.read(min(1024, target - frames))
            frames += len(data)
            elapsed = frames / rate
            block_rms = float(np.sqrt(np.mean(np.square(data)))) if data.size else 0
            if silence_timeout:
                if elapsed <= calibration_seconds:
                    noise.append(block_rms)
                    continue
                if noise:
                    threshold = max(.004, float(np.median(noise)) * 2.5)
                    noise.clear()
                    send({'phase':'listening','message':'Speak now. Recording ends automatically after silence.'})
                if speech_start is None:
                    preroll.append(data.copy())
                    if block_rms > threshold:
                        if candidate_start is None:candidate_start=elapsed-len(data)/rate
                        if elapsed-candidate_start >= .10:
                            speech_start = elapsed
                            last_speech = elapsed
                            chunks.extend(preroll)
                    else:candidate_start=None
                    if speech_start is None and elapsed >= calibration_seconds + start_timeout:
                        raise NoSpeechError('No speech detected before the start timeout. Check input level and try again.')
                else:
                    chunks.append(data.copy())
                    if block_rms > threshold:
                        last_speech = elapsed
                    if elapsed - last_speech >= silence_timeout or elapsed - speech_start >= seconds:
                        break
            else:
                chunks.append(data.copy())
            overflows += int(bool(overflow))
            now = time.monotonic()
            if now - last_meter >= .25:
                rms = float(np.sqrt(np.mean(np.square(data)))) if data.size else 0
                send({'phase': 'listening', 'level_dbfs': round(20 * math.log10(max(rms, 1e-9)), 1), 'seconds': round(frames / rate, 1)})
                last_meter = now
    if not chunks:
        raise NoSpeechError('Recording stopped before any audio was captured. Try again and speak after Listening appears.')
    audio = np.concatenate(chunks).reshape(-1)
    if not np.isfinite(audio).all():
        raise ValueError('Microphone returned invalid audio. Select another device or update its driver.')
    rms = float(np.sqrt(np.mean(np.square(audio))))
    peak = float(np.max(np.abs(audio)))
    return audio, rate, {'seconds': round(len(audio) / rate, 2), 'level_dbfs': round(20 * math.log10(max(rms, 1e-9)), 1),
                         'peak': round(peak, 4), 'overflows': overflows, 'silence': rms < .001,
                         'clipping': peak >= .99, 'permission_tested': True}


def romanize(text):
    # Roman Urdu is a writing style, not a separate acoustic language.
    # Keep the original Urdu transcript in the response for correction/review.
    if not re.search(r'[\u0600-\u06ff\u0900-\u097f]', text):
        return text
    global _ROMANIZER
    if _ROMANIZER is None:
        from uroman import Uroman
        _ROMANIZER=Uroman()
    return _ROMANIZER.romanize_string(text, lcode='urd')


def transcribe_audio(audio, rate, directory, language, send):
    import av
    import numpy as np
    from faster_whisper import WhisperModel
    send({'phase': 'transcribing', 'message': 'Transcribing offline on CPU (INT8). No audio is uploaded.'})
    if rate != 16000:
        # Resample native microphone rates in RAM. Never leave a WAV behind on cancel.
        frame = av.AudioFrame.from_ndarray(audio.reshape(1, -1).astype(np.float32), format='fltp', layout='mono')
        frame.sample_rate = rate
        resampler = av.AudioResampler(format='fltp', layout='mono', rate=16000)
        frames = resampler.resample(frame) + resampler.resample(None)
        audio = np.concatenate([f.to_ndarray().reshape(-1) for f in frames])
    cache_key = str(directory)
    model = _WHISPER_CACHE.get(cache_key)
    if model is None:
        model = WhisperModel(cache_key, device='cpu', compute_type='int8',
                             cpu_threads=max(1, min(2, os.cpu_count() or 1)), num_workers=1, local_files_only=True)
        _WHISPER_CACHE[cache_key] = model
    segments, info = model.transcribe(audio, language=None if language == 'auto' else language,
                                      beam_size=1, best_of=1, temperature=0, vad_filter=True,
                                      condition_on_previous_text=False, without_timestamps=True)
    text = ' '.join(segment.text.strip() for segment in segments if segment.text.strip()).strip()
    if not text:
        raise NoSpeechError('No speech was recognized. Check input level, select English or Roman Urdu explicitly, and try a short clear sentence.')
    result = romanize(text) if language in ('ur', 'auto') else text
    return {'text': result, 'original_text': text, 'detected_language': info.language,
            'romanized': result != text, 'offline': True, 'model': 'Whisper tiny multilingual / CPU INT8',
            'notice': 'Review before sending. Urdu-to-Latin spelling is approximate; short/noisy clips and code-switching can be inaccurate.'}


def voice_worker(connection, stop_event, operation, options, directory, keep_open=False):
    """Spawn target: no network code is called for recording/transcription."""
    def send(message):
        connection.send(message)
    try:
        os.environ.setdefault('HF_HUB_DISABLE_TELEMETRY', '1')
        if operation == 'model':
            result = install_model(directory, send)
        elif operation == 'tts':
            from .tts import speak_reply
            result = speak_reply(options['text'], options.get('allow_online', False), stop_event, send, options.get('preferred_voice',''))
        else:
            import sounddevice as sd
            if operation == 'diagnostics':
                result = enumerate_inputs(sd)
            else:
                if operation == 'capture' and options.get('engine', 'offline') == 'offline' and not model_manifest(directory, verify=True):
                    raise ValueError('Verified offline model not installed. Run Install offline model in Voice Assistant first.')
                audio, rate, metrics = record_audio(sd, options['device'], options['seconds'], stop_event, send,
                    options.get('silence_timeout') if operation == 'capture' else None, options.get('start_timeout', 5),
                    0 if options.get('discard_on_stop') else .5)
                if options.get('discard_on_stop') and stop_event.is_set():
                    result={'no_speech':True,'diagnostics':metrics}
                elif operation == 'test':
                    result = {**metrics, 'guidance': 'No input signal: check mute, input selection and Windows microphone privacy.' if metrics['silence'] else 'Input signal detected. Clipping/overflows may require reducing gain or selecting another device.'}
                else:
                    if metrics['silence']:
                        raise NoSpeechError('No microphone signal detected. Run Microphone diagnostics and Test input; check mute, device and Windows privacy settings.')
                    if options.get('engine', 'offline') == 'google':
                        from .voice_online import google_transcribe
                        try:
                            result = google_transcribe(audio, rate, options.get('locale') or ('ur-PK' if options['language']=='ur' else 'en-IN'), options['language']!='en', send)
                        except NoSpeechError:
                            raise
                        except Exception as exc:
                            if not model_manifest(directory, verify=True):
                                raise ValueError('Google recognition failed ('+type(exc).__name__+'). Offline fallback model is not installed. Check connectivity/language or install the tiny model.') from exc
                            send({'phase':'transcribing','message':'Google unavailable/unintelligible; using verified offline fallback.'})
                            result = transcribe_audio(audio, rate, directory, options['language'], send)
                            result['fallback_reason'] = type(exc).__name__
                    else:
                        result = transcribe_audio(audio, rate, directory, options['language'], send)
                    result['diagnostics'] = metrics
        send({'phase': 'done', 'result': result})
    except Exception as exc:
        if isinstance(exc, ImportError) or (isinstance(exc, OSError) and 'portaudio' in str(exc).lower()):
            message = 'Python voice dependencies are missing or cannot load. Run INSTALL_VOICE.bat. On Windows also check the Microsoft Visual C++ x64 runtime.'
        elif type(exc).__name__ == 'PortAudioError':
            message = 'Microphone could not be opened: ' + str(exc)[:200] + '. Check the selected input, mute, Windows microphone privacy and desktop-app access.'
        elif operation == 'model' and not isinstance(exc, ValueError):
            message = 'Offline model download failed (' + type(exc).__name__ + '). Check Internet access to huggingface.co and its Hugging Face/Xet download hosts, then retry. Existing chat remains available.'
        else:
            message = str(exc)[:450]
        error={'phase':'error','error':message,'error_type':type(exc).__name__}
        if isinstance(exc,NoSpeechError):error['error_code']='no_speech'
        send(error)
    finally:
        if not keep_open:
            connection.close()


def reusable_voice_worker(connection, stop_event, commands, operation, options, directory):
    """Keep only a recently used capture/model worker warm; microphone stays closed."""
    try:
        while True:
            voice_worker(connection, stop_event, operation, options, directory, keep_open=True)
            if not commands.poll(45):
                break
            operation, options = commands.recv()
    except (EOFError, OSError):
        pass
    finally:
        connection.close()
        commands.close()


class VoiceService:
    def __init__(self, data_dir, context=None):
        self.directory = Path(data_dir) / 'voice-models' / MODEL_NAME
        self.context = context or multiprocessing.get_context('spawn')
        self.lock = threading.RLock()
        self.process = self.connection = self.stop_event = None
        self.commands = None
        self.started = 0
        self.state = {'phase': 'idle', 'job_id': None}

    def _read_messages(self):
        if self.connection:
            try:
                while self.connection.poll():
                    message = self.connection.recv()
                    self.state.update(message)
            except (EOFError, OSError):
                pass

    def _collect(self):
        self._read_messages()
        if self.process:
            terminal = self.state['phase'] in ('done', 'error', 'cancelled')
            elapsed = time.monotonic() - self.started
            limit = 600 if self.state.get('operation') == 'model' else 120
            if self.process.is_alive() and elapsed > limit:
                self._stop_process()
                self.state.update(phase='error', error='Voice operation timed out. Check diagnostics and try again.')
            elif not self.process.is_alive():
                # The child may have sent its final result after the first poll.
                self._read_messages()
                terminal = self.state['phase'] in ('done', 'error', 'cancelled')
                if not terminal:
                    self.state.update(phase='error', error='Voice worker exited unexpectedly. Check desktop.log, audio drivers and voice dependencies.')
                self._release()

    def _release(self):
        if self.process:
            self.process.join(timeout=.05)
            self.process.close()
            self.process = None
        if self.connection:
            self.connection.close()
            self.connection = None
        if self.commands:
            self.commands.close()
            self.commands = None
        self.stop_event = None

    def _stop_process(self):
        if self.process:
            if self.state.get('operation') == 'tts' and self.stop_event:
                self.stop_event.set()
                self.process.join(timeout=.5)
            if self.process.is_alive():
                self.process.terminate()
                self.process.join(timeout=1)
            if self.process.is_alive():
                self.process.kill()
                self.process.join(timeout=1)
            if self.process.is_alive():
                raise ValueError('Could not stop the voice worker. Close the application.')
            self._release()
            stage = self.directory.parent / '.tiny-download'
            if self.state.get('operation') == 'model' and stage.is_dir() and not stage.is_symlink():
                shutil.rmtree(stage)

    def status(self):
        with self.lock:
            self._collect()
            missing = [p for p in VOICE_PACKAGES if importlib.util.find_spec(p) is None]
            return {**self.state, 'dependencies_missing': missing,
                    'model_ready': model_manifest(self.directory) is not None,
                    'model_directory': str(self.directory), 'offline_recognition': True, 'max_seconds': MAX_SECONDS}

    def start(self, operation, *, device=None, language='en', seconds=10, engine='offline', locale='en-IN', silence_timeout=None, start_timeout=5, text='', allow_online=False, preferred_voice='', discard_on_stop=False):
        if operation not in ('capture', 'diagnostics', 'test', 'model', 'tts'):
            raise ValueError('Unsupported voice operation')
        if language not in ('en', 'ur', 'auto'):
            raise ValueError('Select English, Roman Urdu or automatic language.')
        if device is not None and (type(device) is not int or device < 0):
            raise ValueError('Microphone device must be a nonnegative device ID or system default.')
        if type(seconds) not in (int, float) or not math.isfinite(seconds) or not 2 <= seconds <= MAX_SECONDS:
            raise ValueError('Recording duration must be 2–15 seconds.')
        if engine not in ('google', 'offline') or locale not in ('en-IN','ur-PK','hi-IN','en-US','en-GB'):
            raise ValueError('Unsupported recognition engine or language locale.')
        if silence_timeout is not None and (type(silence_timeout) not in (int,float) or not .4 <= silence_timeout <= 3):
            raise ValueError('Silence timeout must be 0.4–3 seconds.')
        if type(start_timeout) not in (int,float) or not 2 <= start_timeout <= 15:
            raise ValueError('Speech start timeout must be 2–15 seconds.')
        if operation == 'tts' and (not isinstance(text,str) or not text.strip() or len(text)>1800):
            raise ValueError('Spoken reply must contain 1–1800 characters.')
        if not isinstance(preferred_voice,str) or len(preferred_voice)>150 or re.search('asad|uzma',preferred_voice,re.I):
            raise ValueError('Choose a voice other than Asad/Uzma.')
        options = {'device':device,'language':language,'seconds':seconds,'engine':engine,'locale':locale,
                   'silence_timeout':silence_timeout,'start_timeout':start_timeout,'text':text,'allow_online':allow_online,'preferred_voice':preferred_voice,'discard_on_stop':discard_on_stop is True}
        with self.lock:
            self._collect()
            if self.process and self.commands and operation == 'capture' and self.state.get('operation') == 'capture' and self.state['phase'] in ('done','error'):
                try:
                    self.stop_event.clear()
                    self.commands.send((operation,options))
                    self.started = time.monotonic()
                    self.state = {'job_id':uuid.uuid4().hex,'operation':operation,'phase':'starting','message':'Reusing recent voice worker; microphone opens only for this request.'}
                    return dict(self.state)
                except (BrokenPipeError,EOFError,OSError):
                    self._stop_process()
            if self.process:
                if self.state['phase'] in ('done', 'error', 'cancelled'):
                    self._stop_process()
                else:
                    raise ValueError('Another voice operation is running. Stop or cancel it first.')
            receiver, sender = self.context.Pipe(duplex=False)
            event = self.context.Event()
            command_receiver, command_sender = self.context.Pipe(duplex=False)
            target = reusable_voice_worker if operation == 'capture' else voice_worker
            args = (sender,event,command_receiver,operation,options,str(self.directory)) if operation == 'capture' else (sender,event,operation,options,str(self.directory))
            process = self.context.Process(target=target, args=args, daemon=True)
            try:
                process.start()
            except Exception:
                receiver.close(); sender.close(); command_receiver.close(); command_sender.close()
                raise
            sender.close()
            command_receiver.close()
            if operation == 'capture':
                self.commands = command_sender
            else:
                command_sender.close()
            self.process, self.connection, self.stop_event = process, receiver, event
            self.started = time.monotonic()
            self.state = {'job_id': uuid.uuid4().hex, 'operation': operation, 'phase': 'starting', 'message': 'Starting local Python voice worker.'}
            return dict(self.state)

    def stop_recording(self):
        with self.lock:
            self._collect()
            if not self.process or self.state.get('operation') not in ('capture', 'test'):
                raise ValueError('No microphone recording is active.')
            self.stop_event.set()
            return {'stopping': True, 'job_id': self.state['job_id']}

    def cancel(self):
        with self.lock:
            self._stop_process()
            self.state = {'phase': 'cancelled', 'job_id': self.state.get('job_id')}
            return {'cancelled': True}
