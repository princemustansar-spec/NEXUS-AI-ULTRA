"""Real WebView2 DOM/driver test on a mapped local fixture; no real WhatsApp account."""
from pathlib import Path
import sys
import tempfile
import time
import traceback
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))


def main():
    import webview
    from nexus.whatsapp import WhatsApp
    from diagnostics.whatsapp_layout import capture
    errors=[]
    fixtures=Path(__file__).resolve().parent/'fixtures/whatsapp'
    with tempfile.TemporaryDirectory(prefix='nexus-wa-native-',ignore_cleanup_errors=True) as directory:
        # WebView2 need not raise NavigationCompleted for its initial about:blank.
        window=webview.create_window('NEXUS WhatsApp LOCAL FIXTURE',html='<html><body>Local fixture bootstrap</body></html>',width=950,height=650,js_api=None)
        wa=WhatsApp();wa.attach(webview)
        def run():
            try:
                assert window.events.loaded.wait(40),'Local HTML WebView2 did not initialize'
                from System import Action
                from Microsoft.Web.WebView2.Core import CoreWebView2HostResourceAccessKind
                def mapping():
                    window.native.webview.CoreWebView2.SetVirtualHostNameToFolderMapping('web.whatsapp.com',str(fixtures),CoreWebView2HostResourceAccessKind.DenyCors)
                window.native.Invoke(Action(mapping))
                window.load_url('https://web.whatsapp.com/index.html')
                deadline=time.monotonic()+15
                while time.monotonic()<deadline:
                    try:
                        if window.evaluate_js("document.body?.dataset.nexusWaFixture==='true'"):break
                    except Exception:pass
                    time.sleep(.1)
                else:raise AssertionError('Local fixture marker missing; never run messaging automation on an unverified page')
                nested=(fixtures/'nested.js').read_text(encoding='utf-8')
                assert window.evaluate_js('('+nested+')()') is True
                opaque=(fixtures/'opaque.js').read_text(encoding='utf-8')
                assert window.evaluate_js('('+opaque+')()') is True
                assert window.evaluate_js("document.querySelectorAll('#history .message-in,#history .message-out').length")==0
                layout=capture(window)
                assert layout['main']['prefixed_ids']==0 and layout['main']['data_ids']==22 and layout['main']['message_containers']==22 and layout['main']['message_classes']==0
                import json
                safe=json.dumps(layout)
                assert '12025550101' not in safe and 'Nexus Test Contact' not in safe and 'Old message' not in safe
                assert window.evaluate_js('window.clicks')==0
                # Only attach after proving this page is the isolated local fixture.
                wa.window=window
                draft=wa.prepare('Nexus Test Contact','Fixture message only')
                assert draft['status']=='draft_prepared',draft
                assert draft['recipient_phone']=='+12025550101' and draft['recipient_id']=='phone:+12025550101',draft
                private_safe=json.dumps(capture(window))
                assert '12025550101' not in private_safe and 'Nexus Test Contact' not in private_safe
                assert window.evaluate_js('window.clicks')==0,'Preparation must never send'
                approval=wa.approval(draft['draft_id']);wa.verify_approval(approval)
                sent=wa.send(draft['draft_id'])
                assert sent['sent'] is True and sent['delivery_verified'] is False,sent
                assert window.evaluate_js('window.clicks')==1
                try:wa.send(draft['draft_id']);raise AssertionError('Consumed draft was sent twice')
                except ValueError:pass
                fresh=wa.prepare('Nexus Test Contact','Second local fixture draft')
                assert fresh['status']=='draft_prepared',fresh
                window.evaluate_js("document.querySelector('#composer').textContent='User edited this draft'")
                blocked=wa.send(fresh['draft_id'])
                assert blocked['sent'] is False and window.evaluate_js('window.clicks')==1,blocked
                print('Native WebView2 LOCAL FIXTURE: 22 opaque IDs with no legacy prefixes/classes, live Contact info phone, exact approval, one send/tick, replay and edited-draft guards passed; no real account/messages',flush=True)
            except BaseException:
                errors.append(traceback.format_exc());print(errors[-1],flush=True)
            finally:
                wa.window=None
                window.destroy()
        webview.start(run,gui='edgechromium',private_mode=True,storage_path=str(Path(directory)/'profile'))
    if errors:raise SystemExit(1)


if __name__=='__main__':main()
