import hashlib
import json
from pathlib import Path

import pytest

from scripts.import_encrypted import import_source


def test_import_preserves_ciphertext_and_snapshots(encrypted_source,tmp_path):
    source=encrypted_source[0]
    target=tmp_path/'private'/'current.enc.json'
    expected=hashlib.sha256(source.read_bytes()).hexdigest()
    result=import_source(source,target)
    assert result['fingerprint']==expected and source.read_bytes()==target.read_bytes()
    assert (target.parent/'source-snapshots'/f'{expected}.enc.json').is_file()
    assert target.stat().st_mode & 0o777 == 0o600
    html=tmp_path/'legacy.html'
    html.write_text('<script id=enc type="application/json">'+source.read_text()+'</script>')
    import_source(html,target,legacy_html=True)
    assert source.read_bytes()==target.read_bytes()


def test_import_rejects_public_repository_destinations(encrypted_source):
    root=Path(__file__).resolve().parent.parent
    with pytest.raises(ValueError,match='outside'):
        import_source(encrypted_source[0],root/'private.enc.json')
