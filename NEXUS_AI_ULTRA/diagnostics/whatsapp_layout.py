"""Run the installed NEXUS and inspect WhatsApp layout metadata on Enter.

No app update, debug port, chat text, contact names, raw identifiers or cookies.
The installed app otherwise runs normally with its existing settings/profile.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile
import threading
import time
from urllib.parse import urlparse

LAYOUT_JS = r"""(()=>{
 'use strict';
 if(location.origin!=='https://web.whatsapp.com')return {origin_ok:false};
 const main=document.querySelector('#main');
 const count=(root,selector)=>root?root.querySelectorAll(selector).length:0;
 const shape=value=>({prefix:value.startsWith('true_')?'true':value.startsWith('false_')?'false':'other',has_chat_suffix:/@(?:c\.us|s\.whatsapp\.net|g\.us|lid)(?:_|$)/.test(value),pattern:value.replace(/[A-Za-z]+/g,'a').replace(/\d+/g,'0').replace(/[^a0@._:+-]/g,'?').slice(0,70)});
 const counts=root=>{
  const ids=[...(root?.querySelectorAll('[data-id]')||[])];
  return {data_ids:ids.length,prefixed_ids:ids.filter(e=>/^(true|false)_/.test(e.getAttribute('data-id')||'')).length,
   message_classes:count(root,'.message-in,.message-out'),message_containers:count(root,'[data-testid="msg-container"]'),
   pre_plain_text:count(root,'[data-pre-plain-text]'),selectable_text:count(root,'.selectable-text'),copyable_text:count(root,'.copyable-text'),
   rows:count(root,'[role="row"]'),listitems:count(root,'[role="listitem"]'),
   headers:count(root,'header'),editors:count(root,'footer [contenteditable="true"]'),
   alternate_ids:count(root,'[data-message-id],[data-msg-id]')};
 };
 const roles=new Set(['row','grid','group','listitem','document','textbox','button','application','presentation','list','log']);
 const describe=e=>({tag:e.tagName.toLowerCase(),role:roles.has(e.getAttribute('role'))?e.getAttribute('role'):e.hasAttribute('role')?'other':null,
  in_main:!!main?.contains(e),data_attributes:[...e.attributes].map(a=>a.name).filter(n=>/^data-[a-z][a-z_-]{0,45}$/.test(n)).slice(0,12),
  id_shape:e.hasAttribute('data-id')?shape(e.getAttribute('data-id')):null});
 const candidates=root=>{
  if(!root)return [];
  let els=[...root.querySelectorAll('[data-pre-plain-text],[data-testid="msg-container"]')];
  if(!els.length)els=[...root.querySelectorAll('.selectable-text,[data-id]')];
  return els.slice(0,2).map(e=>{const chain=[];for(let i=0;e&&i<5;i++,e=e.parentElement)chain.push(describe(e));return chain;});
 };
 const nodes=[...document.querySelectorAll('*')].slice(0,16000),shadow=nodes.filter(e=>e.shadowRoot).slice(0,6);
 const frames=[...document.querySelectorAll('iframe')].slice(0,6).map(e=>{try{return {readable:!!e.contentDocument,counts:e.contentDocument?counts(e.contentDocument):null};}catch(_){return {readable:false};}});
 return {origin_ok:true,visibility:document.visibilityState,has_focus:document.hasFocus(),ready_state:document.readyState,
  main_found:!!main,document:counts(document),main:counts(main),
  main_samples:candidates(main),document_samples:candidates(document),
  shadow_roots:shadow.map(e=>({host:describe(e),counts:counts(e.shadowRoot)})),frames};
})()"""

def capture(window):
    url=urlparse(window.get_current_url() or '')
    if url.scheme!='https' or url.hostname!='web.whatsapp.com' or url.port not in (None,443) or url.username or url.password:
        raise ValueError('Only the NEXUS window at https://web.whatsapp.com can be inspected.')
    value=window.evaluate_js(LAYOUT_JS)
    if not isinstance(value,dict) or value.get('origin_ok') is not True:raise ValueError('WhatsApp origin could not be verified.')
    return value

def report(root,window):
    before=capture(window)
    # Bring the same window forward to distinguish an occluded/virtualized view.
    window.show();time.sleep(.8)
    focused=capture(window)
    bridge=Path(root)/'static/whatsapp_dom.js'
    return {'report_version':1,'bridge_sha256':hashlib.sha256(bridge.read_bytes()).hexdigest() if bridge.is_file() else 'missing',
            'before_focus':{key:before[key] for key in ('visibility','has_focus','main','document') if key in before},'observed':focused}

def main(argv=None):
    parser=argparse.ArgumentParser(description='Read-only WhatsApp layout support runner.')
    parser.add_argument('--installation',required=True,type=Path)
    parser.add_argument('--output',type=Path,default=Path(tempfile.gettempdir())/'nexus-whatsapp-layout.json')
    args=parser.parse_args(argv);root=args.installation.resolve()
    if not (root/'run.py').is_file() or not (root/'nexus/whatsapp.py').is_file():parser.error('Choose the installed NEXUS source folder.')
    sys.path.insert(0,str(root));os.chdir(root)
    from nexus.whatsapp import whatsapp
    import run
    def inspect():
        print('\nNEXUS WhatsApp mein purani chat kholein, jis mein messages nazar aate hon.\nPhir is PowerShell window mein wapas aa kar Enter dabayein.\n',flush=True)
        while True:
            try:
                input()
                if whatsapp.window is None:
                    print('Open WhatsApp Center -> Open WhatsApp first, then press Enter again.',flush=True);continue
                data=report(root,whatsapp.window)
                if not data['observed']['main']['headers'] or not data['observed']['main']['editors']:
                    print('Open a chat with a visible header and message input, then press Enter again.',flush=True);continue
                args.output.write_text(json.dumps(data,ensure_ascii=True,indent=2),encoding='utf-8')
                print('\nNEXUS_LAYOUT_REPORT_START\n'+json.dumps(data,ensure_ascii=True,indent=2)+'\nNEXUS_LAYOUT_REPORT_END\nSaved: '+str(args.output)+'\nClose NEXUS when finished.',flush=True)
                return
            except (EOFError,KeyboardInterrupt):return
            except Exception as exc:print('Layout capture did not complete: '+type(exc).__name__+'. Check the WhatsApp window, then press Enter again.',flush=True)
    threading.Thread(target=inspect,daemon=True,name='WhatsApp-layout-support').start()
    return run.main(['--gui'])

if __name__=='__main__':raise SystemExit(main())
