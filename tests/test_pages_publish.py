import base64
import json
import secrets
import stat
from pathlib import Path

import pytest

from backend.auth import decrypt_source
from scripts.build_pages import build,validate
from scripts.update_encrypted import update
from tests.fixtures import encrypted_fixture,fixture_data


def test_daily_encrypt_preserves_logins_and_browser_key_salt(tmp_path):
    password,viewer=secrets.token_urlsafe(24),secrets.token_urlsafe(24)
    original=encrypted_fixture(fixture_data(),{'admin':(password,'a'),'viewer':(viewer,'g')})
    source=tmp_path/'source.enc.json';source.write_text(json.dumps(original))
    data=fixture_data();data['rec']['tg'][0]=12345
    plain=tmp_path/'validated.json';plain.write_text(json.dumps(data))
    output=tmp_path/'daily.enc.json'
    assert update(source,plain,output,'admin',password)==dict(canvassed=9,interested=6,installed=3)
    actual=json.loads(output.read_text())
    assert actual['u']==original['u'] and actual['i']!=original['i'] and actual['c']!=original['c']
    assert decrypt_source(output,'admin',password)[0]==data
    # Deliberately proves the accepted model: a viewer password can decrypt all data.
    assert decrypt_source(output,'viewer',viewer)[0]==data
    assert stat.S_IMODE(output.stat().st_mode)==0o600
    with pytest.raises(ValueError,match='never overwritten'): update(source,plain,output,'admin',password)
    with pytest.raises(ValueError,match='administrator'): update(source,plain,tmp_path/'denied.enc.json','viewer',viewer)
    root=tmp_path/'site';(root/'pages').mkdir(parents=True)
    before=build(output,owner='SYNTHETIC TEST DATA',root=root)
    after=build(root=root)
    assert after==before
    assert len(base64.b64decode(after['ledger_salt']))==16
    assert json.loads((root/'pages/data.enc.json').read_text())==actual
    assert 'web/command-center.js?v=' in (root/'index.html').read_text()


def test_public_publisher_rejects_plaintext_even_in_version_field(tmp_path):
    with pytest.raises(ValueError): validate(fixture_data())
    envelope=encrypted_fixture(fixture_data(),{'admin':(secrets.token_urlsafe(24),'a')})
    envelope['v']={'customer':'not publishable'}
    with pytest.raises(ValueError): validate(envelope)
