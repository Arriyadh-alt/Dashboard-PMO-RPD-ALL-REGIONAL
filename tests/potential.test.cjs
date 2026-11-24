const {test}=require('node:test'),assert=require('node:assert/strict');
require('../web/potential.js');
const source={reg:['Barat','Timur'],W:[[0,0,1,1,10,3,2,5],[0,0,1,2,20,4,1,8],[0,0,2,1,8,1,0,3],[0,1,1,1,4,1,0,2],[1,2,1,1,9,2,1,4],[0,0,0,0,2,0,0,0]]};
test('V4 includes out-of-master interest but deducts only matched eligible interest',()=>{
  const data={reg:['Barat'],W:[],G:[[0,0,1,1,3,2,1,1,1],[0,0,0,0,0,1,1,0,0]]};
  assert.deepEqual(RPDPotential.total(RPDPotential.rows(data,{})),{potential:3,canvassed:3,interested:2,installed:1,remaining:2});
  assert.equal(RPDPotential.total(RPDPotential.rows(data,{rw:0})).interested,1);
});
test('geographic hierarchy reconciles from regional stock down to individual RT',()=>{
  const expected={potential:40,interested:8,installed:3,canvassed:16,remaining:32};
  const scope={reg:'Barat',ab:0,kel:0,rw:-1,rt:-1};
  assert.deepEqual(RPDPotential.total(RPDPotential.rows(source,scope)),expected);
  for(const rw of [0,1,2]){
    const parent=RPDPotential.total(RPDPotential.rows(source,{...scope,rw})),children=RPDPotential.groups(source,{...scope,rw}).rows;
    for(const key of Object.keys(expected))assert.equal(children.reduce((n,row)=>n+row[key],0),parent[key]);
  }
  assert.equal(RPDPotential.total(RPDPotential.rows(source,{...scope,rw:1,rt:2})).remaining,16);
  assert.equal(RPDPotential.groups(source,scope).level,'rw');
  assert.equal(RPDPotential.groups(source,{...scope,rw:1}).level,'rt');
});
test('unknown RW/RT remain explicit and missing historical canvassing is not fabricated',()=>{
  assert.equal(RPDPotential.rows(source,{kel:0,rw:0,rt:0}).length,1);
  const old={reg:['Barat'],W:[[0,0,1,1,10,3,2]]};
  assert.equal(RPDPotential.total(RPDPotential.rows(old)).canvassed,null);
  assert.equal(RPDPotential.total(RPDPotential.rows(old)).remaining,7);
});

test('kelurahan/RW/RT selection preserves team and independent report filters',()=>{
  const fs=require('node:fs'),vm=require('node:vm'),code=fs.readFileSync('web/command-center.js','utf8');
  const context={S:{reg:'Barat',ab:0,kel:0,rw:1,rt:1,coordinator:'Fixture Team',statuses:['Done'],start:'2026-11-01'},D:{reg:['Barat','Timur']}};
  vm.createContext(context);vm.runInContext(code.slice(code.indexOf('function selectPotentialScope('),code.indexOf('\nfunction potentialView(')),context);
  for(const [key,value] of [['kel',1],['rw',2],['rt',3]]){
    context.selectPotentialScope(key,value);
    assert.equal(context.S.coordinator,'Fixture Team');assert.equal(context.S.statuses[0],'Done');assert.equal(context.S.start,'2026-11-01');
  }
  context.selectPotentialScope('rw',1);assert.equal(context.S.rt,-1);
  context.selectPotentialScope('ab',1);assert.equal(context.S.reg,'Timur');assert.equal(context.S.coordinator,'');assert.equal(context.S.kel,-1);
});
