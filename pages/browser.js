/* GitHub Pages mode. Encryption is not server authorization; all work stays local. */
(() => {
  'use strict';
  const root=new URL('../',document.currentScript.src),encoder=new TextEncoder();
  let worker=null,nextId=0,pending=new Map(),queue=Promise.resolve(),key=null,storageKey='',cachedRaw=null,events=[],actor='',manifest=null,generation=0,legacyRaw=null,legacyValid=false;
  const b64=bytes=>{let value='';for(let i=0;i<bytes.length;i+=32768)value+=String.fromCharCode(...bytes.subarray(i,i+32768));return btoa(value)};
  const bytes=value=>Uint8Array.from(atob(value),character=>character.charCodeAt(0));
  const hash=async value=>Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256',value)),byte=>byte.toString(16).padStart(2,'0')).join('');
  async function derive(value,salt){const material=await crypto.subtle.importKey('raw',encoder.encode(value),'PBKDF2',false,['deriveKey']);return crypto.subtle.deriveKey({name:'PBKDF2',salt,iterations:500000,hash:'SHA-256'},material,{name:'AES-GCM',length:256},false,['encrypt','decrypt'])}
  const decrypt=async (key,iv,cipher)=>crypto.subtle.decrypt({name:'AES-GCM',iv:bytes(iv)},key,bytes(cipher));
  async function encrypt(value){const iv=crypto.getRandomValues(new Uint8Array(12)),data=encoder.encode(JSON.stringify(value));if(data.length>3000000)throw new Error('Riwayat lokal terlalu besar. Unduh cadangan sebelum melanjutkan.');return JSON.stringify({v:1,account:actor,salt:manifest.ledger_salt,i:b64(iv),c:b64(new Uint8Array(await crypto.subtle.encrypt({name:'AES-GCM',iv},key,data)))})}
  async function openState(raw){const envelope=JSON.parse(raw);if(envelope.v!==1||envelope.account!==actor||envelope.salt!==manifest.ledger_salt)throw new Error('Cadangan bukan untuk akun/dashboard ini.');const value=JSON.parse(new TextDecoder().decode(await decrypt(key,envelope.i,envelope.c)));if(!Array.isArray(value))throw new Error('Format riwayat tidak valid.');return value}
  function stop(){generation++;if(worker)worker.terminate();worker=null;for(const request of pending.values())request.reject(new Error('Sesi lokal ditutup.'));pending.clear();key=null;events=[];actor='';storageKey='';cachedRaw=null;manifest=null;const controls=document.getElementById('local-history-controls');if(controls)controls.hidden=true}
  function call(message,transfer=[]){return new Promise((resolve,reject)=>{if(!worker)return reject(new Error('Silakan masuk kembali.'));const id=++nextId;pending.set(id,{resolve,reject});worker.postMessage({id,...message},transfer)})}
  async function jsonFile(path){const response=await fetch(new URL(path,root),{cache:'no-store',credentials:'omit'});if(!response.ok)throw new Error('Berkas dashboard tidak tersedia.');return response.json()}
  async function login(body){
    stop();const epoch=generation;
    try{
      const account=String(body.account||'').replace(/\s/g,'').toLowerCase(),password=String(body.password||'').trim();
      if(!account||!password)throw new Error('Masukkan ID dan kata sandi.');
      manifest=await jsonFile('pages/data-manifest.json');
      const response=await fetch(new URL('pages/data.enc.json?v='+encodeURIComponent(manifest.fingerprint),root),{cache:'no-store',credentials:'omit'});
      if(!response.ok)throw new Error('Sumber terenkripsi tidak tersedia.');
      const encoded=await response.arrayBuffer();
      if(await hash(encoded)!==manifest.fingerprint)throw new Error('Versi data sedang diperbarui. Muat ulang halaman.');
      const envelope=JSON.parse(new TextDecoder().decode(encoded));
      actor=(await hash(encoder.encode(account))).slice(0,16);
      const wrapped=envelope.u[actor];if(!wrapped)throw new Error('ID atau kata sandi tidak valid.');
      const wrappingKey=await derive(account+'\n'+password,bytes(wrapped.s));
      let dataKey;
      try{dataKey=await crypto.subtle.importKey('raw',await decrypt(wrappingKey,wrapped.i,wrapped.k),{name:'AES-GCM'},false,['decrypt'])}catch{throw new Error('ID atau kata sandi tidak valid.')}
      const packed=await decrypt(dataKey,envelope.i,envelope.c);
      const source=await new Response(new Blob([packed]).stream().pipeThrough(new DecompressionStream('gzip'))).arrayBuffer();
      key=await derive('rpd-local-events:v1\n'+account+'\n'+password,bytes(manifest.ledger_salt));
      storageKey='rpd_local_v1_'+manifest.ledger_salt.slice(0,12)+'_'+actor;
      try{cachedRaw=localStorage.getItem(storageKey)}catch{cachedRaw=null}
      if(cachedRaw){try{events=await openState(cachedRaw)}catch{throw new Error('Riwayat lokal tidak dapat dibuka dengan kata sandi ini. Jangan hapus penyimpanan; unduh cadangan/masuk dengan kredensial sebelumnya.')}}
      if(epoch!==generation)throw new Error('Sesi diganti. Silakan masuk kembali.');
      worker=new Worker(new URL('pages/analysis-worker.js?v='+encodeURIComponent(manifest.worker)+'&engine='+encodeURIComponent(manifest.engine),root),{type:'module'});
      worker.onmessage=event=>{const message=event.data;if(message.progress){const label=document.getElementById('le');if(label&&!document.getElementById('lg').hidden)label.textContent=message.progress;return}const request=pending.get(message.id);if(!request)return;pending.delete(message.id);message.ok?request.resolve(message):request.reject(new Error(message.error||'Operasi lokal gagal.'))};
      worker.onerror=()=>{for(const request of pending.values())request.reject(new Error('Mesin laporan lokal gagal dimuat. Gunakan peramban terbaru dan muat ulang.'));pending.clear()};
      const result=await call({type:'init',source,role:wrapped.r==='a'?'owner':'guest',actor,events,info:{fingerprint:manifest.fingerprint,loaded_at:new Date().toISOString(),imported_at:null,published_at:manifest.published_at,owner:manifest.owner||'',snapshot_count:1,storage_mode:'Encrypted browser-local history; not shared or tamper-proof'}},[source]);
      return result.result;
    }catch(error){stop();throw error}
  }
  async function locked(task){if(!navigator.locks)throw new Error('Penyuntingan lokal memerlukan peramban dengan Web Locks. Gunakan Chrome/Edge terbaru; laporan tetap dapat dibaca.');return navigator.locks.request(storageKey,async()=>{if(localStorage.getItem(storageKey)!==cachedRaw)throw new Error('Riwayat berubah di tab lain. Keluar dan masuk kembali sebelum menyunting.');return task()})}
  async function persist(next){const epoch=generation,targetKey=storageKey,raw=await encrypt(next);if(epoch!==generation||targetKey!==storageKey)throw new Error('Sesi lokal ditutup sebelum penyimpanan.');try{localStorage.setItem(targetKey,raw)}catch{throw new Error('Riwayat belum disimpan: penyimpanan peramban penuh/tidak tersedia. Unduh cadangan dan jangan tutup halaman.')}cachedRaw=raw;events=next}
  async function request(path,options={}){
    if(path==='/api/logout'){stop();return {ok:true}}
    const run=async()=>{
      if(path==='/health')return {configured:true,service:'browser-only'};
      if(path==='/api/login')return login(JSON.parse(options.body));
      if(path==='/api/logout'){stop();return {ok:true}}
      const method=(options.method||'GET').toUpperCase(),mutation=(method==='POST'&&path.startsWith('/api/followups/'))||(method!=='GET'&&path.startsWith('/api/admin/'));
      const execute=async()=>{const response=await call({type:'request',path,method,body:options.body?JSON.parse(options.body):null,mutation});if(mutation){try{await persist(response.events)}catch(error){await call({type:'restore',events});throw error}}return response.result};
      return mutation?locked(execute):execute();
    };
    const result=queue.then(run);queue=result.catch(()=>{});return result;
  }
  function saveBlob(blob,name){const link=document.createElement('a'),url=URL.createObjectURL(blob);link.href=url;link.download=name;document.body.appendChild(link);link.click();link.remove();setTimeout(()=>URL.revokeObjectURL(url),10000)}
  let pdfReady=null;
  function script(path){return new Promise((resolve,reject)=>{const element=document.createElement('script');element.src=new URL(path,root);element.onload=resolve;element.onerror=()=>{element.remove();reject(new Error('PDF lokal tidak dapat dimuat. Coba kembali.'))};document.head.appendChild(element)})}
  async function pdfLibraries(){if(!pdfReady)pdfReady=(async()=>{const assets=await jsonFile('pages/vendor/manifest.json');for(const item of assets.javascript)await script('pages/vendor/'+item.path);await script('pages/pdf.js?v='+manifest.pdf)})().catch(error=>{pdfReady=null;throw error});return pdfReady}
  async function download(path,name){const report=await request(path);if(report.pdf_model){await pdfLibraries();saveBlob(new Blob([window.RPDPDF.renderPDF(report.pdf_model,window.jspdf.jsPDF,window.autoTable)],{type:'application/pdf'}),name)}else saveBlob(new Blob([bytes(report.binary)],{type:report.media_type}),name)}
  function ready(role,boot){
    const controls=document.getElementById('local-history-controls');if(controls)controls.hidden=role!=='owner';
    const legacy=document.getElementById('legacy-mapping-controls');if(!legacy)return;legacy.hidden=true;legacyRaw=null;legacyValid=false;
    if(role!=='owner')return;
    try{legacyRaw=localStorage.getItem('rpd_ov');if(!legacyRaw)return;
      const values=JSON.parse(legacyRaw);legacyValid=values!==null&&typeof values==='object'&&!Array.isArray(values);
      if(legacyValid&&!Object.keys(values).length)return;
      legacy.hidden=false;legacy.open=true;
      const preview=document.getElementById('legacy-mapping-preview');preview.replaceChildren();
      if(legacyValid)for(const [index,value]of Object.entries(values)){
        const name=/^(0|[1-9]\d*)$/.test(index)?boot.data.svs[Number(index)]:null;
        if(!name)legacyValid=false;
        const row=document.createElement('p');row.textContent='Indeks '+index+' · '+(name||'Tidak ada pada sumber aktif')+' · '+JSON.stringify(value);preview.appendChild(row);
      }
      document.getElementById('confirm-legacy-mapping').checked=false;
      document.getElementById('import-legacy-mapping').disabled=true;
      document.getElementById('legacy-mapping-status').textContent=legacyValid?'Belum diimpor. Verifikasi nomor urut dengan sumber lama; jangan menebak identitas.':'Pemetaan tidak cocok dengan sumber aktif. Salinan lama dipertahankan; unduh untuk rekonsiliasi manual.';
    }catch{legacy.hidden=false;document.getElementById('legacy-mapping-status').textContent='Salinan lama tidak dapat dibaca; tetap dipertahankan dan dapat diunduh.'}
  }
  document.addEventListener('change',event=>{if(event.target.id==='confirm-legacy-mapping')document.getElementById('import-legacy-mapping').disabled=!event.target.checked||!legacyValid});
  document.addEventListener('click',async event=>{
    if(event.target.id==='backup-legacy-mapping'&&legacyRaw!==null)saveBlob(new Blob([legacyRaw],{type:'application/json'}),'RPD-legacy-mapping-local.json');
    if(event.target.id!=='import-legacy-mapping')return;
    const status=document.getElementById('legacy-mapping-status');event.target.disabled=true;
    try{
      if(!legacyValid||!document.getElementById('confirm-legacy-mapping').checked)throw new Error('Verifikasi identitas terlebih dahulu.');
      if(localStorage.getItem('rpd_ov')!==legacyRaw)throw new Error('Salinan lama berubah di tab lain. Muat ulang sebelum mengimpor.');
      const current=await request('/api/bootstrap'),values=JSON.parse(legacyRaw);
      for(const [index,value]of Object.entries(current.overrides))values[index]={...values[index],...value};
      await request('/api/admin/mappings',{method:'PUT',body:JSON.stringify({version:current.mapping_version,values})});
      if(localStorage.getItem('rpd_ov')===legacyRaw)localStorage.removeItem('rpd_ov');
      location.reload();
    }catch(error){status.textContent=error.message;event.target.disabled=false}
  });
  document.addEventListener('click',async event=>{const button=event.target.closest('#backup-local');if(!button)return;try{if(!key)throw new Error('Masuk terlebih dahulu.');saveBlob(new Blob([await encrypt(events)],{type:'application/json'}),'RPD-encrypted-local-history.json')}catch(error){document.getElementById('service-status').textContent=error.message}});
  document.addEventListener('change',async event=>{if(event.target.id!=='restore-local'||!event.target.files.length)return;try{const file=event.target.files[0];if(file.size>4500000)throw new Error('Berkas cadangan terlalu besar.');const next=await openState(await file.text());await locked(async()=>{if(events.length)throw new Error('Pemulihan hanya pada riwayat lokal kosong; riwayat yang ada tidak ditimpa.');await call({type:'restore',events:next});try{await persist(next)}catch(error){await call({type:'restore',events});throw error}});location.reload()}catch(error){document.getElementById('service-status').textContent=error.message}finally{event.target.value=''}});
  window.RPDStatic=Object.freeze({request,download,ready,stop});
})();
