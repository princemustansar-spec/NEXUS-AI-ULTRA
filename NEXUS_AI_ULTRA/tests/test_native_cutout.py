from types import SimpleNamespace
from unittest.mock import Mock
from nexus.avatar import FloatingAvatar, apply_form_cutout
from create_shortcut import shortcut_target


def test_native_glass_keeps_form_input_without_a_transparency_key(monkeypatch):
    monkeypatch.setattr('nexus.avatar.extend_native_glass',Mock())
    form=SimpleNamespace(webview=SimpleNamespace(),Handle=SimpleNamespace(ToInt64=lambda:123),Invalidate=Mock())
    key,transparent,empty=object(),object(),object()
    apply_form_cutout(form,key,transparent,empty)
    assert form.AllowTransparency
    assert form.BackColor is key and form.TransparencyKey is empty
    assert form.webview.BackColor is key and form.webview.DefaultBackgroundColor is transparent
    form.Invalidate.assert_called_once()


def test_showing_from_gui_does_not_hide_the_dashboard():
    class Event:
        def __iadd__(self,fn):return self
    main=SimpleNamespace(hide=Mock(),show=Mock(),restore=Mock())
    window=SimpleNamespace(events=SimpleNamespace(closed=Event()),show=Mock(),destroy=Mock())
    host=SimpleNamespace(create_window=Mock(return_value=window))
    a=FloatingAvatar();a.attach(host,main,'http://127.0.0.1:8765/static/avatar.html')
    a.show();a.show();main.hide.assert_not_called()
    assert host.create_window.call_args.kwargs['background_color']=='#010203'
    a.attach(None)


def test_repaired_source_shortcut_does_not_use_a_retained_old_exe(tmp_path):
    pythonw=tmp_path/'.venv/Scripts/pythonw.exe';pythonw.parent.mkdir(parents=True);pythonw.touch()
    (tmp_path/'run.py').write_text('')
    old=tmp_path/'dist/NEXUS_AI_ULTRA/NEXUS_AI_ULTRA.exe';old.parent.mkdir(parents=True);old.touch()
    target,args,working=shortcut_target(tmp_path,prefer_source=True)
    assert target==pythonw and args=='"'+str(tmp_path/'run.py')+'"' and working==tmp_path


def test_cutout_is_applied_on_the_native_ui_thread(monkeypatch):
    import sys
    import nexus.avatar as module
    key,transparent,empty=object(),object(),object()
    color=SimpleNamespace(Black=key,Transparent=transparent,Empty=empty)
    monkeypatch.setattr(module,'extend_native_glass',Mock())
    monkeypatch.setitem(sys.modules,'System',SimpleNamespace(Action=lambda fn:fn))
    monkeypatch.setitem(sys.modules,'System.Drawing',SimpleNamespace(Color=color))
    form=SimpleNamespace(webview=SimpleNamespace(),Handle=SimpleNamespace(ToInt64=lambda:123),InvokeRequired=True,BeginInvoke=Mock(side_effect=lambda fn:fn()),Invalidate=Mock())
    window=SimpleNamespace(native=form)
    a=FloatingAvatar();a.window=window
    with monkeypatch.context() as patch:
        patch.setattr(module.sys,'platform','win32')
        assert a.configure_cutout(window)
    assert a.cutout_ready
    form.BeginInvoke.assert_called_once()
    assert form.TransparencyKey is empty and form.webview.DefaultBackgroundColor is transparent
