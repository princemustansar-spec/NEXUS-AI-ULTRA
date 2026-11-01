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
    main.hide.assert_not_called() # already hidden at creation, never hide the GUI when showing from Settings
    companion.destroy.assert_called_once();backend.close.assert_called_once()


def test_floating_launcher_is_an_explicit_manual_start_not_a_login_task():
    root=Path(__file__).resolve().parent.parent
    text=(root/'START_FLOATING_NEXUS.bat').read_text()
    assert 'run.py" --floating' in text
    assert 'schtasks' not in text.lower() and 'reg add' not in text.lower()


def test_desktop_saved_floating_mode_is_honored_without_forcing_microphone(tmp_path,monkeypatch):
    main=SimpleNamespace(events=SimpleNamespace(closed=Event()),hide=Mock(),show=Mock(),restore=Mock())
    companion=SimpleNamespace(events=SimpleNamespace(closed=Event()),destroy=Mock())
    host=SimpleNamespace(settings={},create_window=Mock(side_effect=[main,companion]))
    host.start=Mock(side_effect=lambda *args,**kwargs:args[0]() if args else None)
    backend=SimpleNamespace(start=Mock(return_value={'name':'NEXUS','token':'fixture','avatar_settings':{'desktop_mode':'floating','auto_voice':False}}),url='http://127.0.0.1:8765',port=8765,data_dir=tmp_path,close=Mock())
    connection=Mock(side_effect=AssertionError('Auto voice disabled'))
    monkeypatch.setattr('nexus.desktop.http.client.HTTPConnection',connection)
    run_desktop(backend,host)
    assert host.create_window.call_args_list[0].kwargs['hidden']
    assert host.create_window.call_count==2
    connection.assert_not_called();main.hide.assert_not_called()


def test_explicit_gui_flag_overrides_saved_desktop_mode(tmp_path,monkeypatch):
    import run
    monkeypatch.setenv('NEXUS_DATA_DIR',str(tmp_path))
    backend=SimpleNamespace(close=Mock());host=object();desktop=Mock()
    monkeypatch.setattr(run,'configure_logging',Mock())
    monkeypatch.setattr(run,'LocalBackend',lambda data:backend)
    monkeypatch.setattr(run,'load_webview',lambda:host)
    monkeypatch.setattr(run,'run_desktop',desktop)
    assert run.main(['--gui'])==0
    desktop.assert_called_once_with(backend,host,floating=False)
