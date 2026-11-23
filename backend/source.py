"""One private immutable dataset per imported source, shared by authenticated sessions."""

import hashlib
import json
import secrets
import threading

from .analytics import prepare
from .auth import decrypt_payload, unwrap_key
from .store import now_iso


class RotationRequired(RuntimeError):
    pass


class SourceCache:
    def __init__(self):
        self.lock=threading.RLock()
        self.stamp=None
        self.envelope=None
        self.fingerprint=None
        self.key=None
        self.data=None

    def authenticate(self,path,account,password,stamp,allow_legacy=False):
        with self.lock:
            if self.stamp!=stamp or self.envelope is None:
                raw=path.read_bytes()
                envelope=json.loads(raw)
                self.envelope=envelope
                self.fingerprint=hashlib.sha256(raw).hexdigest()
                self.stamp=stamp
                self.key=self.data=None
            envelope=self.envelope
            if not allow_legacy and envelope.get('v')!=2:
                raise RotationRequired('Legacy source requires private credential/key rotation')
        # Every sign-in still verifies the account password; cached data never bypasses auth.
        key,role=unwrap_key(envelope,account,password)
        with self.lock:
            if self.envelope is not envelope:
                raise OSError('Source changed while authenticating; retry')
            if self.data is None:
                source=decrypt_payload(envelope,key)
                prepared=prepare(source)
                manifest=path.with_suffix(path.suffix+'.manifest.json')
                imported_at=None
                if manifest.is_file():
                    metadata=json.loads(manifest.read_text())
                    if metadata.get('fingerprint')==self.fingerprint:
                        imported_at=metadata.get('imported_at')
                self.data={'source':source,'prepared':prepared,'info':{
                    'fingerprint':self.fingerprint,'loaded_at':now_iso(),'imported_at':imported_at}}
                self.key=key
            elif not secrets.compare_digest(self.key,key):
                raise ValueError('Invalid source key')
            return self.data,role
