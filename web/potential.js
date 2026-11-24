/* MASTER DATA potential only, all periods. W columns 0..6 keep legacy meanings;
   column 7 counts eligible master customers linked to the survey workbook. */
(() => {
  'use strict';
  const inArea=(source,scope,row)=>(!scope.reg||source.reg[row[0]]===scope.reg)&&(!(scope.ab>=0)||row[0]===scope.ab)&&(!(scope.kel>=0)||row[1]===scope.kel);
  function rows(source,scope={}){
    return source.W.filter(row=>inArea(source,scope,row)&&(!(scope.rw>=0)||row[2]===scope.rw)&&(!(scope.rt>=0)||row[3]===scope.rt));
  }
  function total(selected){
    const known=selected.every(row=>Number.isInteger(row[7]));
    return selected.reduce((value,row)=>({potential:value.potential+row[4],interested:value.interested+row[5],
      installed:value.installed==null||!Number.isInteger(row[6])?null:value.installed+row[6],
      canvassed:known?value.canvassed+row[7]:null,remaining:value.remaining+row[4]-row[5]}),
      {potential:0,interested:0,installed:0,canvassed:known?0:null,remaining:0});
  }
  function groups(source,scope={}){
    const level=!(scope.kel>=0)?'kel':!(scope.rw>=0)?'rw':'rt',map=new Map();
    for(const row of rows(source,scope)){
      const identity=JSON.stringify(level==='kel'?row.slice(0,2):level==='rw'?row.slice(0,3):row.slice(0,4));
      if(!map.has(identity))map.set(identity,{ab:row[0],kel:row[1],rw:level==='kel'?-1:row[2],rt:level==='rt'?row[3]:-1,rows:[]});
      map.get(identity).rows.push(row);
    }
    return {level,rows:[...map.values()].map(({rows,...group})=>({...group,...total(rows)}))};
  }
  globalThis.RPDPotential={rows,total,groups,inArea};
})();
