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


def test_locked_history_reports_disclose_source_only_calculations():
    app=browser()
    app.info['history_locked']=True
    assert any('Source-only' in line for line in app.request('/api/reports/executive.pdf')['pdf_model']['metadata'])


def test_mapping_survives_absent_surveyor_and_current_roster_edits():
    app=browser()
    app.request('/api/admin/mappings','PUT',{'version':0,'values':{'1':{'st':1}}})
    daily=fixture_data()
    daily['svs'][1]='FIXTURE TEMPORARY SURVEYOR C'
    absent=BrowserAPI(daily,'owner','actor',app.info,app.store.events)
    absent.request('/api/admin/mappings','PUT',{'version':1,'values':{'0':{'kl':'Fixture Team B'}}})
    assert absent.store.latest('mapping')['all']['FIXTURE SURVEYOR B']=={'st':1}
    # Resetting the current editor clears current-roster edits, not archived names.
    absent.request('/api/admin/mappings','PUT',{'version':2,'values':{}})
    returned=BrowserAPI(fixture_data(),'owner','actor',app.info,absent.store.events)
    assert returned.bootstrap()['overrides']=={'1':{'st':1}}


def test_returned_surveyor_retired_coordinator_does_not_block_unrelated_edits():
    app=browser()
    app.request('/api/admin/mappings','PUT',{'version':0,'values':{'1':{'kl':'Fixture Team B','st':1}}})
    daily=fixture_data()
    daily['svs'][1]='FIXTURE TEMPORARY SURVEYOR C'
    daily['meta']['korlaps']=['Fixture Team A','Fixture Team C']
    daily['kl'][1]='Fixture Team C'
    absent=BrowserAPI(daily,'owner','actor',app.info,app.store.events)
    absent.request('/api/admin/mappings','PUT',{'version':1,'values':{'0':{'st':2}}})
    daily['svs'][1]='FIXTURE SURVEYOR B'
    returned=BrowserAPI(daily,'owner','actor',app.info,absent.store.events)
    values=returned.bootstrap()['overrides']
    values['0']={'kl':'Fixture Team C'}
    returned.request('/api/admin/mappings','PUT',{'version':2,'values':values})
    assert returned.bootstrap()['overrides']['1']=={'kl':'Fixture Team B','st':1}
    assert returned.bootstrap()['overrides']['0']=={'kl':'Fixture Team C'}
    for invalid in [{'0':{'kl':'Fixture Team B'}},{'0':{'kl':None}},{'0':{'kl':123}},{'1':{'st':True}}]:
        with pytest.raises(ValueError,match='coordinator/status'):
            returned.request('/api/admin/mappings','PUT',{'version':3,'values':invalid})
    # Moving the archived assignment to a current coordinator removes its exemption.
    returned.request('/api/admin/mappings','PUT',{'version':3,'values':{'1':{'kl':'Fixture Team C'}}})
    with pytest.raises(ValueError,match='coordinator/status'):
        returned.request('/api/admin/mappings','PUT',{'version':4,'values':{'1':{'kl':'Fixture Team B'}}})
