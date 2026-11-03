"""Native-host contract tests; fake GUI is explicit, never a rendering claim."""
import os
from pathlib import Path
import socket
import sys
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from nexus.desktop import LocalBackend, load_webview, run_desktop
from create_shortcut import shortcut_target


def backend_stub(tmp_path):
    return SimpleNamespace(start=Mock(return_value={'name':'Configured NEXUS'}), close=Mock(),
                           url='http://127.0.0.1:8765', data_dir=tmp_path)


def test_native_window_reuses_existing_gui_and_closes_backend(tmp_path):
    b = backend_stub(tmp_path)
    w = SimpleNamespace(settings={}, create_window=Mock(return_value=object()), start=Mock())
    run_desktop(b, w)
    b.start.assert_called_once()
    args, options = w.create_window.call_args
    assert args == ('Configured NEXUS', b.url)
    assert options['js_api'] is None and options['resizable'] and options['maximized']
    assert options['background_color'] == '#030d18'
    w.start.assert_called_once_with(gui='edgechromium', debug=False, http_server=False,
                                    private_mode=False, storage_path=str(tmp_path/'webview'))
    assert not w.settings['ALLOW_FILE_URLS'] and not w.settings['ALLOW_DOWNLOADS']
    b.close.assert_called_once()


def test_webview_failure_shuts_down_and_never_falls_back_to_browser(tmp_path, monkeypatch):
    import webbrowser
    opened = Mock()
    monkeypatch.setattr(webbrowser, 'open', opened)
    b = backend_stub(tmp_path)
    w = SimpleNamespace(settings={}, create_window=Mock(return_value=object()), start=Mock(side_effect=RuntimeError('WebView2 missing')))
    with pytest.raises(RuntimeError, match='WebView2'):
        run_desktop(b,w)
    b.close.assert_called_once()
    opened.assert_not_called()


def test_backend_readiness_failure_still_cleans_up(tmp_path):
    b=backend_stub(tmp_path);b.start.side_effect=RuntimeError('readiness failed')
    w=SimpleNamespace(create_window=Mock())
    with pytest.raises(RuntimeError,match='readiness failed'):
        run_desktop(b,w)
    w.create_window.assert_not_called();b.close.assert_called_once()


def test_occupied_port_does_not_overwrite_pid_or_stop_owner(tmp_path):
    sock=socket.socket();sock.bind(('127.0.0.1',0));sock.listen(1)
    (tmp_path/'server.pid').write_text('999999999')
    backend=LocalBackend(tmp_path,port=sock.getsockname()[1])
    try:
        with pytest.raises(RuntimeError,match='unavailable'):backend.prepare()
        backend.close()
        assert (tmp_path/'server.pid').read_text()=='999999999'
        assert sock.fileno()!=-1
    finally:sock.close()


def test_close_removes_only_owned_pid(tmp_path):
    b=LocalBackend(tmp_path)
    b.pidfile.write_text(str(os.getpid()));b.close();assert not b.pidfile.exists()
    b.pidfile.write_text('999999999');b.close();assert b.pidfile.exists()


def test_missing_native_gui_is_an_error_not_browser_fallback(monkeypatch):
    monkeypatch.setattr(sys,'platform','linux')
    with pytest.raises(RuntimeError,match='Windows 11'):load_webview()


def test_source_desktop_shortcut_quotes_paths(tmp_path):
    root=tmp_path/'NEXUS with spaces'
    pythonw=root/'.venv'/'Scripts'/'pythonw.exe'
    pythonw.parent.mkdir(parents=True);pythonw.touch()
    target,args,working=shortcut_target(root)
    assert target==pythonw and args=='"'+str(root/'run.py')+'"' and working==root


def test_portable_shortcut_has_no_python_dependency(tmp_path):
    exe=tmp_path/'dist'/'NEXUS_AI_ULTRA'/'NEXUS_AI_ULTRA.exe'
    exe.parent.mkdir(parents=True);exe.touch()
    target,args,working=shortcut_target(tmp_path)
    assert target==exe and args=='' and working==exe.parent


def test_shortcut_rejects_missing_installation(tmp_path):
    with pytest.raises(RuntimeError,match='INSTALL'):shortcut_target(tmp_path)


def test_main_desktop_default_and_headless_alias(tmp_path,monkeypatch):
    import run
    monkeypatch.setenv('NEXUS_DATA_DIR',str(tmp_path))
    monkeypatch.setattr(run,'configure_logging',Mock())
    b=SimpleNamespace(prepare=Mock(),run=Mock(),close=Mock(),failure=None)
    factory=Mock(return_value=b);load=Mock(return_value=object());desktop=Mock()
    monkeypatch.setattr(run,'LocalBackend',factory)
    monkeypatch.setattr(run,'load_webview',load)
    monkeypatch.setattr(run,'run_desktop',desktop)
    assert run.main([])==0
    load.assert_called_once();desktop.assert_called_once_with(b,load.return_value)
    load.reset_mock();desktop.reset_mock()
    assert run.main(['--headless'])==0
    load.assert_not_called();desktop.assert_not_called();b.run.assert_called_once()
    assert run.main(['--no-browser'])==0


def test_gui_design_and_voice_output_preserved():
    import hashlib
    root=Path(__file__).resolve().parent.parent
    # Baseline includes the requested expanded AI Chat layout.
    expected = {'index.html': '1ab25a5286fe9dcba86cacd39da6b6437f60cd3cfb9694b4d2f37d2d7f1ba6e5', 'style.css': '0caf81930830b915d527da9d1adf8103f4237975dfbe2ee5b2c50334b5746192'}
    for name,digest in expected.items():
        content=(root/'static'/name).read_bytes()
        if name=='index.html':
            for script in ('accounts.js','whatsapp_ui.js'):content=content.replace(('<script src="/static/'+script+'"></script>').encode(),b'')
        assert hashlib.sha256(content).hexdigest()==digest
    speak=next(line for line in (root/'static/app.js').read_text(encoding='utf-8').splitlines() if line.startswith('function browserSpeak(text)'))
    assert hashlib.sha256(speak.replace('function browserSpeak','function speak').encode()).hexdigest()=='cafd9fc715762259b89d0b546c144af54b55f557edd4fe3175b7112d8363061d'


def test_real_backend_inside_desktop_host(tmp_path,monkeypatch):
    import importlib
    import httpx
    monkeypatch.setenv('NEXUS_DATA_DIR',str(tmp_path))
    import nexus.app
    importlib.reload(nexus.app)
    b=LocalBackend(tmp_path,port=0)
    checked=[]
    def native_loop_double(**kwargs):
        # Exercise the actual server and persistence during the mocked GUI loop.
        with httpx.Client(trust_env=False) as c:
            state=c.get(b.url+'/api/state').json()
            assert state['monitor']['pid']==os.getpid()
            r=c.post(b.url+'/api/records/memory',json={'text':'embedded-host-check'},headers={'x-nexus-token':state['token']})
            assert r.status_code==200
            assert c.get(b.url+'/').status_code==200
            assert any(m['text']=='embedded-host-check' for m in c.get(b.url+'/api/state').json()['memory'])
        checked.append(True)
    w=SimpleNamespace(settings={},create_window=Mock(return_value=object()),start=native_loop_double)
    run_desktop(b,w)
    assert checked and not b.thread.is_alive() and not b.pidfile.exists()
    with pytest.raises(httpx.HTTPError):httpx.get(b.url+'/api/state',timeout=.3,trust_env=False)
