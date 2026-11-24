"""One-time cryptographic Guest/Admin separation. Never prints account credentials.

All retained Admin passwords are required to wrap a fresh customer-data key.
Existing Guest wrappers retain their key, but only an aggregate projection is
encrypted with it. Historical public snapshots cannot be revoked by this tool.
"""
import argparse
import base64
import copy
import getpass
import gzip
import hashlib
import json
import os
from pathlib import Path

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from backend.aggregate import project
from backend.auth import normalize_id, unwrap_key, user_key
from scripts.build_pages import ROOT, validate


def encoded(value):
    return base64.b64encode(value).decode()


def encrypt(data, key, wrappers):
    iv = os.urandom(12)
    packed = gzip.compress(json.dumps(data, ensure_ascii=False, allow_nan=False, separators=(',', ':')).encode())
    envelope = {'v': 2, 'u': wrappers, 'i': encoded(iv), 'c': encoded(AESGCM(key).encrypt(iv, packed, None))}
    validate(envelope)
    return envelope


def private_output(path, value):
    path = Path(path).resolve()
    if path == ROOT or ROOT in path.parents:
        raise ValueError('Generated encrypted outputs must be reviewed outside the repository')
    if path.exists():
        raise ValueError('Choose new output paths; existing files are never overwritten')
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    with os.fdopen(os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), 'w') as file:
        json.dump(value, file, separators=(',', ':'))


def split(source, owner_output, guest_output, credentials, disable_other_admins=False):
    envelope = json.loads(Path(source).read_text())
    validate(envelope)
    old_key = None
    retained = {}
    for account, password in credentials:
        key, role = unwrap_key(envelope, account, password)
        if role != 'owner' or (old_key is not None and old_key != key):
            raise ValueError('All provided credentials must authorize the same Admin source')
        old_key = key
        retained[user_key(account)] = (normalize_id(account), password)
    admins = {account for account, wrapped in envelope['u'].items() if wrapped['r'] == 'a'}
    if not retained or (set(retained) != admins and not disable_other_admins):
        raise ValueError('Every retained Admin credential is required; disabling other Admins needs explicit approval')
    guests = {account: wrapped for account, wrapped in envelope['u'].items() if wrapped['r'] == 'g'}
    if not guests:
        raise ValueError('A separate existing Guest account is required')
    data = json.loads(gzip.decompress(AESGCM(old_key).decrypt(base64.b64decode(envelope['i']), base64.b64decode(envelope['c']), None)))
    aggregate = project(data)
    new_key = os.urandom(32)
    wrappers = {}
    for identity, (account, password) in retained.items():
        wrapped = copy.deepcopy(envelope['u'][identity])
        wrapping_key = hashlib.pbkdf2_hmac('sha256', (account + '\n' + password.strip()).encode(), base64.b64decode(wrapped['s']), 500000, 32)
        iv = os.urandom(12)
        wrapped.update(i=encoded(iv), k=encoded(AESGCM(wrapping_key).encrypt(iv, new_key, None)))
        wrappers[identity] = wrapped
    # Kept only inside the newly protected Admin plaintext, never in bootstrap.
    data['_guest_access'] = {'key': encoded(old_key), 'wrappers': guests}
    owner = encrypt(data, new_key, wrappers)
    guest = encrypt(aggregate, old_key, guests)
    for path in (owner_output, guest_output):
        resolved = Path(path).resolve()
        if resolved == ROOT or ROOT in resolved.parents or resolved.exists():
            raise ValueError('Both output paths must be new and outside the repository')
    private_output(owner_output, owner)
    private_output(guest_output, guest)
    return {'admin_accounts': len(wrappers), 'guest_accounts': len(guests), 'disabled_admin_accounts': len(admins - retained.keys()), 'survey_rows': sum(row[3] for row in aggregate['days'])}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source', type=Path)
    parser.add_argument('owner_output', type=Path)
    parser.add_argument('guest_output', type=Path)
    parser.add_argument('--disable-other-admins', action='store_true', help='Use only with explicit approval to disable other Admin accounts')
    args = parser.parse_args()
    credentials = [(os.environ.get('RPD_UPDATE_ACCOUNT') or input('Admin ID: '), os.environ.get('RPD_UPDATE_PASSWORD') or getpass.getpass('Admin password: '))]
    if os.environ.get('RPD_SECOND_ADMIN_ID') and os.environ.get('RPD_SECOND_ADMIN_PASSWORD'):
        credentials.append((os.environ['RPD_SECOND_ADMIN_ID'], os.environ['RPD_SECOND_ADMIN_PASSWORD']))
    print(json.dumps(split(args.source, args.owner_output, args.guest_output, credentials, args.disable_other_admins)))
