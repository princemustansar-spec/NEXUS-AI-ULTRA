import importlib
from urllib.parse import urlparse, parse_qs
from unittest.mock import Mock
import pytest
from fastapi.testclient import TestClient
from nexus.tools import explicit_youtube_request

@pytest.mark.parametrize('text', ['youtube open karo sad song lagao','YouTube kholo sad song chalao','open youtube and play sad song'])
def test_direct_youtube_search_intent(text):
    url=explicit_youtube_request(text)['url']
    assert urlparse(url).hostname=='www.youtube.com'
    assert parse_qs(urlparse(url).query)['search_query']==['sad song']

@pytest.mark.parametrize('text', ['youtube open karo','open youtube'])
def test_direct_youtube_home(text):
    assert explicit_youtube_request(text)=={'url':'https://www.youtube.com/'}

@pytest.mark.parametrize('text', ['youtube open mat karo','What happens when I open youtube?','Explain youtube open karo','open youtube? no do not','hello'])
def test_noncommand_or_negative_text_is_not_executed(text):
    assert explicit_youtube_request(text) is None

@pytest.fixture
def browser_client(tmp_path,monkeypatch):
    monkeypatch.setenv('NEXUS_DATA_DIR',str(tmp_path))
    import nexus.app
    app=importlib.reload(nexus.app)
    opened=Mock(return_value=True)
    monkeypatch.setattr('nexus.tools.webbrowser.open',opened)
    async def no_inference(*args,**kwargs):
        pytest.fail('Direct YouTube command must execute without a paid/model request')
    monkeypatch.setattr(app.providers,'request',no_inference)
    with TestClient(app.app) as client:
        client.headers['x-nexus-token']=app.session_token
        yield client,app,opened
    app.store.db.close()


def test_youtube_executes_without_approval_and_reports_request_only(browser_client):
    client,app,opened=browser_client
    response=client.post('/api/chat',json={'text':'youtube open karo sad song lagao'})
    assert response.status_code==200
    assert 'request' in response.json()['text'] and 'Play karein' in response.json()['text']
    assert response.json()['provider']=='NEXUS browser'
    assert opened.call_count==1
    assert parse_qs(urlparse(opened.call_args.args[0]).query)['search_query']==['sad song']
    assert not app.pending
    assert len(app.store.list('chat'))==2


def test_browser_failure_is_reported_instead_of_success(browser_client):
    client,app,opened=browser_client;opened.return_value=False
    response=client.post('/api/chat',json={'text':'open youtube'})
    assert response.status_code==200 and 'launch nahi hua' in response.json()['text']
    assert not app.pending


@pytest.mark.parametrize('mode',['disabled','emergency'])
def test_direct_browser_command_honors_existing_controls(browser_client,mode):
    client,app,opened=browser_client
    if mode=='disabled':app.store.set('denied_tools',['open_url'])
    else:app.emergency=True
    response=client.post('/api/chat',json={'text':'open youtube'})
    assert response.status_code==400
    opened.assert_not_called()


def test_search_and_public_url_auto_but_file_changes_still_need_approval(browser_client,tmp_path):
    client,app,opened=browser_client
    assert client.post('/api/tools/web_search',json={'query':'weather'}).json()['result']['browser_requested']
    assert client.post('/api/tools/open_url',json={'url':'https://www.youtube.com/'}).json()['result']['browser_requested']
    assert not app.pending
    result=client.post('/api/tools/create_text',json={'path':str(tmp_path/'note.txt'),'text':'hello'}).json()
    assert result['approval_required'] and result['id'] in app.pending
    assert not (tmp_path/'note.txt').exists()


@pytest.mark.parametrize('url',['file:///C:/Windows','https://127.0.0.1/','http://www.youtube.com/','https://user:password@example.com/'])
def test_auto_url_keeps_validation(browser_client,url):
    client,app,opened=browser_client
    assert client.post('/api/tools/open_url',json={'url':url}).status_code==400
    opened.assert_not_called()
