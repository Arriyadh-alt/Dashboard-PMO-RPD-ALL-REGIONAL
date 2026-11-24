/* Same-origin API only. Customer rows and credentials are never persisted in the browser. */
let A = null, CSRF = '', SOURCE = {}, CAP = {}, BOOT = {}, QUALITY = null, ADMIN = null;
let analysisRevision = 0, viewRevision = 0, searchRevision = 0, searchTimer, PAGE = 0;
let CURRENT_ROWS = [], CASE = null, caseReturnFocus = null, regionSort = 'installation_rate', trendUnit = 'monthly';
let renderedTab='';const legacyPanels=new Map();
let gridSequence=0;const grids=new Map(),gridStates=new Map();
const caseSorts=['pam','survey_date','regional','surveyor','canvassing','status','fa_date','obstacle','potential_status','arrears','followup'];

function rememberLegacyPanel(){if(renderedTab)document.querySelectorAll('#main .legacy-report').forEach((panel,index)=>legacyPanels.set(renderedTab+':'+(panel.id||index),panel.open))}
const PAGE_SIZE = 50;
const pageTitles = {ringkasan:'Ringkasan', analytics:'Analisis Kinerja', kelurahan:'Data Wilayah', korlap:'Kinerja Tim', outstanding:'Outstanding', data:'Cari PAM ID', catatan:'Admin'};
const unavailable = 'Data belum tersedia';
const percent = value => value == null ? unavailable : PC(value);
const number = value => value == null ? unavailable : N(value);
const timeLabel = value => value ? new Intl.DateTimeFormat('id-ID',{dateStyle:'medium',timeStyle:'short'}).format(new Date(value)) : unavailable;
const scopeKeys = ['m0','m1','reg','ab','kel','coordinator','statuses','start','end'];
const scopeObject = () => Object.fromEntries(scopeKeys.map(key=>[key,S[key]]).filter(([,value])=>value!==''));
const params = () => {const p=new URLSearchParams();for(const [key,value] of Object.entries(scopeObject())){if(key==='statuses')value.forEach(status=>p.append('status',status));else p.set(key,value)}return p};
const notice = (message,warning=false) => `<p class="scope-note${warning?' warning':''}">${esc(message)}</p>`;
const blank = (title,message) => `<section class="empty-state"><h2>${esc(title)}</h2><p>${esc(message)}</p></section>`;
const skeleton = () => `<div class="skeleton" role="status" aria-label="Memuat laporan"><div class="skeleton-line"></div><div class="skeleton-line"></div><div class="skeleton-line"></div><p class="mu sm">${window.RPDStatic?'Memuat laporan lokal…':'Memuat data terotorisasi…'}</p></div>`;
const option = (value,text,selected) => `<option value="${esc(value)}"${selected?' selected':''}>${esc(text)}</option>`;
const setStatus = message => {$('#service-status').textContent=message};

async function api(path, options={}) {
  if(window.RPDStatic)return window.RPDStatic.request(path,options);
  let response;
  try {response=await fetch(path,{credentials:'same-origin',...options,headers:{...(options.body?{'Content-Type':'application/json'}:{}),...(CSRF?{'X-CSRF-Token':CSRF}:{}),...options.headers}})}
  catch {throw new Error('Backend tidak terjangkau. Periksa koneksi dan coba kembali.')}
  const data=await response.json().catch(()=>({detail:'Backend privat diperlukan. GitHub Pages tidak menyediakan API data.'}));
  if(!response.ok){if(response.status===401&&path!=='/api/login'){localLogout();$('#le').textContent='Sesi berakhir. Silakan masuk kembali.'}throw new Error(typeof data.detail==='string'?data.detail:'Nilai atau filter tidak valid.')}
  return data;
}

async function download(path, filename) {
  if(window.RPDStatic)return window.RPDStatic.download(path,filename);
  const response=await fetch(path,{credentials:'same-origin'});
  if(!response.ok){const error=await response.json().catch(()=>({}));if(response.status===401)localLogout();throw new Error(error.detail||'Laporan tidak tersedia.')}
  const url=URL.createObjectURL(await response.blob()), link=document.createElement('a');
  link.href=url;link.download=filename;document.body.appendChild(link);link.click();link.remove();setTimeout(()=>URL.revokeObjectURL(url),10000);
}

function init(payload) {
  BOOT=payload;D=payload.data;ROLE=payload.role;CSRF=payload.csrf;SOURCE=payload.source;CAP=payload.capabilities;OV=payload.overrides;WM=null;
  Object.assign(S,{m0:0,m1:D.months.length-1,reg:'',ab:-1,kel:-1,rw:-1,rt:-1,coordinator:'',statuses:[],start:'',end:'',tab:'ringkasan',q:'',open:'',all:0,advanced:false});
  window.RPDPublic?.hide();
  $('#lg').hidden=true;$('#app').hidden=false;$('#out').hidden=false;$('#role').textContent=ROLE==='owner'?'Admin':'Guest';
  $('#sub').textContent='Tanggal survei: '+fd(D.meta.tmin)+' – '+fd(D.meta.tmax);
  $('#tab-catatan').hidden=ROLE!=='owner';document.querySelector('.export-menu').hidden=!CAP.customer_detail;
  for(const tab of ['korlap','outstanding','data'])$('#tab-'+tab).hidden=!CAP.customer_detail;
  try{const saved=JSON.parse(sessionStorage.getItem('rpd_session_scope')||'null'),scope=resolvePreset(saved);if(scope)Object.assign(S,scope)}catch{}
  S.coordinator='';S.statuses=[];$('#lp').value='';$('#li').value='';refresh();$('#main').focus({preventScroll:true});
  window.RPDStatic?.ready(ROLE,BOOT);
}

function localLogout() {
  S.dq={p:'',k:'',s:'',c:0,f:0,r:0};
  window.RPDStatic?.stop();
  analysisRevision++;viewRevision++;searchRevision++;clearTimeout(searchTimer);
  D=REC=WM=A=QUALITY=ADMIN=null;OV={};ROLE=CSRF='';SOURCE=CAP=BOOT={};CURRENT_ROWS=[];CASE=null;PAGE=0;grids.clear();gridStates.clear();legacyPanels.clear();renderedTab='';
  const dialog=$('#case-dialog');if(dialog?.open)dialog.close();if(dialog)dialog.remove();
  try{sessionStorage.removeItem('rpd_session_scope')}catch{}
  $('#main').innerHTML='';$('#app').hidden=true;$('#lg').hidden=false;$('#out').hidden=true;$('#lb').disabled=false;$('#lb').textContent='Masuk';$('#li').value='';$('#lp').value='';$('#le').textContent='';$('#sub').textContent='';setStatus('');$('#li').focus();
  window.RPDPublic?.show();
}

async function go() {
  if($('#lb').disabled)return;performance.mark('rpd:login-start');$('#lb').disabled=true;$('#lb').textContent='Memuat…';$('#le').textContent='Memeriksa akun…';$('#login-form').setAttribute('aria-busy','true');
  try {const payload=await api('/api/login',{method:'POST',body:JSON.stringify({account:$('#li').value,password:$('#lp').value})});init(window.RPDStatic?payload:await api('/api/bootstrap'))}
  catch(error){$('#le').textContent=error.message;$('#lb').disabled=false;$('#lb').textContent='Masuk'}
  finally{$('#lp').value='';$('#login-form').setAttribute('aria-busy','false')}
}

async function ensureOperationalData(){
  if(!window.RPDStatic||!CAP.customer_detail||CAP.details_loaded)return;
  const loaded=await api('/api/bootstrap?details=1');if(!D)return;
  D=loaded.data;BOOT=loaded;CAP=loaded.capabilities;OV=loaded.overrides;WM=null;fill();
}

async function refresh() {
  if(!D)return;rememberLegacyPanel();const revision=++analysisRevision;viewRevision++;searchRevision++;A=null;PAGE=0;setStatus('');fill();
  $('#main').setAttribute('aria-busy','true');$('#main').innerHTML=skeleton();
  try{sessionStorage.setItem('rpd_session_scope',JSON.stringify(presetScope()))}catch{}
  try {
    if(S.tab!=='ringkasan'||S.coordinator||S.statuses.length)await ensureOperationalData();
    if(revision!==analysisRevision||!D)return;
    const result=await api('/api/analysis?'+params()+'&view='+encodeURIComponent(S.tab==='kelurahan'&&S.advanced?'details':S.tab));if(revision!==analysisRevision||!D)return;A=result;render();performance.mark('rpd:usable')}
  catch(error){if(revision!==analysisRevision)return;setStatus(error.message);$('#main').innerHTML=blank('Laporan belum tersedia','Ubah filter atau coba kembali. Tidak ada hasil lama yang ditampilkan sebagai hasil filter baru.')+'<p><button id="retry-analysis">Coba kembali</button></p>'}
  finally{if(revision===analysisRevision)$('#main').setAttribute('aria-busy','false')}
}

function presetList() {try{const data=JSON.parse(localStorage.getItem('rpd_filter_presets')||'{}');return data&&typeof data==='object'&&!Array.isArray(data)?data:{}}catch{return {}}}
function savePresetList(value){try{localStorage.setItem('rpd_filter_presets',JSON.stringify(value))}catch{setStatus('Preset tidak dapat disimpan pada peramban ini.')}}

function presetScope(){
  return {version:2,scope:scopeObject(),field:{rw:S.rw??-1,rt:S.rt??-1},period:[D.months[S.m0],D.months[S.m1]],openingBucket:S.m0===0,areaKey:S.ab>=0?BOOT.area_keys[S.ab]:null,kelName:S.kel>=0?D.kels[S.kel]:null};
}

function resolvePreset(value){
  if(value?.version!==2||!value.scope||!Array.isArray(value.period))return null;
  const scope=value.scope,m0=D.months.indexOf(value.period[0]),m1=D.months.indexOf(value.period[1]);
  const ab=value.areaKey===null?-1:BOOT.area_keys.indexOf(value.areaKey);
  if(m0<0||m1<m0||(value.areaKey!==null&&ab<0))return null;
  if(!scope.start&&value.openingBucket!==(m0===0))return null;
  const reg=scope.reg&&ab>=0?D.reg[ab]:scope.reg||'';
  if(reg&&!D.reg.includes(reg))return null;
  const geography=BOOT.geography.filter(([area])=>(!reg||D.reg[area]===reg)&&(ab<0||area===ab));
  const kelIds=[...new Set(geography.map(([,kel])=>kel))].filter(kel=>D.kels[kel]===value.kelName);
  if(value.kelName!==null&&kelIds.length!==1)return null;
  const coordinator=scope.coordinator||'',teams=D.S.filter(row=>(!reg||D.reg[row[1]]===reg)&&(ab<0||row[1]===ab)).map(eKl);
  if(coordinator&&!teams.includes(coordinator))return null;
  if(!Array.isArray(scope.statuses)||scope.statuses.some(status=>!D.dic.kf.includes(status)))return null;
  const neighborhood=key=>Number.isInteger(value.field?.[key])&&value.field[key]>=0&&value.field[key]<=999?value.field[key]:-1;
  return {m0,m1,reg,ab,kel:value.kelName===null?-1:kelIds[0],rw:neighborhood('rw'),rt:neighborhood('rt'),coordinator,statuses:scope.statuses,start:scope.start||'',end:scope.end||''};
}

async function resolvePresetForUse(value){
  // Operational names/statuses are intentionally absent from the login overview.
  // Load them only after an explicit request, then validate against the active source.
  if(value?.scope?.coordinator||value?.scope?.statuses?.length)await ensureOperationalData();
  return resolvePreset(value);
}

function fill() {
  if(!D)return;
  if(!$('#fco'))$('#gf').insertAdjacentHTML('beforeend',`<details class="more-filters" id="extra-filters"><summary>Periode khusus &amp; filter lainnya</summary><input id="filter-search" type="hidden"><div class="advanced-grid"><label class="field">Dari bulan<select id="f0"></select></label><label class="field">Sampai bulan<select id="f1"></select></label><label class="field">Dari tanggal<input id="fstart" type="date"></label><label class="field">Sampai tanggal<input id="fend" type="date"></label><label class="field team-filter">Koordinator / tim<select id="fco"></select></label><label class="field status-filter">Status pemasangan<select id="fstatus" multiple size="3"></select></label></div><details class="preset-row"><summary>Filter tersimpan</summary><input id="preset-name" aria-label="Nama filter" maxlength="50" placeholder="Nama filter"><button id="save-preset">Simpan</button><select id="preset-list" aria-label="Filter tersimpan"></select><button id="load-preset">Terapkan</button><button id="delete-preset">Hapus</button></details></details>`);
  document.querySelector('.team-filter').hidden=!CAP.customer_detail||!['korlap','outstanding','data'].includes(S.tab);
  document.querySelector('.status-filter').hidden=!CAP.customer_detail||!['outstanding','data'].includes(S.tab);
  $('#f0').innerHTML=D.months.map((_,i)=>option(i,ML(i),i===S.m0)).join('');
  $('#f1').innerHTML=D.months.map((_,i)=>option(i,ML(i),i===S.m1)).join('');
  $('#fr').innerHTML=option('','Semua regional',!S.reg)+[...new Set(D.reg)].sort().map(region=>option(region,region,region===S.reg)).join('');
  const search=($('#filter-search')?.value||'').toLocaleLowerCase('id');
  $('#fa').innerHTML=option(-1,'Semua area bisnis',S.ab<0)+D.abs.map((name,i)=>({name,i})).filter(item=>(!S.reg||D.reg[item.i]===S.reg)&&(!search||item.name.toLowerCase().includes(search)||item.i===S.ab)).map(item=>option(item.i,item.name,item.i===S.ab)).join('');
  const geography=BOOT.geography||D.P.map(row=>[row[0],row[1]]);
  const kelIds=[...new Set(geography.filter(([area])=>(!S.reg||D.reg[area]===S.reg)&&(S.ab<0||area===S.ab)).map(([,kel])=>kel))];
  $('#fk').innerHTML=option(-1,'Semua kelurahan',S.kel<0)+kelIds.filter(i=>!search||D.kels[i].toLowerCase().includes(search)||i===S.kel).sort((a,b)=>D.kels[a].localeCompare(D.kels[b],'id')).map(i=>option(i,D.kels[i],i===S.kel)).join('');
  const coordinators=[...new Set(D.S.filter(row=>(!S.reg||D.reg[row[1]]===S.reg)&&(S.ab<0||row[1]===S.ab)).map(eKl))].sort();
  if(S.coordinator&&!coordinators.includes(S.coordinator))S.coordinator='';
  if(S.kel>=0&&!kelIds.includes(S.kel))S.kel=-1;
  $('#fco').innerHTML=option('','Semua koordinator / tim',!S.coordinator)+coordinators.map(name=>option(name,LB[name]||name,name===S.coordinator)).join('');
  $('#fstatus').innerHTML=D.dic.kf.filter(Boolean).map(status=>option(status,status,S.statuses.includes(status))).join('');
  $('#fstart').value=S.start;$('#fend').value=S.end;
  const day=d=>[d.getFullYear(),String(d.getMonth()+1).padStart(2,'0'),String(d.getDate()).padStart(2,'0')].join('-'),today=new Date(),week=new Date(today),month=new Date(today);week.setDate(week.getDate()-6);month.setDate(1);
  $('#fperiod').value=!S.start&&!S.end&&!S.m0&&S.m1===D.months.length-1?'all':S.end===day(today)&&S.start===day(today)?'today':S.end===day(today)&&S.start===day(week)?'week':S.end===day(today)&&S.start===day(month)?'month':'custom';
  const selectedPreset=$('#preset-list').value;$('#preset-list').innerHTML=option('','Pilih preset',!selectedPreset)+Object.keys(presetList()).map(name=>option(name,name,name===selectedPreset)).join('');
  const active=[];if(S.reg)active.push(S.reg);if(S.ab>=0)active.push(D.abs[S.ab]);if(S.kel>=0)active.push(D.kels[S.kel]);if(S.coordinator)active.push(S.coordinator);active.push(...S.statuses);if(S.start||S.end)active.push((S.start||'awal sumber')+' → '+(S.end||'akhir bulan'));
  $('#active-filters').innerHTML=(active.length?active:['Seluruh cakupan operasional']).map(text=>`<span class="chip">${esc(text)}</span>`).join('');
  $('#period-label').textContent=(S.start||ML(S.m0))+' – '+(S.end||ML(S.m1));$('#filter-text').textContent='Filter laporan'+(active.length||S.m0||S.m1!==D.months.length-1?' · aktif':'');
}

function previousText(key,rate=false) {
  if(!A.previous)return 'Periode sebelumnya: Insufficient Data';
  const previous=A.previous[key],current=A.metrics[key];if(previous==null||current==null)return 'Perbandingan: Insufficient Data';
  const change=current-previous;return (change>0?'+':'')+(rate?(change*100).toFixed(1).replace('.',',')+' pp':N(change))+' vs '+A.previous_scope.start+' – '+A.previous_scope.end;
}

function metricCard(title,value,change,definition,route,rate=false) {
  const missing=value==null;return `<article class="intel-card"><span class="metric-label" title="${esc(definition)}">${esc(title)}</span><button class="metric-value${missing?' unavailable':''}" data-route="${route}" title="${esc(definition)}">${missing?unavailable:rate?percent(value):number(value)}</button></article>`;
}

function vExecutive() {
  const m=A.metrics,master=A.master;
  return `<div class="intel-kpis">`+[
    metricCard('Total Potensi',master.potential,'',master.scope,'kelurahan'),
    metricCard('Tercanvassing',m.canvassed,'','PAM unik menurut tanggal survei terpilih.','kelurahan'),
    metricCard('Berminat',m.interested,'','PAM unik Berminat pada periode survei terpilih.','kelurahan'),
    metricCard('Terpasang',m.installed,'','PAM unik Berminat dengan status Done, pada periode survei terpilih. Bukan jumlah pemasangan menurut tanggal pasang.','kelurahan'),
    metricCard('Sisa Potensi',master.remaining,'',master.scope,'kelurahan')
  ].join('')+`</div><p class="scope-caption">Potensi: stok master seluruh periode. Kinerja: PAM unik pada tanggal survei terpilih.${m.excluded_geography_customers||m.conflicted_status_customers?' Konflik wilayah/status dikecualikan dari metrik terkait.':''}</p>`+
  `<div class="overview-charts"><section class="panel"><h2>Tren Kinerja</h2>${performanceChart()}</section><section class="panel">${bars('Terpasang per Regional',A.regions.map(r=>r.installed),A.regions.map(r=>r.name))}</section></div>`+
  `<div class="overview-conversion"><span>Persentase Berminat <strong>${percent(m.interest_rate)}</strong></span><span>Persentase Terpasang <strong>${percent(m.installation_rate)}</strong></span>${A.target.available?`<span>Capaian Target <strong>${percent(A.target.achievement)}</strong></span>`:''}</div>`+regionTable()+
  (A.insights.filter(i=>i.severity==='High').length?`<h2>Catatan Penting</h2><div class="compact-insights">${A.insights.filter(i=>i.severity==='High').slice(0,3).map(item=>`<article><strong>${esc(item.area)}</strong><p>Persentase terpasang ${percent(item.metric)}, di bawah cakupan terpilih ${percent(item.baseline)}.</p><p>Tindak lanjut: ${esc(item.action)}</p></article>`).join('')}</div>`:'');
}

function performanceChart(){
  const rows=A.trends;if(!rows.length)return '<p class="mu">Tidak ada aktivitas pada periode ini.</p>';
  const series=[['canvassed','Tercanvassing','#173d60'],['interested','Berminat','#178678'],['installation_events','Terpasang','#8296a6']],width=600,height=185,left=48,right=15,top=12,bottom=28,max=Math.max(1,...rows.flatMap(r=>series.map(([key])=>r[key]||0))),x=i=>left+(width-left-right)*(rows.length===1?.5:i/(rows.length-1)),y=v=>top+(height-top-bottom)*(1-v/max);
  return '<div class="chart-key">'+series.map(([,label,color])=>`<span><i style="background:${color}"></i>${label}</span>`).join('')+'</div>'+`<svg class="trend-svg" viewBox="0 0 ${width} ${height}" role="img" aria-label="Tren tercanvassing, berminat dan pemasangan per bulan">`+[0,.5,1].map(t=>`<line x1="${left}" x2="${width-right}" y1="${y(max*t)}" y2="${y(max*t)}" stroke="var(--ln)"/><text x="${left-6}" y="${y(max*t)+3}" text-anchor="end">${N(max*t)}</text>`).join('')+series.map(([key,label,color])=>`<polyline points="${rows.map((r,i)=>x(i)+','+y(r[key]||0)).join(' ')}" fill="none" stroke="${color}" stroke-width="2"/>`+rows.map((r,i)=>`<circle cx="${x(i)}" cy="${y(r[key]||0)}" r="3" fill="${color}"><title>${esc(r.month+' · '+label+': '+N(r[key]||0))}</title></circle>`).join('')).join('')+rows.filter((_,i)=>i===0||i===rows.length-1||i%Math.max(1,Math.ceil(rows.length/5))===0).map(r=>`<text x="${x(rows.indexOf(r))}" y="${height-6}" text-anchor="middle">${esc(r.month)}</text>`).join('')+'</svg><p class="chart-caption">Survei menurut tanggal survei; terpasang menurut tanggal pemasangan.</p><details><summary class="sm">Lihat angka tren</summary>'+dataTable(['Bulan','Tercanvassing','Berminat','Terpasang'],rows.map(r=>[esc(r.month),N(r.canvassed),N(r.interested),N(r.installation_events)]))+'</details>';
}

function funnelStage(title,count,base,previous,detached=false) {
  const conversion=base==null?null:R(count,base),drop=base==null?null:base-count;
  return `<div class="funnel-stage${detached?' detached':''}"><div class="funnel-heading"><span>${esc(title)}</span><strong>${number(count)}</strong></div>${detached?'':`<div class="funnel-track"><i style="width:${Math.min(100,(conversion??0)*100)}%"></i></div>`}<small>${detached?'Stok master terpisah; konversi ke kohort survei: Insufficient Data':base==null?'Baseline kohort survei; bukan persentase dari master':'Konversi tahap '+percent(conversion)+' · drop-off '+number(drop)+' ('+percent(base?drop/base:null)+')'}</small><small>Periode sebelumnya: ${previous==null?unavailable:N(previous)}</small></div>`;
}

function vAnalytics() {
  const m=A.metrics,target=A.target;
  return `<div class="intel-panels"><section class="panel"><h2>Ringkasan Konversi</h2><div class="funnel">${funnelStage('Total Potensi · stok master',A.master.potential,null,null,true)}${funnelStage('Tercanvassing · PAM unik',m.canvassed,null,A.previous?.canvassed)}${funnelStage('Berminat · periode survei sama',m.interested,m.canvassed,A.previous?.interested)}${funnelStage('Terpasang · periode survei sama',m.installed,m.interested,A.previous?.installed)}</div><p class="footer-definition">Persentase terpasang dari tercanvassing: ${percent(R(m.installed,m.canvassed))}. Cakupan master → canvassed tidak dihitung karena populasi master eligible belum dapat ditautkan dengan aman.</p></section><section class="panel"><h2>Target &amp; Realisasi</h2>${target.available?`<div class="compact-stats"><div class="compact-stat"><span>Target bulanan terpilih</span><strong>${N(target.target)}</strong></div><div class="compact-stat"><span>Terpasang · tanggal pasang</span><strong>${N(target.actual)}</strong></div><div class="compact-stat"><span>Sisa target</span><strong>${N(target.remaining)}</strong></div></div><p class="progress-label">Pencapaian ${percent(target.achievement)}</p><div class="bar-compact"><i style="width:${Math.min(100,target.achievement*100)}%"></i></div>`:blank('Target belum tersedia',target.reason)}${notice(target.reason)}<p class="mu sm">Kebutuhan harian, tren target historis dan estimasi selesai: ${unavailable}. Tidak ada target atau hari kerja yang dibuat otomatis.</p>${ROLE==='owner'?'<p><button data-route="catatan">Konfigurasi target dengan bukti sumber</button></p>':''}</section></div>
  <h2>Tren aktivitas aktual</h2>${notice('Tanggal survei untuk canvassed/minat; tanggal pemasangan untuk event Done. Status kohort adalah status dalam impor saat ini, bukan status historis pada akhir bulan. Nilai nol tidak mengonfirmasi tidak ada aktivitas di luar cakupan sumber.')}
  <div class="inline-controls"><label for="trend-unit">Agregasi aktivitas</label><select id="trend-unit">${[['daily','Harian'],['weekly','Mingguan ISO'],['monthly','Bulanan']].map(([key,text])=>option(key,text,key===trendUnit)).join('')}</select><span class="mu">Menampilkan tanggal dengan catatan; bukan absensi atau snapshot historis.</span></div><div class="two trend-grid">${trendCharts()}</div>${regionTable()}`;
}

function trendCharts() {
  const rows=A.trend_series?.[trendUnit]||A.trends,labels=rows.map(row=>row.month);
  return bars('PAM unik tercanvassing · tanggal survei',rows.map(row=>row.canvassed),labels)+bars('PAM unik berminat · tanggal survei',rows.map(row=>row.interested),labels)+bars('PAM unik Done · tanggal pemasangan',rows.map(row=>row.installation_events),labels);
}

function dataTable(headers,rows,empty='Tidak ada data yang cocok dengan filter.',remote=false) {
  const {sort:caseSort='',descending:caseDescending=false}=S.dq;
  if(remote)return `<div class="tw"><table class="report-table"><thead><tr>${headers.map((header,i)=>`<th scope="col" aria-sort="${caseSort===caseSorts[i]?(caseDescending?'descending':'ascending'):'none'}"><button data-case-sort="${caseSorts[i]}">${header} ${caseSort===caseSorts[i]?(caseDescending?'↓':'↑'):'↕'}</button></th>`).join('')}</tr></thead><tbody>${rows.length?rows.map(cells=>'<tr>'+cells.map((cell,i)=>`<td${i===0?' class="text"':''}>${cell}</td>`).join('')+'</tr>').join(''):`<tr><td colspan="${headers.length}">${esc(empty)}</td></tr>`}</tbody></table></div>`;
  const id=S.tab+'-'+gridSequence++;grids.set(id,{headers,rows,empty});return `<section class="table-grid" data-grid="${id}">${gridHTML(id)}</section>`;
}

function gridHTML(id){
  const {headers,rows,empty}=grids.get(id),state=gridStates.get(id)||{q:'',page:0,col:-1,direction:1};gridStates.set(id,state);
  const plain=value=>String(value??'').replace(/<[^>]*>/g,' ').replace(/&[^;]+;/g,' ').trim(),text=value=>plain(value).toLocaleLowerCase('id');
  let selected=rows.filter(row=>!state.q||row.some(cell=>text(cell).includes(state.q.toLocaleLowerCase('id'))));
  if(state.col>=0)selected.sort((a,b)=>{let x=plain(a[state.col]),y=plain(b[state.col]);const number=v=>/^[-\d.,%\s]+$/.test(v)?Number(v.replace(/\./g,'').replace(',','.').replace(/[%\s]/g,'')):NaN,nx=number(x),ny=number(y);return (Number.isFinite(nx)&&Number.isFinite(ny)?nx-ny:x.localeCompare(y,'id',{numeric:true}))*state.direction});
  const size=25,pages=Math.max(1,Math.ceil(selected.length/size));state.page=Math.min(state.page,pages-1);
  return (rows.length>8?`<div class="table-controls"><input type="search" data-grid-search="${id}" aria-label="Cari dalam tabel" placeholder="Cari dalam tabel" value="${esc(state.q)}"><span>${N(selected.length)} baris</span></div>`:'')+`<div class="tw"><table class="report-table"><thead><tr>${headers.map((header,i)=>`<th scope="col" aria-sort="${state.col===i?(state.direction===1?'ascending':'descending'):'none'}"><button data-grid-sort="${id}" data-column="${i}">${header} ${state.col===i?(state.direction===1?'↑':'↓'):'↕'}</button></th>`).join('')}</tr></thead><tbody>${selected.length?selected.slice(state.page*size,(state.page+1)*size).map(cells=>'<tr>'+cells.map((cell,index)=>`<td${index===0?' class="text"':''}>${cell}</td>`).join('')+'</tr>').join(''):`<tr><td colspan="${headers.length}" class="text">${esc(empty)}</td></tr>`}</tbody></table></div>`+(pages>1?`<div class="pagination"><span>Halaman ${state.page+1} dari ${pages}</span><div><button data-grid-page="${id}" data-step="-1"${state.page===0?' disabled':''}>Sebelumnya</button> <button data-grid-page="${id}" data-step="1"${state.page===pages-1?' disabled':''}>Berikutnya</button></div></div>`:'');
}

function updateGrid(id){const container=document.querySelector('[data-grid="'+id+'"]');if(container)container.innerHTML=gridHTML(id)}

function regionTable() {
  const rows=[...A.regions].sort((a,b)=>(b[regionSort]??-1)-(a[regionSort]??-1));
  return `<h2>Kinerja Regional</h2>`+dataTable(['Regional','Potensi','Tercanvassing','Berminat','Terpasang','Sisa Potensi','Persentase Terpasang'],rows.map(row=>[`<button data-region="${esc(row.name)}">${esc(row.name)}</button>`,N(row.potential),N(row.canvassed),N(row.interested),N(row.installed),N(row.remaining),percent(row.installation_rate)]));
}

function vRegional() {
  return (CAP.customer_detail?potentialView():'')+`<details class="legacy-report"><summary>Kinerja Regional &amp; Area Bisnis</summary>`+regionTable()+`<h2>Area Bisnis</h2>`+dataTable(['Area Bisnis','Regional','Tercanvassing','Berminat','Terpasang','Sisa Potensi','Persentase Terpasang'],A.areas.map(row=>[`<button data-area="${row.key}">${esc(row.name)}</button>`,esc(row.regional),N(row.canvassed),N(row.interested),N(row.installed),N(row.remaining),percent(row.installation_rate)]))+
  '<p class="scope-caption">Potensi mengikuti stok master seluruh periode; kinerja mengikuti filter tanggal survei.</p>'+
  '</details>'+(CAP.customer_detail?`<details class="legacy-report" id="area-details"${S.advanced?' open':''}><summary>Analisis Kinerja &amp; Prioritas Wilayah</summary>${S.advanced?vAnalytics()+dataTable(['Area Bisnis','Prioritas','Alasan'],A.areas.map(r=>[esc(r.name),esc(r.priority),esc(r.reason)])):''}</details><details class="legacy-report"><summary>Rincian Kelurahan, RW &amp; RT Sebelumnya</summary>${notice('Stok master seluruh periode; hanya filter regional dan area bisnis berlaku.')}${vKel()}</details>`:'');
}

function selectPotentialScope(key,value){
  const order=['reg','ab','kel','rw','rt'],index=order.indexOf(key);if(index<0)return false;
  S[key]=value;for(const child of order.slice(index+1))S[child]=-1;
  if(key==='ab'&&S.ab>=0)S.reg=D.reg[S.ab];
  if(index<2)S.coordinator='';
  return true;
}

function potentialView(){
  const parent=D.W.filter(row=>RPDPotential.inArea(D,S,row)),rws=[...new Set(parent.map(row=>row[2]))].sort((a,b)=>a-b);
  if(S.kel<0||!rws.includes(S.rw))S.rw=S.rt=-1;
  const rts=[...new Set(parent.filter(row=>row[2]===S.rw).map(row=>row[3]))].sort((a,b)=>a-b);
  if(S.rw<0||!rts.includes(S.rt))S.rt=-1;
  const neighborhood=(kind,value)=>value?kind+' '+String(value).padStart(3,'0'):kind+' tidak tercatat';
  const select=(key,label,items,selected,disabled=false)=>`<label class="field potential-${key}">${label}<input id="potential-${key}" list="potential-options-${key}" type="text" autocomplete="off" aria-label="${label} potensi" placeholder="Pilih ${label.toLowerCase()}" value="${esc(items.find(item=>item.value===selected)?.label||'')}"${disabled?' disabled':''}><datalist id="potential-options-${key}">${items.map(item=>`<option value="${esc(item.label)}" data-value="${esc(item.value)}"></option>`).join('')}</datalist></label>`;
  const regions=[{value:'',label:'Semua regional'},...[...new Set(D.reg)].sort().map(name=>({value:name,label:name}))],
    areas=[{value:-1,label:'Semua area bisnis'},...D.abs.flatMap((name,i)=>!S.reg||D.reg[i]===S.reg?[{value:i,label:!S.reg&&D.abs.filter(value=>value===name).length>1?name+' · '+D.reg[i]:name}]:[])],
    kelIds=[...new Set(D.P.filter(row=>(!S.reg||D.reg[row[0]]===S.reg)&&(S.ab<0||row[0]===S.ab)).map(row=>row[1]))],
    kels=[{value:-1,label:'Semua kelurahan'},...kelIds.sort((a,b)=>D.kels[a].localeCompare(D.kels[b],'id')).map(i=>({value:i,label:D.kels[i]}))],
    rwOptions=[{value:-1,label:'Semua RW'},...rws.map(value=>({value,label:neighborhood('RW',value)}))],
    rtOptions=[{value:-1,label:'Semua RT'},...rts.map(value=>({value,label:neighborhood('RT',value)}))];
  const selected=RPDPotential.rows(D,S),totals=RPDPotential.total(selected),grouped=RPDPotential.groups(D,S),
    drill=(row,label)=>`<button data-field-drill="${grouped.level}" data-field-ab="${row.ab}" data-field-kel="${row.kel}" data-field-rw="${row.rw}" data-field-rt="${row.rt}">${esc(label)}</button>`;
  const headers=[...(grouped.level==='kel'?['Kelurahan','Area Bisnis']:[]),'RW','RT','Potensi','Canvassing','Berminat','Terpasang','Sisa'];
  const cells=grouped.rows.map(row=>[
    ...(grouped.level==='kel'?[drill(row,D.kels[row.kel]),esc(D.abs[row.ab])]:[]),
    grouped.level==='kel'?'–':grouped.level==='rw'?drill(row,neighborhood('RW',row.rw)):esc(neighborhood('RW',row.rw)),
    grouped.level==='rt'?drill(row,neighborhood('RT',row.rt)):'Semua RT',
    ...['potential','canvassed','interested','installed','remaining'].map(key=>row[key]==null?'Belum tersedia':N(row[key]))]);
  return `<section class="potential-panel"><div class="section-heading"><h2>Cek Potensi Wilayah</h2><span class="report-badge">Stok master · seluruh periode</span></div><div class="potential-filters"><details class="potential-context"${S.kel<0||!matchMedia('(max-width:600px)').matches?' open':''}><summary>${S.kel>=0?esc(D.kels[S.kel])+' · Ubah Wilayah':'Pilih Wilayah'}</summary><div class="potential-context-fields">`+
    select('reg','Regional',regions,S.reg)+select('ab','Area Bisnis',areas,S.ab)+select('kel','Kelurahan',kels,S.kel,S.ab<0)+'</div></details><div class="potential-neighborhood">'+
    select('rw','RW',rwOptions,S.rw,S.kel<0)+select('rt','RT',rtOptions,S.rt,S.rw<0)+'<button id="reset-potential" type="button">Reset Filter</button></div></div>'+
    '<div class="intel-kpis potential-kpis">'+[['potential','Total Potensi'],['canvassed','Tercanvassing'],['interested','Berminat'],['installed','Terpasang'],['remaining','Sisa Potensi']].map(([key,label])=>`<article class="intel-card"><span class="metric-label">${label}</span><strong class="metric-value${totals[key]==null?' unavailable':''}">${totals[key]==null?'Belum tersedia':N(totals[key])}</strong></article>`).join('')+'</div>'+
    '<p class="scope-caption">Tercanvassing: potensi master yang tercatat di survei. Sisa = Potensi − Berminat. Filter periode, tim dan status tidak mengubah stok ini.</p>'+
    `<div class="potential-table">${dataTable(headers,cells,'Tidak ada potensi pada wilayah ini.')}</div></section>`;
}

function vTeam() {
  const rows=[...A.teams].sort((a,b)=>(b.interested_per_observed_day??-1)-(a.interested_per_observed_day??-1));
  return `<h2>Kinerja Koordinator</h2>${notice('Hari-surveyor teramati = pasangan surveyor + tanggal dengan baris survei valid. Ini bukan absensi atau hari kerja berbayar. Perbandingan belum menyesuaikan beban kerja/kondisi area; target tim dan atribusi lintas tim yang ambigu tidak diasumsikan.')}`+
  dataTable(['Koordinator / tim','Surveyor beraktivitas','Status aktif¹','Tercanvassing','Berminat','Terpasang²','Konversi minat','Hari-surveyor teramati','Minat / hari teramati'],rows.map(row=>[`${esc(LB[row.name]||row.name)}${CAP.customer_detail?`<details><summary>Surveyor</summary>${(row.individuals||[]).map(person=>`<p>${esc(person.name)} · ${N(person.canvassed)} Tercanvassing · ${N(person.interested)} minat · ${N(person.installed)} Done</p>`).join('')}</details>`:''}`,N(row.surveyors_with_activity),N(row.active_surveyors),N(row.canvassed),N(row.interested),N(row.installed),percent(row.interest_rate),N(row.observed_surveyor_days),row.interested_per_observed_day==null?unavailable:row.interested_per_observed_day.toFixed(2)]))+
  `<p class="footer-definition">¹ Status pemetaan sumber/override, bukan absensi. ² Atribusi mengikuti surveyor dalam baris survei, bukan penanggung jawab pemasangan. Pelanggan lintas tim dapat muncul pada beberapa tim; subtotal tidak selalu aditif.</p>`+
  (ROLE==='owner'?`<details class="legacy-report"><summary>Laporan koordinator asli &amp; pemetaan surveyor</summary>${notice('Laporan asli mengikuti bulan survei, regional dan area saja; filter lanjutan tidak berlaku. PDF lama berisi SEMUA surveyor, tanpa filter dan hanya administrator.',true)}${vKorlap()}</details>`:'');
}

function vOutstanding() {
  const out=A.outstanding;
  return `<h2>Intervensi pemasangan</h2><div class="compact-stats"><div class="compact-stat"><span>Baris sumber berminat belum Done/Cancel</span><strong>${N(out.survey_rows)}</strong></div><div class="compact-stat"><span>Referensi kasus pada cakupan ini</span><strong>${N(out.case_references)}</strong></div><div class="compact-stat"><span>Aging belum terverifikasi</span><strong>${N(out.aging['Insufficient Data'])}</strong></div></div>`+
  `<div class="intel-panels"><section class="panel"><h2>Status asli sumber</h2>${dataTable(['Konfirmasi pemasangan','Baris sumber'],Object.entries(out.by_status).map(([status,count])=>[esc(status),N(count)]))}<h2>Outstanding per regional</h2>${dataTable(['Regional','Baris sumber'],Object.entries(out.by_region).map(([region,count])=>[esc(region),N(count)]))}</section><section class="panel"><h2>Aging terverifikasi</h2>${dataTable(['Hari','Referensi kasus'],Object.entries(out.aging).map(([age,count])=>[esc(age),N(count)]))}<p class="footer-definition">Per ${esc(out.aging_as_of)}. ${esc(out.aging_rule)} Status manual tidak menimpa status sumber.</p></section></div>`+
  notice(`Kategori PAM JAYA tetap dipakai persis seperti sumber. ${N(out.active_references)} referensi aktif, ${N(out.manually_resolved)} ditutup secara manual setelah impor, ${N(out.urgent_count)} melewati tenggat PIC. Aging hanya menghitung referensi aktif. Tanggal survei/FA tidak otomatis menjadi awal kasus; riwayat dicatat terpisah.`)+
  (CAP.customer_detail&&out.urgent.length?`<h2>Tindak Lanjut Melewati Tenggat</h2>${dataTable(['Referensi kasus','PIC','Tenggat'],out.urgent.map(item=>[esc(item.ref),esc(item.pic),esc(item.target_date)]))}`:'')+
  (CAP.customer_detail?`<h2>Daftar Tindak Lanjut</h2><p class="mu sm">Buka referensi kasus untuk PIC, aksi, tenggat, catatan resolusi dan riwayat append-only.</p><div id="case-table">${skeleton()}</div>`:blank('Detail kasus dibatasi','Peran ini hanya mengakses ringkasan agregat. Administrator diperlukan untuk PAM ID dan pencatatan tindak lanjut.'));
}

function vData() {
  if(!CAP.customer_detail)return blank('Akses dibatasi','Halaman ini hanya untuk Admin.');
  const q=S.dq,opts=(values,selected,title)=>values.map((value,index)=>option(index,index?value:title,index===selected)).join('');
  return `<h2>Pencarian PAM ID</h2><p class="mu sm">Pencarian dilakukan ${window.RPDStatic?'lokal di perangkat ini':'di server'} dan mengikuti seluruh filter global. PAM ID dapat dicari dari digit awal; data sumber tidak memuat nama, alamat atau telepon pelanggan.</p><div class="fl data-filters"><input id="qp" placeholder="PAM ID" value="${esc(q.p)}" inputmode="numeric" aria-label="PAM ID"><input id="qk" placeholder="Kelurahan" value="${esc(q.k)}" aria-label="Kelurahan"><input id="qs" placeholder="Surveyor" value="${esc(q.s)}" aria-label="Surveyor"><select id="qc" aria-label="Hasil canvassing">${opts(D.dic.c1,q.c,'Semua hasil canvassing')}</select><select id="qf" aria-label="Status pemasangan">${opts(D.dic.kf,q.f,'Semua status pemasangan')}</select><select id="qr" aria-label="Status potensi">${opts(D.dic.pr,q.r,'Semua status potensi')}</select></div><div id="case-table">${skeleton()}</div>`;
}

function caseSearchControl(){return `<div class="table-controls"><input id="case-search" type="search" maxlength="150" aria-label="Cari di seluruh hasil" placeholder="Cari di seluruh hasil" value="${esc(S.dq.query||'')}"></div>`}

async function dt() {
  if(!CAP.customer_detail||!['data','outstanding'].includes(S.tab))return;
  const revision=++searchRevision,tab=S.tab,container=$('#case-table');if(!container)return;
  const q=S.dq,body={scope:scopeObject(),pam:tab==='data'?q.p:'',kelurahan:tab==='data'?q.k:'',surveyor:tab==='data'?q.s:'',canvassing:tab==='data'?q.c:0,installation:tab==='data'?q.f:0,potential:tab==='data'?q.r:0,outstanding_only:tab==='outstanding',offset:PAGE*PAGE_SIZE,limit:PAGE_SIZE};
  Object.assign(body,{query:(q.query||'').slice(0,150),sort:q.sort||'',descending:!!q.descending});
  container.setAttribute('aria-busy','true');
  try {const result=await api('/api/records/search',{method:'POST',body:JSON.stringify(body)});if(revision!==searchRevision||S.tab!==tab)return;CURRENT_ROWS=result.rows;
    const focus=document.activeElement?.id==='case-search',cursor=focus?document.activeElement.selectionStart:null;
    container.innerHTML=caseSearchControl()+`<div class="pagination"><span>${N(result.total)} baris cocok · halaman ${PAGE+1}</span><div><button id="page-prev"${PAGE===0?' disabled':''}>Sebelumnya</button> <button id="page-next"${result.offset+result.limit>=result.total?' disabled':''}>Berikutnya</button></div></div>`+
    dataTable(['PAM ID / kasus','Tanggal survei','Regional / area / kelurahan','Surveyor / koordinator','Hasil canvassing','Status sumber','FA / pemasangan','Kendala','Flag / potensi / pelanggan','Tunggakan (Rp)','Tindak lanjut'],result.rows.map((row,index)=>[`<button data-case="${index}">${esc(row.pam)}</button><small class="mu">${esc(row.ref)}</small>`,esc(row.survey_date),`${esc(row.regional)} / ${esc(row.area)} / ${esc(row.kelurahan)}`,`${esc(row.surveyor)} / ${esc(row.coordinator)}`,esc(row.canvassing),esc(row.status),`${esc(row.fa_date||'–')} / ${esc(row.installation_date||'–')}`,esc(row.obstacle||'–'),`${esc(row.master_flag||'–')} / ${esc(row.potential_status||'–')} / ${esc(row.customer_status||'–')}`,number(row.arrears),row.followup?`${esc(row.followup.pic)}<br>${esc(row.followup.status)}<br>${esc(row.followup.target_date||'Tanpa tenggat')}`:'Belum dicatat']),undefined,true);
    if(focus){const input=$('#case-search');input.focus();input.setSelectionRange(cursor,cursor)}
  }catch(error){if(revision===searchRevision)container.innerHTML=caseSearchControl()+blank('Pencarian gagal',error.message)}finally{if(revision===searchRevision)container.removeAttribute('aria-busy')}
}

function vGovernance() {
  if(ROLE!=='owner')return blank('Akses dibatasi','Halaman ini hanya untuk Admin.');
  return `<h2>Kualitas Data</h2><div id="quality-content">${QUALITY?qualityContent():skeleton()}</div><section class="admin-section"><h2>Pengaturan &amp; Riwayat</h2><p class="mu sm">${window.RPDStatic?'Perubahan hanya tersimpan di peramban dan akun ini. Unduh cadangan untuk pindah perangkat.':'Perubahan disimpan di layanan privat.'}</p><div id="admin-content">${ADMIN?adminContent():skeleton()}</div>${document.querySelector('#local-admin-tools')?.innerHTML||''}</section><details class="legacy-report"><summary>Laporan Operasional Asli</summary>${notice('Hitungan per baris survei; hanya periode bulan, regional dan area bisnis berlaku.')}${vRingkasan()}</details><details class="legacy-report"><summary>Catatan &amp; Definisi Sumber</summary>${vCatatan()}</details>`;
}

function qualityContent() {
  const q=QUALITY;
  return `<div class="quality-grid">`+[['Imported records',q.imported_records],['Valid records',q.valid_records],['Duplicate excess rows',q.duplicate_records],['Duplicate PAM IDs',q.duplicate_customers],['Missing mandatory',q.missing_mandatory],['Invalid PAM IDs',q.invalid_pam],['Unmatched mapping',q.unmatched_mapping],['Conflicting geography',q.ambiguous_geography_customers]].map(([text,value])=>`<div class="compact-stat"><span>${esc(text)}</span><strong>${N(value)}</strong></div>`).join('')+`</div>`+
  notice('Mandatory: PAM numerik valid, tanggal survei, indeks regional/area/kelurahan/surveyor yang dapat dipetakan. Duplicate excess rows = jumlah baris di atas satu per PAM ID. Tidak ada duplikat yang dihapus dari sumber.')+
  dataTable(['Sumber Data','Value'],[['Last successful import',esc(timeLabel(q.source.imported_at))],['Source loaded for this session',esc(timeLabel(q.source.loaded_at))],['Survey-date range',esc(D.meta.tmin+' – '+D.meta.tmax)],['Source fingerprint',`<span class="source-id">${esc(q.source.fingerprint)}</span>`],['Data ownership',esc(BOOT.data_owner||unavailable)],['Synchronization errors',unavailable+' · no synchronization job supplied'],['Historical state comparison',esc(q.snapshot_comparison)]])+
  `<h2>Rekonsiliasi Sumber</h2>${dataTable(['Source field','Count'],Object.entries(q.source_sync).map(([key,value])=>[esc(key),typeof value==='number'?N(value):esc(String(value))]))}<p class="footer-definition">Counter rekonsiliasi impor, bukan jumlah kegagalan sinkronisasi backend. Snapshot terenkripsi dipertahankan oleh import CLI; tidak dibuat ulang menjadi riwayat bisnis yang tidak tersedia.</p>`;
}

function adminContent() {
  const rules=ADMIN.rules;
  return `<details><summary>Target pemasangan bulanan</summary><p class="mu sm">Target hanya dibandingkan untuk bulan penuh dan cakupan yang persis sama. Input berdasarkan dokumen target yang sah.</p><form class="admin-form" id="target-form"><label class="field">Bulan<select name="month">${D.months.map(month=>option(month,month,month===D.months[S.m1])).join('')}</select></label><label class="field">Target PAM terpasang<input name="target" type="number" min="1" max="10000000" required></label><label class="field">Cakupan aktif<input value="${esc(S.ab>=0?D.abs[S.ab]:S.reg||'Seluruh regional')}" readonly></label><label class="field wide">Bukti / dokumen target<input name="evidence" maxlength="1000" required></label><button>Simpan target dengan audit</button><p class="form-status" role="status"></p></form><h2>Target aktif</h2>${dataTable(['Bulan','Regional / area','Target','Bukti'],Object.values(ADMIN.targets).map(item=>[esc(item.month),esc(item.area_name||item.region||'Seluruh regional'),N(item.target),esc(item.evidence)]))}</details>
  <details><summary>Aturan Prioritas</summary><form class="admin-form" id="rules-form"><label class="field">Minimum PAM unik<input name="minimum_sample" type="number" min="1" max="100000" value="${rules.minimum_sample}" required></label><label class="field">High backlog rate (0–1)<input name="high_backlog_rate" type="number" step="0.01" min="0.01" max="1" value="${rules.high_backlog_rate}" required></label><label class="field">Cooling interest rate (0–1)<input name="cooling_interest_rate" type="number" step="0.01" min="0" max="1" value="${rules.cooling_interest_rate}" required></label><button>Simpan aturan</button><p class="form-status" role="status"></p></form></details>
  <details><summary>Kesiapan Pasokan &amp; Pemasangan</summary><form class="admin-form" id="context-form"><label class="field">Area bisnis<select name="area">${D.abs.map((name,i)=>option(i,name,i===S.ab)).join('')}</select></label><label class="field">Supply<select name="supply"><option value="unknown">Unknown</option><option value="ready">Ready</option><option value="constrained">Constrained</option></select></label><label class="field">Kesiapan pemasangan<select name="readiness"><option value="unknown">Unknown</option><option value="ready">Ready</option><option value="blocked">Blocked</option></select></label><label class="field wide">Bukti aktual / referensi<input name="evidence" maxlength="1000" required></label><button>Simpan konteks area</button><p class="form-status" role="status"></p></form><h2>Konteks area aktif</h2>${dataTable(['Area','Supply','Readiness','Bukti'],Object.entries(ADMIN.area_context).map(([key,value])=>[esc(D.abs[+key]||key),esc(value.supply),esc(value.readiness),esc(value.evidence)]))}</details>
  <h2>${window.RPDStatic?'Riwayat lokal':'Audit log'} · perubahan terbaru</h2>${ADMIN.events.length?ADMIN.events.map(event=>`<div class="history-entry"><strong>${esc(event.kind)} · ${esc(event.ref)}</strong><p>${esc(JSON.stringify(event.payload))}</p><small>${esc(timeLabel(event.at))} · actor ${esc(event.actor)} · event ${event.id}</small></div>`).join(''):'<p class="mu sm">Belum ada perubahan.</p>'}`;
}

async function loadGovernance(revision) {
  try {if(!QUALITY)QUALITY=await api('/api/quality');if(revision!==viewRevision||S.tab!=='catatan')return;$('#quality-content').innerHTML=qualityContent();
    if(ROLE==='owner'){if(!ADMIN)ADMIN=await api('/api/admin/audit');if(revision===viewRevision&&S.tab==='catatan')$('#admin-content').innerHTML=adminContent()}}
  catch(error){if(revision===viewRevision)setStatus(error.message)}
}

function revealSelectedTab(){
  const nav=document.querySelector('.tabs'),selected=nav.querySelector('[aria-selected="true"]');
  if(!selected||nav.scrollWidth<=nav.clientWidth)return;
  const viewport=nav.getBoundingClientRect(),tab=selected.getBoundingClientRect();
  if(tab.left<viewport.left)nav.scrollLeft+=tab.left-viewport.left;
  else if(tab.right>viewport.right)nav.scrollLeft+=tab.right-viewport.right;
}

function render() {
  if(!D)return;rememberLegacyPanel();const revision=++viewRevision;gridSequence=0;grids.clear();
  document.querySelectorAll('.tabs button').forEach(button=>{const active=button.dataset.tab===S.tab;button.setAttribute('aria-selected',active);button.tabIndex=active?0:-1});
  $('#page-title').textContent=pageTitles[S.tab];$('#main').setAttribute('aria-labelledby','tab-'+S.tab);
  if(!A){$('#main').innerHTML=skeleton();return}
  $('#main').innerHTML=({ringkasan:vExecutive,analytics:vAnalytics,kelurahan:vRegional,korlap:vTeam,outstanding:vOutstanding,data:vData,catatan:vGovernance})[S.tab]();
  renderedTab=S.tab;document.querySelectorAll('#main .legacy-report').forEach((panel,index)=>{const key=S.tab+':'+(panel.id||index);if(legacyPanels.has(key))panel.open=legacyPanels.get(key)});if(ROLE!=='owner')$('#pdf')?.remove();
  if(S.tab==='kelurahan'&&CAP.customer_detail)kt();if(['data','outstanding'].includes(S.tab))dt();if(S.tab==='catatan')loadGovernance(revision);
  if(S.tab==='catatan')window.RPDStatic?.ready(ROLE,BOOT);
  document.querySelectorAll('th[data-i]').forEach(cell=>{cell.tabIndex=0;cell.setAttribute('role','button');cell.setAttribute('aria-label','Urutkan '+cell.textContent.trim())});
  const reports={ringkasan:'executive',analytics:'executive',kelurahan:'area',korlap:'team',outstanding:'outstanding'};if(reports[S.tab])$('#report-kind').value=reports[S.tab];
}

async function svOv(previous) {
  try {const result=await api('/api/admin/mappings',{method:'PUT',body:JSON.stringify({version:BOOT.mapping_version,values:OV})});BOOT.mapping_version=result.version;ADMIN=null;await refresh()}
  catch(error){OV=previous;if(D){try{const current=await api('/api/bootstrap');OV=current.overrides;BOOT.mapping_version=current.mapping_version;await refresh()}catch{render()}}setStatus(error.message)}
}

async function openCase(index,trigger) {
  CASE=CURRENT_ROWS[index];if(!CASE)return;caseReturnFocus=trigger;
  let dialog=$('#case-dialog');if(!dialog){dialog=document.createElement('dialog');dialog.id='case-dialog';dialog.setAttribute('aria-labelledby','case-title');document.body.appendChild(dialog);dialog.addEventListener('close',()=>{const ref=CASE?.ref;CASE=null;if(!D)return;const index=CURRENT_ROWS.findIndex(row=>row.ref===ref),replacement=index>=0?document.querySelector(`#main [data-case="${index}"]`):null;if(caseReturnFocus?.isConnected)caseReturnFocus.focus();else if(replacement)replacement.focus();else $('#main').focus({preventScroll:true})})}
  const row=CASE,latest=row.followup||{};
  if(ROLE!=='owner'){
    dialog.innerHTML=`<div class="dialog-header"><h2 id="case-title">PAM ${esc(row.pam)}</h2><button id="close-case" aria-label="Tutup detail kasus">Tutup</button></div><div class="dialog-content"><p class="scope-caption">Guest internal · Hanya baca</p><dl class="case-readonly">`+
      [['Regional',row.regional],['Area Bisnis',row.area],['Kelurahan',row.kelurahan],['Surveyor',row.surveyor],['Status sumber',row.status],['Tunggakan (Rp)',number(row.arrears)]].map(([label,value])=>`<div><dt>${esc(label)}</dt><dd>${esc(value||'–')}</dd></div>`).join('')+'</dl><h2>Riwayat tindakan</h2><div id="case-history"></div></div>';
    dialog.showModal();await loadCaseHistory(row.ref);return;
  }
  dialog.innerHTML=`<div class="dialog-header"><h2 id="case-title">PAM ${esc(row.pam)} · follow-up</h2><button id="close-case" aria-label="Tutup detail kasus">Tutup</button></div><div class="dialog-content"><p class="mu sm">${esc(row.ref)} · ${esc(row.area)} · status sumber ${esc(row.status)}</p><form id="followup-form" class="admin-form"><label class="field">PIC penanggung jawab<input name="pic" maxlength="150" value="${esc(latest.pic||row.coordinator)}" required></label><label class="field">Status tindak lanjut (terpisah)<select name="status">${D.dic.kf.filter(Boolean).concat(D.dic.kf.includes('Tidak tercatat')?[]:['Tidak tercatat']).map(status=>option(status,status,status===(latest.status||row.status))).join('')}</select></label><label class="field">Target selesai<input name="target_date" type="date" value="${esc(latest.target_date||'')}"></label><label class="field wide">Aksi tindak lanjut<textarea name="action" maxlength="2000" required></textarea></label><label class="field wide">Catatan resolusi<textarea name="resolution_notes" maxlength="2000">${esc(latest.resolution_notes||'')}</textarea></label><label class="field">Awal kasus terkonfirmasi<input name="case_started" type="date" value="${esc(latest.case_started||'')}" max="${new Date().toISOString().slice(0,10)}"></label><label class="field">Total hari jeda terverifikasi<input name="pause_days" type="number" min="0" max="36500" value="${latest.pause_days||0}"></label><label class="field">Alasan jeda<input name="pause_reason" maxlength="500" value="${esc(latest.pause_reason||'')}"></label><button>Tambahkan ke riwayat</button><p class="form-status" role="status"></p></form><p class="mu sm">Awal kasus dan jeda memerlukan bukti operasional. Tidak diambil otomatis dari tanggal survei. Aksi baru tidak menghapus aksi sebelumnya.</p><h2>Riwayat tindakan</h2><div id="case-history">${skeleton()}</div></div>`;
  dialog.showModal();await loadCaseHistory(row.ref);
}

async function loadCaseHistory(ref,before=null) {
  try {const history=await api('/api/followups/'+encodeURIComponent(ref)+(before?'?before='+before:''));if(!CASE||CASE.ref!==ref)return;const container=$('#case-history'),markup=history.events.length?history.events.map(event=>`<article class="history-entry"><strong>${esc(event.payload.pic)} · ${esc(event.payload.status)}</strong><p>${esc(event.payload.action)}</p><p>Tenggat: ${esc(event.payload.target_date||'Tidak ditetapkan')} · Resolusi: ${esc(event.payload.resolution_notes||'–')}</p><small>${esc(timeLabel(event.at))} · actor ${esc(event.actor)} · event ${event.id}</small></article>`).join(''):'<p class="mu sm">Belum ada tindakan tersimpan.</p>';if(before){container.querySelector('[data-history-before]')?.remove();container.insertAdjacentHTML('beforeend',markup)}else container.innerHTML=markup;if(history.next_before)container.insertAdjacentHTML('beforeend',`<button data-history-before="${history.next_before}">Muat riwayat lebih lama</button>`)}
  catch(error){if(CASE?.ref===ref)$('#case-history').textContent=error.message}
}

document.addEventListener('submit',async event=>{
  const form=event.target;if(!['followup-form','target-form','rules-form','context-form'].includes(form.id))return;event.preventDefault();const button=form.querySelector('button'),status=form.querySelector('.form-status');button.disabled=true;status.textContent='Menyimpan…';
  if(ROLE!=='owner'){status.textContent='Guest hanya dapat membaca.';button.disabled=false;return}
  const values=Object.fromEntries(new FormData(form)),ref=CASE?.ref;let path,method='POST';
  if(form.id==='followup-form'){path='/api/followups/'+encodeURIComponent(ref);for(const key of ['case_started','target_date'])values[key]=values[key]||null;values.pause_days=+values.pause_days}
  if(form.id==='target-form'){path='/api/admin/targets';values.target=+values.target;values.region=S.reg;values.area=S.ab}
  if(form.id==='rules-form'){path='/api/admin/rules';method='PUT';for(const key of Object.keys(values))values[key]=+values[key]}
  if(form.id==='context-form'){path='/api/admin/area-context';values.area=+values.area}
  try {await api(path,{method,body:JSON.stringify(values)});ADMIN=null;status.textContent=window.RPDStatic?'Tersimpan terenkripsi hanya di peramban dan akun ini; tidak tersinkron ke tim.':'Tersimpan di backend; riwayat sebelumnya tetap ada.';
    if(form.id==='followup-form'){if(CASE?.ref===ref){form.elements.action.value='';await loadCaseHistory(ref)}if(D)await refresh()}
    else await refresh();
  }catch(error){status.textContent=error.message}finally{button.disabled=false}
});

document.addEventListener('input',event=>{
  const target=event.target;if(target.id==='filter-search'){fill();return}
  if(target.id.startsWith('potential-')){target.setCustomValidity('');return}
  if(target.id==='case-search'){S.dq.query=target.value=target.value.slice(0,150);PAGE=0;clearTimeout(searchTimer);searchRevision++;searchTimer=setTimeout(dt,300);return}
  if(target.dataset.gridSearch){const id=target.dataset.gridSearch,state=gridStates.get(id);state.q=target.value;state.page=0;const pos=target.selectionStart;updateGrid(id);const field=document.querySelector('[data-grid-search="'+id+'"]');field?.focus();field?.setSelectionRange(pos,pos);return}
  if(target.id==='q'){S.q=target.value;S.all=0;kt()}
  else if(['qp','qk','qs'].includes(target.id)){S.dq[{qp:'p',qk:'k',qs:'s'}[target.id]]=target.value;PAGE=0;clearTimeout(searchTimer);searchTimer=setTimeout(dt,250)}
});

document.addEventListener('change',async event=>{
  const target=event.target;
  if(target.id.startsWith('potential-')){
    const key=target.id.slice(10),match=[...target.list.options].find(option=>option.value.toLocaleLowerCase('id')===target.value.trim().toLocaleLowerCase('id'));
    if(!match){target.setCustomValidity('Pilih wilayah dari daftar.');target.reportValidity();return}
    if(!selectPotentialScope(key,key==='reg'?match.dataset.value:Number(match.dataset.value)))return;
    gridStates.clear();await refresh();document.getElementById(key==='kel'&&S.kel>=0?'potential-rw':target.id)?.focus({preventScroll:true});return;
  }
  if(target.id==='fperiod'){
    const kind=target.value;if(kind==='custom'){$('#extra-filters').open=true;return}
    const now=new Date(),local=d=>[d.getFullYear(),String(d.getMonth()+1).padStart(2,'0'),String(d.getDate()).padStart(2,'0')].join('-');
    S.m0=0;S.m1=D.months.length-1;S.start=S.end='';
    if(kind!=='all'){S.end=local(now);const start=new Date(now);if(kind==='week')start.setDate(start.getDate()-6);if(kind==='month')start.setDate(1);S.start=local(start)}
    refresh();return;
  }
  if(target.id==='f0'||target.id==='f1'){S[target.id==='f0'?'m0':'m1']=+target.value;if(S.m0>S.m1){if(target.id==='f0')S.m1=S.m0;else S.m0=S.m1}S.start=S.end='';refresh()}
  else if(target.id==='fr'){S.reg=target.value;S.ab=S.kel=S.rw=S.rt=-1;S.coordinator='';refresh()}
  else if(target.id==='fa'){S.ab=+target.value;if(S.ab>=0)S.reg=D.reg[S.ab];S.kel=S.rw=S.rt=-1;S.coordinator='';refresh()}
  else if(target.id==='fk'){S.kel=+target.value;S.rw=S.rt=-1;refresh()}
  else if(target.id==='fco'){S.coordinator=target.value;refresh()}
  else if(target.id==='fstatus'){S.statuses=[...target.selectedOptions].map(item=>item.value);refresh()}
  else if(target.id==='fstart'||target.id==='fend'){S[target.id==='fstart'?'start':'end']=target.value;refresh()}
  else if(['qc','qf','qr'].includes(target.id)){S.dq[{qc:'c',qf:'f',qr:'r'}[target.id]]=+target.value;PAGE=0;dt()}
  else if(target.id==='regional-rank'){regionSort=target.value;render()}
  else if(target.id==='trend-unit'){trendUnit=target.value;render()}
  else if(target.dataset.ov!==undefined){const previous=structuredClone(OV),index=target.dataset.ov;OV[index]=OV[index]||{};OV[index][target.dataset.f]=target.dataset.f==='st'?+target.value:target.value;document.querySelectorAll('[data-ov]').forEach(control=>control.disabled=true);await svOv(previous)}
});

document.addEventListener('click',async event=>{
  const target=event.target.closest('button,th[data-i],tr[data-k]');if(!target)return;
  if(target.dataset.fieldDrill){
    const level=target.dataset.fieldDrill;S.ab=Number(target.dataset.fieldAb);S.reg=D.reg[S.ab];S.kel=Number(target.dataset.fieldKel);
    S.rw=level==='kel'?-1:Number(target.dataset.fieldRw);S.rt=level==='rt'?Number(target.dataset.fieldRt):-1;
    gridStates.clear();await refresh();return;
  }
  if(target.id==='reset-potential'){Object.assign(S,{reg:'',ab:-1,kel:-1,rw:-1,rt:-1,coordinator:''});gridStates.clear();refresh();return}
  if(target.dataset.caseSort){const q=S.dq;q.descending=q.sort===target.dataset.caseSort?!q.descending:false;q.sort=target.dataset.caseSort;PAGE=0;dt();return}
  if(target.dataset.gridSort){const id=target.dataset.gridSort,state=gridStates.get(id),col=+target.dataset.column;state.direction=state.col===col?-state.direction:1;state.col=col;state.page=0;updateGrid(id);return}
  if(target.dataset.gridPage){const id=target.dataset.gridPage;gridStates.get(id).page+=+target.dataset.step;updateGrid(id);return}
  const route=target.dataset.tab||target.dataset.route;
  if(route){if((route==='catatan'&&ROLE!=='owner')||(!CAP.customer_detail&&!['ringkasan','kelurahan'].includes(route)))return;S.tab=route==='analytics'?'kelurahan':route;S.all=0;PAGE=0;setStatus('');refresh();revealSelectedTab();if(target.dataset.route)$('#main').focus({preventScroll:true});return}
  if(target.id==='retry-analysis'){refresh();return}
  if(target.dataset.export){const buttons=[...document.querySelectorAll('[data-export]')];buttons.forEach(button=>button.disabled=true);setStatus('');try{const extension=target.dataset.export,kind=$('#report-kind').value;await download('/api/reports/'+kind+'.'+extension+'?'+params(),'RPD-'+kind+'.'+extension)}catch(error){setStatus(error.message)}finally{buttons.forEach(button=>button.disabled=false)}return}
  if(target.id==='rs'){gridStates.clear();Object.assign(S,{m0:0,m1:D.months.length-1,reg:'',ab:-1,kel:-1,rw:-1,rt:-1,coordinator:'',statuses:[],start:'',end:'',q:'',open:'',openK:null,all:0,dq:{p:'',k:'',s:'',c:0,r:0,f:0,n:100}});$('#filter-search').value='';$('#fperiod').value='all';refresh();return}
  if(target.id==='save-preset'){const name=$('#preset-name').value.trim();if(!name){setStatus('Masukkan nama preset.');return}const presets=presetList();Object.defineProperty(presets,name,{value:presetScope(),enumerable:true,writable:true,configurable:true});savePresetList(presets);fill();setStatus('Preset filter disimpan tanpa data pelanggan.');return}
  if(target.id==='load-preset'){const value=presetList()[$('#preset-list').value];if(!value)return;const revision=analysisRevision;try{setStatus('Memeriksa filter tersimpan…');const scope=await resolvePresetForUse(value);if(revision!==analysisRevision||!D)return;if(!scope){setStatus('Cakupan preset lama tidak dapat diverifikasi pada sumber aktif. Simpan ulang preset; filter tidak diubah.');return}Object.assign(S,scope);refresh()}catch(error){if(D)setStatus(error.message)}return}
  if(target.id==='delete-preset'){const presets=presetList();delete presets[$('#preset-list').value];savePresetList(presets);fill();return}
  if(target.dataset.region!==undefined){S.reg=target.dataset.region;S.ab=S.kel=S.rw=S.rt=-1;S.coordinator='';refresh();return}
  if(target.dataset.area!==undefined){S.ab=+target.dataset.area;S.reg=D.reg[S.ab];S.kel=S.rw=S.rt=-1;S.coordinator='';refresh();return}
  if(target.id==='page-prev'||target.id==='page-next'){PAGE+=target.id==='page-next'?1:-1;dt();return}
  if(target.dataset.case!==undefined){await openCase(+target.dataset.case,target);return}
  if(target.id==='close-case'){$('#case-dialog').close();return}
  if(target.dataset.historyBefore&&CASE){target.disabled=true;try{await loadCaseHistory(CASE.ref,+target.dataset.historyBefore)}finally{if(target.isConnected)target.disabled=false}return}
  if(target.id==='pdf'){try{await download('/api/legacy-report.pdf','RPD-all-surveyors-unfiltered.pdf')}catch(error){setStatus(error.message)}return}
  if(target.id==='ovx'){const previous=OV;OV={};await svOv(previous);return}
  if(target.id==='all'){S.all=1;render();return}
  if(target.matches('th[data-i]')){const id=target.closest('table').dataset.id,index=+target.dataset.i,state=S.sort[id]||{i:T[id].si,d:-1};S.sort[id]={i:index,d:state.i===index?-state.d:(T[id].cols[index].t==='s'?1:-1)};render();return}
  if(target.matches('tr[data-k]')){const [kind,...rest]=target.dataset.k.split(':'),value=rest.join(':');if(kind==='reg'){S.reg=S.reg===value?'':value;S.ab=S.kel=-1;S.coordinator='';refresh()}else if(kind==='ab'){S.ab=S.ab===+value?-1:+value;if(S.ab>=0)S.reg=D.reg[S.ab];S.kel=-1;S.coordinator='';refresh()}else{if(kind==='kel')S.openK=S.openK===+value?null:+value;else S.open=S.open===value?'':value;render()}return}
});

function setTheme(theme){document.documentElement.dataset.theme=theme;$('#thm').setAttribute('aria-label',theme==='dark'?'Aktifkan tema terang':'Aktifkan tema gelap');$('#thm').setAttribute('aria-pressed',theme==='dark')}
try{setTheme(localStorage.getItem('rpd_theme')==='dark'?'dark':'light');if(!window.RPDStatic)localStorage.removeItem('rpd_ov')}catch{setTheme('light')}
$('#thm').onclick=()=>{const theme=document.documentElement.dataset.theme==='dark'?'light':'dark';setTheme(theme);try{localStorage.setItem('rpd_theme',theme)}catch{}};
$('#login-form').onsubmit=event=>{event.preventDefault();go()};
$('#out').onclick=async()=>{try{await api('/api/logout',{method:'POST'})}catch{}finally{localLogout()}};
$('#ft').onclick=()=>{const open=$('#gf').classList.toggle('open');$('#ft').setAttribute('aria-expanded',open)};
document.querySelectorAll('.tabs button').forEach(button=>{button.setAttribute('aria-label',button.textContent.trim());button.title=button.textContent.trim()});
document.querySelector('.tabs').addEventListener('keydown',event=>{const buttons=[...document.querySelectorAll('.tabs button')],index=buttons.indexOf(document.activeElement);if(index<0)return;let next=index;if(['ArrowDown','ArrowRight'].includes(event.key))next=(index+1)%buttons.length;else if(['ArrowUp','ArrowLeft'].includes(event.key))next=(index+buttons.length-1)%buttons.length;else if(event.key==='Home')next=0;else if(event.key==='End')next=buttons.length-1;else return;event.preventDefault();buttons[next].click();buttons[next].focus()});
document.addEventListener('keydown',event=>{if(['Enter',' '].includes(event.key)&&event.target.matches('th[data-i]')){event.preventDefault();event.target.click()}});
document.addEventListener('toggle',event=>{if(event.target.id==='area-details'&&event.target.open&&!S.advanced){S.advanced=true;refresh()}},true);
$('#collapse-nav').onclick=()=>{const closed=document.body.classList.toggle('nav-collapsed'),button=$('#collapse-nav');button.setAttribute('aria-expanded',!closed);button.setAttribute('aria-label',closed?'Buka menu':'Tutup menu');button.querySelector('.nav-text').textContent=closed?'Buka menu':'Tutup menu'};
const navLayout=()=>document.querySelector('.tabs').setAttribute('aria-orientation',matchMedia('(max-width:600px)').matches?'horizontal':'vertical');
navLayout();matchMedia('(max-width:600px)').addEventListener('change',navLayout);
api('/health').then(health=>{if(!health.configured)$('#le').textContent='Backend privat belum dikonfigurasi. Hubungi administrator untuk akses layanan privat.'}).catch(error=>{$('#le').textContent=error.message});
