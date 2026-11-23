
let D,REC,OV={},ROLE='',WM=null;
const $=s=>document.querySelector(s),N=n=>Math.round(n).toLocaleString('id-ID'),PC=v=>(v*100).toFixed(1).replace('.',',')+'%',R=(a,b)=>b?a/b:null,
MN=['Jan','Feb','Mar','Apr','Mei','Jun','Jul','Agu','Sep','Okt','Nov','Des'],
ML=(i,s)=>{const[y,m]=D.months[i].split('-');return(i==0&&!s?'s.d. ':'')+MN[m-1]+' '+(s?y.slice(2):y)},
esc=s=>String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/"/g,'&quot;'),tc=s=>esc(s.toLowerCase().replace(/(^|[\s.'-])(\w)/g,(a,b,c)=>b+c.toUpperCase()));
const icon=name=>`<svg class="icon" aria-hidden="true"><use href="#i-${name}"/></svg>`;
const S={kel:-1,coordinator:'',statuses:[],start:'',end:'',m0:0,m1:0,reg:'',ab:-1,tab:'ringkasan',sort:{},q:'',open:'',all:0,dq:{p:'',k:'',s:'',c:0,r:0,f:0,n:100}},T={};
const ok=r=>r[0]>=S.m0&&r[0]<=S.m1&&(S.ab>=0?r[1]==S.ab:(!S.reg||D.reg[r[1]]==S.reg));
const sum=(rows,o,n)=>{const t=Array(n).fill(0);for(const r of rows)for(let i=0;i<n;i++)t[i]+=r[o+i];return t};
const grp=(rows,kf,o,n)=>{const m=new Map();for(const r of rows){const k=kf(r);let t=m.get(k);if(!t)m.set(k,t=Array(n).fill(0));for(let i=0;i<n;i++)t[i]+=r[o+i]}return m};
function tbl(id,cols,rows,tot,o={}){
 const st=S.sort[id]||{i:o.si,d:-1};T[id]={si:o.si,cols};
 const cmp=(a,b)=>{const x=a.v[st.i],y=b.v[st.i];return(typeof x=='string'?x.localeCompare(y,'id'):(x??-1)-(y??-1))*st.d};
 const rs=[...rows].sort((a,b)=>(a.g||0)-(b.g||0)||cmp(a,b)),lim=o.lim&&!S.all?o.lim:1e9;
 const cell=(c,v)=>c.t=='s'?`<td class=s>${v}</td>`:c.t=='n'?`<td>${N(v)}</td>`:c.t=='p'?`<td>${v==null?'–':PC(v)}</td>`:`<td>${v==null?'–':`<span class=tr><i style="width:${Math.min(100,v*100)}%"></i></span>${PC(v)}`}</td>`;
 let h=`<p class=hint>Geser tabel ke samping untuk melihat semua kolom.</p><div class=tw><table data-id=${id}><thead><tr>`+cols.map((c,i)=>`<th data-i=${i} class="${c.t=='s'?'s':''}">${c.h}${st.i==i?(st.d>0?' ▲':' ▼'):''}</th>`).join('')+'</tr></thead><tbody>',sp=0;
 if(!rs.length)h+=`<tr><td colspan=${cols.length} style="text-align:center;padding:30px;color:var(--mu)">Tidak ada data yang cocok dengan filter ini.</td></tr>`;
 rs.slice(0,lim).forEach(r=>{if(r.g&&!sp){sp=1;h+=`<tr class=sp><td colspan=${cols.length}>${o.sep}</td></tr>`}
  h+=`<tr${r.k?` class=c data-k="${esc(r.k)}"`:''}${r.on?' aria-selected=true':''}>`+r.v.map((v,i)=>cell(cols[i],v)).join('')+'</tr>';
  if(r.sub)h+=`<tr class=sb><td colspan=${cols.length}>${r.sub}</td></tr>`});
 if(tot)h+='<tr class=t>'+tot.map((v,i)=>cell(cols[i],v)).join('')+'</tr>';
 h+='</tbody></table></div>';if(rs.length>lim)h+=`<p><button id=all>Tampilkan semua ${N(rs.length)} baris</button></p>`;return h}
const kpi=(l,v,s)=>`<div class=k><div class=mu>${l}</div><div class=kv>${N(v)}</div><div class="mu sm">${s}</div></div>`;
function seg(items,tot){return `<div class="seg" role="img" aria-label="${items.map(([l,v])=>l+': '+N(v)).join(', ')}">`+items.map(([l,v,c])=>`<i title="${l}: ${N(v)}" style="width:${R(v,tot)*100||0}%;background:var(--${c})"></i>`).join('')+`</div><div class="lg">`+items.map(([l,v,c])=>`<div class="legend-row"><b style="background:var(--${c})"></b><span>${l}</span><strong>${N(v)}</strong><em>${PC(R(v,tot)||0)}</em></div>`).join('')+`</div>`}
function bars(t,vals,lab){const mx=Math.max(1,...vals),w=Math.max(360,vals.length*42),step=w/Math.max(1,vals.length),k=v=>v>=1000?(v/1000).toFixed(1).replace('.',',')+'k':v;
 return `<div class="bc"><div class="sm">${t}</div>`+(vals.length?`<svg viewBox="0 0 ${w} 160" role="img" aria-label="${t}">`+[40,80,120].map(y=>`<line x1="0" x2="${w}" y1="${y}" y2="${y}" stroke="var(--ln)" stroke-dasharray="3 4"/>`).join('')+vals.map((v,i)=>{const h=v/mx*98;return `<rect x="${i*step+step*.22}" y="${130-h}" width="${step*.56}" height="${h}" rx="3" fill="var(--b1)"><title>${lab[i]}: ${N(v)}</title></rect><text x="${i*step+step/2}" y="${123-h}" font-size="9" text-anchor="middle" fill="var(--fg)">${k(v)}</text><text x="${i*step+step/2}" y="150" font-size="8" text-anchor="middle" fill="var(--mu)">${lab[i]}</text>`}).join('')+'</svg>':'<p class="mu sm">Tidak ada data pada periode ini.</p>')+'</div>'}
const CA=[{h:'Tercanvassing',t:'n'},{h:'Berminat',t:'n'},{h:'% berminat',t:'p'},{h:'Assign FA',t:'n'},{h:'Terpasang',t:'n'},{h:'Outstanding',t:'n'},{h:'Cancel',t:'n'},{h:'% terpasang dari berminat',t:'b'}];
const rowA=t=>[t[0],t[1],R(t[1],t[0]),t[6],t[7],t[8],t[9],R(t[7],t[1])];
function vRingkasan(){
 const A=D.A.filter(ok),t=sum(A,2,10),[c,b,tb,bd,ptd,nb,af,tp,os,cn]=t;
 const rg=r=>S.ab>=0?r[0]==S.ab:(!S.reg||D.reg[r[0]]==S.reg),pm=D.P.filter(rg).reduce((x,r)=>x+r[2],0),ba=D.P.filter(rg).reduce((x,r)=>x+r[3],0);
 const uq=!S.m0&&S.m1==D.months.length-1&&!S.reg&&S.ab<0?' · '+N(D.meta.uniq)+' PAM ID unik':'';
 let h=`<h2>Posisi saat ini <span class="mu sm">Realisasi operasional</span></h2><div class="cg">`+[
 ['Tercanvassing',c,'Baris pelanggan'+uq,'chart'],
 ['Berminat',b,PC(R(b,c)||0)+' dari tercanvassing','users'],
 ['Assign FA',af,'Berkas berminat siap dijadwalkan','file'],
 ['Outstanding',os,'Berminat belum Assign FA','clock'],
 ['Terpasang',tp,'Done · '+PC(R(tp,b)||0)+' dari berminat','check'],
 ['Sisa potensi',pm-ba,'Master − berminat · seluruh periode','target']
 ].map(x=>`<div class="cd"><div class="card-top"><div class="cl">${x[0]}</div><span class="metric-icon">${icon(x[3])}</span></div><div class="cv">${N(x[1])}</div><div class="mu sm2">${x[2]}</div></div>`).join('')+`</div>`;
 h+=`<div class="two breakdowns"><section class="panel"><h2>Hasil canvassing <span class="panel-sub">Komposisi hasil survei</span></h2>${seg([['Berminat',b,'b1'],['Tidak berminat',tb,'b2'],['Belum diketahui',bd,'b3'],['PTD',ptd,'b4'],['Tidak ada bangunan',nb,'b5']],c)}</section>
 <section class="panel"><h2>Status pemasangan <span class="panel-sub">Pelanggan berminat</span></h2>${seg([['Terpasang',tp,'b1'],['Assign FA',af,'b2'],['Outstanding',os,'b3'],['Cancel',cn,'b4']],b)}</section></div>`;
 const ms=[...new Set(A.map(r=>r[0]))].sort((a,b)=>a-b),gm=grp(A,r=>r[0],2,10),ge=grp(D.E.filter(ok),r=>r[0],2,2),lab=ms.map(i=>ML(i,1));
 h+=`<h2>Tren bulanan <span class="mu sm">Perkembangan dari waktu ke waktu</span></h2><div class="two trend-grid">`+bars('Tercanvassing · bulan survei',ms.map(i=>gm.get(i)[0]),lab)+bars('Berminat · bulan survei',ms.map(i=>gm.get(i)[1]),lab)+bars('Meter terpasang · bulan pemasangan',ms.map(i=>(ge.get(i)||[0,0])[1]),lab)+`</div>`;
 const g=grp(A,r=>D.reg[r[1]],2,10);
 h+=`<h2>Kinerja per regional <span class="mu sm">Klik baris untuk memfilter laporan</span></h2>`+tbl('reg',[{h:'Regional',t:'s'},...CA],[...g].map(([k,t])=>({k:'reg:'+k,on:S.reg==k,v:[esc(k),...rowA(t)]})),['Total',...rowA(t)],{si:1});
 const ga=grp(A,r=>r[1],2,10);
 h+=`<h2>Kinerja per area bisnis</h2>`+tbl('ab',[{h:'Area bisnis',t:'s'},{h:'Regional',t:'s'},...CA],[...ga].map(([k,t])=>({k:'ab:'+k,on:S.ab==k,v:[esc(D.abs[k]),esc(D.reg[k]),...rowA(t)]})),['Total','',...rowA(t)],{si:2});
 return h}
function kdata(){const M=new Map();for(const r of D.P){if(S.ab>=0?r[0]!=S.ab:(S.reg&&D.reg[r[0]]!=S.reg))continue;M.set(r[0]*1000+r[1],r)}
 return[...M].map(([k,r])=>({k,a:r[0],n:D.kels[r[1]],pot:r[2],b:r[3],tp:r[4]}))}
function wm(){if(!WM){WM=new Map;for(const r of D.W){const k=r[0]*1000+r[1];let e=WM.get(k);if(!e)WM.set(k,e={rw:new Set,rt:new Set});if(r[2]){e.rw.add(r[2]);if(r[3])e.rt.add(r[2]*1000+r[3])}}}return WM}
function vKel(){const r=kdata(),pot=r.reduce((x,y)=>x+y.pot,0),b=r.reduce((x,y)=>x+y.b,0),tp=r.reduce((x,y)=>x+y.tp,0),ba=D.A.filter(x=>S.ab>=0?x[1]==S.ab:(!S.reg||D.reg[x[1]]==S.reg)).reduce((x,y)=>x+y[3],0);
 return`<h2>Potensi riil, berminat, dan sisa potensi</h2><div class=kg>`+kpi('Potensi master',pot,'MASTER DATA, kolom Potensi')+kpi('Berminat (dikeluarkan)',b,PC(R(b,pot)||0)+' dari potensi master')+kpi('Terpasang',tp,'dari berminat tersebut')+kpi('Berminat belum terpasang',b-tp,'assign FA, outstanding, cancel')+kpi('Sisa potensi riil',pot-b,'potensi master − berminat')+kpi('Berminat di luar potensi master',ba-b,'tidak mengurangi potensi')+`</div>
 <p class="mu sm" style="margin-top:10px">${N(r.length)} kelurahan pada filter ini. Klik baris kelurahan untuk melihat RW dan RT. Tab ini selalu memakai seluruh periode dan mengikuti filter regional dan area bisnis.</p><p><input id=q type=search placeholder="Cari kelurahan" value="${esc(S.q)}" aria-label="Cari kelurahan"></p><div id=kt></div>`}
function rwTbl(a,kel){const m=new Map(),o=(x,y)=>(x[0]||1e9)-(y[0]||1e9);for(const r of D.W)if(r[0]==a&&r[1]==kel){let e=m.get(r[2]);if(!e)m.set(r[2],e={p:0,b:0,rt:[]});e.p+=r[4];e.b+=r[5];e.rt.push([r[3],r[4],r[5]])}
 return`<table><thead><tr><th class=s>RW</th><th>Jumlah RT</th><th>Potensi master</th><th>Berminat</th><th>Sisa potensi</th><th class=s>Sisa / master per RT</th></tr></thead><tbody>`+[...m].sort(o).map(([rw,e])=>{e.rt.sort(o);return`<tr><td class=s>${rw?'RW '+rw:'RW tidak tercatat'}</td><td>${N(e.rt.filter(x=>x[0]).length)}</td><td>${N(e.p)}</td><td>${N(e.b)}</td><td>${N(e.p-e.b)}</td><td class=s style="white-space:normal;min-width:260px">${e.rt.map(([rt,n,b])=>(rt?'RT '+rt:'RT tidak tercatat')+' ('+N(n-b)+'/'+N(n)+')').join(', ')}</td></tr>`}).join('')+`</tbody></table>`}
function kt(){const q=S.q.trim().toUpperCase(),W=wm();
 const rows=kdata().filter(x=>!q||x.n.includes(q)).map(x=>{const e=W.get(x.k),open=S.openK==x.k;return{k:'kel:'+x.k,on:open,sub:open?rwTbl(x.a,x.k%1000):'',t:[x.pot,x.b,x.tp,e?e.rw.size:0,e?e.rt.size:0],v:[tc(x.n),esc(D.abs[x.a]),esc(D.reg[x.a]),x.pot,e?e.rw.size:0,e?e.rt.size:0,x.b,x.tp,x.b-x.tp,x.pot-x.b,R(x.b,x.pot)]}});
 const s=sum(rows.map(r=>r.t),0,5);
 $('#kt').innerHTML=tbl('kel',[{h:'Kelurahan',t:'s'},{h:'Area bisnis',t:'s'},{h:'Regional',t:'s'},{h:'Potensi master',t:'n'},{h:'Jumlah RW',t:'n'},{h:'Jumlah RT',t:'n'},{h:'Berminat (dikeluarkan)',t:'n'},{h:'Terpasang',t:'n'},{h:'Berminat belum terpasang',t:'n'},{h:'Sisa potensi riil',t:'n'},{h:'% berminat dari potensi',t:'b'}],rows,['Total','','',s[0],s[3],s[4],s[1],s[2],s[1]-s[2],s[0]-s[1],R(s[1],s[0])],{si:9,lim:60})}
const LB={'AKUN GENERIK':'Akun generik “Surveyor Marketing”','BELUM TERDAFTAR':'Belum ada di list koordinator','PENGAWAS':'Pengawas (koordinator belum ditentukan)'},STL=['Aktif','Resign','Pengawas'];
const eKl=r=>OV[r[3]]?.kl||D.kl[r[2]],eSt=i=>OV[i]?.st??D.st[i];
function vKorlap(){
 const G=new Map();for(const r of D.S.filter(ok)){const k=eKl(r);let g=G.get(k);if(!g)G.set(k,g={t:Array(10).fill(0),sv:new Map()});let s=g.sv.get(r[3]);if(!s)g.sv.set(r[3],s=Array(10).fill(0));for(let i=0;i<10;i++){g.t[i]+=r[4+i];s[i]+=r[4+i]}}
 const rows=[...G].map(([k,g])=>{const t=g.t,n=g.sv.size,na=[...g.sv.keys()].filter(i=>!eSt(i)).length,main=D.meta.korlaps.includes(k);
  const sub=`<table><thead><tr><th class=s>Surveyor</th><th class=s>Status</th><th>Tercanvassing</th><th>Berminat</th><th>% berminat</th><th>Assign FA</th><th>Terpasang</th><th>Outstanding</th><th>Cancel</th></tr></thead><tbody>`+[...g.sv].sort((a,b)=>b[1][0]-a[1][0]).map(([i,s])=>`<tr><td class=s>${tc(D.svs[i])}</td><td class=s>${STL[eSt(i)]}</td><td>${N(s[0])}</td><td>${N(s[1])}</td><td>${PC(R(s[1],s[0]))}</td><td>${N(s[3])}</td><td>${N(s[2])}</td><td>${N(s[4])}</td><td>${N(s[5])}</td></tr>`).join('')+'</tbody></table>';
  return{k:'kl:'+k,g:main?0:1,on:S.open==k,sub:S.open==k?sub:'',v:[main?tc(k):LB[k]||tc(k),na,n-na,t[0],t[1],R(t[1],t[0]),t[3],t[2],R(t[2],t[1]),t[4],t[5],R(t[0],n)],t}});
 const m=rows.filter(r=>!r.g),a=sum(m.map(r=>r.t),0,10),sa=m.reduce((x,r)=>x+r.v[1],0),sr=m.reduce((x,r)=>x+r.v[2],0);
 return`<h2>Pencapaian per koordinator <span class="mu sm">klik baris untuk melihat surveyor</span></h2><p class="mu sm">File tidak memuat target, jadi pencapaian ditampilkan sebagai realisasi dan rasio. Surveyor resign dan pengawas tetap dihitung di koordinator asalnya. Total hanya menjumlahkan tujuh koordinator.</p><p><button id=pdf>Unduh PDF semua surveyor</button></p>`+tbl('kl',[{h:'Koordinator',t:'s'},{h:'Surveyor aktif',t:'n'},{h:'Resign / pengawas',t:'n'},{h:'Tercanvassing',t:'n'},{h:'Berminat',t:'n'},{h:'% berminat',t:'b'},{h:'Assign FA',t:'n'},{h:'Terpasang',t:'n'},{h:'% terpasang dari berminat',t:'b'},{h:'Outstanding',t:'n'},{h:'Cancel',t:'n'},{h:'Rata-rata canvass per surveyor',t:'n'}],rows,['Total koordinator',sa,sr,a[0],a[1],R(a[0]?a[1]:0,a[0]),a[3],a[2],R(a[2],a[1]),a[4],a[5],R(a[0],sa+sr)||0],{si:3,sep:'Di luar tujuh koordinator'})+(ROLE=='owner'?editor():'')}
function editor(){
 const kls=[...D.meta.korlaps,'PENGAWAS','BELUM TERDAFTAR','AKUN GENERIK'],def={},cnt=new Map();for(const r of D.S){def[r[3]]=D.kl[r[2]];cnt.set(r[3],(cnt.get(r[3])||0)+r[4])}
 const rows=[...cnt].sort((a,b)=>b[1]-a[1]).map(([i,c])=>{const k=OV[i]?.kl||def[i];return`<tr><td class=s>${tc(D.svs[i])}</td><td>${N(c)}</td><td><select data-ov=${i} data-f=kl>${kls.map(x=>`<option value="${esc(x)}"${x==k?' selected':''}>${LB[x]||tc(x)}</option>`).join('')}</select></td><td><select data-ov=${i} data-f=st>${STL.map((x,j)=>`<option value=${j}${j==eSt(i)?' selected':''}>${x}</option>`).join('')}</select></td></tr>`}).join('');
 return`<h2>Editor pemetaan surveyor <span class="mu sm">khusus owner</span></h2><p class="mu sm">${window.RPDStatic?'Perubahan disimpan terenkripsi hanya pada peramban dan akun ini, tidak tersinkron ke tim.':'Perubahan disimpan di backend dengan jejak audit.'} JSON di bawah adalah salinan pemetaan aktif; tidak mengubah data sumber.</p><div class=tw style="max-height:420px;overflow:auto"><table><thead><tr><th class=s>Surveyor</th><th>Baris</th><th class=s>Koordinator</th><th class=s>Status</th></tr></thead><tbody>${rows}</tbody></table></div><p><textarea readonly aria-label="Perubahan pemetaan">${esc(JSON.stringify(Object.fromEntries(Object.entries(OV).map(([i,v])=>[D.svs[i],v]))))}</textarea></p><p><button id=ovx>Hapus semua perubahan</button></p>`}
const DT=n=>n?`${n%100}/${(n/100|0)%100}/${2000+(n/10000|0)}`:'–',PID=(p,a)=>String(p).padStart(['Timur','Utara'].includes(D.reg[a])?8:9,'0');
function vCatatan(){const m=D.meta,T=sum(D.A,2,10),PM=D.P.reduce((x,r)=>x+r[2],0),sy=m.sync,B={};for(const r of D.S)B[D.kl[r[2]]]=(B[D.kl[r[2]]]||0)+r[4];const nu=new Set(D.S.filter(r=>D.kl[r[2]]=='BELUM TERDAFTAR').map(r=>r[3])).size;return`<h2>Definisi metrik</h2><div class=tw><table><tbody>
<tr><td class=s>Tercanvassing</td><td class=s style="white-space:normal">Jumlah baris survei di sheet Detail (${N(m.rows)} baris, ${N(m.uniq)} PAM ID unik), dihitung menurut Tanggal Survey.</td></tr>
<tr><td class=s>Berminat</td><td class=s style="white-space:normal">Hasil Canvasing = Berminat.</td></tr>
<tr><td class=s>Assign FA, Terpasang, Outstanding, Cancel</td><td class=s style="white-space:normal">Kolom Konfirmasi Pemasangan (Assign FA, Done, Outstanding, Cancel). Keempatnya membagi habis pelanggan berminat tanpa sisa, jadi saling lepas.</td></tr>
<tr><td class=s>Potensi master</td><td class=s style="white-space:normal">Jumlah PAM ID di MASTER DATA dengan kolom paling kanan (FINAL FLAG) bernilai POTENSI, per kelurahan, RW, dan RT.</td></tr>
<tr><td class=s>Sisa potensi riil</td><td class=s style="white-space:normal">Potensi master dikurangi PAM ID potensi yang berstatus Berminat di sheet Update (${N(sy.deduct)} PAM ID). Selalu memakai seluruh periode.</td></tr></tbody></table></div>
<h2>Temuan analisis</h2><div class=note><ul>
<li><b>Sinkronisasi Update dan MASTER DATA.</b> Dari ${N(sy.pot_master)} PAM ID potensi di MASTER DATA, ${N(sy.deduct)} ternyata berminat di sheet Update dan dikeluarkan, sehingga potensi riil menjadi ${N(sy.pot_master-sy.deduct)} (${N(sy.deduct_tp)} di antaranya sudah terpasang). Kolom Data Potensi di MASTER DATA baru mencatat ${N(sy.dp_b)} berminat, jadi master belum mengikuti Update.</li>
<li><b>Berminat di luar potensi master.</b> ${N(T[1]-sy.deduct)} dari ${N(T[1])} pelanggan berminat tidak termasuk potensi master (${N(sy.outside)} tidak ada di MASTER DATA dan ${N(sy.non_berm)} berstatus NON POTENSI), sehingga tidak mengurangi potensi.</li>
<li><b>Perlu keputusan.</b> ${N(sy.nb)} PAM ID potensi berstatus tidak ada bangunan dan ${N(sy.ptd)} berstatus PTD di sheet Update, tetapi masih dihitung potensi. Bisa dilihat di tab Cek PAM ID lewat filter Status potensi.</li>
<li><b>Selisih antar sheet.</b> ${N(sy.ab_diff)} PAM ID berbeda area bisnis dan ${N(sy.kel_diff)} berbeda kelurahan antara Update dan MASTER DATA (potensi mengikuti MASTER DATA). ${N(sy.master_missing)} PAM ID di MASTER DATA tidak ada di Update.</li>
<li><b>Pemetaan koordinator.</b> Pemetaan dari Anda (Rano, Fadly, surveyor resign, dan pengawas) sudah dipakai. Masih di luar koordinator: ${N(B['AKUN GENERIK']||0)} baris akun generik “Surveyor Marketing”, ${N(B['BELUM TERDAFTAR']||0)} baris dari ${nu} nama yang belum ada di list, dan ${N(B['PENGAWAS']||0)} baris dari tujuh pengawas yang timnya belum disebutkan.</li>
<li><b>Nama surveyor digabung.</b> Nama yang sama dengan tambahan atau salah huruf disatukan ke nama di list, misalnya Muhamad/Muhammad, Ryan Piet Hariyadi/Haryadi, dan Mochammad Gilang P/Perdana. Nama yang bisa orang berbeda (mis. Imam Saputra dan Gian Saputra) tidak digabung.</li>
<li><b>Koordinator Ghani berprofil lain.</b> Hampir seluruh barisnya berstatus berminat, kemungkinan tim tindak lanjut. Sebaiknya tidak dibandingkan langsung dengan koordinator lain.</li>
<li><b>${N(T[1]-T[7])} pelanggan berminat belum terpasang:</b> ${N(T[6])} Assign FA, ${N(T[8])} Outstanding, ${N(T[9])} Cancel.</li>
<li><b>Sumber data.</b> File terbaru memuat sheet Update 19112026 dan MASTER DATA, tetapi tidak memuat List Surveyor dan Korlapnya, sehingga pemetaan koordinator tetap memakai data sebelumnya. Flag master, status pelanggan, tunggakan, RW, dan RT dari MASTER DATA terbaru.</li>
<li><b>RW dan RT.</b> ${N(m.rt_bad)} dari ${N(PM)} PAM ID potensi tidak punya RW atau RT yang valid (kosong, 0, atau di atas 99) dan dikelompokkan sebagai “tidak tercatat”.</li>
<li><b>Kualitas data.</b> Dua baris berstatus “cancel” huruf kecil disamakan dengan Cancel. ${N(m.rows-m.uniq)} PAM ID muncul dua kali (umumnya di dua area bisnis berbeda) dan tetap dihitung per baris. Kolom Month tidak konsisten, jadi periode memakai Tanggal Survey. Survei sebelum Okt 2025 (±50 baris) digabung ke Okt 2025.</li></ul></div>`}

const fd=s=>{if(!s||typeof s!=='string')return 'Insufficient Data';const[y,m,d]=s.split('-');return +d+' '+MN[m-1]+' '+y};
