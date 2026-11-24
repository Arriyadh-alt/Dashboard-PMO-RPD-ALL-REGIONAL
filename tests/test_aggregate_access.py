import base64
import gzip
import json

import pytest
from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from backend.aggregate import project
from backend.auth import unwrap_key
from scripts.split_access import split
from tests.fixtures import encrypted_fixture, fixture_data


def unique_source():
    source = fixture_data()
    source['rec'] = {key: [values[i] for i in (0, 1, 2, 3, 4, 5, 7, 8)] for key, values in source['rec'].items()}
    return source


def unpack(envelope, key):
    return json.loads(gzip.decompress(AESGCM(key).decrypt(base64.b64decode(envelope['i']), base64.b64decode(envelope['c']), None)))


def test_projection_never_contains_identity_or_internal_data():
    value = project(unique_source())
    assert set(value) == {'aggregate_version', 'months', 'abs', 'reg', 'kels', 'P', 'days', 'install_days', 'area_keys', 'coverage', 'meta'}
    assert set(value['meta']) == {'tmin', 'tmax'}
    raw = json.dumps(value)
    for marker in ('10000001', 'SURVEYOR', 'Fixture Team', 'Supply verification', 'pdf', 'rec', 'pam'):
        assert marker not in raw
    assert sum(row[3] for row in value['days']) == 8


def test_ambiguous_duplicate_source_cannot_be_published_as_additive_cube():
    with pytest.raises(ValueError, match='unique PAM'):
        project(fixture_data())


def test_retained_admins_and_guest_have_different_capabilities(tmp_path):
    source = tmp_path / 'old.json'
    envelope = encrypted_fixture(unique_source(), {'first': ('first-password', 'a'), 'second': ('second-password', 'a'), 'viewer': ('guest-password', 'g')})
    source.write_text(json.dumps(envelope))
    owner, guest = tmp_path / 'owner.json', tmp_path / 'guest.json'
    with pytest.raises(ValueError, match='Every retained Admin'):
        split(source, owner, guest, [('first', 'first-password')])
    assert not owner.exists() and not guest.exists()
    split(source, owner, guest, [('first', 'first-password'), ('second', 'second-password')])
    full, aggregate = json.loads(owner.read_text()), json.loads(guest.read_text())
    keys = []
    for account, password in [('first', 'first-password'), ('second', 'second-password')]:
        key, role = unwrap_key(full, account, password)
        assert role == 'owner'
        assert unpack(full, key)['rec'] == unique_source()['rec']
        keys.append(key)
    guest_key, role = unwrap_key(aggregate, 'viewer', 'guest-password')
    assert role == 'guest' and keys[0] == keys[1] and guest_key != keys[0]
    assert 'rec' not in unpack(aggregate, guest_key)
    with pytest.raises(InvalidTag):
        unpack(full, guest_key)
    with pytest.raises(ValueError):
        unwrap_key(full, 'viewer', 'guest-password')
    assert guest.stat().st_mode & 0o777 == 0o600


def test_disabling_an_admin_is_explicit_and_keeps_other_passwords(tmp_path):
    source = tmp_path / 'old.json'
    source.write_text(json.dumps(encrypted_fixture(unique_source(), {'first': ('password', 'a'), 'second': ('another-password', 'a'), 'viewer': ('guest-password', 'g')})))
    result = split(source, tmp_path / 'full.json', tmp_path / 'guest.json', [('first', 'password')], disable_other_admins=True)
    assert result['disabled_admin_accounts'] == 1
