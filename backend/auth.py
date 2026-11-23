"""Compatibility with the existing encrypted source; credentials never leave the server."""

import base64
import gzip
import hashlib
import json
import secrets
import threading
import time
from collections import defaultdict, deque
from dataclasses import dataclass
from pathlib import Path

from cryptography.hazmat.primitives.ciphers.aead import AESGCM


def normalize_id(value):
    return "".join(value.split()).lower()


def user_key(value):
    return hashlib.sha256(normalize_id(value).encode()).hexdigest()[:16]


def unwrap_key(envelope, account, password):
    account = normalize_id(account)
    wrapped = envelope.get("u", {}).get(user_key(account))
    # Unknown accounts do the same expensive derivation, without disclosing membership.
    salt = base64.b64decode(wrapped["s"]) if wrapped else b"rpd-dummy-salt00"
    key = hashlib.pbkdf2_hmac("sha256", (account + "\n" + password.strip()).encode(), salt, 500000, 32)
    if not wrapped:
        raise ValueError("Invalid credentials")
    raw = AESGCM(key).decrypt(base64.b64decode(wrapped["i"]), base64.b64decode(wrapped["k"]), None)
    if wrapped.get("r") not in ("a", "g"):
        raise ValueError("Unsupported role")
    return raw, "owner" if wrapped["r"] == "a" else "guest"


def decrypt_payload(envelope, key):
    compressed=AESGCM(key).decrypt(base64.b64decode(envelope['i']),base64.b64decode(envelope['c']),None)
    return json.loads(gzip.decompress(compressed))


def decrypt_source(path, account, password):
    """Keep the original PBKDF2(500000)/AES-GCM/gzip data contract exactly."""
    envelope=json.loads(Path(path).read_text())
    key,role=unwrap_key(envelope,account,password)
    return decrypt_payload(envelope,key),role


class SessionCapacity(RuntimeError):
    pass


@dataclass
class Session:
    actor: str
    role: str
    data: dict
    csrf: str
    created: float
    touched: float
    source_stamp: tuple


class Sessions:
    """Opaque tokens only; one process. Restart revokes sessions by design."""

    def __init__(self):
        self.values = {}
        self.failures = defaultdict(deque)
        self.lock = threading.RLock()
        self.login_slots = threading.BoundedSemaphore(4)

    def _prune(self, now):
        for key, value in list(self.values.items()):
            if now - value.created > 3600 or now - value.touched > 1200:
                del self.values[key]
        for key, entries in list(self.failures.items()):
            while entries and now - entries[0] > 900:
                entries.popleft()
            if not entries:
                del self.failures[key]

    def limited(self, peer):
        with self.lock:
            self._prune(time.monotonic())
            return len(self.failures.get(peer, ())) >= 10

    def failed(self, peer):
        with self.lock:
            self.failures[peer].append(time.monotonic())

    def create(self, actor, role, data, stamp):
        token = secrets.token_urlsafe(32)
        now = time.monotonic()
        with self.lock:
            self._prune(now)
            # Old imports are revoked together; one account cannot fill the global pool.
            for key,value in list(self.values.items()):
                if value.source_stamp!=stamp:
                    del self.values[key]
            own=sorted(((key,value) for key,value in self.values.items() if value.actor==actor),key=lambda item:item[1].created)
            for key,_ in own[:-4]:
                del self.values[key]
            if len(self.values) >= 100:
                raise SessionCapacity("Session capacity reached")
            self.values[hashlib.sha256(token.encode()).hexdigest()] = Session(
                actor, role, data, secrets.token_urlsafe(32), now, now, stamp
            )
        return token

    def get(self, token, stamp):
        key = hashlib.sha256(token.encode()).hexdigest()
        with self.lock:
            self._prune(time.monotonic())
            session = self.values.get(key)
            if session and session.source_stamp != stamp:
                del self.values[key]
                return None
            if session:
                session.touched = time.monotonic()
            return session

    def remove(self, token):
        with self.lock:
            self.values.pop(hashlib.sha256(token.encode()).hexdigest(), None)
