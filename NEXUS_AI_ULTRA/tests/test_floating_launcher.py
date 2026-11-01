import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock
from nexus.desktop import run_desktop

class Event:
    def __init__(self):self.handlers=[]
    def __iadd__(self,handler):self.handlers.append(handler);return self


def test_floating_boot_hides_main_and_explicitly_starts_auto_voice(tmp_path,monkeypatch):
    main=SimpleNamespace(events=SimpleNamespace(closed=Event()),hide=Mock(),show=Mock(),restore=Mock())
    companion=SimpleNamespace(events=SimpleNamespace(closed=Event()),destroy=Mock())
    host=SimpleNamespace(settings={},create_window=Mock(side_effect=[main,companion]))
    def start(callback,**options):callback()
    host.start=Mock(side_effect=start)
    backend=SimpleNamespace(start=Mock(return_value={'name':'NEXUS','token':'session-fixture'}),url='http://127.0.0.1:8765',port=8765,data_dir=tmp_path,close=Mock())
    response=SimpleNamespace(status=200,read=lambda:b'{"active":true}')
    connection=SimpleNamespace(request=Mock(),getresponse=lambda:response,close=Mock())
    monkeypatch.setattr('nexus.desktop.http.client.HTTPConnection',lambda *a,**k:connection)
    run_desktop(backend,host,floating=True)
    options=host.create_window.call_args_list[0].kwargs
    assert options['hidden'] and not options['maximized']
    assert host.create_window.call_count==2
    args=connection.request.call_args
    assert args.args[:2]==('POST','/api/handsfree/start')
    assert json.loads(args.kwargs['body'])=={'consent':True,'online_consent':True}
    assert args.kwargs['headers']['X-Nexus-Token']=='session-fixture'
    assert main.hide.called
    companion.destroy.assert_called_once();backend.close.assert_called_once()


def test_floating_launcher_is_an_explicit_manual_start_not_a_login_task():
    root=Path(__file__).resolve().parent.parent
    text=(root/'START_FLOATING_NEXUS.bat').read_text()
    assert 'run.py" --floating' in text
    assert 'schtasks' not in text.lower() and 'reg add' not in text.lower()
