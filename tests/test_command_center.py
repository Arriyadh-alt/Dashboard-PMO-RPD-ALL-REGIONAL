def test_bootstrap_includes_master_only_kelurahan(signed,app):
    client,_=signed()
    session=next(iter(app.state.sessions.values.values()))
    session.data['source']['kels'].append('MASTER ONLY KEL')
    session.data['source']['P'].append([0,2,25,0,0])
    boot=client.get('/api/bootstrap').json()
    assert [0,2] in boot['geography']
    assert client.get('/api/analysis?kel=2').json()['master']['potential']==25

def test_long_followup_action_can_span_pdf_pages(signed):
    client,_=signed()
    ref=client.post('/api/records/search',json={'outstanding_only':True,'limit':1}).json()['rows'][0]['ref']
    assert client.post('/api/followups/'+ref,json={'pic':'Fixture PIC','status':'Outstanding','action':('Evidence and follow-up task. '*100)[:2000]}).status_code==200
    response=client.get('/api/reports/outstanding.pdf')
    assert response.status_code==200 and response.content.startswith(b'%PDF')

import csv
from datetime import date, timedelta
from io import BytesIO, StringIO
import json
import sqlite3

from openpyxl import load_workbook
import pytest

from backend.analytics import DEFAULT_RULES, area_key, build_analysis, prepare, priority, target_ref
from backend.store import Store
def test_operations_keep_area_identity_after_import_reordering(tmp_path):
    data=fixture_data()
    store=Store(tmp_path/'operations.sqlite3')
    original=prepare(data)
    ref=original['rows'][0]['ref']
    store.append('followup',ref,'fixture',{'status':'Outstanding','pic':'Verified PIC'})
    store.append('area_context',area_key(data,0),'fixture',{'supply':'constrained','evidence':'verified'})
    store.append('target',target_ref('2026-11','Barat',0,data),'fixture',{'target':12})
    data['abs'].reverse();data['reg'].reverse()
    for key,area_column in [('A',1),('S',1),('E',1),('P',0),('W',0)]:
        for row in data[key]: row[area_column]=1-row[area_column]
    data['rec']['ab']=[1-value for value in data['rec']['ab']]
    refreshed=prepare(data)
    assert refreshed['rows'][0]['ref']==ref
    assert store.latest('followup')[ref]['pic']=='Verified PIC'
    report=build_analysis(data,refreshed,{'m0':2,'m1':2,'reg':'Barat','ab':1},store,'owner')
    assert report['target']['target']==12
    assert report['areas'][0]['name']=='Fixture Area A'
    assert report['areas'][0]['priority']=='Requires Supply Improvement'

from backend.auth import decrypt_source
from tests.fixtures import fixture_data


def test_original_crypto_contract_and_normalization(encrypted_source):
    data, role = decrypt_source(encrypted_source[0], "  FIXTURE-ADMIN  ", encrypted_source[1])
    assert role == "owner" and data["meta"]["rows"] == 14
    with pytest.raises(Exception):
        decrypt_source(encrypted_source[0], "fixture-admin", "wrong")


def test_unique_cohort_does_not_count_duplicates_or_conflicting_geography(signed):
    client, _ = signed()
    result = client.get("/api/analysis").json()
    assert result["metrics"] == {"canvassed": 9, "interested": 6, "installed": 3,
        "interest_rate": 6/9, "installation_rate": .5, "conflicted_status_customers": 1,
        "excluded_geography_customers": 1, "survey_rows": 13}
    assert result["master"]["potential"] == 150 and result["master"]["remaining"] == 125
    assert result["previous"] is None and not result["target"]["available"]


def test_cascading_filters_and_real_previous_survey_cohort(signed):
    client, _ = signed()
    current = client.get("/api/analysis?m0=2&m1=2").json()
    assert current["metrics"]["canvassed"] == 4
    assert current["metrics"]["interested"] == 2
    assert current["previous"]["canvassed"] == 2
    assert current["previous_scope"] == {"start":"2026-10-01", "end":"2026-10-31"}
    filtered = client.get("/api/analysis?m0=2&m1=2&reg=Barat&ab=0&kel=0").json()
    assert filtered["metrics"]["canvassed"] == 3
    assert filtered["metrics"]["interested"] == 1
    assert filtered["master"]["remaining"] == 80
    assert len(filtered["areas"]) == 1
    exact = client.get("/api/analysis?start=2026-11-02&end=2026-11-02&status=Done").json()
    assert exact["metrics"]["installed"] == 1
    assert client.get("/api/analysis?m0=2&m1=1").status_code == 422
    assert client.get("/api/analysis?start=2026-12-01&end=2026-11-01").status_code == 422


def test_quality_reports_source_rows_without_deleting_them(signed):
    client, _ = signed()
    quality = client.get("/api/quality").json()
    assert quality["imported_records"] == 14 and quality["valid_records"] == 13
    assert quality["duplicate_records"] == 3 and quality["duplicate_customers"] == 3
    assert quality["invalid_pam"] == 1 and quality["ambiguous_geography_customers"] == 1
    assert quality["source"]["imported_at"] is None


def test_lookup_filters_paginate_and_preserve_operational_fields(signed):
    client, _ = signed()
    result = client.post("/api/records/search",json={"scope":{"m0":2,"m1":2},"limit":2}).json()
    assert result["total"] == 8 and len(result["rows"]) == 2
    next_page = client.post("/api/records/search",json={"scope":{"m0":2,"m1":2},"limit":2,"offset":2}).json()
    assert next_page["rows"][0]["pam"].endswith("7")
    found = client.post("/api/records/search",json={"pam":"010000007","installation":1}).json()
    assert found["total"] == 1 and found["rows"][0]["installation_date"] == "2026-11-04"
    assert {"arrears","obstacle","master_flag","potential_status","customer_status"} <= found["rows"][0].keys()
    assert client.post("/api/records/search",json={"limit":5000}).status_code == 422


def test_followups_append_history_and_aging_uses_confirmed_case_start(signed, app):
    client, _ = signed()
    row = client.post("/api/records/search",json={"pam":"10000006"}).json()["rows"][0]
    ref = row["ref"]
    before = client.get("/api/analysis?m0=2&m1=2").json()["outstanding"]
    assert before["aging"][">30"] == 0
    payload = {"pic":"Fixture PIC", "status":"Assign FA", "action":"Confirm source case start", "target_date":(date.today()-timedelta(days=1)).isoformat(),
               "case_started":(date.today()-timedelta(days=20)).isoformat(), "pause_days":5, "pause_reason":"Confirmed operational pause"}
    assert client.post(f"/api/followups/{ref}",json=payload).status_code == 200
    current = client.get("/api/analysis?m0=2&m1=2").json()["outstanding"]
    assert current["aging"]["15–30"] == 1 and current["urgent_count"] == 1
    payload.update(status="Done", action="Confirmed resolution", resolution_notes="Fixture resolution")
    assert client.post(f"/api/followups/{ref}",json=payload).status_code == 200
    history = client.get(f"/api/followups/{ref}").json()["events"]
    assert len(history) == 2 and history[0]["payload"]["status"] == "Done" and history[1]["payload"]["status"] == "Assign FA"
    assert client.get("/api/analysis?m0=2&m1=2").json()["outstanding"]["manually_resolved"] == 1
    # Source status and rows were not rewritten by the follow-up workflow.
    assert client.post("/api/records/search",json={"pam":"10000006"}).json()["rows"][0]["status"] == "Assign FA"
    with app.state.store.connect() as db:
        with pytest.raises(sqlite3.IntegrityError):
            db.execute("UPDATE events SET payload='{}' WHERE kind='followup'")
    payload.update(case_started=(date.today()+timedelta(days=1)).isoformat())
    assert client.post(f"/api/followups/{ref}",json=payload).status_code == 422


def test_mapping_target_and_priority_changes_are_traceable(signed):
    client, _ = signed()
    assert client.put("/api/admin/mappings",json={"0":{"kl":"Fixture Team B","st":1}}).status_code == 200
    assert "Fixture Team B" in [entry["name"] for entry in client.get("/api/analysis").json()["teams"]]
    assert client.put("/api/admin/mappings",json={"0":{"kl":"Made up team"}}).status_code == 422
    target={"month":"2026-11","region":"","area":-1,"target":10,"evidence":"Fixture approved monthly plan"}
    assert client.post("/api/admin/targets",json=target).status_code == 200
    analysis = client.get("/api/analysis?m0=2&m1=2").json()
    assert analysis["target"]["actual"] == 2 and analysis["target"]["achievement"] == .2
    assert not client.get("/api/analysis?m0=2&m1=2&coordinator=Fixture%20Team%20B").json()["target"]["available"]
    assert client.post("/api/admin/area-context",json={"area":0,"supply":"constrained","readiness":"blocked","evidence":"Fixture verified supply report"}).status_code == 200
    assert client.get("/api/analysis").json()["areas"][0]["priority"] == "Requires Supply Improvement"
    log = client.get("/api/admin/audit").json()
    assert {event["kind"] for event in log["events"]} >= {"mapping","target","area_context"}


def test_priority_does_not_assume_remaining_potential_means_readiness():
    metrics={"canvassed":100,"interested":40,"installed":10,"interest_rate":.4}
    assert priority(metrics,{},DEFAULT_RULES)[0] == "Insufficient Data"
    assert priority(metrics,{"supply":"ready","readiness":"ready"},DEFAULT_RULES)[0] == "High Priority"


@pytest.mark.parametrize("kind",["executive","regional","area","team","outstanding"])
@pytest.mark.parametrize("extension",["csv","xlsx","pdf"])
def test_reports_respect_filters_and_format(signed,kind,extension):
    client, _ = signed()
    response = client.get(f"/api/reports/{kind}.{extension}?m0=2&m1=2&reg=Barat&ab=0")
    assert response.status_code == 200
    assert f"RPD-{kind}.{extension}" in response.headers["content-disposition"]
    if extension == "csv":
        content = response.content.decode("utf-8-sig")
        assert "2026-11-01" in content and "2026-11-30" in content
        parsed=list(csv.reader(StringIO(content)))
        assert parsed[0][0].endswith("Report") and any("Source loaded at:" in row[0] for row in parsed if row)
        if kind == "regional":
            assert "Timur" not in content
        if kind == "outstanding":
            assert "10000007" not in content
    elif extension == "xlsx":
        book = load_workbook(BytesIO(response.content))
        assert book.active["A1"].value.endswith("Report")
    else:
        assert response.content.startswith(b"%PDF-")


def test_xlsx_and_csv_formula_injection_is_literal(app):
    data=fixture_data();data['abs'][0]='=HYPERLINK("https://invalid.example")'
    prepared=prepare(data)
    from backend.exports import make_report
    analysis=build_analysis(data,prepared,{},app.state.store,'owner')
    source={"loaded_at":"2026-11-23T00:00:00Z","fingerprint":"fixture","imported_at":None}
    xlsx,_=make_report('area','xlsx',analysis,data,prepared,{},app.state.store,'owner',source)
    sheet=load_workbook(BytesIO(xlsx)).active
    cells=[cell for row in sheet for cell in row if str(cell.value).startswith('=HYPERLINK')]
    assert len(cells)==1 and cells[0].data_type=='s'
    csv_data,_=make_report('area','csv',analysis,data,prepared,{},app.state.store,'owner',source)
    assert "'=HYPERLINK" in csv_data.decode('utf-8-sig')
