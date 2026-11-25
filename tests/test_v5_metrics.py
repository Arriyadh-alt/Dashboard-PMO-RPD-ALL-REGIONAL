"""V5 source integrity, calendar edges, actual snapshots and role boundaries."""
from copy import deepcopy
from datetime import date, datetime, timezone
import pytest

from backend import aging
from backend.analytics import build_analysis, normalize_pam, prepare
from backend.browser_api import BrowserAPI, LocalEvents
from backend.exports import report_table
from scripts.v5_metrics import address_neighborhood
from scripts.workbook_contract import bootstrap_aliases, convert
from scripts.workbook_intake import flexible_date, profile
from tests.test_v4_metrics import snapshot


def v5_source(change=None):
    baseline,intake=snapshot()
    intake['layout_version']=5
    intake['summary']['master_secondary_id_mismatches']=0
    for index,row in enumerate(intake['master']): row['address']='JALAN SINTETIS RT.003 RW.005' if index==0 else ''
    for row in intake['survey']: row.update(date_quality='valid',incomplete_reason='Alasan sintetis')
    if change: change(intake)
    aliases=bootstrap_aliases(baseline,intake)
    data,_=convert(baseline,intake,aliases,full_snapshot=True)
    return data,intake,aliases


@pytest.mark.parametrize('days,bucket',[(0,'0–7'),(1,'0–7'),(7,'0–7'),(8,'8–14'),(14,'8–14'),(15,'15–30'),(30,'15–30'),(31,'31–60'),(60,'31–60'),(61,'61–90'),(90,'61–90'),(91,'>90')])
def test_calendar_boundaries(days,bucket):
    from datetime import timedelta
    reference=date(2026,11,25)
    row=aging.aged({'survey_date':(reference-timedelta(days=days)).isoformat()},reference)
    assert row['survey_age_days']==days and row['aging_bucket']==bucket


@pytest.mark.parametrize('survey,quality,anomaly',[(None,'missing','missing'),(None,'invalid','invalid'),('not-a-date','invalid','invalid'),('2026-11-26','valid','future')])
def test_invalid_dates_are_not_zero_days(survey,quality,anomaly):
    row=aging.aged({'survey_date':survey,'survey_date_quality':quality},date(2026,11,25))
    stats=aging.statistics([row])
    assert row['survey_age_days'] is None and row['date_anomaly']==anomaly
    assert stats['average_aging'] is None and stats['excluded_dates']==1
    assert sum(stats['aging'].values())==stats['survey_rows']==1


@pytest.mark.parametrize('raw,expected',[('000000101','101'),(' 101.0 ','101'),('1.01E+2','101'),('101.1',''),('0',''),('1234567890',''),('abc','')])
def test_normalize_numeric_text_identifiers(raw,expected):
    assert normalize_pam(raw)==expected


@pytest.mark.parametrize('raw,expected',[('25 November 2026','2026-11-25'),('25/11/2026 09:30','2026-11-25'),('2026-11-24T18:00:00Z','2026-11-25'),(datetime(2026,11,25,9,30),'2026-11-25'),(None,None)])
def test_supported_survey_dates(raw,expected):
    assert flexible_date(raw)==expected


def test_explicit_address_only_and_ambiguous_labels_rejected():
    assert address_neighborhood('RT/RW: 003/005')=={'rt':3,'rw':5}
    assert address_neighborhood('JALAN 003/005 NO 9')=={'rt':0,'rw':0}
    assert address_neighborhood('RT.003 RW.005 RT.004')=={'rt':0,'rw':0}


def test_address_enrichment_keeps_all_survey_and_master_populations():
    def change(intake): intake['master'][0].update(rw='',rt='')
    data,intake,_=v5_source(change)
    assert len(data['rec']['pam'])==len(intake['survey'])==3
    assert data['rec']['rw'][0]==5 and data['rec']['rt'][0]==3
    assert sum(row[4] for row in data['G'])==3
    assert sum(row[5] for row in data['G'])==3
    assert sum(row[9] for row in data['G'])==1
    assert data['_admin_mapping_report']['totals']['address_enriched']==1


@pytest.mark.parametrize('quality',['missing','invalid'])
def test_missing_dates_stay_in_total_outstanding(quality):
    def change(intake): intake['survey'][2].update(survey_date=None,date_quality=quality)
    data,_,_=v5_source(change)
    rows=aging.records(data,prepare(data),{'aging_date':'2026-11-25'},{},{})
    assert len(rows)==1 and rows[0]['survey_age_days'] is None
    assert aging.statistics(rows)['aging']['Tanggal Belum Valid']==1


def test_daily_aging_needs_no_source_import():
    data,_,_=v5_source(); prepared=prepare(data)
    today=aging.records(data,prepared,{'aging_date':'2026-11-25'},{},{})[0]
    yesterday=aging.records(data,prepared,{'aging_date':'2026-11-24'},{},{})[0]
    assert today['survey_age_days']==yesterday['survey_age_days']+1


def test_jakarta_midnight_not_device_local_day(monkeypatch):
    class Clock(datetime):
        @classmethod
        def now(cls,tz=None): return datetime(2026,11,24,17,0,tzinfo=timezone.utc).astimezone(tz)
    monkeypatch.setattr(aging,'datetime',Clock)
    assert aging.jakarta_today()==date(2026,11,25)


def test_real_snapshot_transitions_do_not_assume_installation():
    data,intake,aliases=v5_source()
    newer=deepcopy(intake);newer['reporting_date']='2026-11-24';newer['workbook_sha256']='b'*64
    newer['survey'][2]['installation_status']='Assign FA'
    newer['survey'][0]['installation_status']='Outstanding'
    after,_=convert(data,newer,aliases,full_snapshot=True)
    assert len(after['outstanding_history'])==2
    changes=after['outstanding_history'][-1]['transitions']
    assert changes['new']==1 and changes['assign_fa']==1 and changes['installed']==0
    historical=aging.records(after,prepare(after),{'snapshot':'2026-11-23','aging_date':'2026-11-25'},{},{})
    assert normalize_pam(historical[0]['pam'])=='103' and historical[0]['historical']
    again,_=convert(after,newer,aliases,full_snapshot=True)
    assert len(again['outstanding_history'])==2


def test_guest_detail_readonly_and_admin_report_absent():
    data,_,_=v5_source()
    guest={k:v for k,v in data.items() if k!='_admin_mapping_report'}
    api=BrowserAPI(guest,'guest','fixture',{},operational_guest=True)
    assert api.request('/api/records/search','POST',{'outstanding_only':True})['total']==1
    with pytest.raises(ValueError,match='Admin'): api.request('/api/admin/mapping-validation')
    with pytest.raises(ValueError,match='Admin'): api.request('/api/followups/anything','POST',{})


def test_export_bucket_reference_and_query_match_the_table():
    data,_,_=v5_source(); prepared=prepare(data)
    filters={'aging_date':'2026-11-25','out_query':'103'}
    expected=aging.search(data,prepared,filters,{},{},{'query':'103'})['rows']
    headers,rows=report_table('outstanding',build_analysis(data,prepared,filters,LocalEvents(),'owner'),data,prepared,filters,LocalEvents(),'owner')
    assert len(rows)==len(expected)==1
    assert rows[0][headers.index('Aging per')]=='2026-11-25'
    assert rows[0][headers.index('Aging Sejak Survey (Hari)')]==expected[0]['survey_age_days']
