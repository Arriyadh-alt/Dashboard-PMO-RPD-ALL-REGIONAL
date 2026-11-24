"""Population regressions: unmatched surveys must never become zero field KPIs."""
from copy import deepcopy

import pytest
from openpyxl import Workbook

from backend.analytics import build_analysis, prepare
from backend.browser_api import LocalEvents
from scripts.v4_metrics import validate_intake
from scripts.workbook_contract import bootstrap_aliases, convert
from scripts.workbook_intake import V4_MASTER_COLUMNS, V4_SURVEY_COLUMNS, profile, read_intake
from tests.test_workbook_contract import matching_snapshot


def snapshot():
    baseline, intake = matching_snapshot()
    intake.update(layout_version=4, reporting_date='2026-11-23', workbook_sha256='f'*64)
    # Customer 103 is interested but outside master; customer 104 is master-only.
    intake['survey'][2].update(result='Berminat', installation_status='Outstanding')
    for row in intake['survey']:
        row.update(minat='  bERMINAT  ' if row['result']=='Berminat' else '',
                   pam_display=row['pam'].zfill(9), illegal_flag='Case Closed', file_status='Lengkap',
                   admin_note_present=True, incomplete_reason_present=False)
    intake['summary'] = {kind: profile(intake[kind]) for kind in ('survey', 'master')}
    return baseline, intake


def test_field_cube_includes_outside_master_without_subtracting_it_from_master_stock():
    baseline, intake = snapshot()
    data, _ = convert(baseline, intake, bootstrap_aliases(baseline,intake), full_snapshot=True)
    assert [sum(row[i] for row in data['G']) for i in range(4,9)] == [3,3,2,1,1]
    outside = [row for row in data['G'] if row[2:4]==[0,0]]
    assert sum(row[6] for row in outside)==1
    analysis = build_analysis(data,prepare(data),{},LocalEvents(),'owner')
    assert analysis['metrics']['interested']==2
    assert analysis['master']['remaining']==2  # 3 - 1 eligible matched, NOT 3 - 2 historical
    assert analysis['outstanding']['survey_rows']==1
    assert analysis['outstanding']['by_illegal_flag']=={'Case Closed':1}
    broken = deepcopy(data); broken['G'][0][5] += 1
    with pytest.raises(ValueError,match='do not reconcile'):
        prepare(broken)


@pytest.mark.parametrize('field,value,message', [('minat','','Q / AO'),('installation_status','','partition')])
def test_inconsistent_interest_or_status_membership_rejects_the_snapshot(field,value,message):
    _, intake=snapshot(); intake['survey'][0][field]=value
    with pytest.raises(ValueError,match=message):
        validate_intake(intake)


def test_matched_pam_with_conflicting_geography_is_not_assigned_a_random_master_rt():
    baseline,intake=snapshot(); baseline['kels'].append('OTHER KEL')
    intake['master'][0]['kelurahan']='OTHER KEL'
    data,_=convert(baseline,intake,bootstrap_aliases(baseline,intake),full_snapshot=True)
    assert data['meta']['geographic_join_mismatches']==1
    assert sum(row[6] for row in data['G'] if row[2:4]==[0,0])==2
    assert sum(row[8] for row in data['G'])==1


def test_existing_private_owner_bootstrap_preserves_the_v4_field_cube(tmp_path):
    import json, secrets
    from fastapi.testclient import TestClient
    from backend.main import create_app
    from tests.fixtures import encrypted_fixture
    baseline,intake=snapshot()
    data,_=convert(baseline,intake,bootstrap_aliases(baseline,intake),full_snapshot=True)
    password=secrets.token_urlsafe(24)
    source=tmp_path/'synthetic.enc.json'
    source.write_text(json.dumps(encrypted_fixture(data,{'fixture-admin':(password,'a')})))
    app=create_app(source,tmp_path/'state',origin='http://testserver',dev=True)
    with TestClient(app,headers={'origin':'http://testserver'}) as client:
        assert client.post('/api/login',json={'account':'fixture-admin','password':password}).status_code==200
        boot=client.get('/api/bootstrap').json()
        assert boot['data']['G']==data['G']
        assert boot['data']['meta']['reporting_date']=='2026-11-23'


def test_audit_rejects_date_swaps_that_preserve_global_daily_counts():
    from scripts.reconcile_v4 import reconcile
    baseline,intake=snapshot();aliases=bootstrap_aliases(baseline,intake)
    data,_=convert(baseline,intake,aliases,full_snapshot=True)
    assert reconcile(intake,data,aliases)['passed']
    intake['survey'][0]['meter_date'],intake['survey'][2]['meter_date']=intake['survey'][2]['meter_date'],intake['survey'][0]['meter_date']
    result=reconcile(intake,data,aliases)
    assert not result['passed']
    assert any(row['metric']=='Meter per-PAM dates' and row['status']=='FAIL' for row in result['checks'])


def test_audit_rejects_a_wrong_outstanding_category_with_an_unchanged_total():
    from scripts.reconcile_v4 import reconcile
    baseline,intake=snapshot();aliases=bootstrap_aliases(baseline,intake)
    data,_=convert(baseline,intake,aliases,full_snapshot=True)
    data['dic']['fs'].append('Tidak Lengkap');data['rec']['fs'][2]=len(data['dic']['fs'])-1
    result=reconcile(intake,data,aliases)
    assert not result['passed']
    assert any(row['metric']=='Outstanding file categories · exact buckets' and row['status']=='FAIL' for row in result['checks'])


@pytest.mark.parametrize('field,value',[('reporting_date','2026-11-24'),('workbook_sha256','0'*64)])
def test_audit_rejects_stale_metadata_even_when_records_are_identical(field,value):
    from scripts.reconcile_v4 import reconcile
    baseline,intake=snapshot();aliases=bootstrap_aliases(baseline,intake)
    data,_=convert(baseline,intake,aliases,full_snapshot=True)
    intake[field]=value
    with pytest.raises(ValueError,match='provenance'):
        reconcile(intake,data,aliases)


def test_xlsx_discovers_renamed_sheets_and_inserted_columns_and_drops_customer_notes(tmp_path):
    path=tmp_path/'Update Report RPD 23112026.xlsx'
    book=Workbook();book.remove(book.active)
    for name,columns in [('Unrelated date suffix',V4_SURVEY_COLUMNS),('Customer master renamed',V4_MASTER_COLUMNS)]:
        sheet=book.create_sheet(name)
        values={key:'' for key in columns}
        values.update(pam='000000123', survey_date='2026-11-19', region='Barat',area='Fixture',
            minat='Berminat', result='Berminat',installation_status='Done',
            admin_note='PRIVATE NOTE MUST NOT LEAVE INTAKE', incomplete_reason='PRIVATE REASON')
        sheet.append(['Inserted extra column',*columns.values()])
        sheet.append(['Ignored',*[values[key] for key in columns]])
    book.create_sheet('Summary').append([V4_SURVEY_COLUMNS['pam'],V4_SURVEY_COLUMNS['survey_date']])
    book.create_sheet('Notes').append(['Repeated title','Repeated title'])
    book.save(path)
    result=read_intake(path,v4=True)
    assert result['layout_version']==4 and result['reporting_date']=='2026-11-23'
    assert result['survey'][0]['pam']=='123' and result['survey'][0]['pam_display']=='000000123'
    assert result['survey'][0]['admin_note_present'] is True
    assert 'PRIVATE NOTE' not in str(result) and 'PRIVATE REASON' not in str(result)
    assert result['summary']['shifted_columns']['survey']
