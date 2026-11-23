"""Pin self-hosted Pyodide and report dependencies; no customer data leaves the browser."""
import hashlib
import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from urllib.request import urlopen

ROOT=Path(__file__).resolve().parent.parent/'pages'/'vendor'
VERSION='314.0.8'
BASE=f'https://cdn.jsdelivr.net/pyodide/v{VERSION}/full/'


def read(url):
    with urlopen(url,timeout=90) as response:
        return response.read()


def main():
    runtime=ROOT/'pyodide'
    runtime.mkdir(parents=True,exist_ok=True)
    wheels=ROOT/'wheels'
    wheels.mkdir(exist_ok=True)
    lock=json.loads(read(BASE+'pyodide-lock.json'))
    manifest={'version':VERSION,'files':{},'wheels':[],'javascript':[]}
    jobs=[(BASE+name,runtime/name,None) for name in ['pyodide.mjs','pyodide.asm.mjs','pyodide.asm.wasm','python_stdlib.zip','pyodide-lock.json']]
    # Reports are text tables only: never ship a raster-image decoder to the browser.
    for name in ['micropip']:
        item=lock['packages'][name]
        jobs.append((BASE+item['file_name'],runtime/item['file_name'],item['sha256']))
    for name,version in [('openpyxl','3.1.5'),('et_xmlfile','2.0.0')]:
        metadata=json.loads(read(f'https://pypi.org/pypi/{name}/{version}/json'))
        wheel=next(item for item in metadata['urls'] if item['filename'].endswith('none-any.whl'))
        jobs.append((wheel['url'],wheels/wheel['filename'],wheel['digests']['sha256']))
        manifest['wheels'].append(wheel['filename'])
    def download(job):
        url,path,expected=job
        data=read(url)
        actual=hashlib.sha256(data).hexdigest()
        if expected and actual!=expected:
            raise ValueError('Dependency checksum mismatch: '+path.name)
        path.write_bytes(data)
        return str(path.relative_to(ROOT)),{'url':url,'sha256':actual,'bytes':len(data)}
    with ThreadPoolExecutor(max_workers=6) as pool:
        manifest['files']=dict(pool.map(download,jobs))
    for name,file,version in [('jspdf','jspdf.umd.min.js','4.2.1'),('jspdf-autotable','jspdf.plugin.autotable.min.js','5.0.9')]:
        source=ROOT.parent.parent/'node_modules'/name
        data=(source/'dist'/file).read_bytes()
        relative=name+'-'+version+'.min.js'
        (ROOT/relative).write_bytes(data)
        license_path=next(path for path in [source/'LICENSE',source/'LICENSE.txt',source/'LICENSE.md'] if path.is_file())
        (ROOT/('LICENSE-'+name+'.txt')).write_bytes(license_path.read_bytes())
        manifest['files'][relative]={'url':f'https://www.npmjs.com/package/{name}/v/{version}','sha256':hashlib.sha256(data).hexdigest(),'bytes':len(data)}
        manifest['javascript'].append({'path':relative,'version':version})
    (ROOT/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    print('Vendored verified browser dependencies:',len(jobs),'files,',sum(row['bytes'] for row in manifest['files'].values()),'bytes')


if __name__=='__main__':
    main()
