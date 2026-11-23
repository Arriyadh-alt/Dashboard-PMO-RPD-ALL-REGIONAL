/* Self-hosted Python/WASM worker: the reviewed analytics, not a second implementation. */
import {loadPyodide} from './vendor/pyodide/pyodide.mjs';
let python=null,reportReady=false,chain=Promise.resolve();
const base=new URL('.',self.location.href),version=new URL(self.location.href).searchParams.get('engine')||'';
const progress=()=>self.postMessage({progress:'Menyiapkan laporan di perangkat ini…'});

async function runtime(){
  if(python)return python;
  progress();
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
            api=BrowserAPI(json.loads(request['source']),request['role'],request['actor'],request['info'],request['events'])
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
    await runtime();
    if(message.type==='init')message.source=new TextDecoder().decode(message.source);
    if(message.path&&/\/api\/reports\/[^?]+\.xlsx(\?|$)/.test(message.path))await reports();
    python.globals.set('_request_json',JSON.stringify(message));
    const response=JSON.parse(python.runPython('handle(_request_json)'));
    python.runPython('del _request_json');
    self.postMessage({id:message.id,...response});
  }catch(error){self.postMessage({id:message.id,ok:false,error:'Laporan lokal tidak dapat disiapkan. '+error.message})}
}
self.onmessage=event=>{chain=chain.then(()=>process(event.data)).catch(()=>{})};
