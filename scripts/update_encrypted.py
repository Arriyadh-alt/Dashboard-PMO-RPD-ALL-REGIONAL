"""Encrypt a validated daily JSON contract while preserving existing Pages logins.

Workbook-to-contract mapping must first be verified against the actual Excel file.
Inputs/outputs with plaintext are kept outside the checkout. No credentials are logged.
"""
import argparse
import base64
import getpass
import gzip
import json
import os
from pathlib import Path

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from backend.analytics import build_analysis,prepare
from backend.auth import unwrap_key
from backend.browser_api import LocalEvents
from scripts.build_pages import ROOT,validate
from scripts.split_access import encrypt,private_output
from backend.aggregate import project


def update(source,plaintext,output,account,password,guest_output=None):
    plaintext,output=Path(plaintext).resolve(),Path(output).resolve()
    if any(path==ROOT or ROOT in path.parents for path in (plaintext,output)):
        raise ValueError('Plaintext input and new encrypted output must be outside the repository')
    if output.exists(): raise ValueError('Choose a new output path; existing snapshots are never overwritten')
    envelope=json.loads(Path(source).read_text());validate(envelope)
    key,role=unwrap_key(envelope,account,password)
    if role!='owner': raise ValueError('An authorized source administrator is required')
    data=json.loads(plaintext.read_text())
    previous=json.loads(gzip.decompress(AESGCM(key).decrypt(base64.b64decode(envelope['i']),base64.b64decode(envelope['c']),None)))
    access=previous.get('_guest_access')
    if access and access.get('scope') == 'operational_v3':
        raise ValueError('Use scripts.publish_v3 for a matching full V3 release, including approved public aggregates')
    guest=None;pair=None
    if access:
        if guest_output is None: raise ValueError('A paired Guest output is required for this protected source')
        guest_path=Path(guest_output).resolve()
        if guest_path==ROOT or ROOT in guest_path.parents or guest_path.exists(): raise ValueError('Choose a new Guest output outside the repository')
        if guest_path==output: raise ValueError('Admin and Guest output paths must differ')
        data['_guest_access']=access
        pair=os.urandom(16).hex()
        guest=encrypt(project(data),base64.b64decode(access['key']),access['wrappers'],pair)
    else:
        data.pop('_guest_access',None)
    prepared=prepare(data)
    analysis=build_analysis(data,prepared,{},LocalEvents(),'owner')
    packed=gzip.compress(json.dumps(data,ensure_ascii=False,allow_nan=False).encode())
    iv=os.urandom(12)
    encrypted={**envelope,'i':base64.b64encode(iv).decode(),'c':base64.b64encode(AESGCM(key).encrypt(iv,packed,None)).decode()}
    if pair is not None: encrypted['p']=pair
    validate(encrypted)
    output.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
    descriptor=os.open(output,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
    with os.fdopen(descriptor,'w') as file: json.dump(encrypted,file,separators=(',',':'))
    if guest is not None: private_output(guest_output,guest)
    return {'canvassed':analysis['metrics']['canvassed'],'interested':analysis['metrics']['interested'],'installed':analysis['metrics']['installed']}


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source',type=Path)
    parser.add_argument('plaintext',type=Path)
    parser.add_argument('output',type=Path)
    parser.add_argument('--guest-output',type=Path,help='Required paired aggregate-only Guest output for protected sources')
    args=parser.parse_args()
    account=os.environ.get('RPD_UPDATE_ACCOUNT') or input('Authorized source administrator ID: ')
    password=os.environ.get('RPD_UPDATE_PASSWORD') or getpass.getpass('Source password: ')
    result=update(args.source,args.plaintext,args.output,account,password,args.guest_output)
    print('New encrypted snapshot created. Existing account wrappers preserved. Verify these unique totals against the workbook:',result)
