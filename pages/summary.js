/* Identity-free cubes. Security comes from separate encrypted datasets and keys,
   not this view adapter. Formulas match backend.analytics for unique snapshots. */
(() => {
  'use strict';
  const ratio=(a,b)=>b?a/b:null;
  const iso=date=>date.toISOString().slice(0,10);
  const date=value=>new Date(value+'T00:00:00Z');
  const endMonth=value=>iso(new Date(Date.UTC(+value.slice(0,4),+value.slice(5,7),0)));
  const blank=()=>({canvassed:0,interested:0,installed:0,pending_customers:0,survey_rows:0,conflicted_status_customers:0,excluded_geography_customers:0});
  const rates=value=>({...value,interest_rate:ratio(value.interested,value.canvassed),installation_rate:ratio(value.installed,value.interested)});
  function bounds(data,scope){
    const m0=+(scope.m0||0),m1=scope.m1==null?data.months.length-1:+scope.m1;
    if(m0<0||m1<m0||m1>=data.months.length)throw new Error('Periode tidak valid.');
    const start=scope.start||(m0?data.months[m0]+'-01':null),end=scope.end||endMonth(data.months[m1]);
    if((start&&!/^\d{4}-\d{2}-\d{2}$/.test(start))||!/^\d{4}-\d{2}-\d{2}$/.test(end)||(start&&start>end))throw new Error('Periksa tanggal mulai dan akhir.');
    return {start,end};
  }
  const geography=(data,scope,row)=>(!scope.reg||data.reg[row[0]]===scope.reg)&&(!(Number(scope.ab)>=0)||row[0]===+scope.ab)&&(!(Number(scope.kel)>=0)||row[1]===+scope.kel);
  const within=(value,b)=>(!b.start||value>=b.start)&&value<=b.end;
  function stock(data,scope){
    const totals=data.P.filter(row=>geography(data,scope,row)).reduce((a,r)=>a.map((v,i)=>v+r[i+2]),[0,0,0]);
    return {potential:totals[0],matched_interested:totals[1],remaining:totals[0]-totals[1],installed:totals[2],scope:'Stok master seluruh periode; mengikuti regional, area bisnis dan kelurahan.'};
  }
  function cohort(rows){
    const m=blank();
    for(const row of rows){m.canvassed+=row[3];m.interested+=row[4];m.installed+=row[5];m.pending_customers+=row[6]}
    m.survey_rows=m.canvassed;return rates(m);
  }
  function prior(data,scope,b){
    if(!b.start||!data.coverage[0])return null;
    const finish=new Date(date(b.start).getTime()-86400000);let begin;
    if(scope.start||scope.end)begin=new Date(finish.getTime()-(date(b.end)-date(b.start)));
    else begin=new Date(Date.UTC(+b.start.slice(0,4),+b.start.slice(5,7)-1-(+(scope.m1??data.months.length-1)-+(scope.m0||0)+1),1));
    const start=iso(begin),end=iso(finish),low=[data.coverage[0],data.meta.tmin||''].sort().at(-1),high=[data.coverage[1],data.meta.tmax||'9999'].sort()[0];
    return start<low||end>high?null:{start,end};
  }
  function analyse(data,scope={},events=[]){
    scope={ab:-1,kel:-1,...scope};
    if(scope.coordinator||scope.statuses?.length)throw new Error('Filtrasi tim/status memerlukan laporan rinci.');
    const b=bounds(data,scope),geo=data.days.filter(r=>geography(data,scope,r)),rows=geo.filter(r=>within(r[2],b)),metrics=cohort(rows),master=stock(data,scope),previousBounds=prior(data,scope,b);
    const groups=(kind,values)=>values.flatMap(value=>{
      const filter={...scope,...(kind==='region'?{reg:value}:{ab:value})};
      if(kind==='region'&&scope.reg&&scope.reg!==value)return [];
      if(kind==='area'&&((scope.reg&&data.reg[value]!==scope.reg)||(+scope.ab>=0&&+scope.ab!==value)))return [];
      const subset=rows.filter(r=>kind==='region'?data.reg[r[0]]===value:r[0]===value),m=cohort(subset),p=stock(data,filter);
      if(!m.canvassed&&!p.potential)return [];
      return [{...m,name:kind==='region'?value:data.abs[value],key:value,potential:p.potential,remaining:p.remaining,contribution:ratio(m.installed,metrics.installed),pending:m.pending_customers,last_activity:subset.length?subset.map(r=>r[2]).sort().at(-1):null,regional:kind==='region'?value:data.reg[value],priority:'Data belum tersedia',reason:'Periksa kesiapan pemasangan pada laporan rinci.',obstacles:{}}];
    });
    const regions=groups('region',[...new Set(data.reg)].sort()),areas=groups('area',data.abs.map((_,i)=>i)),trends=new Map();
    const bucket=month=>{if(!trends.has(month))trends.set(month,{month,...blank(),installation_events:0});return trends.get(month)};
    for(const r of rows){const item=bucket(r[2].slice(0,7));item.canvassed+=r[3];item.interested+=r[4];item.installed+=r[5];item.survey_rows+=r[3]}
    const installRows=data.install_days.filter(r=>geography(data,scope,r));
    for(const r of installRows)if(within(r[2],b))bucket(r[2].slice(0,7)).installation_events+=r[3];
    const timeline=[...trends.values()].sort((a,c)=>a.month.localeCompare(c.month)).map(rates);
    let target={available:false,reason:'Data belum tersedia'};
    const latest=kind=>Object.fromEntries(events.filter(e=>e.kind===kind).map(e=>[e.ref,e.payload]));
    if(+scope.kel<0&&!scope.start&&!scope.end){
      const months=data.months.slice(+(scope.m0||0),+(scope.m1??data.months.length-1)+1),targets=latest('target'),entries=months.map(m=>targets[m+'|'+(scope.reg||'')+'|'+(+scope.ab>=0?data.area_keys[+scope.ab]:'all')]);
      if(entries.length&&entries.every(Boolean)){
        const total=entries.reduce((a,r)=>a+r.target,0),actual=installRows.filter(r=>r[2]>=months[0]+'-01'&&r[2]<=b.end).reduce((a,r)=>a+r[3],0);
        target={available:true,target:total,actual,achievement:ratio(actual,total),remaining:Math.max(0,total-actual),reason:'PAM Done menurut tanggal pemasangan; target terkonfigurasi untuk bulan penuh.'};
      }
    }
    const rules={minimum_sample:20,high_backlog_rate:0.30,cooling_interest_rate:0.10,...latest('rules').all};
    const insights=regions.filter(r=>r.canvassed>=rules.minimum_sample&&r.interested&&r.installation_rate<metrics.installation_rate).slice(0,3).map(r=>({area:r.name,severity:'High',metric:r.installation_rate,baseline:metrics.installation_rate,unit:'installation_rate',action:'Periksa outstanding dan kesiapan pemasangan.'}));
    return {metrics,master,previous:previousBounds?cohort(geo.filter(r=>within(r[2],previousBounds))):null,previous_scope:previousBounds,regions,areas,teams:[],trends:timeline,trend_series:{monthly:timeline},target,insights,rules,scope:{...b,cohort:'PAM unik menurut tanggal survei; stok master seluruh periode.'}};
  }
  function bootstrap(summary,source,role,info,events=[]){
    const latest=events.filter(e=>e.kind==='mapping'&&e.ref==='all').at(-1),values=latest?.payload||{};
    const data=source?Object.fromEntries(['months','abs','reg','kels','svs','st','kl','A','S','E','P','W','G','dic'].filter(k=>k in source).map(k=>[k,source[k]])):{months:summary.months,abs:summary.abs,reg:summary.reg,kels:summary.kels,P:summary.P,svs:[],st:[],kl:[],A:[],S:[],E:[],W:[],dic:{kf:[]}};
    data.meta=source?source.meta:{...summary.meta,rows:summary.days.reduce((a,r)=>a+r[3],0)};
    return {data,role,csrf:'',overrides:Object.fromEntries((source?.svs||[]).flatMap((n,i)=>values[n]?[[i,values[n]]]:[])),mapping_version:latest?.id||0,geography:[...new Map([...summary.days,...summary.P].map(r=>[r[0]+':'+r[1],[r[0],r[1]]])).values()],area_keys:summary.area_keys,data_owner:info.owner||'',source:info,capabilities:{customer_detail:role==='owner'||!!info.operational_access,aggregate_only:!source&&!info.operational_access,browser_only:true,details_loaded:!!source}};
  }
  async function project(source){
    if([...source.abs,...source.reg].some(v=>/[^\x00-\x7f]/.test(v)))return null;
    const fields=['pam','ab','kel','sv','mi','t','c1','kf','fa','mt','kd','mf','pr','sc','tg'],r=source.rec,n=r?.pam?.length;
    if(!Number.isInteger(n)||fields.some(k=>!Array.isArray(r[k])||r[k].length!==n))return null;
    if(r.it&&(!Array.isArray(r.it)||r.it.length!==n||r.it.some(v=>v!==0&&v!==1&&v!==true&&v!==false)))return null;
    const sourceDate=value=>{if(!value)return null;value=Math.trunc(Number(value));const y=Math.floor(value/10000),year=y<100?2000+y:y,month=Math.floor(value/100)%100,day=value%100,str=String(year).padStart(4,'0')+'-'+String(month).padStart(2,'0')+'-'+String(day).padStart(2,'0');try{return iso(date(str))===str?str:null}catch{return null}};
    const seen=new Set(),days=new Map(),installs=new Map();let first=null,last=null;
    for(let i=0;i<n;i++){
      const raw=String(r.pam[i]).trim(),pam=/^[0-9]{1,9}$/.test(raw)?raw.replace(/^0+/,''):'';
      const survey=sourceDate(r.t[i]),area=r.ab[i],kel=r.kel[i],sv=r.sv[i];
      if(!pam||!survey||![[area,source.abs],[kel,source.kels],[sv,source.svs]].every(([k,a])=>Number.isInteger(k)&&k>=0&&k<a.length))continue;
      if(seen.has(pam))return null;seen.add(pam);
      const interest=r.it?!!r.it[i]:String(source.dic.c1[r.c1[i]]||'').trim().toLowerCase()==='berminat',status=String(source.dic.kf[r.kf[i]]||'').trim().toLowerCase(),done=status==='done',key=area+':'+kel+':'+survey;
      if(!days.has(key))days.set(key,[area,kel,survey,0,0,0,0]);const row=days.get(key);row[3]++;row[4]+=+interest;row[5]+=+(interest&&done);row[6]+=+(interest&&!done&&status!=='cancel');
      if(!first||survey<first)first=survey;if(!last||survey>last)last=survey;
      const installation=done&&sourceDate(r.mt[i]);if(installation){const key=area+':'+kel+':'+installation;if(!installs.has(key))installs.set(key,[area,kel,installation,0]);installs.get(key)[3]++}
    }
    const area_keys=await Promise.all(source.abs.map(async(name,i)=>{const region=source.reg[i].trim().toLowerCase(),area=name.trim().toLowerCase(),input=new TextEncoder().encode(region.length+':'+region+area);return [...new Uint8Array(await crypto.subtle.digest('SHA-256',input))].map(b=>b.toString(16).padStart(2,'0')).join('').slice(0,24)}));
    return {aggregate_version:1,months:source.months,abs:source.abs,reg:source.reg,kels:source.kels,P:source.P,days:[...days.values()],install_days:[...installs.values()],area_keys,coverage:[first,last],meta:{tmin:source.meta.tmin,tmax:source.meta.tmax,...(source.meta.reporting_date?{reporting_date:source.meta.reporting_date}:{})}};
  }
  globalThis.RPDSummary={analyse,bootstrap,bounds,project};
})();
