"""Dependency-free checks of the intentionally small public surface."""

from html.parser import HTMLParser
import hashlib
from pathlib import Path

REPO=Path(__file__).resolve().parent.parent
ROOT=REPO/'web'
import json
import sys
from urllib.parse import urlsplit
sys.path.insert(0,str(REPO))
from scripts.build_pages import validate
from scripts.build_pages import MODULES
import zipfile


class Page(HTMLParser):
    def __init__(self):
        super().__init__()
        self.identifiers=set()
        self.scripts=[]

    def handle_starttag(self,tag,attributes):
        values=dict(attributes)
        if 'id' in values:
            assert values['id'] not in self.identifiers, f"Duplicate id: {values['id']}"
            self.identifiers.add(values['id'])
        if tag=='script':
            assert values.get('src'), 'Inline script or embedded data is forbidden'
            self.scripts.append(values['src'])
        if tag=='link' and values.get('rel')=='stylesheet' and not values.get('href','').startswith('https://'):
            assert (ROOT/urlsplit(values['href']).path).is_file(), 'Missing stylesheet'


page=Page()
html=(ROOT/'index.html').read_text()
assert 'id=enc' not in html and 'application/json' not in html, 'Protected payload must stay off the public surface'
page.feed(html)
assert len(page.scripts)==2 and all((ROOT/path).is_file() for path in page.scripts)
assert len([identifier for identifier in page.identifiers if identifier.startswith('tab-')])==6
assert not list(REPO.glob('*.enc.json')), 'Private input must be outside this repository'
manifest=json.loads((REPO/'pages/data-manifest.json').read_text())
encrypted=(REPO/'pages/data.enc.json').read_bytes()
validate(json.loads(encrypted))
assert hashlib.sha256(encrypted).hexdigest()==manifest['fingerprint'], 'Published encrypted source and manifest differ'
assert hashlib.sha256((REPO/'pages/engine.zip').read_bytes()).hexdigest()==manifest['engine'], 'Browser engine must be rebuilt after Python changes'
with zipfile.ZipFile(REPO/'pages/engine.zip') as engine:
    for name in MODULES:
        assert engine.read('backend/'+name)==(REPO/'backend'/name).read_bytes(), 'Stale browser Python module: '+name
for key,path in [('worker','pages/analysis-worker.js'),('pdf','pages/pdf.js'),('summary','pages/summary.js')]:
    assert hashlib.sha256((REPO/path).read_bytes()).hexdigest()==manifest[key], 'Stale browser asset manifest: '+path
for path in ['pages/browser.js','web/app.js','web/command-center.js','web/styles.css','web/command-center.css']:
    assert path+'?v='+hashlib.sha256((REPO/path).read_bytes()).hexdigest()[:16] in (REPO/'index.html').read_text(), 'Rebuild the Pages shell for '+path
public=Page()
public.feed((REPO/'index.html').read_text().replace('web/styles.css','styles.css').replace('web/command-center.css','command-center.css'))
assert len(public.scripts)==3 and len([key for key in public.identifiers if key.startswith('tab-')])==6
assert 'local-admin-tools' in (REPO/'index.html').read_text()
assert manifest.get('accounts') and manifest.get('guest_fingerprint'), 'Production requires separate Admin/Guest encrypted capabilities'
assert all(w['r']=='a' for w in json.loads(encrypted)['u'].values()), 'Guest must not unwrap the customer-data key'
guest=(REPO/'pages/guest.enc.json').read_bytes()
validate(json.loads(guest))
assert all(w['r']=='g' for w in json.loads(guest)['u'].values())
assert hashlib.sha256(guest).hexdigest()==manifest['guest_fingerprint']
assert manifest['accounts']=={**json.loads(encrypted)['u'],**json.loads(guest)['u']}
assert manifest['snapshot_pair']==json.loads(encrypted)['p']==json.loads(guest)['p'], 'Guest and Admin must describe the same snapshot'
for relative,info in json.loads((REPO/'pages/vendor/manifest.json').read_text())['files'].items():
    assert hashlib.sha256((REPO/'pages/vendor'/relative).read_bytes()).hexdigest()==info['sha256'], 'Vendored dependency changed: '+relative
print('Public checks passed: five menus, Admin tools, separate encrypted capabilities and pinned local runtime verified.')
