"""Deliberately synthetic source matching the original columnar/encryption contracts."""

import base64
from collections import defaultdict
import gzip
import hashlib
import json
import os

from cryptography.hazmat.primitives.ciphers.aead import AESGCM


def fixture_data():
    # PAM suffix, area, month-index, survey YYMMDD, interest code, installation code, meter date.
    source = [(1,0,0,260901,1,1,260905),(2,0,0,260902,1,2,0),(3,1,0,260903,2,0,0),
              (4,0,1,261002,1,1,261005),(5,1,1,261003,1,3,0),
              (6,0,2,261101,1,2,0),(6,0,2,261101,1,2,0),(7,1,2,261102,1,1,261104),
              (8,0,2,261103,2,0,0),(9,0,2,261104,1,2,0),(9,1,2,261104,1,2,0),
              (10,0,2,261105,1,2,0),(10,0,2,261105,2,1,261106),(0,0,0,260904,0,0,0)]
    fields = ('pam','ab','kel','sv','mi','t','c1','kf','fa','mt','kd','mf','pr','sc','tg')
    records = {key:[] for key in fields}
    area_totals, surveyor_totals, events = defaultdict(lambda:[0]*10), defaultdict(lambda:[0]*10), defaultdict(lambda:[0]*2)
    for suffix, area, month, survey, interest, status, meter in source:
        fa = survey if status == 2 else 0
        values = ('bad' if suffix == 0 else 10000000+suffix,area,area,area,month,survey,interest,status,fa,meter,1 if status==3 else 0,1,1,1,10000)
        for key,value in zip(fields,values):
            records[key].append(value)
        stats = [1,int(interest==1),int(interest==2),int(interest==0),0,0,int(status==2),int(status==1),int(status==3),int(status==4)]
        team_stats = [stats[0],stats[1],stats[7],stats[6],stats[8],stats[9],0,0,0,0]
        for index,value in enumerate(stats):
            area_totals[(month,area)][index] += value
        for index,value in enumerate(team_stats):
            surveyor_totals[(month,area)][index] += value
        events[(month,area)][0] += bool(fa)
        events[(month,area)][1] += bool(meter)
    sync = {key:0 for key in ('pot_master','deduct','deduct_tp','dp_b','outside','non_berm','nb','ptd','ab_diff','kel_diff','master_missing')}
    sync.update(pot_master=150,deduct=25,deduct_tp=12)
    return {"months":["2026-09","2026-10","2026-11"],"abs":["Fixture Area A","Fixture Area B"],
            "reg":["Barat","Timur"],"kels":["FIXTURE KEL A","FIXTURE KEL B"],
            "svs":["FIXTURE SURVEYOR A","FIXTURE SURVEYOR B"],"st":[0,0],"kl":["Fixture Team A","Fixture Team B"],
            "A":[[month,area,*values] for (month,area),values in area_totals.items()],
            "S":[[month,area,area,area,*values] for (month,area),values in surveyor_totals.items()],
            "E":[[month,area,*values] for (month,area),values in events.items()],
            "P":[[0,0,100,20,10],[1,1,50,5,2]],"W":[[0,0,1,1,60,15],[0,0,1,2,40,5],[1,1,2,1,50,5]],
            "meta":{"rows":14,"uniq":11,"tmin":"2026-09-01","tmax":"2026-11-05","rt_bad":0,
                    "korlaps":["Fixture Team A","Fixture Team B"],"sync":sync},
            "dic":{"c1":["","Berminat","Tidak berminat","Belum diketahui","PTD","Tidak ada bangunan"],
                   "kf":["","Done","Assign FA","Outstanding","Cancel"],"kd":["","Supply verification needed"],
                   "mf":["","POTENSI"],"pr":["","POTENSI","NON POTENSI"],"sc":["","Fixture status"]},
            "rec":records,"pdf":base64.b64encode(b'%PDF-1.4\n% Synthetic test artifact\n%%EOF').decode()}


def encrypted_fixture(data, accounts):
    """Accounts are supplied at runtime, never embedded in a deployed application."""
    b64 = lambda value:base64.b64encode(value).decode()
    data_key, iv = os.urandom(32), os.urandom(12)
    envelope = {'v':2,"u":{},"i":b64(iv),"c":b64(AESGCM(data_key).encrypt(iv,gzip.compress(json.dumps(data).encode()),None))}
    for account,(password,role) in accounts.items():
        account=''.join(account.split()).lower()
        salt, nonce = os.urandom(16), os.urandom(12)
        key=hashlib.pbkdf2_hmac('sha256',(account+'\n'+password.strip()).encode(),salt,500000,32)
        envelope['u'][hashlib.sha256(account.encode()).hexdigest()[:16]]={"r":role,"s":b64(salt),"i":b64(nonce),"k":b64(AESGCM(key).encrypt(nonce,data_key,None))}
    return envelope


if __name__ == '__main__':
    import argparse
    from pathlib import Path
    parser=argparse.ArgumentParser(description='Generate SYNTHETIC data outside the repository for local UI testing only.')
    parser.add_argument('output',type=Path)
    args=parser.parse_args()
    root=Path(__file__).resolve().parent.parent
    if root in args.output.resolve().parents:
        raise SystemExit('Fixture output must be outside the repository.')
    admin=os.environ['RPD_FIXTURE_ADMIN_PASSWORD']
    viewer=os.environ['RPD_FIXTURE_VIEWER_PASSWORD']
    args.output.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
    args.output.write_text(json.dumps(encrypted_fixture(fixture_data(),{'fixture-admin':(admin,'a'),'fixture-viewer':(viewer,'g')})))
    args.output.chmod(0o600)
    print('SYNTHETIC fixture created. Not production-data verification.')
