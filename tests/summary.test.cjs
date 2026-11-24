const {test}=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm'),{execFileSync}=require('node:child_process'),{webcrypto}=require('node:crypto');
const python=fs.existsSync('.venv/bin/python')?'.venv/bin/python':'python3';
const fixture=JSON.parse(execFileSync(python,['-c',`
import json
from tests.test_aggregate_access import unique_source
from backend.aggregate import project
from backend.analytics import build_analysis,prepare
from backend.browser_api import LocalEvents
d=unique_source()
scopes=[{}, {'reg':'Barat'}, {'reg':'Timur'}, {'ab':0}, {'ab':1}, {'kel':0}, {'kel':1}, {'m0':1,'m1':1}, {'m0':2,'m1':2}, {'start':'2026-09-01','end':'2026-09-30'}, {'start':'2026-11-04','end':'2026-11-30'}]
scopes=[{'m0':0,'m1':2,'reg':'','ab':-1,'kel':-1,**s} for s in scopes]
expected=[build_analysis(d,prepare(d),s,LocalEvents(),'owner') for s in scopes]
print(json.dumps({'source':d,'projection':project(d),'scopes':scopes,'expected':expected}))
`],{encoding:'utf8'}));
const context={crypto:webcrypto,TextEncoder,console};vm.createContext(context);vm.runInContext(fs.readFileSync('pages/summary.js','utf8'),context);
const plain=value=>JSON.parse(JSON.stringify(value));
test('fast owner projection exactly matches the published identity-free Python projection',async()=>{
  const actual=await context.RPDSummary.project(fixture.source);
  for(const key of Object.keys(fixture.projection))assert.deepEqual(plain(key==='days'||key==='install_days'?[...actual[key]].sort():actual[key]),key==='days'||key==='install_days'?[...fixture.projection[key]].sort():fixture.projection[key],key);
});
for(const [i,scope] of fixture.scopes.entries())test('aggregate formula parity '+JSON.stringify(scope),()=>{
  const actual=plain(context.RPDSummary.analyse(fixture.projection,scope)),expected=fixture.expected[i];
  assert.deepEqual(actual.metrics,expected.metrics);assert.deepEqual(actual.previous,expected.previous);
  for(const key of ['potential','matched_interested','remaining','installed'])assert.equal(actual.master[key],expected.master[key]);
  for(const kind of ['regions','areas'])for(const item of expected[kind]){
    const a=actual[kind].find(r=>r.key===item.key);assert.ok(a);
    for(const key of ['canvassed','interested','installed','potential','remaining','interest_rate','installation_rate'])assert.equal(a[key],item[key],kind+'.'+key);
  }
  assert.deepEqual(actual.trends.map(r=>[r.month,r.canvassed,r.interested,r.installation_events]),expected.trends.map(r=>[r.month,r.canvassed,r.interested,r.installation_events]));
});
test('team or status scopes never silently use additive cubes',()=>{
  for(const scope of [{coordinator:'team'},{statuses:['Done']}])assert.throws(()=>context.RPDSummary.analyse(fixture.projection,scope));
});
test('Guest bootstrap contains neither roster nor internal dictionaries',()=>{
  const boot=context.RPDSummary.bootstrap(fixture.projection,null,'guest',{},[]);
  assert.equal(boot.capabilities.customer_detail,false);assert.equal(boot.capabilities.aggregate_only,true);
  assert.equal(boot.data.svs.length,0);assert.equal(boot.data.S.length,0);assert.equal(boot.data.W.length,0);
  assert.equal(boot.data.rec,undefined);assert.equal(boot.data._guest_access,undefined);
});
