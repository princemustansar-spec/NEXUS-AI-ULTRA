import importlib
import threading
from types import SimpleNamespace
from unittest.mock import Mock
import pytest
from fastapi.testclient import TestClient
from nexus.whatsapp import WhatsApp


class Clock:
    def __init__(self):self.value=0
    def now(self):return self.value
    def sleep(self,n):self.value+=n


class Fixture(WhatsApp):
    def __init__(self,names=None,icon='msg-check'):
        self.timer=Clock();super().__init__(self.timer.now,self.timer.sleep)
        self.names=names or ['Saad Cheema'];self.recipient='Saad Cheema';self.thread='923001234567@c.us'
        self.composer='';self.session='session-one';self.icon=icon;self.clicks=0;self.outgoing=[];self.block=False;self.fail_after_click=False
    def open(self):return {'status':'ready'}
    def _call(self,op,args=None):
        args=args or {}
        if op=='search':self.query=args['query'];return {'status':'searching'}
        if op=='results':return {'status':'ready','query':self.query,'matches':[{'name':n} for n in self.names if self.query.casefold() in n.casefold()]}
        if op=='select':self.recipient=args['contact'];return {'status':'selected'}
        state={'status':'ready','session':self.session,'recipient':self.recipient,'recipient_id':self.thread,'composer':self.composer,'at_bottom':True,'outgoing':list(self.outgoing)}
        if op in ('state','scroll_bottom'):return state
        if op=='compose':
            if self.composer and self.composer!=args['message']:return {'status':'blocked','reason':'Existing unsent draft protected'}
            self.composer=args['message'];return {**state,'status':'composed','composer':self.composer}
        if op=='send':
            if self.block or self.composer!=args['message'] or self.session!=args['session'] or self.thread!=args['recipient_id'] or self.recipient!=args['recipient']:
                return {'clicked':False,'reason':'Draft or recipient changed'}
            before=[m['id'] for m in self.outgoing];self.clicks+=1
            if self.fail_after_click:raise ValueError('Lost connection after click')
            self.outgoing.append({'id':'new-'+str(self.clicks),'text':self.composer,'icon':self.icon});self.composer=''
            return {'clicked':True,'before':before}
        raise AssertionError(op)


def test_prepare_exact_contact_then_single_confirmed_send_and_observed_ticks():
    wa=Fixture();draft=wa.prepare('saad cheema','Kidhar ho?')
    assert draft['status']=='draft_prepared' and draft['recipient']=='Saad Cheema' and not draft['sent']
    assert wa.clicks==0 and 'approval_required' not in draft
    review=wa.approval(draft['draft_id']);assert review['message']=='Kidhar ho?' and review['recipient_id']==wa.thread
    wa.verify_approval(review)
    receipt=wa.send(draft['draft_id'])
    assert receipt['sent'] is True and receipt['delivery_verified'] is False and wa.clicks==1
    with pytest.raises(ValueError,match='attempted'):wa.send(draft['draft_id'])


@pytest.mark.parametrize('names,status',[(['Saad Cheema','Saad Cheema'],'ambiguous'),(['Saad Cheema Work'],'exact_name_required'),(['Someone Else'],'not_found')])
def test_search_never_guesses_duplicates_or_partial_names(names,status):
    wa=Fixture(names);result=wa.prepare('Saad Cheema','hello')
    assert result['status']==status and wa.clicks==0 and wa.composer==''


def test_existing_user_draft_is_protected():
    wa=Fixture();wa.composer='My unsent draft';result=wa.prepare('Saad Cheema','Different message')
    assert result['status']=='blocked' and wa.composer=='My unsent draft' and wa.clicks==0


@pytest.mark.parametrize('change',['composer','recipient','thread','session'])
def test_changes_after_preparation_block_send(change):
    wa=Fixture();draft=wa.prepare('Saad Cheema','hello')
    setattr(wa,change,'changed')
    result=wa.send(draft['draft_id']);assert result['sent'] is False and wa.clicks==0


def test_unknown_attempt_is_never_retried_even_with_new_preparation():
    wa=Fixture();draft=wa.prepare('Saad Cheema','hello');wa.fail_after_click=True
    result=wa.send(draft['draft_id']);assert result['sent'] is None and wa.clicks==1
    assert wa.prepare('Saad Cheema','hello')['status']=='already_attempted'
    with pytest.raises(ValueError):wa.send(draft['draft_id'])
    assert wa.clicks==1


def test_duplicate_approved_drafts_cannot_send_the_same_message_twice():
    wa=Fixture();one=wa.prepare('Saad Cheema','hello');two=wa.prepare('Saad Cheema','hello')
    assert wa.send(one['draft_id'])['sent']
    with pytest.raises(ValueError,match='already has a send attempt'):wa.send(two['draft_id'])
    assert wa.clicks==1


@pytest.mark.parametrize('icon,status,sent,delivered',[('msg-time','pending',None,False),('msg-error','failed',False,False),('msg-dblcheck','sent_verified',True,True)])
def test_receipt_distinguishes_pending_failure_and_delivery(icon,status,sent,delivered):
    wa=Fixture(icon=icon);draft=wa.prepare('Saad Cheema','hello');result=wa.send(draft['draft_id'])
    assert result['status']==status and result['sent'] is sent and result.get('delivery_verified') is delivered
    assert wa.clicks==1
    if icon=='msg-time':
        wa.outgoing[-1]['icon']='msg-check'
        assert wa.status(draft['draft_id'])['sent'] is True and wa.clicks==1


def test_expiry_denial_and_emergency_stop_never_click_send():
    wa=Fixture();draft=wa.prepare('Saad Cheema','hello');wa.timer.sleep(301)
    with pytest.raises(ValueError):wa.send(draft['draft_id'])
    wa=Fixture();draft=wa.prepare('Saad Cheema','hello');wa.cancel_draft(draft['draft_id'])
    with pytest.raises(ValueError):wa.send(draft['draft_id'])
    wa.pause()
    with pytest.raises(ValueError,match='Emergency'):wa.prepare('Saad Cheema','hello')
    assert wa.clicks==0


def test_review_metadata_cannot_be_replaced_with_a_different_message():
    wa=Fixture();draft=wa.prepare('Saad Cheema','hello');review=wa.approval(draft['draft_id'])
    with pytest.raises(ValueError,match='changed'):wa.verify_approval({**review,'message':'different'})
    assert wa.clicks==0


def test_native_origin_is_rechecked_before_any_dom_script():
    wa=WhatsApp();evaluate=Mock()
    wa.window=SimpleNamespace(get_current_url=lambda:'https://evil.example/',evaluate_js=evaluate)
    with pytest.raises(ValueError,match='only'):wa._call('send',{})
    evaluate.assert_not_called()


def test_approval_route_shows_exact_details_and_requires_one_use_token(tmp_path,monkeypatch):
    monkeypatch.setenv('NEXUS_DATA_DIR',str(tmp_path))
    import nexus.app
    app=importlib.reload(nexus.app);wa=Fixture()
    monkeypatch.setattr(app,'whatsapp',wa)
    import nexus.whatsapp as module
    monkeypatch.setattr(module,'whatsapp',wa)
    with TestClient(app.app) as c:
        assert c.post('/api/tools/whatsapp_send',json={'draft_id':'forged'}).status_code==403
        c.headers['x-nexus-token']=app.session_token
        prepared=c.post('/api/tools/whatsapp_prepare',json={'contact':'Saad Cheema','message':'Kidhar ho?'}).json()['result']
        body={'draft_id':prepared['draft_id']};queued=c.post('/api/tools/whatsapp_send',json=body).json()
        assert queued['approval_required'] and queued['args']['message']=='Kidhar ho?' and queued['args']['recipient']=='Saad Cheema'
        assert c.post('/api/tools/whatsapp_send',json=body).json()['id']==queued['id']
        assert wa.clicks==0 and len(app.pending)==1
        sent=c.post('/api/approvals/'+queued['id'],json={'approve':True}).json()['result']
        assert sent['sent'] and wa.clicks==1
        assert c.post('/api/approvals/'+queued['id'],json={'approve':True}).status_code==400
        assert wa.clicks==1
    app.store.db.close()


def test_cached_acceptance_is_not_erased_when_the_user_moves_to_another_chat():
    wa=Fixture();draft=wa.prepare('Saad Cheema','hello');assert wa.send(draft['draft_id'])['sent']
    wa.recipient='Other Contact';wa.thread='9999999@c.us'
    assert wa.status()['sent'] is True and wa.clicks==1


def test_denial_invalidates_prepared_draft_and_permission_denial_blocks_send(tmp_path,monkeypatch):
    monkeypatch.setenv('NEXUS_DATA_DIR',str(tmp_path))
    import nexus.app
    app=importlib.reload(nexus.app);wa=Fixture()
    monkeypatch.setattr(app,'whatsapp',wa)
    import nexus.whatsapp as module
    monkeypatch.setattr(module,'whatsapp',wa)
    with TestClient(app.app) as c:
        c.headers['x-nexus-token']=app.session_token
        draft=wa.prepare('Saad Cheema','hello')
        approval=c.post('/api/tools/whatsapp_send',json={'draft_id':draft['draft_id']}).json()
        assert c.post('/api/approvals/'+approval['id'],json={'approve':False}).json()['denied']
        with pytest.raises(ValueError):wa.send(draft['draft_id'])
        wa.composer=''  # User clears the cancelled draft before preparing different text.
        second=wa.prepare('Saad Cheema','hello again')
        app.store.set('denied_tools',['whatsapp_send'])
        assert c.post('/api/tools/whatsapp_send',json={'draft_id':second['draft_id']}).status_code==400
        assert wa.clicks==0
    app.store.db.close()
