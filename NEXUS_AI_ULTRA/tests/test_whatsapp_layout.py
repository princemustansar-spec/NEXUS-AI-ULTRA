from types import SimpleNamespace
from unittest.mock import Mock
import pytest
from diagnostics.whatsapp_layout import capture,report

@pytest.mark.parametrize('url',['http://web.whatsapp.com/','https://evil.test/','https://web.whatsapp.com.evil.test/','https://web.whatsapp.com:444/'])
def test_layout_capture_rejects_other_origins_without_evaluation(url):
    evaluate=Mock();window=SimpleNamespace(get_current_url=lambda:url,evaluate_js=evaluate)
    with pytest.raises(ValueError):capture(window)
    evaluate.assert_not_called()

def test_layout_report_compares_focus_and_hashes_installed_bridge(tmp_path,monkeypatch):
    (tmp_path/'static').mkdir();(tmp_path/'static/whatsapp_dom.js').write_text('fixture bridge')
    before={'origin_ok':True,'visibility':'visible','has_focus':False,'main':{'data_ids':0},'document':{'data_ids':2}}
    after={**before,'has_focus':True}
    window=SimpleNamespace(get_current_url=lambda:'https://web.whatsapp.com/',evaluate_js=Mock(side_effect=[before,after]),show=Mock())
    monkeypatch.setattr('diagnostics.whatsapp_layout.time.sleep',lambda n:None)
    data=report(tmp_path,window)
    assert data['before_focus']['has_focus'] is False and data['observed']['has_focus'] is True
    assert len(data['bridge_sha256'])==64;window.show.assert_called_once()
