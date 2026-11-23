"""Import the existing ciphertext unchanged into private storage and preserve snapshots.

This validates the envelope only. An authorized sign-in must validate the decrypted
business contract; the import timestamp is not the source workbook refresh time.
"""

import argparse
import base64
import hashlib
import json
import os
from pathlib import Path
import re
import tempfile
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parent.parent


def import_source(input_path, output_path, legacy_html=False):
    output = Path(output_path).resolve()
    if output == ROOT or ROOT in output.parents:
        raise ValueError("Private storage must be outside the public repository.")
    content = Path(input_path).read_text()
    if legacy_html:
        found = re.search(r'<script\s+id=[\"\']?enc[\"\']?[^>]*>(.*?)</script>', content, re.S)
        if not found:
            raise ValueError("No legacy encrypted envelope found.")
        content = found[1]
    envelope = json.loads(content)
    if not isinstance(envelope.get("u"), dict) or not envelope["u"]:
        raise ValueError("Missing encrypted accounts.")
    if len(base64.b64decode(envelope["i"], validate=True)) != 12 or len(base64.b64decode(envelope["c"], validate=True)) < 16:
        raise ValueError("Invalid encrypted payload.")
    for account, wrapped in envelope["u"].items():
        if not re.fullmatch(r"[a-f0-9]{16}", account) or wrapped.get("r") not in ("a", "g"):
            raise ValueError("Invalid encrypted account metadata.")
        for field, length in (("s", 16), ("i", 12), ("k", 48)):
            if len(base64.b64decode(wrapped[field], validate=True)) != length:
                raise ValueError("Invalid account envelope.")
    output.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    output.parent.chmod(0o700)
    snapshots = output.parent / "source-snapshots"
    snapshots.mkdir(exist_ok=True, mode=0o700)
    def archive(raw):
        fingerprint = hashlib.sha256(raw).hexdigest()
        target = snapshots / (fingerprint + ".enc.json")
        if not target.exists():
            with target.open("xb") as file:
                file.write(raw)
            target.chmod(0o600)
        return fingerprint
    if output.exists():
        archive(output.read_bytes())
    raw = content.encode()
    fingerprint = archive(raw)
    descriptor, temporary = tempfile.mkstemp(dir=output.parent, prefix=".rpd-import-")
    try:
        with os.fdopen(descriptor, "wb") as file:
            file.write(raw)
            file.flush()
            os.fsync(file.fileno())
        os.replace(temporary, output)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
    manifest = {"fingerprint": fingerprint, "imported_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                "validation": "Encrypted envelope only; authorized business-data validation required."}
    path = output.with_suffix(output.suffix + ".manifest.json")
    path.write_text(json.dumps(manifest, indent=2))
    path.chmod(0o600)
    return manifest


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--legacy-html", action="store_true")
    arguments = parser.parse_args()
    result = import_source(arguments.input, arguments.output, arguments.legacy_html)
    print("Encrypted snapshot preserved. Fingerprint:", result["fingerprint"])
    print(result["validation"])
