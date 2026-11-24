"""Build a zero-server entrypoint and publish ONLY an already-encrypted daily source.

Excel schemas must be verified before conversion; this does not guess workbook columns.
"""
import argparse
import base64
import hashlib
import json
import os
import re
import zipfile
from datetime import datetime,timezone
from pathlib import Path

ROOT=Path(__file__).resolve().parent.parent
MODULES=['__init__.py','analytics.py','exports.py','browser_api.py']


def engine(root=ROOT):
    path=root/'pages/engine.zip'
    with zipfile.ZipFile(path,'w',zipfile.ZIP_DEFLATED) as archive:
        for name in MODULES:
            entry=zipfile.ZipInfo('backend/'+name,date_time=(2026,1,1,0,0,0))
            entry.compress_type=zipfile.ZIP_DEFLATED
            archive.writestr(entry,(ROOT/'backend'/name).read_bytes())
    return hashlib.sha256(path.read_bytes()).hexdigest()


def validate(envelope):
    if not isinstance(envelope,dict) or set(envelope)-{'u','i','c','v','p'} or not {'u','i','c'}<=envelope.keys() or not isinstance(envelope['u'],dict) or not envelope['u']:
        raise ValueError('Only the existing encrypted envelope is publishable; plaintext is forbidden')
    if 'v' in envelope and (type(envelope['v']) is not int or envelope['v']!=2):
        raise ValueError('Unsupported envelope version; never put plaintext in public envelope fields')
    if 'p' in envelope and (not isinstance(envelope['p'],str) or not re.fullmatch('[0-9a-f]{32}',envelope['p'])):
        raise ValueError('Snapshot pairing marker must be a random 128-bit identifier')
    for value in [envelope['i'],envelope['c']]: base64.b64decode(value,validate=True)
    if len(base64.b64decode(envelope['i']))!=12 or len(base64.b64decode(envelope['c']))<16: raise ValueError('Invalid encrypted payload')
    for account,wrapped in envelope['u'].items():
        if not re.fullmatch('[0-9a-f]{16}',account) or set(wrapped)!={'r','s','i','k'} or wrapped['r'] not in ('a','g'):
            raise ValueError('Invalid encrypted account wrapper')
        for key in ['s','i','k']: base64.b64decode(wrapped[key],validate=True)
        if len(base64.b64decode(wrapped['i']))!=12 or len(base64.b64decode(wrapped['s']))<16 or len(base64.b64decode(wrapped['k']))!=48: raise ValueError('Invalid wrapped key')


def build(source=None,owner=None,root=ROOT,guest_source=None,bundle_dir=None):
    release = {}
    if bundle_dir is not None:
        bundle = Path(bundle_dir)
        source, guest_source = bundle/'data.enc.json', bundle/'guest.enc.json'
        release = {name: json.loads((bundle/name).read_text()) for name in
                   ('overview.enc.json', 'guest-overview.enc.json', 'public-summary.json')}
    asset=root/'pages/data.enc.json';manifest_path=root/'pages/data-manifest.json'
    previous=json.loads(manifest_path.read_text()) if manifest_path.exists() else {}
    if source is not None:
        envelope=json.loads(Path(source).read_text())
        validate(envelope)
        raw=(json.dumps(envelope,separators=(',',':'))+'\n').encode()
    else:
        raw=asset.read_bytes();validate(json.loads(raw))
    fingerprint=hashlib.sha256(raw).hexdigest()
    manifest={'version':1,'fingerprint':fingerprint,'worker':hashlib.sha256((ROOT/'pages/analysis-worker.js').read_bytes()).hexdigest(),'pdf':hashlib.sha256((ROOT/'pages/pdf.js').read_bytes()).hexdigest(),'published_at':previous.get('published_at') if previous.get('fingerprint')==fingerprint else datetime.now(timezone.utc).isoformat(timespec='seconds'),'ledger_salt':previous.get('ledger_salt') or base64.b64encode(os.urandom(16)).decode(),'owner':owner if owner is not None else previous.get('owner','')}
    manifest['summary']=hashlib.sha256((ROOT/'pages/summary.js').read_bytes()).hexdigest()
    guest_asset=root/'pages/guest.enc.json'
    if guest_source is not None or guest_asset.exists():
        guest_envelope=json.loads(Path(guest_source).read_text() if guest_source is not None else guest_asset.read_text())
        validate(guest_envelope)
        admin_envelope=json.loads(raw)
        if not admin_envelope.get('p') or admin_envelope['p']!=guest_envelope.get('p'):
            raise ValueError('Admin and Guest snapshots must be published as the matching pair')
        if any(w['r']!='a' for w in admin_envelope['u'].values()) or any(w['r']!='g' for w in guest_envelope['u'].values()):
            raise ValueError('Separated publication requires Admin-only and Guest-only encrypted wrappers')
        if set(admin_envelope['u'])&set(guest_envelope['u']):
            raise ValueError('An account cannot have both payload capabilities')
        guest_raw=(json.dumps(guest_envelope,separators=(',',':'))+'\n').encode()
        manifest['guest_fingerprint']=hashlib.sha256(guest_raw).hexdigest()
        manifest['accounts']={**admin_envelope['u'],**guest_envelope['u']}
        manifest['snapshot_pair']=admin_envelope['p']
    if bundle_dir is None and previous.get('overview_fingerprint'):
        if fingerprint != previous['fingerprint']:
            raise ValueError('V3 daily refresh requires a matching full release bundle')
        release = {name: json.loads((root/'pages'/name).read_text()) for name in
                   ('overview.enc.json', 'guest-overview.enc.json', 'public-summary.json')}
    if release:
        from scripts.public_summary import validate as validate_public
        for name, wrappers, field in [('overview.enc.json', admin_envelope['u'], 'overview_fingerprint'),
                                       ('guest-overview.enc.json', guest_envelope['u'], 'guest_overview_fingerprint')]:
            overview = release[name]
            validate(overview)
            if overview.get('p') != manifest['snapshot_pair'] or overview['u'] != wrappers:
                raise ValueError('Overview and detail snapshots must be the matching pair with identical account wrappers')
            manifest[field] = hashlib.sha256((json.dumps(overview,separators=(',',':'))+'\n').encode()).hexdigest()
        validate_public(release['public-summary.json'])
        if release['public-summary.json']['snapshot_pair'] != manifest['snapshot_pair']:
            raise ValueError('Public and internal summaries must be the matching pair')
        manifest['guest_scope'] = 'operational_readonly'
        manifest['public_fingerprint'] = hashlib.sha256((json.dumps(release['public-summary.json'],separators=(',',':'))+'\n').encode()).hexdigest()
    manifest['engine']=engine(root)
    template=(ROOT/'web/index.html').read_text()
    template=template.replace('href="styles.css"','href="web/styles.css"').replace('href="command-center.css"','href="web/command-center.css"')
    template=template.replace('src="app.js"','src="web/app.js"').replace('src="command-center.js"','src="web/command-center.js"')
    template=template.replace('src="potential.js"','src="web/potential.js"')
    template=template.replace('<script src="web/app.js"','<script src="pages/browser.js"></script>\n<script src="web/app.js"')
    public = '''<div id="public-app">
<header class="public-header"><a class="public-brand" href="#public-summary">PMO RPD <span>Seluruh Regional</span></a><nav aria-label="Navigasi publik"><a href="#public-summary">Ringkasan</a><a href="#public-charts">Grafik Kinerja</a><button id="public-login" class="primary" type="button">Masuk</button></nav></header>
<main class="public-main" id="public-summary"><div class="public-heading"><div><span class="eyebrow">PAM JAYA</span><h1>Ringkasan Kinerja</h1></div><p id="public-updated" class="mu"></p></div><div id="public-content" aria-busy="true"><p class="mu" role="status">Memuat ringkasan…</p></div></main>
<footer class="public-footer"><span>PMO RPD · PAM JAYA</span><span>Design by Arriyadh</span></footer></div>'''
    template=template.replace('<div id="lg">',public+'\n<div id="lg" hidden>')
    template=template.replace('</form></section>','<button id="public-back" type="button" class="text-button">Kembali ke Ringkasan</button></form></section>')
    # Public entrypoint loads no operational JavaScript until Masuk is chosen.
    for relative in ['pages/browser.js','web/app.js','web/potential.js','web/command-center.js']:
        template=re.sub(r'<script src="'+re.escape(relative)+r'"(?: defer)?></script>', '', template)
    template=template.replace('</body>','<script src="pages/public.js" data-browser="pages/browser.js" data-app="web/app.js" data-potential="web/potential.js" data-center="web/command-center.js" defer></script>\n</body>')
    note='<p class="scope-note">GitHub Pages · Data dibuka di perangkat ini. Pemegang kata sandi dapat mengakses seluruh data; peran tampilan bukan otorisasi server. Follow-up/pengaturan disimpan terenkripsi hanya pada peramban dan akun ini, tidak tersinkron ke tim. Usia kasus mengikuti jam perangkat.</p><details id="local-history-controls" hidden><summary>Cadangan riwayat lokal terenkripsi</summary><p>Unduh sebelum berganti perangkat atau kata sandi. Pulihkan hanya pada riwayat kosong; jangan hapus penyimpanan sebelum mencadangkan.</p><button id="backup-local" type="button">Unduh cadangan terenkripsi</button><label>Pulihkan cadangan <input id="restore-local" type="file" accept="application/json,.json"></label></details>'
    note+='<details id="legacy-mapping-controls" hidden><summary>Pemetaan dari dashboard lama perlu ditinjau</summary><p>Pemetaan lama memakai nomor urut, bukan identitas surveyor. Pastikan pasangan berikut cocok dengan sumber lama sebelum mengimpor. Pemetaan terenkripsi yang sudah ada didahulukan; data sumber tidak diubah. Salinan lama baru dihapus setelah penyimpanan terenkripsi berhasil.</p><div id="legacy-mapping-preview" style="max-height:12rem;overflow:auto"></div><button id="backup-legacy-mapping" type="button">Unduh salinan lama (JSON lokal)</button><label><input id="confirm-legacy-mapping" type="checkbox"> Saya telah memverifikasi identitas dan pemetaan setiap surveyor.</label><button id="import-legacy-mapping" type="button" disabled>Impor ke riwayat terenkripsi</button><p id="legacy-mapping-status" role="status"></p></details>'
    note=note.replace('<button id="backup-local"','<div id="history-recovery" hidden><p>Riwayat lama terkunci; laporan sementara hanya memakai data sumber. Riwayat tidak dihapus atau ditimpa. Unduh cadangan asli, atau buka dengan kata sandi lama untuk mengenkripsi ulang memakai kata sandi login sekarang.</p><label>Kata sandi lama riwayat <input id="previous-history-password" type="password" autocomplete="off"></label><button id="recover-history" type="button">Buka dan enkripsi ulang riwayat</button><p id="history-recovery-status" role="status"></p></div><button id="backup-local"')
    note=note[note.index('<details id="local-history-controls"'):]
    template=template.replace('<main ','<template id="local-admin-tools">'+note+'</template>\n<main ',1)
    template=template.replace('Backend privat','Mode GitHub Pages').replace('Layanan privat','Dashboard terenkripsi')
    template=template.replace('Sesi backend privat · Akses sesuai peran pengguna.','Dekripsi lokal · Pemegang kata sandi dapat mengakses seluruh data.')
    template=template.replace('</head>','<meta name="referrer" content="no-referrer">\n<meta http-equiv="Content-Security-Policy" content="default-src \'self\'; script-src \'self\' \'wasm-unsafe-eval\'; worker-src \'self\'; connect-src \'self\'; style-src \'self\' \'unsafe-inline\' https://fonts.googleapis.com; font-src \'self\' https://fonts.gstatic.com; img-src \'self\' data: blob:; object-src \'none\'; base-uri \'none\'; form-action \'self\'">\n</head>')
    # Asset versions keep a newly published shell from mixing cached code revisions.
    for relative in ['pages/browser.js','pages/public.js','web/app.js','web/potential.js','web/command-center.js','web/styles.css','web/command-center.css']:
        digest=hashlib.sha256((ROOT/relative).read_bytes()).hexdigest()[:16]
        template=template.replace('"'+relative+'"','"'+relative+'?v='+digest+'"')
    if guest_source is not None or guest_asset.exists():
        guest_asset.write_bytes(guest_raw)
    for name,value in release.items():
        (root/'pages'/name).write_text(json.dumps(value,separators=(',',':'))+'\n')
    asset.write_bytes(raw)
    manifest_path.write_text(json.dumps(manifest,indent=2)+'\n')
    (root/'index.html').write_text(template)
    (root/'.nojekyll').touch()
    return manifest


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source',nargs='?',type=Path,help='Validated encrypted source JSON, never a plaintext workbook/JSON')
    parser.add_argument('--owner',help='Verified data-owner label; use SYNTHETIC TEST DATA for test fixtures')
    parser.add_argument('--guest-source',type=Path,help='Paired encrypted Guest envelope')
    parser.add_argument('--bundle-dir',type=Path,help='Reviewed V3 release directory from scripts.publish_v3')
    args=parser.parse_args()
    manifest=build(args.source,args.owner,guest_source=args.guest_source,bundle_dir=args.bundle_dir)
    print('Static Pages build ready; encrypted source fingerprint:',manifest['fingerprint'])
