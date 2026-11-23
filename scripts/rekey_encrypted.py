"""Create a private-generation envelope with a new key and fresh accounts.

Run as `python -m scripts.rekey_encrypted INPUT OUTPUT --administrator NEW_ID`.
Passwords are entered privately, never supplied on the command line or printed.
Previously published ciphertext/history cannot be revoked by this operation.
"""

import argparse
import base64
import getpass
import gzip
import hashlib
import json
import os
from pathlib import Path
import tempfile

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from backend.auth import decrypt_source, normalize_id, unwrap_key, user_key
from scripts.import_encrypted import ROOT, import_source


def rekey_source(source,output,account,password,accounts):
    output=Path(output).resolve()
    if output==ROOT or ROOT in output.parents:
        raise ValueError('Private output must be outside the repository')
    data,role=decrypt_source(source,account,password)
    if role!='owner':
        raise ValueError('An authorized source administrator is required')
    if not accounts or not any(role=='a' for _,role in accounts.values()):
        raise ValueError('At least one administrator is required')
    old=json.loads(Path(source).read_text())
    normalized={}
    for name,(new_password,new_role) in accounts.items():
        name=normalize_id(name)
        if not name or len(name)>100 or name in normalized or new_role not in ('a','g'):
            raise ValueError('Invalid or duplicate private account')
        new_password=new_password.strip()
        if not 16<=len(new_password)<=256 or new_password==password.strip():
            raise ValueError('Use a fresh password of sixteen to 256 characters')
        if user_key(name) in old['u']:
            try:
                unwrap_key(old,name,new_password)
            except Exception:
                pass
            else:
                raise ValueError('A previously published account password cannot be reused')
        normalized[name]=(new_password,new_role)
    if len({value[0] for value in normalized.values()})!=len(normalized):
        raise ValueError('Use a distinct password for each private account')
    key,iv=os.urandom(32),os.urandom(12)
    b64=lambda value:base64.b64encode(value).decode()
    envelope={'v':2,'u':{},'i':b64(iv),'c':b64(AESGCM(key).encrypt(iv,gzip.compress(json.dumps(data).encode()),None))}
    for name,(new_password,new_role) in normalized.items():
        salt,nonce=os.urandom(16),os.urandom(12)
        wrapper_key=hashlib.pbkdf2_hmac('sha256',(name+'\n'+new_password).encode(),salt,500000,32)
        envelope['u'][user_key(name)]={'r':new_role,'s':b64(salt),'i':b64(nonce),'k':b64(AESGCM(wrapper_key).encrypt(nonce,key,None))}
    output.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
    output.parent.chmod(0o700)
    descriptor,temporary=tempfile.mkstemp(dir=output.parent,prefix='.rpd-rekey-')
    try:
        with os.fdopen(descriptor,'w') as file:
            json.dump(envelope,file)
        return import_source(temporary,output)
    finally:
        os.unlink(temporary)


def private_password(label):
    value=getpass.getpass(label+': ')
    if value!=getpass.getpass('Repeat '+label.lower()+': '):
        raise ValueError('Passwords did not match')
    return value


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source',type=Path)
    parser.add_argument('output',type=Path)
    parser.add_argument('--administrator',required=True)
    parser.add_argument('--viewer')
    args=parser.parse_args()
    if args.viewer and normalize_id(args.viewer)==normalize_id(args.administrator):
        parser.error('Administrator and viewer must have different account IDs')
    source_account=input('Authorized source administrator ID: ')
    source_password=getpass.getpass('Source password: ')
    accounts={args.administrator:(private_password('New administrator password'),'a')}
    if args.viewer:
        accounts[args.viewer]=(private_password('New aggregate viewer password'),'g')
    rekey_source(args.source,args.output,source_account,source_password,accounts)
    print('Private-generation source created. Business records preserved; prior published copies are not revoked.')
