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


def test_case_search_and_sort_cover_all_pages_before_slicing():
    source=fixture_data()
    source['rec']={key:[values[0]]*120 for key,values in source['rec'].items()}
    source['rec']['pam']=list(range(10000000,10000120))
    source['rec']['tg']=list(range(120))
    source['rec']['tg'][-1]=10000
    source['rec']['c1']=[source['dic']['c1'].index('Berminat')]*120
    pending=source['dic']['kf'].index('Outstanding')
    source['rec']['kf']=[pending]*120
    app=BrowserAPI(source,'owner','synthetic-actor',{})
    first=app.request('/api/records/search','POST',dict(limit=50))
    assert first['total']==120 and len(first['rows'])==50
    match=app.request('/api/records/search','POST',dict(query='10000119',outstanding_only=True))
    assert match['total']==1 and int(match['rows'][0]['pam'])==10000119
    ordered=[]
    for offset in (0,50,100):
        result=app.request('/api/records/search','POST',dict(sort='pam',descending=True,offset=offset,limit=50))
        assert result['total']==120
        ordered.extend(int(row['pam']) for row in result['rows'])
    assert ordered==list(range(10000119,9999999,-1))
    assert app.request('/api/records/search','POST',dict(sort='arrears',descending=True,limit=1))['rows'][0]['arrears']==10000
    assert app.request('/api/records/search','POST',dict(query='10.000'))['total']==1
    assert app.request('/api/records/search','POST',dict(query='Belum dicatat'))['total']==120
    app.store.append('followup',match['rows'][0]['ref'],'synthetic-actor',dict(pic='Petugas akhir',status='Proses',target_date='2026-11-30'))
    assert app.request('/api/records/search','POST',dict(query='petugas akhir'))['total']==1
    assert app.request('/api/records/search','POST',dict(query='Belum dicatat'))['total']==119
    with pytest.raises(ValueError):app.request('/api/records/search','POST',dict(sort='not-a-column'))


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
    assert restored.request('/api/analysis')['outstanding']['active_references']==0
    assert restored.request('/api/analysis')['outstanding']['manually_resolved']==1
    assert restored.request('/api/records/search','POST',{'pam':'10000006','outstanding_only':True})['total']==0
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
