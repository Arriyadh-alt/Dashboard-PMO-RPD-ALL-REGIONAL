const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');
const {test}=require('node:test');

// Execute the production pure helpers without starting their legacy DOM application.
const source=fs.readFileSync('web/command-center.js','utf8');
const helpers=source.slice(source.indexOf('function presetScope()'),source.indexOf('\nfunction fill()'));

function fixture(m0){
  const context={D:{months:['2026-09','2026-10','2026-11'],abs:['A','B'],reg:['West','East'],kels:['KEL A','KEL B'],S:[],dic:{kf:['Done']}},
    BOOT:{area_keys:['west-a','east-b'],geography:[[0,0],[1,1]]},
    S:{m0,m1:2,reg:'',ab:-1,kel:-1,coordinator:'',statuses:[],start:'',end:''},eKl:row=>row[3]};
  context.scopeObject=()=>({...context.S});
  vm.createContext(context);vm.runInContext(helpers,context);
  return context;
}

test('bounded start cannot silently become open-ended after an import',()=>{
  const context=fixture(1),saved=context.presetScope();
  context.D.months=['2026-10','2026-11'];
  assert.equal(context.resolvePreset(saved),null);
});

test('open-ended start cannot silently become bounded after an import',()=>{
  const context=fixture(0),saved=context.presetScope();
  context.D.months=['2026-08','2026-09','2026-10','2026-11'];
  assert.equal(context.resolvePreset(saved),null);
});

test('explicit start dates survive an opening-bucket transition',()=>{
  const context=fixture(1);context.S.start='2026-10-06';
  const saved=context.presetScope();context.D.months=['2026-10','2026-11'];
  assert.equal(context.resolvePreset(saved).start,'2026-10-06');
});

test('bounded month scope survives a reordered month index',()=>{
  const context=fixture(1),saved=context.presetScope();
  context.D.months=['2026-08','2026-09','2026-10','2026-11'];
  assert.equal(context.resolvePreset(saved).m0,2);
});

test('area and kelurahan follow stable identities rather than old indices',()=>{
  const context=fixture(0);context.S.ab=0;context.S.kel=0;
  const saved=context.presetScope();
  for(const key of ['abs','reg','kels'])context.D[key].reverse();
  context.BOOT.area_keys.reverse();context.BOOT.geography=[[1,1],[0,0]];
  const restored=context.resolvePreset(saved);
  assert.equal(restored.ab,1);assert.equal(restored.kel,1);
});

test('removed geography and unverifiable older presets are rejected',()=>{
  const context=fixture(0);context.S.ab=0;
  const saved=context.presetScope();context.BOOT.area_keys=['east-b'];
  assert.equal(context.resolvePreset(saved),null);
  assert.equal(context.resolvePreset({scope:context.S}),null);
});

test('operational presets load their validation dictionaries only when explicitly applied',async()=>{
  const context=fixture(0),saved=context.presetScope();
  saved.scope.coordinator='Fixture Team';saved.scope.statuses=['Done'];context.D.dic.kf=[];
  let loads=0;context.ensureOperationalData=async()=>{loads++;context.D.S=[[0,0,0,'Fixture Team']];context.D.dic.kf=['Done']};
  assert.equal(context.resolvePreset(saved),null);
  const scope=await context.resolvePresetForUse(saved);
  assert.equal(loads,1);assert.equal(scope.coordinator,'Fixture Team');assert.equal(scope.statuses[0],'Done');
  await context.resolvePresetForUse(context.presetScope());assert.equal(loads,1,'geographic/date-only presets need no operational download');
});

function legacyOverview(filters={}){
  const context={input:{months:['2026-10','2026-11'],abs:['A','B'],reg:['West','East'],
    A:[[0,0,1,1,0,0,0,0,0,1,0,0],[0,1,1,0,1,0,0,0,0,0,0,0]],
    E:[[1,0,0,5]],P:[],meta:{uniq:2}},filters};
  vm.createContext(context);
  vm.runInContext(fs.readFileSync('web/app.js','utf8'),context);
  return vm.runInContext('D=input;Object.assign(S,{m0:0,m1:1},filters);vRingkasan()',context);
}

test('legacy meter trend retains an event-only month, including when selected alone',()=>{
  for(const filters of [{},{m0:1,m1:1}]){
    const html=legacyOverview(filters);
    assert.match(html,/<title>Nov 26: 5<\/title>/);
    assert.match(html,/<title>Nov 26: 0<\/title>/);
  }
});

test('legacy event-only month still respects regional and area filters',()=>{
  for(const filters of [{reg:'East'},{ab:1}]){
    assert.doesNotMatch(legacyOverview(filters),/Nov 26/);
  }
});
