"""Prepare a reviewed Pages V3 release OUTSIDE the checkout.

Full Admin/Guest records remain encrypted. Login downloads encrypted aggregates
only. The intentionally public projection is restricted to its explicit allowlist.
Account wrappers, passwords and the browser-local ledger salt are unchanged.
"""
import argparse
import base64
import getpass
import gzip
import json
import os
from pathlib import Path

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from backend.aggregate import project as aggregate
from backend.analytics import build_analysis, prepare
from backend.auth import unwrap_key
from backend.browser_api import LocalEvents
from scripts.build_pages import ROOT, validate
from scripts.public_summary import project as public_summary
from scripts.split_access import encrypt, private_output


def publish(source, plaintext, directory, account, password):
    directory, plaintext = Path(directory).resolve(), Path(plaintext).resolve()
    if any(path == ROOT or ROOT in path.parents for path in (directory, plaintext)) or directory.exists():
        raise ValueError('Choose a new private release directory outside the checkout')
    envelope = json.loads(Path(source).read_text())
    validate(envelope)
    key, role = unwrap_key(envelope, account, password)
    if role != 'owner':
        raise ValueError('An authorized source administrator is required')
    previous = json.loads(gzip.decompress(AESGCM(key).decrypt(base64.b64decode(envelope['i']), base64.b64decode(envelope['c']), None)))
    access = previous.get('_guest_access')
    if not access or any(w['r'] != 'a' for w in envelope['u'].values()):
        raise ValueError('V3 requires the previously separated Admin/Guest capabilities')
    data = json.loads(plaintext.read_text())
    data['_guest_access'] = {**access, 'scope': 'operational_v3'}
    prepared = prepare(data)
    summary = aggregate(data, prepared)
    analysis = build_analysis(data, prepared, {}, LocalEvents(), 'owner')
    pair = os.urandom(16).hex()
    guest_key = base64.b64decode(access['key'])
    guest_data = {k: v for k, v in data.items() if k != '_guest_access'}
    release = {
        'data.enc.json': encrypt(data, key, envelope['u'], pair),
        'guest.enc.json': encrypt(guest_data, guest_key, access['wrappers'], pair),
        'overview.enc.json': encrypt(summary, key, envelope['u'], pair),
        'guest-overview.enc.json': encrypt(summary, guest_key, access['wrappers'], pair),
        'public-summary.json': public_summary(data, pair, analysis),
    }
    directory.mkdir(parents=True, mode=0o700)
    for name, value in release.items():
        private_output(directory / name, value)
    return {key: analysis['metrics'][key] for key in ('canvassed', 'interested', 'installed')}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source', type=Path)
    parser.add_argument('plaintext', type=Path)
    parser.add_argument('directory', type=Path)
    parser.add_argument('--approve-public-summary', action='store_true', required=True,
                        help='Explicitly approve the five KPIs, regional totals and monthly trend for public access')
    args = parser.parse_args()
    account = os.environ.get('RPD_UPDATE_ACCOUNT') or input('Authorized source administrator ID: ')
    password = os.environ.get('RPD_UPDATE_PASSWORD') or getpass.getpass('Source password: ')
    print('Prepared paired V3 release; verify counts before publishing:', publish(args.source, args.plaintext, args.directory, account, password))
