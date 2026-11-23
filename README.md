# PMO RPD Command Center

An incremental extension of the existing RPD dashboard: the original operational reports remain available, with seven decision-support workspaces, protected server-side access, filter-aware reports and a separate append-only operations ledger.

## Deployment is intentionally gated

**This branch is not a private-service production deployment.** GitHub Pages cannot execute the required backend. The existing root `index.html` is frozen byte-for-byte, so merging this increment does not replace the live dashboard. The new service serves only `web/`, never that legacy root file. Do not cut over until the private host, rotated encrypted input, authorized source validation and operational sign-off are ready. No service, database, domain or paid resource is automatically provisioned by this repository.

The new service HTML in `web/` has no customer payload. Serving that directory statically shows a backend-required login shell; it cannot unlock private data. The frozen legacy Pages file retains its previously published ciphertext because the owner explicitly required the live site to remain unchanged. Import that ciphertext unchanged for archival, then rotate into a new private generation before enabling production service access.

## Local service

Python 3.12+ is required and used in CI and the container. There is no frontend build step.

```sh
python3.12 -m venv .venv
.venv/bin/python -m pip install -r requirements-dev.txt
```

Import the existing encrypted envelope or the previous single-file HTML into a directory **outside this checkout**:

```sh
.venv/bin/python scripts/import_encrypted.py /secure/previous-index.html /secure/rpd/current.enc.json --legacy-html
# Or: scripts/import_encrypted.py /secure/source.enc.json /secure/rpd/current.enc.json
```

The command copies ciphertext unchanged, validates its envelope, archives content-addressed encrypted snapshots, and records an explicit import timestamp plus append-only import history. Only an authorized sign-in can validate the decrypted business contract. Never add a decrypted workbook, real credential, private SQLite database or new encrypted production input to this public repository.

Production rejects legacy account envelopes. Prepare a private generation with a new data key and fresh accounts (passwords are entered through hidden prompts, never command-line arguments):

```sh
.venv/bin/python -m scripts.rekey_encrypted /secure/rpd/legacy.enc.json /secure/rpd/current.enc.json --administrator NEW_ADMIN --viewer NEW_VIEWER
```

An authorized legacy administrator is required. Business data is preserved; all new account wrappers/data keys are generated again. Original encrypted snapshots remain unchanged. Old account passwords must not be reused. This protects the new service, **not historical copies**: the old page/history can still be decrypted with old credentials until an independently approved legacy retirement/history policy is executed. Repeat the private-generation preparation for any subsequent legacy import; no automatic workbook synchronization is implied.

For loopback development only:

```sh
RPD_DEV=1 RPD_PUBLIC_ORIGIN=http://127.0.0.1:8765 \
RPD_DATA_PATH=/secure/rpd/current.enc.json RPD_STATE_DIR=/secure/rpd/state \
.venv/bin/uvicorn backend.main:app --host 127.0.0.1 --port 8765 --workers 1 --no-access-log
```

Open the loopback URL in the same browser machine. Use an existing authorized account. `RPD_DEV=1` is the explicit exception allowing non-Secure cookies for local HTTP; never enable it on a public host. The application does not load `.env` automatically; provide environment variables through your service manager or container configuration.

## Production operation

1. Choose a private host and persistent, encrypted-at-rest volume; put encrypted input, import manifests, snapshot archives and the SQLite ledger outside any web root. Set volume ownership to the service user (container UID 10001 if using the supplied Dockerfile).
2. Set `RPD_PUBLIC_ORIGIN` to the exact HTTPS origin, `RPD_DATA_PATH`, `RPD_STATE_DIR`, and optionally `RPD_DATA_OWNER`. Serve this application and its API under that same origin, at the origin root.
3. Put an HTTPS reverse proxy in front of the service. Preserve the public `Host`, forward the correct origin, set `FORWARDED_ALLOW_IPS` to the real trusted proxy IP(s) (never `*`), set a 32 KiB request-body cap, and redact query strings from proxy logs. The default trusts loopback only; container proxies need an explicit address. Do not expose the backend port directly.
4. Run **one Uvicorn worker**. Sessions and per-peer/account throttling are process-local; restarts revoke sessions. Each account retains at most five sessions. The decrypted dataset is shared privately per import, not copied per login. Horizontal scaling needs a shared session/rate-limit store first. Place an additional rate limit at the trusted proxy for internet-facing installations.
5. Back up the SQLite database using SQLite's online backup API (not a live `.sqlite3` file copy without its WAL), plus the encrypted snapshots/manifests. Verify restore under the same service identity.
6. Check an authorized administrator and aggregate viewer, real totals against the source workbook, duplicates/conflicts, permissions, refresh imports, PDF/XLSX/CSV scope, and follow-up persistence before cutover. A source-file replacement invalidates old sessions on their next request.
7. Coordinate credential/data-key rotation at cutover: older Git history contains the previously published ciphertext. This migration does not erase that history or revoke old encrypted copies. Do not rewrite repository history without explicit owner approval.

No production data is included with the container. `/health` reports configuration readiness only, not certification of business data. Authentication uses the original PBKDF2/AES-GCM account envelopes on the server; passwords are not stored by this service. A future organizational identity-provider migration remains possible without changing the reporting interface.

### Server-enforced permissions

| Capability | Aggregate viewer (existing `g`) | Administrator (existing `a`) |
|---|---|---|
| Executive/regional/area/team aggregates | Yes | Yes |
| Named individual surveyor drill-down | No; pseudonymized in legacy aggregates | Yes |
| PAM ID/customer records, legacy individual PDF | No | Yes |
| Outstanding exports | Status aggregates only | Filtered case-level report |
| Mapping, targets, readiness, rules, follow-ups, audit log | No | Yes |

Opaque session cookies are HttpOnly, SameSite=Strict, Secure in production, expire absolutely after one hour and after twenty idle minutes, and are revoked on logout/restart. Writes also require a same-origin request and a session CSRF token. Invalid credentials are throttled. Public routes use an explicit asset allowlist; the private data directory and repository files are never mounted as static content.

## Metrics and scope

See [data contracts and definitions](docs/data-contract.md). Original survey-row reports are retained in clearly labeled expandable sections; they use their original month/regional/area scope, not the new customer-cohort filters. Master stock always remains all-period and geography-only. Export definitions include these distinctions.

Missing target calendars, verified case starts/pauses, attendance, state snapshots, supply evidence or geographic boundaries result in **Insufficient Data**, not generated values. Authorized administrators can add evidenced monthly targets and area context without changing the source workbook. Follow-ups preserve the source status alongside manual operational status; source rows are never silently corrected or deleted.

## Validation

```sh
.venv/bin/python -m pytest -q
.venv/bin/python scripts/check_public.py
node --check web/app.js
node --check web/command-center.js
node --test tests/preset_scope.test.cjs
.venv/bin/python -m pip_audit --progress-spinner off
```

Tests use a deliberately synthetic source with duplicate PAM IDs, conflicting geography/status, missing IDs, real event-date versus survey-date distinctions, and both role envelopes. For UI verification, the test-only generator can create a private synthetic fixture; it requires runtime `RPD_FIXTURE_ADMIN_PASSWORD` and `RPD_FIXTURE_VIEWER_PASSWORD` and writes only outside the repository:

```sh
.venv/bin/python -m tests.fixtures /secure/synthetic-rpd.enc.json
```

Fixture account names are `fixture-admin` and `fixture-viewer`. Use generated temporary values, never real production passwords, and label the test server through `RPD_DATA_OWNER="SYNTHETIC TEST DATA — not production"`. Fixture checks do not certify real customer data, credentials or production operation.
