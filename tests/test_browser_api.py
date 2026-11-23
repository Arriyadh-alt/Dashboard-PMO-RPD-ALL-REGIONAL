import json
from datetime import date

import pytest

from backend.analytics import build_analysis,prepare
from backend.browser_api import BrowserAPI,LocalEvents
from backend.store import Store
from scripts.build_pages import validate
from tests.fixtures import fixture_data


def browser(role='owner'):
    return BrowserAPI(fixture_data(),role,'synthetic-actor',{'fingerprint':'synthetic','loaded_at':'2026-11-23T00:00:00+00:00'})


@pytest.mark.parametrize('filters',[{}, {'reg':'Barat'}, {'statuses':['Done']},{'m0':1,'m1':1},{'ab':1,'kel':1}])
def test_browser_uses_identical_reviewed_analytics(tmp_path,filters):
    app=browser()
    actual=build_analysis(app.data,app.prepared,filters,app.store,app.role)
    expected=build_analysis(app.data,prepare(app.data),filters,Store(tmp_path/'state.sqlite3'),'owner')
    assert actual==expected


def test_local_history_mapping_followup_and_reports():
    app=browser()
    boot=app.request('/api/bootstrap')
    assert 'rec' not in boot['data']
    assert app.request('/api/analysis')['metrics']['canvassed']==9
    assert app.request('/api/admin/mappings','PUT',{'version':0,'values':{'0':{'st':1}}})['version']==1
    with pytest.raises(ValueError,match='changed'): app.request('/api/admin/mappings','PUT',{'version':0,'values':{}})
    row=app.request('/api/records/search','POST',{'outstanding_only':True})['rows'][0]
    payload={'pic':'Synthetic operator','status':'Done','action':'Synthetic resolution','resolution_notes':'Verified synthetic','case_started':date.today().isoformat()}
    app.request('/api/followups/'+row['ref'],'POST',payload)
    assert app.request('/api/followups/'+row['ref'])['events'][0]['payload']['status']=='Done'
    restored=BrowserAPI(fixture_data(),'owner','actor',app.info,app.store.events)
    assert restored.request('/api/followups/'+row['ref'])['events']==app.request('/api/followups/'+row['ref'])['events']
    assert restored.request('/api/analysis')['outstanding']['active_references']==5
    for extension in ['csv','xlsx']:
        assert app.request('/api/reports/executive.'+extension)['binary']
    assert app.request('/api/reports/executive.pdf')['pdf_model']['headers']


def test_browser_validation_and_presentation_role_are_not_misrepresented():
    app=browser('guest')
    assert app.bootstrap()['capabilities']['browser_only'] is True
    with pytest.raises(ValueError): app.request('/api/records/search','POST',{})
    with pytest.raises(ValueError): browser().request('/api/analysis?ab=999')
    with pytest.raises(ValueError): browser().request('/api/admin/rules')
    with pytest.raises(ValueError): LocalEvents([{'id':1,'payload':{}}])
    with pytest.raises(ValueError): validate(fixture_data())
