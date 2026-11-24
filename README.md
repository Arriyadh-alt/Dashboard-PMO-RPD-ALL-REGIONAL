# PMO RPD Command Center

Five Bahasa Indonesia workspaces: **Ringkasan, Data Wilayah, Kinerja Tim, Outstanding, Cari PAM ID**, with authorized settings and advanced/original reports in Admin or expandable detail views. **Deployment stays on free GitHub Pages; no company server or paid host.**

## V4 — source accuracy, not another redesign

V4 keeps the five menus, existing encryption/account wrappers and Pages workflow.
All historical **Berminat** membership comes from normalized Update column **Q**;
V4 intake checks its PAM membership against **AO**, and checks that **AI** partitions
that population into Done / Assign FA / Outstanding / Cancel. Cancel remains in
historical interest, not active installation progress. Survey geography comes from
**D/E/I**, never H (Flag Data). Installation/FA events retain **AW/AU** dates.

The existing approved populations are intentionally different:

| Metric | Definition |
|---|---|
| Total Potensi | MASTER DATA `FINAL FLAG = POTENSI` |
| Tercanvassing | All valid unique Update PAM IDs, including `Belum Diketahui` |
| Berminat / Terpasang | All Update Column Q Berminat / AI Done, not master-only |
| Sisa Potensi | Eligible master stock minus **its matched** interested PAMs |
| AP / U Potensi Reconnection | Separate original classifications, not Total/Sisa Potensi |
| Active potential | No separately approved formula; unavailable rather than invented |
| Outstanding | AI `Outstanding` only; Assign FA is a separate active queue |

The new encrypted `G` cube reconciles all survey performance at each geography,
including `RT/RW Belum Terpetakan`. Master RW/RT is used only when the joined
survey/master geographic context agrees; disagreements are counted, not silently
overwritten. `P` and legacy `W[0..7]` retain their established meanings. Remaining
stock deducts only eligible-master interest, so it is **not** Total Potensi minus
all historical Berminat outside that population. Field counts cover all periods;
the caption distinguishes them from date-filtered survey reports.

`python -m scripts.workbook_intake INPUT.xlsx PRIVATE_INTAKE.json` now defaults to
V4 and also accepts `.xlsb`. Sheets are discovered by header signatures, not date
suffixes. Header positions are audited; inserted columns are mapped by header.
`--legacy-layout` reproduces old intake for audits only; V4 sources reject that
layout on subsequent refresh. Continue with `scripts.workbook_contract` using the
authorized encrypted source, reviewed private roster aliases and `--full-snapshot`,
then `scripts.publish_v3` and `scripts.build_pages --bundle-dir` as below. All
plaintext remains outside this checkout. Invalid IDs, ambiguous duplicates,
inconsistent interest/status membership and unreconciled field cubes stop the
release; existing published files remain unchanged until an authorized PR merges.
The original textual PAM display is retained separately from its normalized key.
Customer admin-note/reason text is reduced to presence flags, not republished.

Public retains only the approved aggregate schema, with an optional report date
separate from actual survey-through date. Guest/Admin share the same validated
source/cubes; protected `G`, record dictionaries and issue categories remain
encrypted. Outstanding tables/exports use the same AI-only population; supporting
issue categories can overlap and must not be added together. `Case Closed` is
displayed as its original category, never labelled unresolved illegal.

## GitHub Pages — selected deployment

Keep the existing Pages configuration: **main branch, root `/`**. Merging publishes the updated dashboard. Relative asset paths and `.nojekyll` preserve repository hosting and local runtime assets. Nothing is provisioned.

Sign-in retains PBKDF2-500,000/SHA-256/AES-GCM/gzip. The initial Ringkasan and aggregate geography/time filters use identity-free additive cubes **only after proving one valid row per PAM**; JavaScript/Python parity tests cover unique metrics, stock, regions, areas, trends, dates and previous periods. Duplicate/ambiguous owner snapshots fall back to the unchanged Python analytics. Detailed team, case, diagnostics and exports load self-hosted Python/WASM only when needed. Bootstrap is no longer requested twice. CSV/XLSX/PDF retain their existing report models and calculation definitions.

**V3 access model:** Public visitors see only `pages/public-summary.json`: the five approved KPIs, regional totals and monthly performance trend. No operational JavaScript, account manifest, encrypted source, customer record, staff name, kelurahan or RW/RT data is requested before choosing **Masuk**. Missing public data shows an empty state, never a protected-data fallback.

Internal **Guest** now has all five operational menus, named team drilldowns, PAM lookup, outstanding details, RT/RW potential and read-only reports. This intentionally supersedes V2's aggregate-only Guest restriction. Admin retains existing tools, local follow-ups/settings/mappings, exports and the daily workbook workflow. Guest's encrypted full snapshot excludes the Admin-only access-management sidecar. Both Admin logins and the existing Guest wrappers remain unchanged; Guest cannot decrypt the Admin-key envelope.

Login downloads only a role-specific encrypted overview (about 104 KB), not the full operational source (about 2.28 MB). The full snapshot is decrypted on the first detailed workspace/report request; Python/WASM remains deferred until detailed analytics/search/export needs it. Two recent detailed analysis scopes are cached across menu transitions and invalidated on local mutations.

**Honest static-hosting limit:** this is encryption and browser-side presentation policy, **not trusted backend authorization**. The controller, worker and local adapter reject Guest mutations/Admin routes, but a person controlling their own browser can inspect decrypted data and modify their own local copy. **No dashboard role can write shared records through Pages:** canonical changes require an authorized GitHub workbook PR. Admin local history is encrypted per account/browser and is not shared with Guest or other Admins. Ciphertext is publicly downloadable through direct URLs, and previously published ciphertext/password access cannot be revoked retrospectively. A backend would add server-enforced sessions/roles, centralized writes/history, throttling and revocation; none is provisioned or added in V3. No plaintext customer records or passwords are persisted.

### Field potential definitions and source parity

Data Wilayah adds searchable Regional → Area Bisnis → Kelurahan → RW → RT controls. Choosing RW immediately shows RT rows; selections survive workspace navigation within the session. Mobile collapses the selected area context, leaving RW/RT checking close at hand. Unknown RW/RT remain explicit, not silently excluded.

All five field metrics use **eligible MASTER DATA potential, all periods**, not the broader survey cohort. `W[0..6]` retain area/kelurahan/RW/RT/potential/matched-interested/installed exactly; new `W[7]` counts master potential PAM IDs found in the survey workbook. Sisa remains **potential − matched interested**, not potential − canvassed. Period/team/status filters do not change master stock. The one-time V3 enrichment checked all 20,102 RW/RT groups, reconciled W to P at every kelurahan, and preserved every other source field and the original PDF. Historical snapshots without the extra column show unavailable canvassing, not invented zeros.

### Paired daily publication

`scripts.publish_v3` preserves Admin/Guest wrappers, uses fresh IVs and emits four paired encrypted files plus the strictly allowlisted public projection. `scripts.build_pages --bundle-dir` validates matching snapshot IDs, wrappers, fingerprints and public totals before replacing release assets. A stale/mixed generation is rejected. The previous V2 split/update tools remain for historical envelopes; V3 envelopes require the full V3 release workflow below. Plaintext, keys, passwords and roster aliases stay outside the repository.

### Performance evidence

The real 199,659-row baseline at `88cb5f6` took **25.118 s cold / 25.094 s warm** from submit to usable overview on the session VM. Immediate feedback was **0.7 / 0.3 ms**; Python preparation was about **6 s** and first analysis **13.5–13.9 s**. Aggregate-first browser analysis at `f72c44b` reduced bootstrap to **1.473 / 1.495 s** and usable overview to **1.549 / 1.534 s**, without changing the source records or calculations. These are loopback desktop Chrome measurements, not WAN/mobile guarantees; [the V2 PR](https://github.com/Arriyadh-alt/Dashboard-PMO-RPD-ALL-REGIONAL/pull/6) records exact-revision validation. Do not infer speed from a small synthetic fixture or report shell-only timing as browser performance.

#### V3 same-VM comparison

V3 was remeasured against the retained V2 bundle on the same desktop loopback setup, using the actual production-sized dataset and both existing Admin accounts. Single cold/warm trials (milliseconds), recorded at [the validated V3 revision](https://github.com/Arriyadh-alt/Dashboard-PMO-RPD-ALL-REGIONAL/commit/bc72fd2e4fd3e220f7da688875b57b35625b25b0):

| Measurement | Cold | Warm |
|---|---:|---:|
| Retained V2 submit → usable overview | 926.0 | 928.4 |
| V3 submit → bootstrap | 451.6 | 396.9 |
| V3 submit → usable painted overview | 499.9 | 447.3 |
| V3 immediate feedback | 0.7 | 0.5 |
| V3 Public navigation → usable | 52.0 | 26.6 |

First detailed **field** navigation painted in 349.4 ms; revisiting took 63.5 ms. Login fetched the 104,203-byte encrypted overview, not the 2,281,455-byte operational payload. Key derivation was the largest measured login cost (~406/352 ms). Python-heavy reports still incur their deferred runtime startup; field timings do not certify every report, WAN or mobile speed.

Synthetic Public/Guest/Admin validation covered the five field metrics, team/preset retention, read-only Guest guards, encrypted Admin local persistence and CSV/XLSX/PDF. A 400px viewport reached RT in three field selections after area context, without document overflow; selections are not individual keystrokes. Both real Admin logins reached usable owner overviews. Real Guest login and deployed-network performance remain untested; browser guards do not establish trusted server authorization. No production customer/staff screenshots or recordings were captured.

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
.venv/bin/python -m scripts.publish_v3 pages/data.enc.json /secure/validated-daily.json /secure/release-NEW --approve-public-summary
# Verify the printed unique totals against the Excel workbook before publishing.
.venv/bin/python -m scripts.build_pages --bundle-dir /secure/release-NEW
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
