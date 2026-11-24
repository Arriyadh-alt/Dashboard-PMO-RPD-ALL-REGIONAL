/* Unauthenticated landing. Fetch ONLY the explicitly approved public projection.
   Never fall back to an encrypted operational source or an authentication API. */
(() => {
  'use strict';
  const landing=document.getElementById('public-app');if(!landing)return;
  const loader=document.currentScript,root=new URL('../',loader.src),content=document.getElementById('public-content');
  const loaded=new Set();let internalReady=false,loading=null;
  const escape=value=>String(value).replace(/[&<>"']/g,char=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[char]));
  const count=value=>new Intl.NumberFormat('id-ID').format(value);
  const metrics=['potential','canvassed','interested','installed','remaining'];
  const labels=['Total Potensi','Tercanvassing','Berminat','Terpasang','Sisa Potensi'];
  let snapshot=null,sort='name',descending=false,query='';
  const exact=(object,keys)=>object&&typeof object==='object'&&!Array.isArray(object)&&Object.keys(object).length===keys.length&&keys.every(key=>Object.hasOwn(object,key));
  function approved(data){
    if(!exact(data,['public_version','snapshot_pair','survey_through','metrics','regions','trends',...(Object.hasOwn(data||{},'reporting_date')?['reporting_date']:[])])||(data.reporting_date&&!/^\d{4}-\d{2}-\d{2}$/.test(data.reporting_date))||data.public_version!==1||!exact(data.metrics,metrics)||!Array.isArray(data.regions)||!Array.isArray(data.trends))return false;
    const counts=(object,keys)=>keys.every(key=>Number.isSafeInteger(object[key])&&object[key]>=0);
    return counts(data.metrics,metrics)&&data.regions.every(row=>exact(row,['name',...metrics])&&typeof row.name==='string'&&counts(row,metrics))&&
      data.trends.every(row=>exact(row,['month','canvassed','interested','installation_events'])&&/^\d{4}-\d{2}$/.test(row.month)&&counts(row,['canvassed','interested','installation_events']));
  }
  function trend(rows){
    if(!rows.length)return '<p class="mu">Tren belum tersedia.</p>';
    const series=[['canvassed','Tercanvassing','#17324D'],['interested','Berminat','#168A91'],['installation_events','Terpasang','#8B9BAB']],
      width=640,height=215,left=54,right=20,top=20,bottom=32,max=Math.max(1,...rows.flatMap(row=>series.map(([key])=>row[key]))),
      x=i=>left+(width-left-right)*(rows.length===1?.5:i/(rows.length-1)),y=value=>top+(height-top-bottom)*(1-value/max);
    return '<div class="chart-key">'+series.map(([,label,color])=>`<span><i style="background:${color}"></i>${label}</span>`).join('')+'</div>'+`
      <svg class="trend-svg" viewBox="0 0 ${width} ${height}" role="img" aria-label="Tren kinerja bulanan">`+
      [0,.5,1].map(fraction=>`<line x1="${left}" x2="${width-right}" y1="${y(max*fraction)}" y2="${y(max*fraction)}" stroke="var(--ln)"/><text x="${left-8}" y="${y(max*fraction)+4}" text-anchor="end">${count(Math.round(max*fraction))}</text>`).join('')+
      series.map(([key,label,color])=>`<polyline points="${rows.map((row,i)=>x(i)+','+y(row[key])).join(' ')}" fill="none" stroke="${color}" stroke-width="2"/>`+
        rows.map((row,i)=>`<circle cx="${x(i)}" cy="${y(row[key])}" r="3" fill="${color}"><title>${escape(row.month+' · '+label+': '+count(row[key]))}</title></circle>`).join('')).join('')+
      rows.map((row,i)=>i===0||i===rows.length-1||i%Math.ceil(rows.length/5)===0?`<text x="${x(i)}" y="${height-7}" text-anchor="middle">${escape(row.month)}</text>`:'').join('')+'</svg>'+ 
      '<p class="chart-caption">Survei menurut tanggal survei; terpasang menurut tanggal pemasangan.</p><details><summary>Lihat angka tren</summary><div class="tw"><table><thead><tr><th>Bulan</th><th>Tercanvassing</th><th>Berminat</th><th>Terpasang</th></tr></thead><tbody>'+
      rows.map(row=>`<tr><td>${escape(row.month)}</td><td>${count(row.canvassed)}</td><td>${count(row.interested)}</td><td>${count(row.installation_events)}</td></tr>`).join('')+'</tbody></table></div></details>';
  }
  function comparison(rows){
    const max=Math.max(1,...rows.map(row=>row.installed));
    return '<div class="public-bars">'+[...rows].sort((a,b)=>b.installed-a.installed).map(row=>`<div><span>${escape(row.name)}</span><strong>${count(row.installed)}</strong><div class="public-bar"><i style="width:${100*row.installed/max}%"></i></div></div>`).join('')+'</div>';
  }
  function table(){
    const selected=snapshot.regions.filter(row=>row.name.toLocaleLowerCase('id').includes(query.toLocaleLowerCase('id'))).sort((a,b)=>(sort==='name'?a.name.localeCompare(b.name,'id'):a[sort]-b[sort])*(descending?-1:1));
    return '<div class="tw"><table class="report-table"><thead><tr>'+['name',...metrics].map((key,i)=>`<th scope="col" aria-sort="${sort===key?(descending?'descending':'ascending'):'none'}"><button data-public-sort="${key}">${i?labels[i-1]:'Regional'} ${sort===key?(descending?'↓':'↑'):'↕'}</button></th>`).join('')+'</tr></thead><tbody>'+
      (selected.length?selected.map(row=>'<tr><td class="text">'+escape(row.name)+'</td>'+metrics.map(key=>`<td>${count(row[key])}</td>`).join('')+'</tr>').join(''):'<tr><td colspan="6" class="text">Regional tidak ditemukan.</td></tr>')+'</tbody></table></div>';
  }
  async function load(){
    content.setAttribute('aria-busy','true');
    try{
      const response=await fetch(new URL('pages/public-summary.json',root),{credentials:'omit',cache:'no-cache'});
      if(!response.ok)throw new Error('Unavailable');
      const data=await response.json();if(!approved(data))throw new Error('Unapproved public format');snapshot=data;
      performance.mark('rpd:public-data');
      content.innerHTML='<div class="intel-kpis public-kpis">'+metrics.map((key,i)=>`<article class="intel-card"><span class="metric-label">${labels[i]}</span><strong class="metric-value">${count(data.metrics[key])}</strong></article>`).join('')+'</div>'+ 
        '<p class="scope-caption">Potensi dan sisa: stok master seluruh periode. Kinerja: pelanggan unik pada sumber survei.</p>'+ 
        '<div class="overview-charts" id="public-charts"><section class="panel"><h2>Tren Kinerja</h2>'+trend(data.trends)+'</section><section class="panel"><h2>Terpasang per Regional</h2>'+comparison(data.regions)+'</section></div>'+ 
        '<section class="panel public-regions"><div class="section-heading"><h2>Kinerja Regional</h2><input id="public-region-search" type="search" placeholder="Cari regional" aria-label="Cari regional"></div><div id="public-region-table">'+table()+'</div></section>';
      const formatDate=value=>new Intl.DateTimeFormat('id-ID',{dateStyle:'medium',timeZone:'UTC'}).format(new Date(value+'T00:00:00Z'));
      document.getElementById('public-updated').textContent=(data.reporting_date?'Laporan '+formatDate(data.reporting_date)+' · ':'')+(data.survey_through?'Survei s.d. '+formatDate(data.survey_through):'');
      requestAnimationFrame(()=>performance.mark('rpd:public-usable'));
    }catch{
      snapshot=null;document.getElementById('public-updated').textContent='';
      content.innerHTML='<section class="panel empty-state" id="public-charts"><h2>Ringkasan belum tersedia</h2><p>Data publik belum tersedia. Silakan coba kembali nanti.</p><button id="public-retry" type="button">Coba kembali</button></section>';
    }finally{content.setAttribute('aria-busy','false')}
  }
  function show(){landing.hidden=false;document.getElementById('lg').hidden=true;document.getElementById('app').hidden=true;document.body.classList.add('public-mode')}
  function hide(){landing.hidden=true;document.body.classList.remove('public-mode')}
  async function internal(){
    for(const attribute of ['browser','app','potential','center']){
      if(loaded.has(attribute))continue;
      await new Promise((resolve,reject)=>{const script=document.createElement('script');script.src=new URL(loader.dataset[attribute],root);script.async=false;script.onload=()=>{loaded.add(attribute);resolve()};script.onerror=()=>{script.remove();reject(new Error('Formulir masuk belum dapat dimuat. Coba kembali.'))};document.head.appendChild(script)});
    }
    internalReady=true;
  }
  document.getElementById('login-form').addEventListener('submit',event=>{if(!internalReady)event.preventDefault()});
  document.getElementById('public-login').onclick=async()=>{
    hide();document.getElementById('lg').hidden=false;const button=document.getElementById('lb');button.disabled=true;document.getElementById('le').textContent=internalReady?'':'Menyiapkan formulir masuk…';
    try{if(!loading)loading=internal().catch(error=>{loading=null;throw error});await loading;document.getElementById('le').textContent='';button.disabled=false;document.getElementById('li').focus()}
    catch(error){document.getElementById('le').textContent=error.message;button.disabled=true;document.getElementById('public-back').disabled=false}
  };
  document.getElementById('public-back').onclick=()=>{if(document.getElementById('login-form').getAttribute('aria-busy')==='true')return;document.getElementById('lp').value='';document.getElementById('le').textContent='';show();document.getElementById('public-login').focus()};
  content.addEventListener('click',event=>{const button=event.target.closest('button');if(button?.id==='public-retry'){load();return}const key=button?.dataset.publicSort;if(!snapshot||!['name',...metrics].includes(key))return;descending=sort===key?!descending:false;sort=key;document.getElementById('public-region-table').innerHTML=table()});
  content.addEventListener('input',event=>{if(event.target.id!=='public-region-search'||!snapshot)return;query=event.target.value;document.getElementById('public-region-table').innerHTML=table()});
  window.RPDPublic=Object.freeze({show,hide});show();load();
})();
