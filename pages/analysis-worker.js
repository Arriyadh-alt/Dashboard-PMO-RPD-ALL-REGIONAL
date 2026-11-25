/* Self-hosted Python/WASM worker: the reviewed analytics, not a second implementation. */
const summaryReady=import('./summary.js?v='+encodeURIComponent(new URL(self.location.href).searchParams.get('summary')||''));
let python=null,reportReady=false,chain=Promise.resolve(),initial=null,sourceObject=null,summary=null,bootstrapCache=null,pythonReady=false;
const analysisCache=new Map();
const base=new URL('.',self.location.href),version=new URL(self.location.href).searchParams.get('engine')||'';
const progress=()=>self.postMessage({progress:'Menyiapkan laporan di perangkat ini…'});

async function runtime(){
  if(python)return python;
  progress();
  const {loadPyodide}=await import('./vendor/pyodide/pyodide.mjs');
  python=await loadPyodide({indexURL:new URL('vendor/pyodide/',base).href});
  const response=await fetch(new URL('engine.zip?v='+encodeURIComponent(version),base));
  if(!response.ok)throw new Error('Mesin analitik lokal tidak tersedia. Muat ulang halaman.');
  const archive=new Uint8Array(await response.arrayBuffer()),digest=Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256',archive)),byte=>byte.toString(16).padStart(2,'0')).join('');
  if(digest!==version)throw new Error('Versi laporan berubah. Muat ulang halaman untuk melanjutkan.');
  python.unpackArchive(archive,'zip',{extractDir:'/rpd'});
  python.runPython(`import sys,json,copy\nsys.path.insert(0,'/rpd')\nfrom backend.browser_api import BrowserAPI,LocalEvents\napi=None
def handle(text):
    global api
    request=json.loads(text)
    previous=None
    try:
        if request['type']=='init':
            api=BrowserAPI(json.loads(request['source']),request['role'],request['actor'],request['info'],request['events'],operational_guest=request['info'].get('operational_access',False))
            result=api.bootstrap()
        elif request['type']=='restore':
            api.store=LocalEvents(request['events'])
            result={'ok':True}
        else:
            if api is None: raise ValueError('Silakan masuk kembali.')
            previous=copy.deepcopy(api.store.events) if request.get('mutation') else None
            result=api.request(request['path'],request.get('method','GET'),request.get('body'))
        return json.dumps({'ok':True,'result':result,'events':api.store.events if request.get('mutation') else None},ensure_ascii=False,allow_nan=False)
    except Exception as error:
        if previous is not None: api.store=LocalEvents(previous)
        return json.dumps({'ok':False,'error':str(error)},ensure_ascii=False)
`);
  return python;
}

async function reports(){
  if(reportReady)return;
  progress();
  await python.loadPackage(['micropip']);
  const manifest=await (await fetch(new URL('vendor/manifest.json',base))).json();
  python.globals.set('_report_wheels',JSON.stringify(manifest.wheels.map(name=>new URL('vendor/wheels/'+name,base).href)));
  // Only the pinned pure-Python text/spreadsheet dependencies. No image decoding.
  await python.runPythonAsync('import micropip\nawait micropip.install(json.loads(_report_wheels),deps=False)\ndel _report_wheels');
  reportReady=true;
}

async function process(message){
  try{
    await summaryReady;
    if(message.type==='init'){
      initial={...message,source:new TextDecoder().decode(message.source)};
      const parsed=JSON.parse(initial.source);
      if(!['owner','guest'].includes(message.role))throw new Error('Invalid dataset role');
      if(parsed.aggregate_version===1){summary=parsed;sourceObject=null}
      else {if(message.role!=='owner')throw new Error('Guest dataset is not separated');sourceObject=parsed;summary=await RPDSummary.project(parsed)}
      if(summary){bootstrapCache=RPDSummary.bootstrap(summary,sourceObject,initial.role,initial.info,initial.events);self.postMessage({id:message.id,ok:true,result:bootstrapCache});return}
    }
    if(!initial)throw new Error('Silakan masuk kembali.');
    const operational=initial.role==='owner'||initial.info.operational_access;
    if(message.type==='detail'){
      if(!operational)throw new Error('Akses tidak diizinkan.');
      const source=new TextDecoder().decode(message.source),parsed=JSON.parse(source);
      if(!parsed.rec||parsed.aggregate_version||(initial.role==='guest'&&parsed._guest_access))throw new Error('Invalid operational source');
      initial.source=source;sourceObject=parsed;bootstrapCache=RPDSummary.bootstrap(summary,sourceObject,initial.role,initial.info,initial.events);
      self.postMessage({id:message.id,ok:true,result:bootstrapCache});return;
    }
    const url=message.path?new URL(message.path,'https://local.invalid'):null;
    if(message.type==='request'&&url.pathname==='/api/bootstrap'&&bootstrapCache){self.postMessage({id:message.id,ok:true,result:bootstrapCache});return}
    if(message.type==='request'&&url.pathname==='/api/analysis'&&summary&&(message.method||'GET')==='GET'){
      const scope=Object.fromEntries(url.searchParams);scope.statuses=url.searchParams.getAll('status');
      const fast=['ringkasan','kelurahan','data','catatan'].includes(scope.view)||!operational;
      if(fast&&!scope.coordinator&&!scope.statuses.length&&!(+scope.rw>=0)&&!(+scope.rt>=0)){const result=RPDSummary.analyse(summary,scope,initial.events);self.postMessage({id:message.id,ok:true,result});return}
    }
    if(!operational||(initial.role!=='owner'&&(message.mutation||message.type==='restore'||url?.pathname.startsWith('/api/admin/')||url?.pathname==='/api/quality')))throw new Error('Akses tidak diizinkan.');
    if(!sourceObject)throw new Error('Muat data operasional terlebih dahulu.');
    let analysisKey=null;
    if(url?.pathname==='/api/analysis'&&(message.method||'GET')==='GET'){
      const filters=new URLSearchParams(url.searchParams);filters.delete('view');filters.sort();analysisKey=filters.toString();
      if(analysisCache.has(analysisKey)){self.postMessage({id:message.id,ok:true,result:analysisCache.get(analysisKey)});return}
    }
    if(message.type==='restore'&&!pythonReady){initial.events=message.events;bootstrapCache=RPDSummary.bootstrap(summary,sourceObject,initial.role,initial.info,initial.events);self.postMessage({id:message.id,ok:true,result:{ok:true}});return}
    await runtime();
    if(!pythonReady){
      python.globals.set('_request_json',JSON.stringify(initial));
      const loaded=JSON.parse(python.runPython('handle(_request_json)'));
      python.runPython('del _request_json');if(!loaded.ok)throw new Error('Laporan rinci tidak tersedia');
      pythonReady=true;bootstrapCache=loaded.result;
      if(message.type==='init'){self.postMessage({id:message.id,...loaded});return}
    }
    if(message.path&&/\/api\/reports\/[^?]+\.xlsx(\?|$)/.test(message.path))await reports();
    python.globals.set('_request_json',JSON.stringify(message));
    const response=JSON.parse(python.runPython('handle(_request_json)'));
    python.runPython('del _request_json');
    if(response.ok&&analysisKey!==null){if(analysisCache.size>=2)analysisCache.delete(analysisCache.keys().next().value);analysisCache.set(analysisKey,response.result)}
    if(response.ok&&(message.mutation||message.type==='restore'))analysisCache.clear();
    if(response.ok&&message.type==='restore')initial.events=message.events;
    if(response.ok&&message.mutation){initial.events=response.events;bootstrapCache=summary?RPDSummary.bootstrap(summary,sourceObject,initial.role,initial.info,initial.events):null}
    self.postMessage({id:message.id,...response});
  }catch(error){self.postMessage({id:message.id,ok:false,error:initial?.role==='guest'?'Akses tidak diizinkan.':'Laporan belum dapat dimuat. Coba lagi.'})}
}
self.onmessage=event=>{chain=chain.then(()=>process(event.data)).catch(()=>{})};
