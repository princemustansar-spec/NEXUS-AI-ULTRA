import asyncio
import importlib
import json
import threading
from types import SimpleNamespace
from unittest.mock import Mock
import httpx
import pytest
from nexus import chatgpt_signin as login
from nexus import tts


def test_keepalive_client_is_reused_without_reusing_bearer_headers(monkeypatch):
    seen=[];original=httpx.Client
    def handle(request):seen.append(request.headers.get('Authorization'));return httpx.Response(200,json={'ok':True})
    factory=Mock(side_effect=lambda **kwargs:original(transport=httpx.MockTransport(handle),**kwargs))
    monkeypatch.setattr(login.httpx,'Client',factory)
    transport=login.PooledHTTP()
    transport.get('https://api.openai.com/v1/models',headers={'Authorization':'Bearer account-one'},timeout=20)
    transport.get('https://api.openai.com/v1/models',headers={'Authorization':'Bearer account-two'},timeout=20)
    assert factory.call_count==1 and seen==['Bearer account-one','Bearer account-two']
    transport.close();transport.get('https://api.openai.com/v1/models');assert factory.call_count==2;transport.close()


def test_local_reply_initializes_speaker_once_for_long_text(monkeypatch):
    speak=Mock();monkeypatch.setattr(tts,'windows_speak',speak)
    text='**hello** '*180
    result=tts.speak_reply(text,False,threading.Event(),Mock())
    speak.assert_called_once();assert '*' not in speak.call_args.args[0]
    assert result['provider']=='windows'


def test_online_voice_failure_is_not_retried_on_each_remaining_chunk(monkeypatch):
    calls=[]
    async def unavailable(text):calls.append(text);raise RuntimeError('Offline fixture')
    monkeypatch.setattr(tts,'edge_audio',unavailable);speak=Mock();monkeypatch.setattr(tts,'windows_speak',speak)
    result=tts.speak_reply('hello '*200,True,threading.Event(),Mock())
    assert len(calls)==1 and speak.call_count>1 and result['provider']=='windows'
