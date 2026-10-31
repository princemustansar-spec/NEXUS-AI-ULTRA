import pytest
from nexus.voice_online import recognition_locale

@pytest.mark.parametrize('language,locale,expected', [
    ('ur','auto','ur-PK'), ('ur',None,'ur-PK'), ('ur','','ur-PK'),
    ('en','auto','en-IN'), ('auto','auto','en-IN'),
    ('ur','en-IN','en-IN'), ('ur','ur-PK','ur-PK'), ('en','en-US','en-US'),
])
def test_match_spoken_language_and_preserve_explicit_choice(language,locale,expected):
    assert recognition_locale(language,locale)==expected


def test_invalid_locale_rejected():
    with pytest.raises(ValueError,match='locale'):
        recognition_locale('ur','made-up')

@pytest.mark.parametrize('requested,expected', [('auto','ur-PK'),('en-IN','en-IN')])
def test_voice_route_resolves_worker_locale_but_preserves_preference(tmp_path,monkeypatch,requested,expected):
    import asyncio
    import importlib
    from unittest.mock import Mock
    monkeypatch.setenv('NEXUS_DATA_DIR',str(tmp_path))
    import nexus.app
    m=importlib.reload(nexus.app)
    start=Mock(return_value={'job_id':'fixture','phase':'starting'})
    monkeypatch.setattr(m.voice,'start',start)
    monkeypatch.setattr(m.tts,'cancel',Mock())
    async def inline(fn,*args,**kwargs):return fn(*args,**kwargs)
    monkeypatch.setattr(m.asyncio,'to_thread',inline)
    class Request:
        async def json(self):return {'consent':True,'online_consent':True,'engine':'google','language':'ur','locale':requested}
    asyncio.run(m.voice_start(Request()))
    assert start.call_args.kwargs['locale']==expected
    assert m.store.get('voice_settings')['locale']==requested
    m.store.db.close()
