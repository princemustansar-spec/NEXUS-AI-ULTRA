from email.message import Message
from threading import Event
from unittest.mock import MagicMock, Mock
from urllib.error import HTTPError

import pytest

from nexus import tts


def test_router_auto_uses_one_request_and_reports_served_provider(monkeypatch):
    monkeypatch.setenv('FREELLMAPI_API_KEY', 'test-key')
    response = Mock(headers={'Content-Type': 'audio/wav', 'X-Provider': 'google'})
    response.read.return_value = b'RIFFfixture'
    upstream = MagicMock()
    upstream.return_value.__enter__.return_value = response
    monkeypatch.setattr(tts, 'urlopen', upstream)
    player = Mock()
    monkeypatch.setattr(tts, 'play', player)
    message = 'Long reply. ' * 70
    send = Mock()

    result = tts.speak_reply(message, True, Event(), send)

    upstream.assert_called_once()
    request = upstream.call_args.args[0]
    assert tts.json.loads(request.data) == {
        'model': 'auto', 'input': message.strip(), 'response_format': 'mp3', 'voice': 'echo',
    }
    player.assert_called_once()
    assert result['active_tts'] == 'FreeLLMAPI (google)'
    assert result['fallback_reason'] is None


@pytest.mark.parametrize('status, detail', [(429, 'quota or rate limit'), (502, 'audio providers unavailable')])
def test_fallback_reason_and_cooldown(monkeypatch, status, detail):
    headers = Message()
    headers['Retry-After'] = '75'
    router = Mock(side_effect=HTTPError('http://localhost', status, 'secret', headers, None))
    monkeypatch.setattr(tts, 'freellmapi_audio', router)
    edge = Mock(side_effect=TimeoutError)
    monkeypatch.setattr(tts, 'edge_audio', edge)
    windows = Mock()
    monkeypatch.setattr(tts, 'windows_speak', windows)
    monkeypatch.setattr(tts.time, 'monotonic', lambda: 100)
    states = []

    result = tts.speak_reply('Hello ' * 110, True, Event(), states.append)
    router.assert_called_once()
    edge.assert_called_once()
    assert windows.call_count > 1
    assert result['active_tts'] == 'Windows SAPI'
    failure = f'FreeLLMAPI HTTP {status} ({detail})'
    assert result['fallback_reason'] == f'{failure}; Edge TTS: TimeoutError'
    assert {'freellmapi_retry': (175, failure)} in states

    result = tts.speak_reply('Next reply', True, Event(), states.append, freellmapi_backoff=failure)
    router.assert_called_once()
    assert 'retry cooldown' in result['fallback_reason']


def test_route_falls_back_to_edge_after_invalid_audio(monkeypatch):
    monkeypatch.setattr(tts, 'freellmapi_audio', Mock(return_value=(b'bad', 'google')))

    async def edge(text):
        return b'edge'

    monkeypatch.setattr(tts, 'edge_audio', edge)
    monkeypatch.setattr(tts, 'play', Mock(side_effect=[ValueError(), None]))
    windows = Mock()
    monkeypatch.setattr(tts, 'windows_speak', windows)
    result = tts.speak_reply('Hello', True, Event(), Mock())
    assert result['provider'] == 'edge'
    assert result['fallback_reason'] == 'FreeLLMAPI playback: ValueError'
    windows.assert_not_called()
