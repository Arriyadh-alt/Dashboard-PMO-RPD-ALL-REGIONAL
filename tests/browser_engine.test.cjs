/* Actual vendored WASM smoke: no web server, DOM mocks or production credentials. */
const fs=require('node:fs'),path=require('node:path'),vm=require('node:vm'),assert=require('node:assert/strict'),{execFileSync}=require('node:child_process');
(async()=>{
 const {loadPyodide}=await import('../pages/vendor/pyodide/pyodide.mjs');
 const py=await loadPyodide({indexURL:path.resolve('pages/vendor/pyodide')+'/'});
 py.unpackArchive(new Uint8Array(fs.readFileSync('pages/engine.zip')),'zip',{extractDir:'/rpd'});
 const python=fs.existsSync('.venv/bin/python')?'.venv/bin/python':'python';
 const fixture=execFileSync(python,['-c','import json;from tests.fixtures import fixture_data;print(json.dumps(fixture_data()))'],{encoding:'utf8'});
 py.globals.set('_fixture',fixture);
 const metrics=JSON.parse(py.runPython(`import sys,json\nsys.path.insert(0,'/rpd')\nfrom backend.browser_api import BrowserAPI\napi=BrowserAPI(json.loads(_fixture),'owner','synthetic',{'fingerprint':'synthetic','loaded_at':'2026-11-23T00:00:00Z'})\njson.dumps(api.request('/api/analysis')['metrics'])`));
 assert.equal(metrics.canvassed,9);assert.equal(metrics.interested,6);assert.equal(metrics.installed,3);
 const filtered=JSON.parse(py.runPython(`json.dumps(api.request('/api/analysis?reg=Barat')['metrics'])`));
 assert.equal(filtered.canvassed,6);assert.equal(filtered.interested,4);assert.equal(filtered.installed,2);
 await py.loadPackage(['micropip']);
 py.FS.mkdir('/wheels');
 const wheels=JSON.parse(fs.readFileSync('pages/vendor/manifest.json')).wheels;
 for(const name of wheels)py.FS.writeFile('/wheels/'+name,new Uint8Array(fs.readFileSync('pages/vendor/wheels/'+name)));
 py.globals.set('_wheels',JSON.stringify(wheels.map(name=>'emfs:/wheels/'+name)));
 await py.runPythonAsync(`import micropip\nawait micropip.install(json.loads(_wheels),deps=False)`);
 for(const extension of ['csv','xlsx']){
  py.globals.set('_extension',extension);
  const result=JSON.parse(py.runPython(`json.dumps(api.request('/api/reports/executive.'+_extension))`));
  const content=Buffer.from(result.binary,'base64');assert.ok(content.length>100);
  if(extension==='xlsx')assert.equal(content.subarray(0,2).toString(),'PK');
 }
 const model=JSON.parse(py.runPython("json.dumps(api.request('/api/reports/executive.pdf')['pdf_model'])"));
 // Exercise the UMD GLOBAL exports used by Pages, not the different CommonJS exports.
 const browser={console,atob,btoa,TextEncoder,TextDecoder,Blob,URL};browser.self=browser;vm.createContext(browser);
 for(const file of ['jspdf-4.2.1.min.js','jspdf-autotable-5.0.9.min.js'])vm.runInContext(fs.readFileSync('pages/vendor/'+file,'utf8'),browser);
 browser.window=browser;vm.runInContext(fs.readFileSync('pages/pdf.js','utf8'),browser);
 assert.equal(typeof browser.autoTable,'function');
 assert.equal(Buffer.from(browser.RPDPDF.renderPDF(model,browser.jspdf.jsPDF,browser.autoTable)).subarray(0,4).toString(),'%PDF');
 const unicode={metadata:['Synthetic Unicode report'],headers:['Action'],rows:[['Survey → pemasangan 😀 END']]};
 const pdf=Buffer.from(browser.RPDPDF.renderPDF(unicode,browser.jspdf.jsPDF,browser.autoTable)).toString('latin1');
 const streams=Array.from(pdf.matchAll(/stream\r?\n([\s\S]*?)\r?\nendstream/g),match=>{try{return require('node:zlib').inflateSync(Buffer.from(match[1],'latin1')).toString('latin1')}catch{return match[1]}}).join('\n');
 assert.ok(streams.includes('Survey \\\\u{2192} pemasangan \\\\u{1F600} END'));
 assert.ok(streams.includes('CSV/XLSX'));
 assert.equal(unicode.rows[0][0],'Survey → pemasangan 😀 END');
 assert.equal(py.runPython("'PIL' not in sys.modules"),true);
 console.log('Real local WASM: unique9/6/3; Barat6/4/2; CSV/XLSX/PDF passed without Python image packages.');
})().catch(error=>{console.error(error.message);process.exitCode=1});
