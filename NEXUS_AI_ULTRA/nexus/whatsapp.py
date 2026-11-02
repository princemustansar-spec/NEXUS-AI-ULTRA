"""Named-chat send in one NEXUS-owned WhatsApp WebView; one approval, one attempt."""
import json
from pathlib import Path
import re
import secrets
import threading
import time
import unicodedata
from urllib.parse import urlparse,urlencode

BRIDGE=(Path(__file__).resolve().parent.parent/'static/whatsapp_dom.js').read_text(encoding='utf-8')


def name_key(value):return ' '.join(re.sub(r'[\u200e\u200f\u202a-\u202e]','',unicodedata.normalize('NFKC',value)).casefold().split())


class WhatsApp:
    def __init__(self,clock=time.monotonic,sleep=time.sleep):
        self.host=self.window=None;self.lock=threading.RLock();self.paused=threading.Event()
        self.clock,self.sleep=clock,sleep;self.drafts={}

    def attach(self,host):
        self.host=host
        if host is None:self.close()

    def close(self):
        with self.lock:
            window,self.window=self.window,None;self.drafts.clear()
        if window:
            try:window.destroy()
            except Exception:pass

    def pause(self,value=True):
        if value:self.paused.set()
        else:self.paused.clear()
        if value:
            for draft in list(self.drafts.values()):
                if draft['state']=='prepared':draft['state']='cancelled'

    def _call(self,op,args=None):
        if op=='send' and self.paused.is_set():raise ValueError('Emergency Stop active.')
        if self.window is None:raise ValueError('Open the NEXUS WhatsApp window first.')
        url=urlparse(self.window.get_current_url() or '')
        if url.scheme!='https' or url.hostname!='web.whatsapp.com' or url.port not in (None,443) or url.username or url.password:
            raise ValueError('WhatsApp controls work only in the NEXUS window at https://web.whatsapp.com.')
        try:result=self.window.evaluate_js('('+BRIDGE+')('+json.dumps({'op':op,'args':args or {}})+')')
        except Exception as exc:raise ValueError('WhatsApp page could not be inspected. Check its window and retry preparation.') from None
        if not isinstance(result,dict) or result.get('status')=='wrong_origin':raise ValueError('WhatsApp page could not be verified.')
        return result

    def open(self):
        with self.lock:
            if self.host is None:raise ValueError('WhatsApp automation needs the native NEXUS desktop app.')
            if self.window is None:
                window=self.host.create_window('NEXUS WhatsApp','https://web.whatsapp.com/',width=1100,height=780,min_size=(800,600),js_api=None)
                if window is None:raise ValueError('Could not create the NEXUS WhatsApp window.')
                self.window=window
                def closed():
                    if self.window is window:self.window=None
                window.events.closed+=closed
                return {'status':'loading','sent':False,'message':'WhatsApp window opened. Scan its QR code once if required, then prepare the message.'}
            self.window.show()
            return self.status(page_only=True)

    def _ready(self):
        self.open();deadline=self.clock()+20
        while self.clock()<deadline:
            try:state=self._call('state')
            except ValueError:
                if self.window is None:raise
                self.sleep(.2);continue
            if state.get('status') in ('ready','login_required'):return state
            self.sleep(.2)
        return {'status':'loading','sent':False,'message':'WhatsApp is still loading. Check its window and retry.'}

    def _search(self,query):
        state=self._ready()
        if state.get('status')!='ready':return state
        started=self._call('search',{'query':query})
        if started.get('status')!='searching':return started
        begin=self.clock();deadline=begin+8;previous=None;stable=0
        while self.clock()<deadline:
            state=self._call('results',{'query':query})
            current=state.get('matches',[]);fingerprint=json.dumps(current,sort_keys=True)
            stable=stable+1 if fingerprint==previous else 0;previous=fingerprint
            if state.get('query')==query and stable>=2 and self.clock()-begin>=(.6 if current else 2):return state
            self.sleep(.2)
        return {'status':'blocked','reason':'Contact search did not settle. Retry in the WhatsApp window.'}

    def search(self,query):
        query=str(query).strip()
        if not query or len(query)>100:raise ValueError('Enter the contact name as saved in WhatsApp (up to 100 characters).')
        with self.lock:
            state=self._search(query)
            if state.get('status')!='ready':return {**state,'sent':False}
            return {'status':'matches' if state['matches'] else 'not_found','matches':state['matches'],'sent':False}

    def _trim(self):
        self.drafts={key:value for key,value in self.drafts.items() if value['expires']>self.clock()}
        if len(self.drafts)>=100:raise ValueError('Too many recent drafts. Wait for old drafts to expire.')

    def prepare(self,contact,message):
        contact,message=str(contact).strip(),str(message).replace('\r\n','\n').strip()
        if not contact or len(contact)>100 or not message or len(message)>4000:raise ValueError('Contact and a message of 1–4000 characters are required.')
        if re.search(r'[\x00-\x08\x0b\x0c\x0e-\x1f]',message):raise ValueError('Message contains unsupported control characters.')
        with self.lock:
            if self.paused.is_set():raise ValueError('Emergency Stop active.')
            self._trim();phone=re.sub(r'[+ ()-]','',contact)
            is_phone=phone.isdigit()
            if is_phone:
                if not re.fullmatch(r'[1-9]\d{6,14}',phone):raise ValueError('Use the full international number including country code.')
                state=self._ready()
                if state.get('status')!='ready':return {**state,'sent':False}
                self.window.load_url('https://web.whatsapp.com/send?'+urlencode({'phone':phone}))
            else:
                state=self._search(contact)
                if state.get('status')!='ready':return {**state,'sent':False}
                exact=[m for m in state.get('matches',[]) if name_key(m['name'])==name_key(contact)]
                if len(exact)!=1:return {'status':'ambiguous' if len(exact)>1 else 'exact_name_required' if state.get('matches') else 'not_found','matches':state.get('matches',[]),'sent':False,'message':'Use the exact unique saved name, or provide the international number. No contact was guessed.'}
                selected=self._call('select',{'contact':exact[0]['name']})
                if selected.get('status')!='selected':return {**selected,'sent':False}
                contact=exact[0]['name']
            deadline=self.clock()+12;previous=None;stable=0
            while self.clock()<deadline:
                try:state=self._call('state')
                except ValueError:self.sleep(.2);continue
                valid=state.get('status')=='ready' and state.get('recipient_id') and state.get('composer') is not None
                if is_phone:valid=valid and state['recipient_id'].split('@')[0]==phone and state['recipient_id'].endswith(('@c.us','@s.whatsapp.net'))
                else:valid=valid and name_key(state.get('recipient',''))==name_key(contact)
                identity=(state.get('session'),state.get('recipient'),state.get('recipient_id'))
                stable=stable+1 if valid and identity==previous else 0;previous=identity
                if valid and stable>=2:break
                self.sleep(.2)
            else:return {'status':'blocked','sent':False,'reason':'Could not verify a stable chat identity. Open the exact chat with existing history and retry; no message was sent.'}
            for old_id,old in self.drafts.items():
                if old['recipient_id']==state['recipient_id'] and old['message']==message and old['state'] not in ('prepared','cancelled','blocked'):
                    return {'status':'already_attempted','draft_id':old_id,'sent':old.get('receipt',{}).get('sent'),'retry_allowed':False,'message':'This message already has a send attempt. Check its status; do not resend automatically.'}
            pinned={k:state[k] for k in ('session','recipient','recipient_id')}
            self._call('scroll_bottom')
            self.sleep(.3);state=self._call('state')
            if not state.get('at_bottom') or any(state.get(k)!=v for k,v in pinned.items()):return {'status':'blocked','sent':False,'reason':'Latest chat history could not be verified. Scroll to the bottom and prepare again.'}
            draft={k:state[k] for k in ('session','recipient','recipient_id')};draft.update(message=message,approval_before=[m['id'] for m in state.get('outgoing',[]) if m.get('id')])
            composed=self._call('compose',draft)
            if composed.get('status')!='composed' or composed.get('composer')!=message:return {'status':'blocked','sent':False,'reason':composed.get('reason','Exact composer text was not verified.')}
            if self.paused.is_set():raise ValueError('Emergency Stop active.')
            ident=secrets.token_urlsafe(24);self.drafts[ident]={**draft,'state':'prepared','expires':self.clock()+300,'before':[],'sent_message_id':None}
            return {'status':'draft_prepared',**self.approval(ident),'sent':False,'message_preview':message,'confirmation_required':True,'next_step':'whatsapp_send'}

    def approval(self,ident):
        with self.lock:
            draft=self.drafts.get(ident)
            if not draft or draft['expires']<=self.clock() or draft['state']!='prepared':raise ValueError('WhatsApp draft expired, changed, or already attempted. Prepare a fresh message.')
            return {'draft_id':ident,**{k:draft[k] for k in ('recipient','recipient_id','message')}}

    def cancel_draft(self,ident):
        with self.lock:
            draft=self.drafts.get(ident)
            if draft and draft['state']=='prepared':draft['state']='cancelled'

    def verify_approval(self,args):
        if args!=self.approval(args.get('draft_id','')):raise ValueError('WhatsApp approval details changed. Prepare again.')

    def _receipt(self,ident):
        draft=self.drafts[ident];state=self._call('state')
        if any(state.get(k)!=draft[k] for k in ('session','recipient','recipient_id')):return {'status':'unknown','sent':None,'reason':'Chat changed; check WhatsApp manually.'}
        matches=[m for m in state.get('outgoing',[]) if m.get('id') and m['id'] not in draft['before'] and m.get('text')==draft['message']]
        if draft['sent_message_id']:matches=[m for m in matches if m['id']==draft['sent_message_id']]
        if len(matches)!=1:return {'status':'unknown','sent':None,'reason':'A unique new outgoing message has not been verified.'}
        row=matches[0];draft['sent_message_id']=row['id'];icon=row.get('icon')
        if icon in ('msg-check','msg-dblcheck','msg-dblcheck-ack'):
            return {'status':'sent_verified','sent':True,'delivery_verified':icon!='msg-check','message_id':row['id']}
        return {'status':'failed' if icon=='msg-error' else 'pending','sent':False if icon=='msg-error' else None,'delivery_verified':False,'message_id':row['id']}

    def send(self,ident):
        with self.lock:
            self.approval(ident)
            if self.paused.is_set():raise ValueError('Emergency Stop active.')
            draft=self.drafts[ident]
            if any(other is not draft and other['expires']>self.clock() and other['state']=='attempted' and other['recipient_id']==draft['recipient_id'] and other['message']==draft['message'] for other in self.drafts.values()):
                raise ValueError('This message already has a send attempt. Check WhatsApp; do not resend automatically.')
            draft['state']='attempted';draft['receipt']={'status':'unknown','sent':None,'reason':'Send result not yet verified.'}
            try:
                result=self._call('send',draft)
                if result.get('clicked') is not True:
                    draft['state']='blocked';draft['receipt']={'status':'blocked','sent':False,'reason':result.get('reason','Send was blocked.')}
                    return draft['receipt']
                draft['before']=result.get('before',[])
                deadline=self.clock()+10
                while self.clock()<deadline:
                    receipt=self._receipt(ident);draft['receipt']=receipt
                    if receipt['status'] in ('sent_verified','failed'):break
                    if self.paused.is_set():break
                    self.sleep(.25)
            except Exception:
                draft['receipt']={'status':'unknown','sent':None,'reason':'Send outcome could not be verified. Check WhatsApp; do not automatically resend.'}
            return {**draft['receipt'],'draft_id':ident,'recipient':draft['recipient'],'retry_allowed':False}

    def status(self,ident='',page_only=False):
        with self.lock:
            if not ident and not page_only:
                recent=[key for key,value in self.drafts.items() if value['expires']>self.clock() and value['state']=='attempted']
                if recent:ident=recent[-1]
            if ident:
                draft=self.drafts.get(ident)
                if not draft or draft['expires']<=self.clock():raise ValueError('WhatsApp draft/status expired.')
                if draft['state']=='prepared':return {'status':'draft_prepared',**self.approval(ident),'sent':False}
                if draft['state']=='attempted':
                    try:
                        latest=self._receipt(ident)
                        if latest.get('sent') is not None or draft.get('receipt',{}).get('sent') is not True:draft['receipt']=latest
                    except ValueError:pass
                return {**draft.get('receipt',{'status':draft['state'],'sent':False}),'draft_id':ident,'retry_allowed':False}
            if self.window is None:return {'status':'closed','available':self.host is not None,'sent':False}
            try:state=self._call('state');return {k:state[k] for k in ('status','reason','recipient') if k in state}
            except ValueError:return {'status':'loading','message':'Check the NEXUS WhatsApp window.'}


whatsapp=WhatsApp()
