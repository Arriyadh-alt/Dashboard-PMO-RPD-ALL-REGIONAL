import csv
from io import StringIO
import json
import secrets

from fastapi.testclient import TestClient
import pytest

from backend.auth import Sessions, SessionCapacity, decrypt_source
from backend.main import create_app
from scripts.import_encrypted import import_source
from scripts.rekey_encrypted import rekey_source


def test_sessions_share_one_private_dataset_and_limit_each_account(signed,app):
    signed()
    first=next(iter(app.state.sessions.values.values())).data
    signed('guest')
    assert all(session.data is first for session in app.state.sessions.values.values())
    sessions=Sessions()
    oldest=sessions.create('viewer','guest',first,(1,))
    for _ in range(12): sessions.create('viewer','guest',first,(1,))
    assert len(sessions.values)==5 and sessions.get(oldest,(1,)) is None
    assert sessions.get(sessions.create('admin','owner',first,(1,)),(1,)).role=='owner'


def test_capacity_is_not_misreported_as_invalid_credentials(client,app,encrypted_source,monkeypatch):
    def full(*args): raise SessionCapacity()
    monkeypatch.setattr(app.state.sessions,'create',full)
    response=client.post('/api/login',json={'account':'fixture-admin','password':encrypted_source[1]})
    assert response.status_code==503 and not app.state.sessions.failures


def test_production_requires_rotated_private_generation(tmp_path,encrypted_source):
    envelope=json.loads(encrypted_source[0].read_text())
    envelope.pop('v')
    legacy=tmp_path/'legacy.enc.json'
    legacy.write_text(json.dumps(envelope))
    app=create_app(legacy,tmp_path/'state',origin='https://testserver',dev=False)
    with TestClient(app,base_url='https://testserver',headers={'origin':'https://testserver'}) as client:
        assert client.post('/api/login',json={'account':'fixture-admin','password':encrypted_source[1]}).status_code==503


def test_rekey_preserves_business_data_and_revokes_old_backend_credentials(tmp_path,encrypted_source):
    original=encrypted_source[0].read_bytes()
    admin_password,viewer_password=secrets.token_urlsafe(24),secrets.token_urlsafe(24)
    output=tmp_path/'private.enc.json'
    rekey_source(encrypted_source[0],output,'fixture-admin',encrypted_source[1],{
        'private-admin':(admin_password,'a'),'private-viewer':(viewer_password,'g')})
    baseline,_=decrypt_source(encrypted_source[0],'fixture-admin',encrypted_source[1])
    current,role=decrypt_source(output,'private-admin',admin_password)
    assert current==baseline and role=='owner' and encrypted_source[0].read_bytes()==original
    assert decrypt_source(output,'private-viewer',viewer_password)[1]=='guest'
    with pytest.raises(Exception): decrypt_source(output,'fixture-admin',encrypted_source[1])
    with pytest.raises(ValueError): rekey_source(encrypted_source[0],output,'fixture-admin',encrypted_source[1],{'fixture-admin':(encrypted_source[1],'a')})


def test_import_history_keeps_each_rollback_event(tmp_path,encrypted_source):
    output=tmp_path/'private'/'source.enc.json'
    first=import_source(encrypted_source[0],output)
    second=import_source(encrypted_source[0],output)
    entries=[json.loads(line) for line in output.with_suffix('.json.imports.jsonl').read_text().splitlines()]
    assert len(entries)==2 and entries[0]['fingerprint']==first['fingerprint']==second['fingerprint']


def test_outstanding_export_preserves_source_and_manual_resolution(signed):
    client,_=signed()
    row=client.post('/api/records/search',json={'pam':'10000006'}).json()['rows'][0]
    assert client.post('/api/followups/'+row['ref'],json={'pic':'Verified PIC','status':'Done','action':'Closure verified','resolution_notes':'Fixture resolution'}).status_code==200
    parsed=list(csv.reader(StringIO(client.get('/api/reports/outstanding.csv').content.decode('utf-8-sig'))))
    header=next(index for index,values in enumerate(parsed) if values and values[0]=='Case reference')
    reports=[dict(zip(parsed[header],values)) for values in parsed[header+1:]]
    case=next(values for values in reports if values['Case reference']==row['ref'])
    assert case['Source status']=='Assign FA' and case['Follow-up status']=='Done'
    assert case['Operational state']=='Resolved since import' and case['Resolution notes']=='Fixture resolution'
