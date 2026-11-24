import copy
import json

import pytest

from backend.browser_api import BrowserAPI
from scripts.build_pages import build
from scripts.public_summary import project, validate
from scripts.publish_v3 import publish
from scripts.split_access import split
from tests.fixtures import encrypted_fixture
from tests.test_aggregate_access import unique_source, unpack
from backend.auth import unwrap_key
from tests.test_workbook_contract import matching_snapshot
from scripts.workbook_contract import bootstrap_aliases, convert


def test_new_rw_counts_preserve_every_established_field_and_follow_daily_refresh():
    before, intake = matching_snapshot()
    aliases = bootstrap_aliases(before, intake)
    data, _ = convert(before, intake, aliases, full_snapshot=True, neighborhood_counts=True)
    assert {k:v for k,v in data.items() if k!='W'} == {k:v for k,v in before.items() if k!='W'}
    assert [row[:7] for row in data['W']] == before['W']
    assert [row[7] for row in data['W']] == [1,1,0]
    assert convert(data, intake, aliases, full_snapshot=True)[0] == data


def test_public_release_is_allowlisted_and_rejects_nested_operational_fields():
    public = project(unique_source(), 'a'*32)
    raw=json.dumps(public)
    for forbidden in ('rec', 'svs', 'Fixture Team', 'Fixture Area', 'FIXTURE KEL', '10000001', 'wrappers', 'pam'):
        assert forbidden not in raw
    assert sum(row['canvassed'] for row in public['regions']) == public['metrics']['canvassed'] == 8
    bad=copy.deepcopy(public);bad['regions'][0]['customer']={}
    with pytest.raises(ValueError,match='Unapproved'):validate(bad)
    bad=copy.deepcopy(public);bad['trends'][0]['canvassed']+=1
    with pytest.raises(ValueError,match='reconcile'):validate(bad)


def test_internal_guest_reads_all_monitoring_but_no_mutations_or_admin_routes():
    app=BrowserAPI(unique_source(),'guest','fixture',{},operational_guest=True)
    assert app.bootstrap()['data']['svs']==unique_source()['svs']
    assert app.bootstrap()['capabilities']['customer_detail']
    assert app.request('/api/analysis')['teams'][0]['individuals']
    record=app.request('/api/records/search','POST',{'pam':'10000001'})['rows'][0]
    assert int(record['pam'])==10000001
    assert app.request('/api/followups/'+record['ref'])['events']==[]
    for path,method in [('/api/admin/audit','GET'),('/api/quality','GET'),('/api/admin/mappings','PUT'),('/api/admin/rules','PUT'),('/api/admin/targets','POST'),('/api/admin/area-context','POST'),('/api/followups/'+record['ref'],'POST')]:
        with pytest.raises(ValueError,match='Admin'):app.request(path,method,{})
    assert app.store.events==[]


def test_v3_publish_preserves_wrappers_and_requires_a_matching_complete_bundle(tmp_path):
    original=tmp_path/'old.json';original.write_text(json.dumps(encrypted_fixture(unique_source(),{'admin':('password','a'),'viewer':('guest-password','g')})))
    owner,guest=tmp_path/'owner.json',tmp_path/'guest.json'
    split(original,owner,guest,[('admin','password')])
    plain=tmp_path/'contract.json';plain.write_text(json.dumps(unique_source()))
    bundle=tmp_path/'bundle';publish(owner,plain,bundle,'admin','password')
    admin_envelope=json.loads((bundle/'data.enc.json').read_text());guest_envelope=json.loads((bundle/'guest.enc.json').read_text())
    assert admin_envelope['u']==json.loads(owner.read_text())['u']
    assert guest_envelope['u']==json.loads(guest.read_text())['u']
    for envelope,account,password in [(admin_envelope,'admin','password'),(guest_envelope,'viewer','guest-password')]:
        key,_=unwrap_key(envelope,account,password)
        data=unpack(envelope,key)
        assert data['rec']==unique_source()['rec']
        if account=='viewer':assert '_guest_access' not in data
        overview=json.loads((bundle/('overview.enc.json' if account=='admin' else 'guest-overview.enc.json')).read_text())
        assert unpack(overview,key).get('aggregate_version')==1
        assert 'rec' not in unpack(overview,key)
    root=tmp_path/'site';(root/'pages').mkdir(parents=True)
    first=build(root=root,bundle_dir=bundle)
    assert first['guest_scope']=='operational_readonly'
    assert build(root=root)==first
    before={p:p.read_bytes() for p in (root/'pages').iterdir()}
    broken=json.loads((bundle/'overview.enc.json').read_text());broken['p']='0'*32
    (bundle/'overview.enc.json').write_text(json.dumps(broken))
    with pytest.raises(ValueError,match='matching pair'):build(root=root,bundle_dir=bundle)
    assert all(p.read_bytes()==raw for p,raw in before.items())
