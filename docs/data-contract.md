# Data contracts, populations and scope

## Immutable source compatibility

The input is the existing `{u,i,c}` JSON envelope. Each user entry has `{r,s,i,k}`; `r=a` is administrator and `r=g` is aggregate viewer. User lookup remains the first sixteen hex characters of SHA-256(normalized user ID); a 500,000-iteration PBKDF2-SHA-256 key unwraps the AES-GCM data key; the data key decrypts the gzip-compressed JSON. All of this now runs server-side. Changing an HTML control or a browser variable cannot change API authorization.

The original data object contains `months`, `abs`, `reg`, `kels`, `svs`, `st`, `kl`, `A`, `S`, `E`, `P`, `W`, `meta`, `dic`, `rec`, and optionally `pdf`. The source is held privately; bootstrap has an allowlisted aggregate projection only. Guest surveyor names are pseudonymized. Source accounts/keys, record columns and legacy PDF never appear in bootstrap.

## Preserved legacy metrics

- `A`: `[month, area, canvassed rows, interested, uninterested, unknown, PTD, no building, Assign FA, Done, Outstanding, Cancel]`.
- `S`: `[month, area, coordinator index, surveyor index, canvassed rows, interested, Done, Assign FA, Outstanding, Cancel, ...]`. Its first six measures use a different order from `A`.
- `E`: `[event month, area, assigned FA events, installed-meter events]`.
- `P`: `[area, kelurahan, master potential, matched interested deduction, installed among matched interested]`.
- `W`: `[area, kelurahan, RW, RT, master potential, matched interested deduction]`.

The first month bucket can contain earlier dates (`s.d.`). The legacy reports retain their original calculations, grouping, seven-coordinator subtotal, named owner drill-down, and all-surveyor PDF. They are visibly labeled month/regional/area-only; advanced filters do not silently appear to apply to them. The master geographic hierarchy is not assumed to be a verified customer-coordinate or customer-RT mapping.

## New unique survey cohort

Record columns are `pam, ab, kel, sv, mi, t, c1, kf, fa, mt, kd, mf, pr, sc, tg`. They must all have the same length. Source dates use YYMMDD (YYYYMMDD is also accepted). Labels come from `dic`; source operational statuses are preserved, including unrecognized ones. No source row is deleted or rewritten.

1. Mandatory validity checks: positive numeric PAM ID of at most nine digits, valid survey date, and mappable area/kelurahan/surveyor indices. Source PAM IDs lose presentation-only leading zeros for matching; lookup restores regional display width.
2. Apply the selected survey-date window, regional, area, kelurahan, mapped coordinator and actual source installation-status filters to valid rows.
3. Exclude PAM IDs with conflicting area/kelurahan mappings anywhere in the imported source from unique geographic metrics; count and disclose the exclusion. Do not arbitrarily assign those customers to a region.
4. Count each remaining PAM ID once. Duplicate rows with conflicting interest or installation statuses are disclosed; they are not assumed interested/installed. Conflict detection precedes status filtering, so selecting Done never makes a contradictory duplicate appear resolved. No “latest” status is guessed without a reliable event-history contract. Priority backlog counts only consistent unique interested customers that are neither Done nor Cancel.
5. `Interested / canvassed` and `installed / interested` use this same selected cohort. Installed requires consistent `Berminat` and `Done`. A zero denominator is unavailable, not 0%.

This is conservative decision support, not a source correction. Conflicted customers remain visible through authorized row-level lookup and source-quality counters. Team memberships can overlap, so team-level unique subtotals are not necessarily additive.

## Stock versus events versus historical state

- **Master potential/remaining**: snapshot stock, all periods, filtered only by regional/area/kelurahan. Remaining = potential minus matched interested deduction, not minus every interested survey row.
- **Coverage of master**: unavailable. The source does not provide a verified eligible-master-to-survey unique-customer linkage for the selected cohort.
- **Survey activity**: actual survey dates, with the current import's canvassing/installation statuses. Daily/ISO-week/month bars count each PAM once within that bucket; the same PAM can appear in several buckets. Buckets are not additive unique totals or attendance records.
- **Installation events/targets**: actual installation date, unique PAM IDs with Done, excluding conflicting geography. These are separate from installed customers in a survey-date cohort. A customer can have an installation-date record inconsistent with another duplicate row; these are source event records, not proof of a clean state history.
- **Previous period**: earlier dated survey cohorts using today's imported statuses, never end-of-period state snapshots. Month windows compare the same number of preceding calendar months; explicit date windows compare the same number of preceding calendar days. Coverage uses valid actual dates constrained by declared source bounds, not the opening bucket's month label; that bucket can contain earlier surveys. No comparison is produced if the earlier full window is outside that coverage or the current lower bound is open-ended. Status conflicts in daily/weekly/monthly trends are evaluated within each bucket before filtering, never inherited from a different bucket.
- **Targets**: evidenced month + exact regional/area scope. All selected months must have targets; partial date windows, kelurahan, status and coordinator filters do not reuse a broader target. Required daily performance/forecast is unavailable without a verified working calendar. Targets are append-only operational settings, not fabricated historical target versions.

## Team productivity and priorities

Observed surveyor-days are distinct `(surveyor, survey date)` pairs with valid recorded activity. Interested per observed day is explicitly not attendance-based productivity or a manpower-adjusted fairness score. Done attribution follows the survey cohort's surveyor association, not the installation crew. The original source active/resigned/supervisor mapping remains distinct from attendance.

Priority is triage, not a canvassing readiness declaration. Administrators can adjust minimum sample, high backlog/interest threshold and low interest/canvassed threshold; every update is audited. Evidence-backed constrained supply yields Requires Supply Improvement. Otherwise both supply and installation readiness must be confirmed ready; insufficient sample yields Insufficient Data. With sufficient evidence, low interest is Cooling Down, high backlog is High Priority, remaining backlog is Medium Priority, and no backlog is Low Priority. Remaining potential alone never makes an area High Priority. These are transparent configurable rules, not a trained model or geographic clustering algorithm.

## Outstanding and actions

Source pending = interested rows whose original installation status is neither Done nor Cancel; all other source status labels remain intact. A case reference is SHA-256 of normalized PAM ID + stable regional/area-name identity + survey date, shortened to 24 hex characters. Targets and readiness use that same stable identity, not the import's area index. Reordering the source does not reassign actions; substantive area renames require authorized reconciliation, never a guessed remapping. Duplicate regional/area identities fail contract validation. It is a record-based reference, not an assertion of a legally canonical customer case. Exact duplicate references are grouped for follow-up, while their source rows remain counted separately.

Manual action status never overwrites source status. Source pending references manually marked Done/Cancel are separately identified as resolved since import and excluded from active aging. A target completion date before today on an active reference makes a follow-up overdue.

Aging uses an administrator-confirmed case start date and cumulative verified paused calendar days. No start means Insufficient Data; survey/FA dates are not silently substituted. Buckets are 0–3, 4–7, 8–14, 15–30, >30 days, as of the displayed current server date. Every action preserves PIC, operational status, action, deadline, resolution notes, start/pause confirmation, timestamp and actor in an append-only SQLite ledger. API history pagination can retrieve older entries without deleting them.

## Source quality and provenance

Imported/valid counts are computed from record columns. Duplicate excess rows = sum(count per valid normalized PAM − 1); duplicate customers = number of repeated PAM IDs. Missing mandatory fields and unmatched indices are separate counters; these categories may overlap and should not be added as mutually exclusive errors.

Source reconciliation counters in `meta.sync` retain their original names and meanings. They are not synchronization-error logs. The import manifest timestamp is a successful encrypted-file import time, not the source workbook's refresh time. Session source-load time and survey-date range are shown separately. No successful synchronization, data-owner identity or historical business snapshot is invented.

## Exports and permissions

Executive, regional, area, team and outstanding CSV/XLSX/PDF exports call the same filtered analysis as the screen. Each includes title, survey period, filters, source import/load timestamps, fingerprint, role and metric definitions. Master stock's different scope is explicit. Guest outstanding reports contain status aggregates only; case-level exports and the unfiltered legacy individual PDF require administrator authorization. The old PDF is distinctly labeled as all-surveyor/unfiltered, not presented as a filtered report.

CSV/XLSX source strings are protected against formula execution; PDF text is escaped and long actions can span pages. Outstanding case exports retain the original source status alongside manual status, resolution notes, confirmed start/pause, active/resolved state and aging; manually closed cases are explicitly labeled, not misrepresented as active. Exports above 20,000 rows (2,000 for PDF) are refused with a narrow-filter message, never silently truncated.

Saved presets bind to month labels, stable area identities and kelurahan names rather than import indices. Removed or unverifiable saved scopes require an explicit resave; they never silently widen the report. Moving an implicit lower bound into or out of the open-ended opening bucket also requires a resave, unless the preset already has an explicit start date. The backend rejects out-of-range geography with HTTP 422 consistently for analytics, exports and record search.
