# PMO RPD Command Center

Five Bahasa Indonesia workspaces: **Ringkasan, Data Wilayah, Kinerja Tim, Outstanding, Cari PAM ID**, with authorized settings and advanced/original reports in Admin or expandable detail views. **Deployment stays on free GitHub Pages; no company server or paid host.**

## GitHub Pages — selected deployment

Keep the existing Pages configuration: **main branch, root `/`**. Merging publishes the updated dashboard. Relative asset paths and `.nojekyll` preserve repository hosting and local runtime assets. Nothing is provisioned.

Sign-in retains PBKDF2-500,000/SHA-256/AES-GCM/gzip. The initial Ringkasan and aggregate geography/time filters use identity-free additive cubes **only after proving one valid row per PAM**; JavaScript/Python parity tests cover unique metrics, stock, regions, areas, trends, dates and previous periods. Duplicate/ambiguous owner snapshots fall back to the unchanged Python analytics. Detailed team, case, diagnostics and exports load self-hosted Python/WASM only when needed. Bootstrap is no longer requested twice. CSV/XLSX/PDF retain their existing report models and calculation definitions.

**Current access model:** Admin-only `pages/data.enc.json` has a freshly generated customer-data key. Guest-only `pages/guest.enc.json` contains counts by survey/installation date and regional/area/kelurahan, master stock, date coverage and geographic labels—**no PAM IDs, roster names, staff mappings, customer dictionaries, arrears, PDFs, operational notes or local events**. Guest credentials retain their old wrapped key, which cannot decrypt the newly protected Admin payload. Admin passwords must be provided once to rewrap the new key; no account is silently disabled. Guest can use Ringkasan and Data Wilayah only; lookup, team, outstanding details, Admin and exports are not granted.

This is cryptographic separation of static data, **not backend authorization**. Hiding buttons or changing browser role flags cannot produce the Admin key. Both encrypted files are publicly downloadable. **Historical full snapshots remain in public Git history and cannot be revoked: previously authorized Guest passwords can still decrypt those older snapshots.** There are no server sessions, server throttling, shared audit ledger or remote revocation. Removing those historical copies or revoking previously obtained data is outside this change. No decrypted customer records or passwords are persisted.

### One-time access migration and subsequent refreshes

Run `python -m scripts.split_access OLD_ENVELOPE PRIVATE_ADMIN_OUTPUT PRIVATE_GUEST_OUTPUT` outside Git using authorized Admin credentials via secure environment bindings/prompts. Provide the second Admin through `RPD_SECOND_ADMIN_ID` / `RPD_SECOND_ADMIN_PASSWORD`. The tool refuses missing Admin credentials; `--disable-other-admins` is only for an explicitly approved account retirement. Review/decrypt both outputs and verify Guest-key failure against the Admin payload before publication. Publish the pair with `python -m scripts.build_pages PRIVATE_ADMIN_OUTPUT --guest-source PRIVATE_GUEST_OUTPUT`.

For subsequent daily refreshes, `scripts.update_encrypted` requires `--guest-output PRIVATE_GUEST_OUTPUT` for a protected source. It preserves the current Admin and Guest wrappers, rebuilds the Guest projection from the same validated contract and uses fresh payload IVs. Always publish the pair together. `check_public.py` blocks production publication without separate role-specific envelopes and matching fingerprints. Plaintext contracts, keys, passwords and aliases stay outside the repository.

### Performance evidence

The unchanged real 199,659-row baseline at `88cb5f6` took **25.118 s cold / 25.094 s warm** from submit to usable overview on the session VM. Immediate feedback was **0.7 / 0.3 ms**; Python preparation was about **6 s** and first analysis **13.5–13.9 s**. These are loopback browser measurements, not claims about WAN/mobile performance. Final before/after results belong in the PR after revision validation; do not infer speed from a synthetic small fixture or report a shell-only timing as browser performance.

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

The command prints aggregate counts, actual survey/FA/meter date ranges and normalized cross-sheet geography differences, and writes a new private file with mode `0600`; it refuses an existing output or any workbook/output inside the repository. PAM IDs use the existing matching normalization; nonempty invalid IDs retain `pam_raw` for private correction and every row keeps its workbook row number. Regional/area comparison strips only the verified `Regional ` / `AB ` prefixes, case and repeated whitespace; it does not correct either source. Duplicate IDs remain counted, but their geographic comparisons are withheld rather than choosing an arbitrary row. A filename date is not treated as a survey date or a verified refresh timestamp. Layout changes fail with the missing column names instead of silently selecting different data.

**Intake is not publication.** It does not infer snapshot/incremental semantics, rebuild coordinator aliases, replace the current encrypted contract or modify existing logins. Version 2 additionally selects the PMO recommendation and **Total_Tunggakan_&_Denda**, which is the existing contract's `tg` value (not bare `Tunggakan`). Old version 1 intakes must be regenerated. A workbook alone cannot recover the existing encryption key or administrator password.

### Verified cumulative-workbook mapping

The authorized mapper preserves the existing area/kelurahan/surveyor indices, curated names, roster statuses, coordinator assignments and first `s.d.` month bucket. It rebuilds every record column, the legacy `A/S/K/E` survey/event groups, `P/W` master stock and reconciliation counters. Interest deductions follow the master geography, not a conflicting survey location. Dates come from actual date columns; filename/Month/Year labels are not used. New reporting months are appended when needed. Changed snapshots regenerate the unfiltered all-surveyor PDF from the current source totals rather than silently retaining yesterday's PDF.

The private alias sidecar associates workbook labels with the existing curated roster; it is sensitive and must not enter Git. Bootstrap it **only from an already-matching baseline workbook**. Bootstrap uses PAM associations, then requires exact parity of *all* record columns, classifications, metadata and aggregate groups before writing anything. It preserves the baseline's curated identities; it is not a general-purpose fuzzy-name match or proof that a changed personnel label is the same person.

```sh
# Existing administrator credentials are prompted privately, or bound securely as
# RPD_UPDATE_ACCOUNT / RPD_UPDATE_PASSWORD. Never put credentials in commands.
.venv/bin/python -m scripts.workbook_contract pages/data.enc.json /secure/intake-NEW.json /secure/validated-NEW.json \
  --full-snapshot --aliases /secure/roster-aliases.json --bootstrap-aliases
# Subsequent complete snapshots reuse that private sidecar (omit bootstrap).
.venv/bin/python -m scripts.workbook_contract pages/data.enc.json /secure/intake-NEXT.json /secure/validated-NEXT.json \
  --full-snapshot --aliases /secure/roster-aliases.json
```

`--full-snapshot` is an explicit operator confirmation, not something the mapper infers. Invalid/duplicate PAMs, missing existing survey/known-master IDs, unfamiliar geography/classifications, unknown surveyors and ambiguous coordinator assignments stop conversion for review; no records are guessed, appended twice or silently deleted. New surveyors or legitimate removals require a separately reviewed source/roster migration. Master IDs never represented in the baseline survey cannot be reconstructed from its aggregates, so the operator must still verify complete master-sheet coverage. The mapper is deliberately not an incremental-data importer.

The command writes a new private contract with mode `0600` and prints aggregate results only; all plaintext input/output paths must be outside this repository. If it reports `changed: false`, the workbook is already represented: **skip encryption and publication**, preserving the live ciphertext, existing logins, local-history salt and publication timestamp. If `changed: true`, check totals and use the encrypted publishing workflow below. Neither mapping nor encryption publishes anything by itself.

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
