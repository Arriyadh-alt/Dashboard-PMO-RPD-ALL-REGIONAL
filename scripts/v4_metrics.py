"""V4 audited populations, without changing legacy W/P or inventing potential.

G: area, kelurahan, RW, RT, eligible master stock, all surveyed PAMs,
historical interested PAMs, Done PAMs, eligible-master interested deductions.
The last measure is intentionally NOT all historical interested customers.
"""
from collections import defaultdict

from scripts.workbook_intake import header, text


EXTRA_RECORD_FIELDS = {'it', 'il', 'fs', 'an', 'ir', 'pd'}


def validate_intake(intake):
    if intake.get('layout_version') != 4:
        raise ValueError('V4 metrics require the V4 workbook intake')
    for kind in ('survey', 'master'):
        values = intake['summary'][kind]
        if any(values[key] for key in ('invalid_pam_rows', 'duplicate_excess_rows')):
            raise ValueError('Invalid, duplicate or normalization-colliding PAM IDs require review')
    survey = intake['survey']
    if any((header(row['minat']) == 'berminat') != (header(row['result']) == 'berminat') for row in survey):
        raise ValueError('Column Q / AO Berminat membership differs; retain previous valid release')
    if any((header(row['minat']) == 'berminat') !=
           (header(row['installation_status']) in {'done', 'assign fa', 'outstanding', 'cancel'}) for row in survey):
        raise ValueError('Installation status partition does not reconcile with Column Q Berminat')


def enhance(data, intake, survey, master, ordered_ids, location, neighborhood):
    validate_intake(intake)
    groups = defaultdict(lambda: [0] * 5)
    unmapped, geography_mismatches = 0, 0

    def place(row):
        rw, rt = neighborhood(row['rw']), neighborhood(row['rt'])
        return rw, rt if rw else 0

    def interested(row):
        return bool(row and header(row['minat']) == 'berminat')

    for pam, row in master.items():
        if header(row['master_flag']) != 'potensi':
            continue
        key = (*location(row, True), *place(row))
        groups[key][0] += 1
        groups[key][4] += interested(survey.get(pam))
    for pam in ordered_ids:
        row, matched = survey[pam], master.get(pam)
        area, kel = location(row)
        same_geography = matched is not None and (area, kel) == location(matched, True)
        geography_mismatches += matched is not None and not same_geography
        rw, rt = place(matched) if same_geography else (0, 0)
        unmapped += not rw or not rt
        values = groups[area, kel, rw, rt]
        values[1] += 1
        values[2] += interested(row)
        values[3] += header(row['installation_status']) == 'done'
    data['G'] = [list(key) + value for key, value in sorted(groups.items())]
    rec = data['rec']
    rec['it'] = [int(interested(survey[pam])) for pam in ordered_ids]
    rec['pd'] = [survey[pam]['pam_display'] for pam in ordered_ids]
    for code, field in [('il', 'illegal_flag'), ('fs', 'file_status')]:
        labels = sorted({text(survey[pam][field]) for pam in ordered_ids})
        data['dic'][code] = labels
        indexes = {label: i for i, label in enumerate(labels)}
        rec[code] = [indexes[text(survey[pam][field])] for pam in ordered_ids]
    for code, field in [('an', 'admin_note_present'), ('ir', 'incomplete_reason_present')]:
        rec[code] = [int(survey[pam][field]) for pam in ordered_ids]
    data['meta'].update(reporting_date=intake.get('reporting_date'),
        workbook_sha256=intake['workbook_sha256'], geographic_survey_unmapped=unmapped,
        geographic_join_mismatches=geography_mismatches,
        metric_definitions={
            'interested': 'Column Q normalized Berminat, checked against AO at record level; all historical installation statuses.',
            'canvassed': 'Existing approved rule: all unique valid PAMs in Update, including Belum Diketahui.',
            'potential': 'MASTER DATA FINAL FLAG = POTENSI; not AP or U classifications.',
            'remaining': 'Eligible master stock minus its matched Column Q Berminat PAMs; never subtract out-of-master interest.',
            'potential_reconnection': 'AP and U remain separate source classifications, not Total/Sisa Potensi.',
            'active_potential': 'No separately approved definition; unavailable, not inferred.',
            'geography': 'Survey D/E/I retained; master supplies RW/RT only for a consistent geographic join; otherwise RT/RW Belum Terpetakan.',
        })
