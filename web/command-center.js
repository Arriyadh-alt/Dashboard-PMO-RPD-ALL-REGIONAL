/* Same-origin API only. Customer rows and credentials are never persisted in the browser. */
let A = null, CSRF = '', SOURCE = {}, CAP = {}, BOOT = {}, QUALITY = null, ADMIN = null;
let analysisRevision = 0, viewRevision = 0, searchRevision = 0, searchTimer, PAGE = 0;
let CURRENT_ROWS = [], CASE = null, caseReturnFocus = null, regionSort = 'installation_rate', trendUnit = 'monthly';
let renderedTab='';const legacyPanels=new Map();

function rememberLegacyPanel(){const panel=document.querySelector('#main .legacy-report');if(panel&&renderedTab)legacyPanels.set(renderedTab,panel.open)}
const PAGE_SIZE = 50;
const pageTitles = {ringkasan:'Executive Overview', analytics:'Performance Analytics', kelurahan:'Regional & Area Intelligence', korlap:'Team Performance', outstanding:'Outstanding & Follow-up', data:'Customer Lookup', catatan:'Data Quality & Administration'};
const unavailable = 'Insufficient Data';
const percent = value => value == null ? unavailable : PC(value);
const number = value => value == null ? unavailable : N(value);
const timeLabel = value => value ? new Intl.DateTimeFormat('id-ID',{dateStyle:'medium',timeStyle:'short'}).format(new Date(value)) : unavailable;
const scopeKeys = ['m0','m1','reg','ab','kel','coordinator','statuses','start','end'];
const scopeObject = () => Object.fromEntries(scopeKeys.map(key=>[key,S[key]]).filter(([,value])=>value!==''));
const params = () => {const p=new URLSearchParams();for(const [key,value] of Object.entries(scopeObject())){if(key==='statuses')value.forEach(status=>p.append('status',status));else p.set(key,value)}return p};
const notice = (message,warning=false) => `<p class="scope-note${warning?' warning':''}">${esc(message)}</p>`;
const blank = (title,message) => `<section class="empty-state"><h2>${esc(title)}</h2><p>${esc(message)}</p></section>`;
const skeleton = () => `<div class="skeleton" role="status" aria-label="Memuat laporan"><div class="skeleton-line"></div><div class="skeleton-line"></div><div class="skeleton-line"></div><p class="mu sm">Memuat data terotorisasi…</p></div>`;
const option = (value,text,selected) => `<option value="${esc(value)}"${selected?' selected':''}>${esc(text)}</option>`;
const setStatus = message => {$('#service-status').textContent=message};

async function api(path, options={}) {
  let response;
  try {response=await fetch(path,{credentials:'same-origin',...options,headers:{...(options.body?{'Content-Type':'application/json'}:{}),...(CSRF?{'X-CSRF-Token':CSRF}:{}),...options.headers}})}
  catch {throw new Error('Backend tidak terjangkau. Periksa koneksi dan coba kembali.')}
  const data=await response.json().catch(()=>({detail:'Backend privat diperlukan. GitHub Pages tidak menyediakan API data.'}));
  if(!response.ok){if(response.status===401&&path!=='/api/login'){localLogout();$('#le').textContent='Sesi berakhir. Silakan masuk kembali.'}throw new Error(typeof data.detail==='string'?data.detail:'Nilai atau filter tidak valid.')}
  return data;
}

async function download(path, filename) {
  const response=await fetch(path,{credentials:'same-origin'});
  if(!response.ok){const error=await response.json().catch(()=>({}));if(response.status===401)localLogout();throw new Error(error.detail||'Laporan tidak tersedia.')}
  const url=URL.createObjectURL(await response.blob()), link=document.createElement('a');
  link.href=url;link.download=filename;document.body.appendChild(link);link.click();link.remove();setTimeout(()=>URL.revokeObjectURL(url),10000);
}

function init(payload) {
  BOOT=payload;D=payload.data;ROLE=payload.role;CSRF=payload.csrf;SOURCE=payload.source;CAP=payload.capabilities;OV=payload.overrides;WM=null;
  Object.assign(S,{m0:0,m1:D.months.length-1,reg:'',ab:-1,kel:-1,coordinator:'',statuses:[],start:'',end:'',tab:'ringkasan',q:'',open:'',all:0});
  $('#lg').hidden=true;$('#app').hidden=false;$('#out').hidden=false;$('#role').textContent=ROLE==='owner'?'Administrator':'Aggregate viewer';
  $('#sub').textContent=(BOOT.data_owner?BOOT.data_owner+' · ':'')+'Kohort survei '+fd(D.meta.tmin)+' – '+fd(D.meta.tmax)+' · Metrik unik dan stok master dibedakan.';
  $('#lp').value='';$('#li').value='';fill();refresh();$('#main').focus({preventScroll:true});
}

function localLogout() {
  analysisRevision++;viewRevision++;searchRevision++;clearTimeout(searchTimer);
  D=REC=WM=A=QUALITY=ADMIN=null;OV={};ROLE=CSRF='';SOURCE=CAP=BOOT={};CURRENT_ROWS=[];CASE=null;PAGE=0;
  const dialog=$('#case-dialog');if(dialog?.open)dialog.close();if(dialog)dialog.remove();
  $('#main').innerHTML='';$('#app').hidden=true;$('#lg').hidden=false;$('#out').hidden=true;$('#lb').disabled=false;$('#li').value='';$('#lp').value='';$('#le').textContent='';$('#sub').textContent='';setStatus('');$('#li').focus();
}

async function go() {
  if($('#lb').disabled)return;$('#lb').disabled=true;$('#le').textContent='Memverifikasi sesi backend…';
  try {await api('/api/login',{method:'POST',body:JSON.stringify({account:$('#li').value,password:$('#lp').value})});init(await api('/api/bootstrap'))}
  catch(error){$('#le').textContent=error.message;$('#lb').disabled=false}
  finally{$('#lp').value=''}
}

async function refresh() {
  if(!D)return;rememberLegacyPanel();const revision=++analysisRevision;viewRevision++;searchRevision++;A=null;PAGE=0;setStatus('');fill();
  $('#main').setAttribute('aria-busy','true');$('#main').innerHTML=skeleton();
  try {const result=await api('/api/analysis?'+params());if(revision!==analysisRevision||!D)return;A=result;render()}
  catch(error){if(revision!==analysisRevision)return;setStatus(error.message);$('#main').innerHTML=blank('Laporan belum tersedia','Ubah filter atau coba kembali. Tidak ada hasil lama yang ditampilkan sebagai hasil filter baru.')+'<p><button id="retry-analysis">Coba kembali</button></p>'}
  finally{if(revision===analysisRevision)$('#main').setAttribute('aria-busy','false')}
}

function presetList() {try{const data=JSON.parse(localStorage.getItem('rpd_filter_presets')||'{}');return data&&typeof data==='object'&&!Array.isArray(data)?data:{}}catch{return {}}}
function savePresetList(value){try{localStorage.setItem('rpd_filter_presets',JSON.stringify(value))}catch{setStatus('Preset tidak dapat disimpan pada peramban ini.')}}

function presetScope(){
  return {version:2,scope:scopeObject(),period:[D.months[S.m0],D.months[S.m1]],openingBucket:S.m0===0,areaKey:S.ab>=0?BOOT.area_keys[S.ab]:null,kelName:S.kel>=0?D.kels[S.kel]:null};
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
  return {m0,m1,reg,ab,kel:value.kelName===null?-1:kelIds[0],coordinator,statuses:scope.statuses,start:scope.start||'',end:scope.end||''};
}

function fill() {
  if(!D)return;
  if(!$('#fk'))$('#gf').insertAdjacentHTML('beforeend',`<details class="more-filters"><summary>Filter lanjutan &amp; preset</summary><div class="advanced-grid"><label class="field">Cari opsi wilayah<input id="filter-search" type="search" placeholder="Cari area / kelurahan"></label><label class="field">Kelurahan<select id="fk"></select></label><label class="field">Koordinator / tim<select id="fco"></select></label><label class="field">Status pemasangan (multi-pilih)<select id="fstatus" multiple size="3" aria-describedby="multi-status-help"></select><small id="multi-status-help">Ctrl/Cmd + klik untuk beberapa status.</small></label><label class="field">Tanggal survei mulai (opsional)<input id="fstart" type="date"></label><label class="field">Tanggal survei akhir (opsional)<input id="fend" type="date"></label></div><div class="preset-row"><label for="preset-name" class="sm">Preset</label><input id="preset-name" maxlength="50" placeholder="Nama filter tersimpan"><button id="save-preset">Simpan</button><select id="preset-list" aria-label="Preset filter"></select><button id="load-preset">Terapkan</button><button id="delete-preset">Hapus preset</button></div></details>`);
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
  const missing=value==null;return `<article class="intel-card"><span class="metric-label">${esc(title)}</span><button class="metric-value${missing?' unavailable':''}" data-route="${route}" title="Buka rincian ${esc(title)}">${missing?unavailable:rate?percent(value):number(value)}</button><span class="metric-change">${esc(change)}</span><details class="metric-definition"><summary>Definisi &amp; cakupan</summary><p>${esc(definition)}</p></details><small class="timestamp">${SOURCE.imported_at?'Diimpor':'Sumber dimuat'}: ${esc(timeLabel(SOURCE.imported_at||SOURCE.loaded_at))}</small></article>`;
}

function vExecutive() {
  const m=A.metrics,master=A.master;
  const eligible=A.regions.filter(row=>row.canvassed>=A.rules.minimum_sample&&row.interested>0).sort((a,b)=>(b.installation_rate??-1)-(a.installation_rate??-1));
  const largest=[...A.areas].sort((a,b)=>b.remaining-a.remaining)[0];
  const bottleneck=Object.entries(A.outstanding.by_status).sort((a,b)=>b[1]-a[1])[0];
  const cohortDefinition=A.scope.cohort+' Angka ini bukan jumlah kunjungan atau dokumen.';
  return `<div class="intel-kpis">`+[
    metricCard('Total Customer Potential',master.potential,'Stok master · seluruh periode',master.scope,'kelurahan'),
    metricCard('Unique Customers Canvassed',m.canvassed,previousText('canvassed'),cohortDefinition,'analytics'),
    metricCard('Unique Interested Customers',m.interested,previousText('interested'),'PAM unik dengan status Berminat yang konsisten dalam kohort survei terpilih. '+cohortDefinition,'analytics'),
    metricCard('Unique Installed Customers',m.installed,previousText('installed'),'PAM unik Berminat dengan status Done yang konsisten, dari kohort survei yang sama. Bukan pemasangan dalam periode kalender.','analytics'),
    metricCard('Remaining Potential',master.remaining,'Master − minat yang cocok · seluruh periode',master.scope,'kelurahan'),
    metricCard('Target Achievement',A.target.achievement??null,A.target.available?'Aktual pemasangan / target terkonfigurasi':'Target sebanding belum tersedia',A.target.reason,'analytics',true),
    metricCard('Interest Conversion',m.interest_rate,previousText('interest_rate',true),'PAM unik Berminat / PAM unik tercanvassing dalam kohort survei yang sama. Bukan cakupan master.','analytics',true),
    metricCard('Installation Conversion',m.installation_rate,previousText('installation_rate',true),'PAM unik Done dalam pelanggan Berminat / PAM unik Berminat, kohort survei yang sama.','analytics',true)
  ].join('')+`</div>`+notice(`${A.scope.cohort} ${N(m.excluded_geography_customers)} PAM konflik geografis dikecualikan; ${N(m.conflicted_status_customers)} PAM berstatus konflik tidak diasumsikan berminat/terpasang. ${A.scope.history}`)+
  `<div class="intel-panels"><section class="panel"><h2>Management brief</h2><div class="executive-list">`+[
    ['Periode aktivitas survei',(A.scope.start||'Seluruh awal sumber')+' – '+A.scope.end],
    ['Regional: konversi pemasangan tertinggi',eligible[0]?eligible[0].name+' · '+percent(eligible[0].installation_rate):unavailable],
    ['Regional: konversi pemasangan terendah',eligible.length>1?eligible.at(-1).name+' · '+percent(eligible.at(-1).installation_rate):unavailable],
    ['Sisa potensi master terbesar',largest?largest.name+' · '+N(largest.remaining):unavailable],
    ['Backlog sumber terbesar (baris)',bottleneck?bottleneck[0]+' · '+N(bottleneck[1]):unavailable],
    ['Target pemasangan',A.target.available?percent(A.target.achievement):unavailable]
  ].map(([label,value])=>`<div><span class="mu">${esc(label)}</span><strong>${esc(value)}</strong></div>`).join('')+`</div><p class="footer-definition">Perbandingan regional memerlukan ≥ ${N(A.rules.minimum_sample)} PAM unik dan denominator minat > 0. Kondisi area dan tenaga kerja belum dinormalisasi.</p></section><section class="panel"><h2>Management insights</h2>${A.insights.map(item=>`<article class="insight"><div class="insight-title"><span>${esc(item.area)}</span><span class="severity ${item.severity==='High'?'high':''}">${esc(item.severity)}</span></div><p>${item.unit==='installation_rate'?'Konversi pemasangan '+percent(item.metric)+' vs baseline cakupan terpilih '+percent(item.baseline):N(item.metric)+' baris pending vs '+N(item.baseline)+' baris survei valid.'}</p><p>${esc(item.action)}</p></article>`).join('')}</section></div>`+
  `<details class="legacy-report"><summary>Laporan operasional asli · baris survei, bukan pelanggan unik</summary>${notice('Laporan asli mempertahankan definisi dan hitungan sumber: periode bulanan, regional dan area bisnis saja. Filter tanggal khusus, kelurahan, tim dan status di atas tidak berlaku pada bagian berlabel ini.',true)}${vRingkasan()}</details>`;
}

function funnelStage(title,count,base,previous,detached=false) {
  const conversion=base==null?null:R(count,base),drop=base==null?null:base-count;
  return `<div class="funnel-stage${detached?' detached':''}"><div class="funnel-heading"><span>${esc(title)}</span><strong>${number(count)}</strong></div>${detached?'':`<div class="funnel-track"><i style="width:${Math.min(100,(conversion??0)*100)}%"></i></div>`}<small>${detached?'Stok master terpisah; konversi ke kohort survei: Insufficient Data':base==null?'Baseline kohort survei; bukan persentase dari master':'Konversi tahap '+percent(conversion)+' · drop-off '+number(drop)+' ('+percent(base?drop/base:null)+')'}</small><small>Periode sebelumnya: ${previous==null?unavailable:N(previous)}</small></div>`;
}

function vAnalytics() {
  const m=A.metrics,target=A.target;
  return `<div class="intel-panels"><section class="panel"><h2>Conversion funnel</h2><div class="funnel">${funnelStage('Total Potential · stok master',A.master.potential,null,null,true)}${funnelStage('Canvassed · PAM unik',m.canvassed,null,A.previous?.canvassed)}${funnelStage('Interested · kohort yang sama',m.interested,m.canvassed,A.previous?.interested)}${funnelStage('Installed · kohort yang sama',m.installed,m.interested,A.previous?.installed)}</div><p class="footer-definition">Overall conversion kohort: ${percent(R(m.installed,m.canvassed))}. Cakupan master → canvassed tidak dihitung karena populasi master eligible belum dapat ditautkan dengan aman.</p></section><section class="panel"><h2>Target vs actual</h2>${target.available?`<div class="compact-stats"><div class="compact-stat"><span>Target bulanan terpilih</span><strong>${N(target.target)}</strong></div><div class="compact-stat"><span>PAM Done · tanggal pasang</span><strong>${N(target.actual)}</strong></div><div class="compact-stat"><span>Sisa target</span><strong>${N(target.remaining)}</strong></div></div><p class="progress-label">Pencapaian ${percent(target.achievement)}</p><div class="bar-compact"><i style="width:${Math.min(100,target.achievement*100)}%"></i></div>`:blank('Target belum tersedia',target.reason)}${notice(target.reason)}<p class="mu sm">Kebutuhan harian, tren target historis dan estimasi selesai: ${unavailable}. Tidak ada target atau hari kerja yang dibuat otomatis.</p>${ROLE==='owner'?'<p><button data-route="catatan">Konfigurasi target dengan bukti sumber</button></p>':''}</section></div>
  <h2>Tren aktivitas aktual</h2>${notice('Tanggal survei untuk canvassed/minat; tanggal pemasangan untuk event Done. Status kohort adalah status dalam impor saat ini, bukan status historis pada akhir bulan. Nilai nol tidak mengonfirmasi tidak ada aktivitas di luar cakupan sumber.')}
  <div class="inline-controls"><label for="trend-unit">Agregasi aktivitas</label><select id="trend-unit">${[['daily','Harian'],['weekly','Mingguan ISO'],['monthly','Bulanan']].map(([key,text])=>option(key,text,key===trendUnit)).join('')}</select><span class="mu">Menampilkan tanggal dengan catatan; bukan absensi atau snapshot historis.</span></div><div class="two trend-grid">${trendCharts()}</div>${regionTable()}`;
}

function trendCharts() {
  const rows=A.trend_series?.[trendUnit]||A.trends,labels=rows.map(row=>row.month);
  return bars('PAM unik tercanvassing · tanggal survei',rows.map(row=>row.canvassed),labels)+bars('PAM unik berminat · tanggal survei',rows.map(row=>row.interested),labels)+bars('PAM unik Done · tanggal pemasangan',rows.map(row=>row.installation_events),labels);
}

function dataTable(headers,rows,empty='Tidak ada data yang cocok dengan filter.') {
  return `<div class="tw"><table class="report-table"><thead><tr>${headers.map(header=>`<th scope="col">${header}</th>`).join('')}</tr></thead><tbody>${rows.length?rows.map(cells=>'<tr>'+cells.map((cell,index)=>`<td${index===0?' class="text"':''}>${cell}</td>`).join('')+'</tr>').join(''):`<tr><td colspan="${headers.length}" class="text">${esc(empty)}</td></tr>`}</tbody></table></div>`;
}

function regionTable() {
  const rows=[...A.regions].sort((a,b)=>(b[regionSort]??-1)-(a[regionSort]??-1));
  return `<h2>Regional comparison</h2><div class="inline-controls"><label for="regional-rank">Urutkan regional</label><select id="regional-rank">${[['installation_rate','Konversi pemasangan'],['interest_rate','Konversi minat'],['remaining','Sisa potensi master'],['installed','PAM terpasang']].map(([value,text])=>option(value,text,value===regionSort)).join('')}</select><span class="mu">Ranking tidak menyesuaikan tenaga kerja atau kondisi wilayah.</span></div>`+dataTable(['Regional','Potensi master¹','PAM canvassed','PAM berminat','PAM Done','Sisa master¹','Konversi pasang','Kontribusi Done'],rows.map(row=>[`<button data-region="${esc(row.name)}">${esc(row.name)}</button>`,N(row.potential),N(row.canvassed),N(row.interested),N(row.installed),N(row.remaining),percent(row.installation_rate),percent(row.contribution)]))+`<p class="footer-definition">¹ ${esc(A.master.scope)}</p>`;
}

function vRegional() {
  return regionTable()+`<h2>Area profiling &amp; priority</h2>${notice('Prioritas adalah bantuan triase tindak lanjut, bukan izin menambah canvassing. Potensi tinggi saja tidak menentukan kesiapan. Supply dan kesiapan pemasangan harus dikonfirmasi; tidak ada koordinat atau batas wilayah yang dibuat.')}`+
  dataTable(['Area bisnis','Regional','PAM canvassed','PAM berminat','PAM Done','Sisa master¹','Aktivitas terakhir','Prioritas &amp; alasan'],A.areas.map(row=>[`<button data-area="${row.key}">${esc(row.name)}</button>`,esc(row.regional),N(row.canvassed),N(row.interested),N(row.installed),N(row.remaining),esc(row.last_activity||unavailable),`<span class="severity ${row.priority==='High Priority'?'high':''}">${esc(row.priority)}</span><details><summary>Kriteria &amp; kendala</summary><p>${esc(row.reason)}</p><p>${esc(Object.entries(row.obstacles).map(([key,value])=>key+': '+N(value)).join('; ')||'Kendala tidak tercatat.')}</p></details>`]))+
  notice(`Aturan aktif: minimal ${A.rules.minimum_sample} PAM; High Priority jika backlog/minat ≥ ${percent(A.rules.high_backlog_rate)}; Cooling Down jika minat/canvassed < ${percent(A.rules.cooling_interest_rate)}. Konfirmasi supply/kesiapan wajib, kecuali bukti supply constrained → Requires Supply Improvement.`)+
  `<details class="legacy-report" open><summary>Drill-down kelurahan → RW → RT · stok master seluruh periode</summary>${notice('Bagian master ini mengikuti regional/area bisnis, bukan periode survei, status, tim atau tanggal khusus. Gunakan pencarian kelurahan dan buka baris untuk RW/RT. Hubungan RT ke pelanggan survei belum tersedia.',true)}${vKel()}</details>`;
}

function vTeam() {
  const rows=[...A.teams].sort((a,b)=>(b.interested_per_observed_day??-1)-(a.interested_per_observed_day??-1));
  return `<h2>Coordinator performance</h2>${notice('Hari-surveyor teramati = pasangan surveyor + tanggal dengan baris survei valid. Ini bukan absensi atau hari kerja berbayar. Perbandingan belum menyesuaikan beban kerja/kondisi area; target tim dan atribusi lintas tim yang ambigu tidak diasumsikan.')}`+
  dataTable(['Koordinator / tim','Surveyor beraktivitas','Status aktif¹','PAM canvassed','PAM berminat','PAM Done²','Konversi minat','Hari-surveyor teramati','Minat / hari teramati'],rows.map(row=>[`${esc(LB[row.name]||row.name)}${ROLE==='owner'?`<details><summary>Surveyor terotorisasi</summary>${row.individuals.map(person=>`<p>${esc(person.name)} · ${N(person.canvassed)} PAM canvassed · ${N(person.interested)} minat · ${N(person.installed)} Done</p>`).join('')}</details>`:''}`,N(row.surveyors_with_activity),N(row.active_surveyors),N(row.canvassed),N(row.interested),N(row.installed),percent(row.interest_rate),N(row.observed_surveyor_days),row.interested_per_observed_day==null?unavailable:row.interested_per_observed_day.toFixed(2)]))+
  `<p class="footer-definition">¹ Status pemetaan sumber/override, bukan absensi. ² Atribusi mengikuti surveyor dalam baris survei, bukan penanggung jawab pemasangan. Pelanggan lintas tim dapat muncul pada beberapa tim; subtotal tidak selalu aditif.</p>`+
  `<details class="legacy-report"><summary>Laporan koordinator asli &amp; pemetaan surveyor</summary>${notice('Laporan asli mengikuti bulan survei, regional dan area saja; filter lanjutan tidak berlaku. PDF lama berisi SEMUA surveyor, tanpa filter dan hanya administrator.',true)}${vKorlap()}</details>`;
}

function vOutstanding() {
  const out=A.outstanding;
  return `<h2>Intervensi pemasangan</h2><div class="compact-stats"><div class="compact-stat"><span>Baris sumber berminat belum Done/Cancel</span><strong>${N(out.survey_rows)}</strong></div><div class="compact-stat"><span>Referensi kasus pada cakupan ini</span><strong>${N(out.case_references)}</strong></div><div class="compact-stat"><span>Aging belum terverifikasi</span><strong>${N(out.aging['Insufficient Data'])}</strong></div></div>`+
  `<div class="intel-panels"><section class="panel"><h2>Status asli sumber</h2>${dataTable(['Konfirmasi pemasangan','Baris sumber'],Object.entries(out.by_status).map(([status,count])=>[esc(status),N(count)]))}<h2>Outstanding per regional</h2>${dataTable(['Regional','Baris sumber'],Object.entries(out.by_region).map(([region,count])=>[esc(region),N(count)]))}</section><section class="panel"><h2>Aging terverifikasi</h2>${dataTable(['Hari','Referensi kasus'],Object.entries(out.aging).map(([age,count])=>[esc(age),N(count)]))}<p class="footer-definition">Per ${esc(out.aging_as_of)}. ${esc(out.aging_rule)} Status manual tidak menimpa status sumber.</p></section></div>`+
  notice(`Kategori PAM JAYA tetap dipakai persis seperti sumber. ${N(out.active_references)} referensi aktif, ${N(out.manually_resolved)} ditutup secara manual setelah impor, ${N(out.urgent_count)} melewati tenggat PIC. Aging hanya menghitung referensi aktif. Tanggal survei/FA tidak otomatis menjadi awal kasus; riwayat dicatat terpisah.`)+
  (CAP.customer_detail&&out.urgent.length?`<h2>Urgent follow-ups · tenggat terlewati</h2>${dataTable(['Referensi kasus','PIC','Tenggat'],out.urgent.map(item=>[esc(item.ref),esc(item.pic),esc(item.target_date)]))}`:'')+
  (CAP.customer_detail?`<h2>Case workspace</h2><p class="mu sm">Buka referensi kasus untuk PIC, aksi, tenggat, catatan resolusi dan riwayat append-only.</p><div id="case-table">${skeleton()}</div>`:blank('Detail kasus dibatasi','Peran ini hanya mengakses ringkasan agregat. Administrator diperlukan untuk PAM ID dan pencatatan tindak lanjut.'));
}

function vData() {
  if(!CAP.customer_detail)return blank('Akses administrator diperlukan','PAM ID dan informasi pelanggan tidak dikirim ke peran aggregate viewer.');
  const q=S.dq,opts=(values,selected,title)=>values.map((value,index)=>option(index,index?value:title,index===selected)).join('');
  return `<h2>Customer lookup</h2><p class="mu sm">Pencarian dilakukan di server dan mengikuti seluruh filter global. PAM ID dapat dicari dari digit awal; data sumber tidak memuat nama, alamat atau telepon pelanggan.</p><div class="fl data-filters"><input id="qp" placeholder="PAM ID" value="${esc(q.p)}" inputmode="numeric" aria-label="PAM ID"><input id="qk" placeholder="Kelurahan" value="${esc(q.k)}" aria-label="Kelurahan"><input id="qs" placeholder="Surveyor" value="${esc(q.s)}" aria-label="Surveyor"><select id="qc" aria-label="Hasil canvassing">${opts(D.dic.c1,q.c,'Semua hasil canvassing')}</select><select id="qf" aria-label="Status pemasangan">${opts(D.dic.kf,q.f,'Semua status pemasangan')}</select><select id="qr" aria-label="Status potensi">${opts(D.dic.pr,q.r,'Semua status potensi')}</select></div><div id="case-table">${skeleton()}</div>`;
}

async function dt() {
  if(!CAP.customer_detail||!['data','outstanding'].includes(S.tab))return;
  const revision=++searchRevision,tab=S.tab,container=$('#case-table');if(!container)return;
  const q=S.dq,body={scope:scopeObject(),pam:tab==='data'?q.p:'',kelurahan:tab==='data'?q.k:'',surveyor:tab==='data'?q.s:'',canvassing:tab==='data'?q.c:0,installation:tab==='data'?q.f:0,potential:tab==='data'?q.r:0,outstanding_only:tab==='outstanding',offset:PAGE*PAGE_SIZE,limit:PAGE_SIZE};
  container.setAttribute('aria-busy','true');
  try {const result=await api('/api/records/search',{method:'POST',body:JSON.stringify(body)});if(revision!==searchRevision||S.tab!==tab)return;CURRENT_ROWS=result.rows;
    container.innerHTML=`<div class="pagination"><span>${N(result.total)} baris cocok · halaman ${PAGE+1}</span><div><button id="page-prev"${PAGE===0?' disabled':''}>Sebelumnya</button> <button id="page-next"${result.offset+result.limit>=result.total?' disabled':''}>Berikutnya</button></div></div>`+
    dataTable(['PAM ID / kasus','Tanggal survei','Regional / area / kelurahan','Surveyor / koordinator','Hasil canvassing','Status sumber','FA / pemasangan','Kendala','Flag / potensi / pelanggan','Tunggakan (Rp)','Tindak lanjut'],result.rows.map((row,index)=>[`<button data-case="${index}">${esc(row.pam)}</button><small class="mu">${esc(row.ref)}</small>`,esc(row.survey_date),`${esc(row.regional)} / ${esc(row.area)} / ${esc(row.kelurahan)}`,`${esc(row.surveyor)} / ${esc(row.coordinator)}`,esc(row.canvassing),esc(row.status),`${esc(row.fa_date||'–')} / ${esc(row.installation_date||'–')}`,esc(row.obstacle||'–'),`${esc(row.master_flag||'–')} / ${esc(row.potential_status||'–')} / ${esc(row.customer_status||'–')}`,number(row.arrears),row.followup?`${esc(row.followup.pic)}<br>${esc(row.followup.status)}<br>${esc(row.followup.target_date||'Tanpa tenggat')}`:'Belum dicatat']));
  }catch(error){if(revision===searchRevision)container.innerHTML=blank('Pencarian gagal',error.message)}finally{if(revision===searchRevision)container.removeAttribute('aria-busy')}
}

function vGovernance() {
  return `<h2>Data quality monitoring</h2><div id="quality-content">${QUALITY?qualityContent():skeleton()}</div>${ROLE==='owner'?`<section class="admin-section"><h2>Administrasi &amp; audit trail</h2><p class="mu sm">Perubahan operasional ditambahkan ke ledger privat. Tidak ada koreksi yang menghapus atau menimpa baris sumber.</p><div id="admin-content">${ADMIN?adminContent():skeleton()}</div></section>`:''}<details class="legacy-report"><summary>Catatan &amp; definisi asli sumber</summary>${notice('Catatan analisis bawaan versi sumber dipertahankan; bukan log sinkronisasi backend atau temuan baru yang sudah diverifikasi.',true)}${vCatatan()}</details>`;
}

function qualityContent() {
  const q=QUALITY;
  return `<div class="quality-grid">`+[['Imported records',q.imported_records],['Valid records',q.valid_records],['Duplicate excess rows',q.duplicate_records],['Duplicate PAM IDs',q.duplicate_customers],['Missing mandatory',q.missing_mandatory],['Invalid PAM IDs',q.invalid_pam],['Unmatched mapping',q.unmatched_mapping],['Conflicting geography',q.ambiguous_geography_customers]].map(([text,value])=>`<div class="compact-stat"><span>${esc(text)}</span><strong>${N(value)}</strong></div>`).join('')+`</div>`+
  notice('Mandatory: PAM numerik valid, tanggal survei, indeks regional/area/kelurahan/surveyor yang dapat dipetakan. Duplicate excess rows = jumlah baris di atas satu per PAM ID. Tidak ada duplikat yang dihapus dari sumber.')+
  dataTable(['Data source control','Value'],[['Last successful import',esc(timeLabel(q.source.imported_at))],['Source loaded for this session',esc(timeLabel(q.source.loaded_at))],['Survey-date range',esc(D.meta.tmin+' – '+D.meta.tmax)],['Source fingerprint',`<span class="source-id">${esc(q.source.fingerprint)}</span>`],['Data ownership',esc(BOOT.data_owner||unavailable)],['Synchronization errors',unavailable+' · no synchronization job supplied'],['Historical state comparison',esc(q.snapshot_comparison)]])+
  `<h2>Source reconciliation counters</h2>${dataTable(['Source field','Count'],Object.entries(q.source_sync).map(([key,value])=>[esc(key),typeof value==='number'?N(value):esc(String(value))]))}<p class="footer-definition">Counter rekonsiliasi impor, bukan jumlah kegagalan sinkronisasi backend. Snapshot terenkripsi dipertahankan oleh import CLI; tidak dibuat ulang menjadi riwayat bisnis yang tidak tersedia.</p>`;
}

function adminContent() {
  const rules=ADMIN.rules;
  return `<details><summary>Target pemasangan bulanan</summary><p class="mu sm">Target hanya dibandingkan untuk bulan penuh dan cakupan yang persis sama. Input berdasarkan dokumen target yang sah.</p><form class="admin-form" id="target-form"><label class="field">Bulan<select name="month">${D.months.map(month=>option(month,month,month===D.months[S.m1])).join('')}</select></label><label class="field">Target PAM terpasang<input name="target" type="number" min="1" max="10000000" required></label><label class="field">Cakupan aktif<input value="${esc(S.ab>=0?D.abs[S.ab]:S.reg||'Seluruh regional')}" readonly></label><label class="field wide">Bukti / dokumen target<input name="evidence" maxlength="1000" required></label><button>Simpan target dengan audit</button><p class="form-status" role="status"></p></form><h2>Target aktif</h2>${dataTable(['Bulan','Regional / area','Target','Bukti'],Object.values(ADMIN.targets).map(item=>[esc(item.month),esc(item.area_name||item.region||'Seluruh regional'),N(item.target),esc(item.evidence)]))}</details>
  <details><summary>Aturan prioritas transparan</summary><form class="admin-form" id="rules-form"><label class="field">Minimum PAM unik<input name="minimum_sample" type="number" min="1" max="100000" value="${rules.minimum_sample}" required></label><label class="field">High backlog rate (0–1)<input name="high_backlog_rate" type="number" step="0.01" min="0.01" max="1" value="${rules.high_backlog_rate}" required></label><label class="field">Cooling interest rate (0–1)<input name="cooling_interest_rate" type="number" step="0.01" min="0" max="1" value="${rules.cooling_interest_rate}" required></label><button>Simpan aturan</button><p class="form-status" role="status"></p></form></details>
  <details><summary>Supply &amp; installation readiness terverifikasi</summary><form class="admin-form" id="context-form"><label class="field">Area bisnis<select name="area">${D.abs.map((name,i)=>option(i,name,i===S.ab)).join('')}</select></label><label class="field">Supply<select name="supply"><option value="unknown">Unknown</option><option value="ready">Ready</option><option value="constrained">Constrained</option></select></label><label class="field">Kesiapan pemasangan<select name="readiness"><option value="unknown">Unknown</option><option value="ready">Ready</option><option value="blocked">Blocked</option></select></label><label class="field wide">Bukti aktual / referensi<input name="evidence" maxlength="1000" required></label><button>Simpan konteks area</button><p class="form-status" role="status"></p></form><h2>Konteks area aktif</h2>${dataTable(['Area','Supply','Readiness','Bukti'],Object.entries(ADMIN.area_context).map(([key,value])=>[esc(D.abs[+key]||key),esc(value.supply),esc(value.readiness),esc(value.evidence)]))}</details>
  <h2>Audit log · perubahan terbaru</h2>${ADMIN.events.length?ADMIN.events.map(event=>`<div class="history-entry"><strong>${esc(event.kind)} · ${esc(event.ref)}</strong><p>${esc(JSON.stringify(event.payload))}</p><small>${esc(timeLabel(event.at))} · actor ${esc(event.actor)} · event ${event.id}</small></div>`).join(''):'<p class="mu sm">Belum ada perubahan.</p>'}`;
}

async function loadGovernance(revision) {
  try {if(!QUALITY)QUALITY=await api('/api/quality');if(revision!==viewRevision||S.tab!=='catatan')return;$('#quality-content').innerHTML=qualityContent();
    if(ROLE==='owner'){if(!ADMIN)ADMIN=await api('/api/admin/audit');if(revision===viewRevision&&S.tab==='catatan')$('#admin-content').innerHTML=adminContent()}}
  catch(error){if(revision===viewRevision)setStatus(error.message)}
}

function render() {
  if(!D)return;rememberLegacyPanel();const revision=++viewRevision;
  document.querySelectorAll('.tabs button').forEach(button=>{const active=button.dataset.tab===S.tab;button.setAttribute('aria-selected',active);button.tabIndex=active?0:-1});
  $('#page-title').textContent=pageTitles[S.tab];$('#main').setAttribute('aria-labelledby','tab-'+S.tab);
  if(!A){$('#main').innerHTML=skeleton();return}
  $('#main').innerHTML=({ringkasan:vExecutive,analytics:vAnalytics,kelurahan:vRegional,korlap:vTeam,outstanding:vOutstanding,data:vData,catatan:vGovernance})[S.tab]();
  renderedTab=S.tab;const legacy=document.querySelector('#main .legacy-report');if(legacy&&legacyPanels.has(S.tab))legacy.open=legacyPanels.get(S.tab);if(ROLE!=='owner')$('#pdf')?.remove();
  if(S.tab==='kelurahan')kt();if(['data','outstanding'].includes(S.tab))dt();if(S.tab==='catatan')loadGovernance(revision);
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
  dialog.innerHTML=`<div class="dialog-header"><h2 id="case-title">PAM ${esc(row.pam)} · follow-up</h2><button id="close-case" aria-label="Tutup detail kasus">Tutup</button></div><div class="dialog-content"><p class="mu sm">${esc(row.ref)} · ${esc(row.area)} · status sumber ${esc(row.status)}</p><form id="followup-form" class="admin-form"><label class="field">PIC penanggung jawab<input name="pic" maxlength="150" value="${esc(latest.pic||row.coordinator)}" required></label><label class="field">Status tindak lanjut (terpisah)<select name="status">${D.dic.kf.filter(Boolean).concat(D.dic.kf.includes('Tidak tercatat')?[]:['Tidak tercatat']).map(status=>option(status,status,status===(latest.status||row.status))).join('')}</select></label><label class="field">Target selesai<input name="target_date" type="date" value="${esc(latest.target_date||'')}"></label><label class="field wide">Aksi tindak lanjut<textarea name="action" maxlength="2000" required></textarea></label><label class="field wide">Catatan resolusi<textarea name="resolution_notes" maxlength="2000">${esc(latest.resolution_notes||'')}</textarea></label><label class="field">Awal kasus terkonfirmasi<input name="case_started" type="date" value="${esc(latest.case_started||'')}" max="${new Date().toISOString().slice(0,10)}"></label><label class="field">Total hari jeda terverifikasi<input name="pause_days" type="number" min="0" max="36500" value="${latest.pause_days||0}"></label><label class="field">Alasan jeda<input name="pause_reason" maxlength="500" value="${esc(latest.pause_reason||'')}"></label><button>Tambahkan ke riwayat</button><p class="form-status" role="status"></p></form><p class="mu sm">Awal kasus dan jeda memerlukan bukti operasional. Tidak diambil otomatis dari tanggal survei. Aksi baru tidak menghapus aksi sebelumnya.</p><h2>Riwayat tindakan</h2><div id="case-history">${skeleton()}</div></div>`;
  dialog.showModal();await loadCaseHistory(row.ref);
}

async function loadCaseHistory(ref,before=null) {
  try {const history=await api('/api/followups/'+encodeURIComponent(ref)+(before?'?before='+before:''));if(!CASE||CASE.ref!==ref)return;const container=$('#case-history'),markup=history.events.length?history.events.map(event=>`<article class="history-entry"><strong>${esc(event.payload.pic)} · ${esc(event.payload.status)}</strong><p>${esc(event.payload.action)}</p><p>Tenggat: ${esc(event.payload.target_date||'Tidak ditetapkan')} · Resolusi: ${esc(event.payload.resolution_notes||'–')}</p><small>${esc(timeLabel(event.at))} · actor ${esc(event.actor)} · event ${event.id}</small></article>`).join(''):'<p class="mu sm">Belum ada tindakan tersimpan.</p>';if(before){container.querySelector('[data-history-before]')?.remove();container.insertAdjacentHTML('beforeend',markup)}else container.innerHTML=markup;if(history.next_before)container.insertAdjacentHTML('beforeend',`<button data-history-before="${history.next_before}">Muat riwayat lebih lama</button>`)}
  catch(error){if(CASE?.ref===ref)$('#case-history').textContent=error.message}
}

document.addEventListener('submit',async event=>{
  const form=event.target;if(!['followup-form','target-form','rules-form','context-form'].includes(form.id))return;event.preventDefault();const button=form.querySelector('button'),status=form.querySelector('.form-status');button.disabled=true;status.textContent='Menyimpan…';
  const values=Object.fromEntries(new FormData(form)),ref=CASE?.ref;let path,method='POST';
  if(form.id==='followup-form'){path='/api/followups/'+encodeURIComponent(ref);for(const key of ['case_started','target_date'])values[key]=values[key]||null;values.pause_days=+values.pause_days}
  if(form.id==='target-form'){path='/api/admin/targets';values.target=+values.target;values.region=S.reg;values.area=S.ab}
  if(form.id==='rules-form'){path='/api/admin/rules';method='PUT';for(const key of Object.keys(values))values[key]=+values[key]}
  if(form.id==='context-form'){path='/api/admin/area-context';values.area=+values.area}
  try {await api(path,{method,body:JSON.stringify(values)});ADMIN=null;status.textContent='Tersimpan di backend; riwayat sebelumnya tetap ada.';
    if(form.id==='followup-form'){if(CASE?.ref===ref){form.elements.action.value='';await loadCaseHistory(ref)}if(D)await refresh()}
    else await refresh();
  }catch(error){status.textContent=error.message}finally{button.disabled=false}
});

document.addEventListener('input',event=>{
  const target=event.target;if(target.id==='filter-search'){fill();return}
  if(target.id==='q'){S.q=target.value;S.all=0;kt()}
  else if(['qp','qk','qs'].includes(target.id)){S.dq[{qp:'p',qk:'k',qs:'s'}[target.id]]=target.value;PAGE=0;clearTimeout(searchTimer);searchTimer=setTimeout(dt,250)}
});

document.addEventListener('change',async event=>{
  const target=event.target;
  if(target.id==='f0'||target.id==='f1'){S[target.id==='f0'?'m0':'m1']=+target.value;if(S.m0>S.m1){if(target.id==='f0')S.m1=S.m0;else S.m0=S.m1}S.start=S.end='';refresh()}
  else if(target.id==='fr'){S.reg=target.value;S.ab=S.kel=-1;S.coordinator='';refresh()}
  else if(target.id==='fa'){S.ab=+target.value;if(S.ab>=0)S.reg=D.reg[S.ab];S.kel=-1;S.coordinator='';refresh()}
  else if(target.id==='fk'){S.kel=+target.value;refresh()}
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
  const route=target.dataset.tab||target.dataset.route;
  if(route){S.tab=route;S.all=0;PAGE=0;setStatus('');render();if(target.dataset.route)$('#main').focus({preventScroll:true});return}
  if(target.id==='retry-analysis'){refresh();return}
  if(target.dataset.export){const buttons=[...document.querySelectorAll('[data-export]')];buttons.forEach(button=>button.disabled=true);setStatus('');try{const extension=target.dataset.export,kind=$('#report-kind').value;await download('/api/reports/'+kind+'.'+extension+'?'+params(),'RPD-'+kind+'.'+extension)}catch(error){setStatus(error.message)}finally{buttons.forEach(button=>button.disabled=false)}return}
  if(target.id==='rs'){Object.assign(S,{m0:0,m1:D.months.length-1,reg:'',ab:-1,kel:-1,coordinator:'',statuses:[],start:'',end:'',q:'',open:'',openK:null,all:0,dq:{p:'',k:'',s:'',c:0,r:0,f:0,n:100}});$('#filter-search').value='';refresh();return}
  if(target.id==='save-preset'){const name=$('#preset-name').value.trim();if(!name){setStatus('Masukkan nama preset.');return}const presets=presetList();Object.defineProperty(presets,name,{value:presetScope(),enumerable:true,writable:true,configurable:true});savePresetList(presets);fill();setStatus('Preset filter disimpan tanpa data pelanggan.');return}
  if(target.id==='load-preset'){const value=presetList()[$('#preset-list').value];if(!value)return;const scope=resolvePreset(value);if(!scope){setStatus('Cakupan preset lama tidak dapat diverifikasi pada sumber aktif. Simpan ulang preset; filter tidak diubah.');return}Object.assign(S,scope);refresh();return}
  if(target.id==='delete-preset'){const presets=presetList();delete presets[$('#preset-list').value];savePresetList(presets);fill();return}
  if(target.dataset.region!==undefined){S.reg=target.dataset.region;S.ab=S.kel=-1;S.coordinator='';refresh();return}
  if(target.dataset.area!==undefined){S.ab=+target.dataset.area;S.reg=D.reg[S.ab];S.kel=-1;S.coordinator='';refresh();return}
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
try{setTheme(localStorage.getItem('rpd_theme')==='dark'?'dark':'light');localStorage.removeItem('rpd_ov')}catch{setTheme('light')}
$('#thm').onclick=()=>{const theme=document.documentElement.dataset.theme==='dark'?'light':'dark';setTheme(theme);try{localStorage.setItem('rpd_theme',theme)}catch{}};
$('#login-form').onsubmit=event=>{event.preventDefault();go()};
$('#out').onclick=async()=>{try{await api('/api/logout',{method:'POST'})}catch{}finally{localLogout()}};
$('#ft').onclick=()=>{const open=$('#gf').classList.toggle('open');$('#ft').setAttribute('aria-expanded',open)};
document.querySelectorAll('.tabs button').forEach(button=>{button.setAttribute('aria-label',button.textContent.trim());button.title=button.textContent.trim()});
document.querySelector('.tabs').addEventListener('keydown',event=>{const buttons=[...document.querySelectorAll('.tabs button')],index=buttons.indexOf(document.activeElement);if(index<0)return;let next=index;if(['ArrowDown','ArrowRight'].includes(event.key))next=(index+1)%buttons.length;else if(['ArrowUp','ArrowLeft'].includes(event.key))next=(index+buttons.length-1)%buttons.length;else if(event.key==='Home')next=0;else if(event.key==='End')next=buttons.length-1;else return;event.preventDefault();buttons[next].click();buttons[next].focus()});
document.addEventListener('keydown',event=>{if(['Enter',' '].includes(event.key)&&event.target.matches('th[data-i]')){event.preventDefault();event.target.click()}});
const navLayout=()=>document.querySelector('.tabs').setAttribute('aria-orientation',matchMedia('(max-width:600px)').matches?'horizontal':'vertical');
navLayout();matchMedia('(max-width:600px)').addEventListener('change',navLayout);
api('/health').then(health=>{if(!health.configured)$('#le').textContent='Backend privat belum dikonfigurasi. Hubungi administrator untuk akses layanan privat.'}).catch(error=>{$('#le').textContent=error.message});
