"""Verify voice provenance reaches inference without changing chat permissions."""
import asyncio
import importlib
import httpx
import pytest


@pytest.mark.parametrize('source', ['voice', 'text', None])
def test_chat_preserves_transcript_and_explains_app_capabilities(tmp_path, monkeypatch, source):
    monkeypatch.setenv('NEXUS_DATA_DIR', str(tmp_path))
    import nexus.app
    m = importlib.reload(nexus.app)
    # Older incorrect assistant replies must not remove current app context.
    m.store.add('chat', dict(role='assistant', text='I cannot hear you. Type your message.'))
    captured = []
    async def inference(messages, tools=None, allow_paid=False):
        captured.append((messages, allow_paid))
        return {'role':'assistant', 'content':'Ji, aapki baat text mein mil gai hai.'}, 'Test', 'model'
    monkeypatch.setattr(m.providers, 'request', inference)
    payload = {'text':'Kya meri awaaz aa rahi hai?'}
    if source is not None:
        payload['input_source'] = source
    async def run():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=m.app), base_url='http://127.0.0.1', headers={'x-nexus-token':m.session_token}) as c:
            response = await c.post('/api/chat', json=payload)
            assert response.status_code == 200
            assert response.json()['model'] == 'model'
    asyncio.run(run())
    messages, paid = captured[0]
    assert messages[-1] == {'role':'user', 'content':payload['text']}
    assert 'microphone speech-to-text' in messages[0]['content']
    assert 'not raw audio' in messages[0]['content']
    assert 'Current message input source: '+(source or 'text') in messages[0]['content']
    assert paid is False
    saved = [row for row in m.store.list('chat') if row['role']=='user'][0]
    assert saved['input_source'] == (source or 'text')
    assert saved['text'] == payload['text']
    m.store.db.close()


def test_invalid_source_rejected_before_saving_or_inference(tmp_path, monkeypatch):
    monkeypatch.setenv('NEXUS_DATA_DIR', str(tmp_path))
    import nexus.app
    m = importlib.reload(nexus.app)
    async def inference(*args, **kwargs):
        pytest.fail('Invalid source must not reach provider')
    monkeypatch.setattr(m.providers, 'request', inference)
    async def run():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=m.app), base_url='http://127.0.0.1', headers={'x-nexus-token':m.session_token}) as c:
            response = await c.post('/api/chat', json={'text':'hello', 'input_source':'audio-stream'})
            assert response.status_code == 400
    asyncio.run(run())
    assert not m.store.list('chat')
    m.store.db.close()
