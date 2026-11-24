const {test}=require('node:test'),assert=require('node:assert/strict');
require('../web/potential.js');
const source={reg:['Barat','Timur'],W:[[0,0,1,1,10,3,2,5],[0,0,1,2,20,4,1,8],[0,0,2,1,8,1,0,3],[0,1,1,1,4,1,0,2],[1,2,1,1,9,2,1,4],[0,0,0,0,2,0,0,0]]};
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
