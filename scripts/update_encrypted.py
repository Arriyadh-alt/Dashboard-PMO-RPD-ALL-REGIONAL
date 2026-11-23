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


def update(source,plaintext,output,account,password):
    plaintext,output=Path(plaintext).resolve(),Path(output).resolve()
    if any(path==ROOT or ROOT in path.parents for path in (plaintext,output)):
        raise ValueError('Plaintext input and new encrypted output must be outside the repository')
    if output.exists(): raise ValueError('Choose a new output path; existing snapshots are never overwritten')
    envelope=json.loads(Path(source).read_text());validate(envelope)
    key,role=unwrap_key(envelope,account,password)
    if role!='owner': raise ValueError('An authorized source administrator is required')
    data=json.loads(plaintext.read_text())
    prepared=prepare(data)
    analysis=build_analysis(data,prepared,{},LocalEvents(),'owner')
    packed=gzip.compress(json.dumps(data,ensure_ascii=False,allow_nan=False).encode())
    iv=os.urandom(12)
    encrypted={**envelope,'i':base64.b64encode(iv).decode(),'c':base64.b64encode(AESGCM(key).encrypt(iv,packed,None)).decode()}
    validate(encrypted)
    output.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
    descriptor=os.open(output,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
    with os.fdopen(descriptor,'w') as file: json.dump(encrypted,file,separators=(',',':'))
    return {'canvassed':analysis['metrics']['canvassed'],'interested':analysis['metrics']['interested'],'installed':analysis['metrics']['installed']}


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source',type=Path)
    parser.add_argument('plaintext',type=Path)
    parser.add_argument('output',type=Path)
    args=parser.parse_args()
    account=os.environ.get('RPD_UPDATE_ACCOUNT') or input('Authorized source administrator ID: ')
    password=os.environ.get('RPD_UPDATE_PASSWORD') or getpass.getpass('Source password: ')
    result=update(args.source,args.plaintext,args.output,account,password)
    print('New encrypted snapshot created. Existing account wrappers preserved. Verify these unique totals against the workbook:',result)
