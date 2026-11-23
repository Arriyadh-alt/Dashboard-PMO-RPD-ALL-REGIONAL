# PMO RPD Command Center

Seven decision-support workspaces, original operational reports, unique-customer metrics, filter-aware exports and encrypted customer data. **The selected deployment is the existing free GitHub Pages site; no company server or paid host is required.**

## GitHub Pages — selected deployment

Merging this change intentionally replaces the old root page with the seven-workspace command center. Keep the existing Pages configuration: **main branch, root `/`**. The site uses relative paths, so the repository URL works without a custom domain. `.nojekyll` preserves the local WebAssembly/runtime assets. No API, server, database provisioning, SaaS account or infrastructure deployment is needed.

The existing ciphertext/account wrappers are preserved, now in `pages/data.enc.json` instead of inside HTML. Sign-in uses the same PBKDF2-500,000/SHA-256/AES-GCM/gzip contract in Web Crypto. The reviewed Python analytics run locally in a worker through self-hosted Pyodide; counts are not reimplemented with different JavaScript formulas. CSV/XLSX use the same report model; text-only PDF tables use bundled jsPDF/AutoTable with repeated headers, wrapping and pagination. Browser exports do not ship Pillow or any Python image decoder.

**Accepted access model:** encrypted data is publicly downloadable, including from Git history. Anyone with a valid password can decrypt **every customer**, even if their UI presents aggregate-only views. Presentation roles, local history and browser encryption are not server-enforced authorization. There are no HttpOnly sessions, server throttling, shared audit ledger or remote session revocation in this mode. Use a current Chrome/Edge/Firefox/Safari with Web Crypto, gzip streams and WebAssembly. Local edits require Web Locks; unsupported browsers remain report-readable. Initial loading downloads a self-hosted runtime; repeat visits reuse normal browser caches. No decrypted customer records or passwords are persisted.

### Follow-ups and settings are browser-local

Follow-ups, mappings, targets and readiness/rules changes are encrypted in local browser storage under an account-derived key, separate from the daily source key. They survive reloads and daily data replacement **on that account/browser only**. They are **not shared or synchronized with teammates**, and they are not tamper-proof audit evidence. Existing metrics distinguish imported statuses from local manual changes. Aging uses the displayed device date; keep the device clock correct.

Use **Cadangan riwayat lokal terenkripsi** to download an encrypted backup before clearing storage or moving devices. Restore is allowed only into empty local history for the same dashboard, account and password; it never silently replaces current history. Backups retain their original password. Credential changes require a deliberate migration of these backups using the previous credentials; simply changing the login does not re-encrypt history. Another tab changing history causes a reload/re-login warning rather than a lost update. A full/unavailable browser store refuses the write instead of claiming it was saved. Keep encrypted backups separately; browsing in private mode can discard local storage.

Legacy `rpd_ov` mappings are retained on Pages upgrades. After owner sign-in, review their positional surveyor-index preview against the old roster and explicitly confirm identities before importing into encrypted history. Existing encrypted mappings take precedence. Unmatched/malformed legacy data stays downloadable for manual reconciliation; the old key is removed only after a successful encrypted save, never at page startup.

### Daily Excel updates

Mapping edits/reset affect the current surveyor roster. Overrides for absent surveyors are retained by name and resume if that surveyor returns in a later snapshot.

After a same-account password change, unreadable local history is retained: reports stay available with a source-only warning, edits are blocked, and the backup button downloads the original ciphertext. Use the previous-password recovery control to validate the old history and re-encrypt it under the current login password. A wrong previous password never overwrites the saved copy.

Send the daily Excel file to the Bot. **The first workbook is needed to verify its sheet/column mapping; an authorized existing administrator credential is needed to preserve current logins when encrypting updates.** This repository does not guess an unprovided Excel layout. Confirm whether it is a complete snapshot or incremental input, reconcile unique counts, periods, master stock and duplicates, and create the documented columnar data contract outside the repository. Never append an already-cumulative workbook or label retained master data as freshly updated. Share operational notes through an agreed source workbook if they must reach the whole team; browser-local history is not that shared source.

### Verified Excel Binary intake

The supplied RPD binary workbook has one `Update ...` sheet and one `MASTER DATA` sheet. The read-only adapter validates column names rather than assuming positions, respects the workbook's 1900/1904 date system, and reads cached values without running Excel, macros or external links. It selects only dashboard-required fields; customer names, addresses, telephone numbers, identity-document links, coordinates and free-text customer notes are excluded. The resulting intake still contains sensitive PAM IDs and surveyor names and must remain outside Git and the public site.

```sh
.venv/bin/python -m pip install -r requirements-import.txt
.venv/bin/python -m scripts.workbook_intake /secure/report.xlsb /secure/intake-NEW.json
```

The command prints aggregate counts and actual survey/FA/meter date ranges, and writes a new private file with mode `0600`; it refuses an existing output or any workbook/output inside the repository. A filename date is not treated as a survey date or a verified refresh timestamp. Layout changes fail with the missing column names instead of silently selecting different data.

**Intake is not publication.** It does not infer snapshot/incremental semantics, rebuild coordinator aliases, replace the current encrypted contract or modify existing logins. Compare it with the authorized previous contract, reconcile the source fields/legacy classifications and roster mappings, then use the validated-contract encryption workflow below. A workbook alone cannot recover the existing encryption key or administrator password.

After that review, the repeatable encrypted publishing path is:

```sh
# Plaintext contract and new encrypted generation stay outside this checkout.
# Passwords are prompted privately (or supplied through secure process environment).
.venv/bin/python -m scripts.update_encrypted pages/data.enc.json /secure/validated-daily.json /secure/daily-NEW.enc.json
# Verify the printed unique totals against the Excel workbook before publishing.
.venv/bin/python -m scripts.build_pages /secure/daily-NEW.enc.json
.venv/bin/python scripts/check_public.py
```

Open a PR containing the encrypted source, public manifest and rebuilt entrypoint. The user merges it as before; GitHub Pages publishes it. Do not commit the workbook, plaintext contract, credentials, local browser backups or private state databases. The publisher rejects plaintext-shaped JSON and checks the encrypted envelope; an authorized data check remains required. `published_at` means encrypted-file publication, **not** a claimed workbook refresh. The stable `ledger_salt` must be preserved across daily builds so local history remains readable. Old ciphertext/password access cannot be revoked retrospectively; use the rekey helper for an intentional new data key/accounts when rotating credentials.

For code-only changes, run `python -m scripts.build_pages` without a source argument. This rebuilds `pages/engine.zip` and hash-versioned entrypoint without changing the encrypted snapshot, publication time or local-history key salt. Dependencies are already self-hosted and pinned; changing them requires `npm ci --ignore-scripts`, `python -m scripts.vendor_browser_runtime`, the build, audits and review. See `pages/vendor/NOTICE.md` for provenance/licenses.

## Optional private service (not required for Pages)

Pages PDF uses built-in WinAnsi fonts. Unsupported characters (for example arrows/emoji in notes) are printed as explicit `\u{HEX}` notation with a disclosure, rather than corrupting surrounding words. Choose CSV/XLSX for verbatim Unicode text. Source records and stored notes are never rewritten by PDF formatting.

The previously implemented FastAPI deployment remains available separately. It serves `web/`, which contains no customer payload and requires the private API. The following sections apply **only** if a private host is independently selected later; they do not describe Pages security. No service, database, domain or paid resource is provisioned automatically.

### Local private service

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

The command copies ciphertext unchanged, validates its envelope, archives content-addressed encrypted snapshots, and records an explicit import timestamp plus append-only import history. Only an authorized sign-in can validate the decrypted business contract. For this private deployment, keep its separate encrypted input outside the repository/web root. The only approved public encrypted input is the selected Pages asset described above.

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

### Private-service production operation

1. Choose a private host and persistent, encrypted-at-rest volume; put encrypted input, import manifests, snapshot archives and the SQLite ledger outside any web root. Set volume ownership to the service user (container UID 10001 if using the supplied Dockerfile).
2. Set `RPD_PUBLIC_ORIGIN` to the exact HTTPS origin, `RPD_DATA_PATH`, `RPD_STATE_DIR`, and optionally `RPD_DATA_OWNER`. Serve this application and its API under that same origin, at the origin root.
3. Put an HTTPS reverse proxy in front of the service. Preserve the public `Host`, forward the correct origin, set `FORWARDED_ALLOW_IPS` to the real trusted proxy IP(s) (never `*`), set a 32 KiB request-body cap, and redact query strings from proxy logs. The default trusts loopback only; container proxies need an explicit address. Do not expose the backend port directly.
4. Run **one Uvicorn worker**. Sessions and per-peer/account throttling are process-local; restarts revoke sessions. Each account retains at most five sessions. The decrypted dataset is shared privately per import, not copied per login. Horizontal scaling needs a shared session/rate-limit store first. Place an additional rate limit at the trusted proxy for internet-facing installations.
5. Back up the SQLite database using SQLite's online backup API (not a live `.sqlite3` file copy without its WAL), plus the encrypted snapshots/manifests. Verify restore under the same service identity.
6. Check an authorized administrator and aggregate viewer, real totals against the source workbook, duplicates/conflicts, permissions, refresh imports, PDF/XLSX/CSV scope, and follow-up persistence before cutover. A source-file replacement invalidates old sessions on their next request.
7. Coordinate credential/data-key rotation at cutover: older Git history contains the previously published ciphertext. This migration does not erase that history or revoke old encrypted copies. Do not rewrite repository history without explicit owner approval.

No production data is included with the container. `/health` reports configuration readiness only, not certification of business data. Authentication uses the original PBKDF2/AES-GCM account envelopes on the server; passwords are not stored by this service. A future organizational identity-provider migration remains possible without changing the reporting interface.

#### Server-enforced permissions (private service only)

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
node --check pages/browser.js
node --input-type=module --check < pages/analysis-worker.js
node --check pages/pdf.js
node --test tests/preset_scope.test.cjs
npm ci --ignore-scripts
node tests/browser_engine.test.cjs
npm audit --audit-level=low
.venv/bin/python -m pip_audit -r pages/vendor/requirements-audit.txt --no-deps --disable-pip
.venv/bin/python -m pip_audit --progress-spinner off
```

Tests use a deliberately synthetic source with duplicate PAM IDs, conflicting geography/status, missing IDs, real event-date versus survey-date distinctions, and both role envelopes. For UI verification, the test-only generator can create a private synthetic fixture; it requires runtime `RPD_FIXTURE_ADMIN_PASSWORD` and `RPD_FIXTURE_VIEWER_PASSWORD` and writes only outside the repository:

```sh
.venv/bin/python -m tests.fixtures /secure/synthetic-rpd.enc.json
```

Fixture account names are `fixture-admin` and `fixture-viewer`. Use generated temporary values, never real production passwords, and label the test server through `RPD_DATA_OWNER="SYNTHETIC TEST DATA — not production"`. Fixture checks do not certify real customer data, credentials or production operation.
