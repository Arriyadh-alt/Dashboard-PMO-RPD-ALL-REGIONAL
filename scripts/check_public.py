"""Dependency-free checks of the intentionally small public surface."""

from html.parser import HTMLParser
import hashlib
from pathlib import Path

REPO=Path(__file__).resolve().parent.parent
ROOT=REPO/'web'
assert hashlib.sha256((REPO/'index.html').read_bytes()).hexdigest()=='12d5248b2d027f149823eeb85c562cba02c2f97b65b8e064a3634b8f6afa2b42', 'Legacy Pages entrypoint must remain unchanged until an approved cutover'


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
            assert (ROOT/values['href']).is_file(), 'Missing stylesheet'


page=Page()
html=(ROOT/'index.html').read_text()
assert 'id=enc' not in html and 'application/json' not in html, 'Protected payload must stay off the public surface'
page.feed(html)
assert len(page.scripts)==2 and all((ROOT/path).is_file() for path in page.scripts)
assert len([identifier for identifier in page.identifiers if identifier.startswith('tab-')])==7
assert not list(REPO.glob('*.enc.json')), 'Private input must be outside this repository'
print('Public-surface checks passed: seven workspaces, external assets, no embedded data.')
