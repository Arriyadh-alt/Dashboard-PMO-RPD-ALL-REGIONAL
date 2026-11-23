"""Map a reviewed cumulative XLSB intake to the existing encrypted-source contract.

No production files are written. Roster aliases stay in a private sidecar, never in
Git. Bootstrap is allowed only against an otherwise identical baseline snapshot;
it retains that baseline's curated identities, not a guessed spelling algorithm.
"""
import argparse
import base64
from collections import defaultdict
from copy import deepcopy
from datetime import date
import getpass
import io
import json
import math
import os
from pathlib import Path
from xml.sax.saxutils import escape

from backend.analytics import normalize_pam, prepare
from backend.auth import decrypt_source
from scripts.build_pages import ROOT
from scripts.workbook_intake import header, text, write_private


RECORD_FIELDS = {'pam', 'mi', 't', 'ab', 'kel', 'sv', 'fa', 'mt', 'tg',
                 'c1', 'c2', 'kf', 'kd', 'rp', 'mf', 'sc', 'pr'}
SURVEY_LABELS = {'c1': 'result', 'c2': 'result_detail', 'kf': 'installation_status',
                 'kd': 'obstacle', 'rp': 'recommendation'}
PTD = 'Permanent Total Disconnection (PTD)'
NO_BUILDING = 'Tidak Ada Bangunan'


def private_path(path):
    path = Path(path).resolve()
    if path == ROOT or ROOT in path.parents:
        raise ValueError('Keep plaintext inputs and outputs outside the repository')
    return path


def index_records(rows):
    result = {}
    for row in rows:
        pam = normalize_pam(text(row['pam']))
        if not pam or pam in result:
            raise ValueError('Invalid or duplicate PAM IDs require source review')
        result[pam] = row
    if not result:
        raise ValueError('A complete snapshot cannot have an empty sheet')
    return result


def baseline_ids(baseline):
    ids = [normalize_pam(text(value)) for value in baseline['rec']['pam']]
    if not all(ids) or len(set(ids)) != len(ids):
        raise ValueError('Baseline duplicate/invalid PAM IDs require source review')
    return ids


def bootstrap_aliases(baseline, intake):
    """Propose existing curated identities by PAM; caller MUST enforce full parity."""
    rows = index_records(intake['survey'])
    ids = baseline_ids(baseline)
    if set(ids) != rows.keys():
        raise ValueError('Alias bootstrap requires the identical PAM population')
    aliases = {}
    for j, pam in enumerate(ids):
        raw = text(rows[pam]['surveyor'])
        canonical = baseline['svs'][baseline['rec']['sv'][j]]
        if not raw or raw in aliases and aliases[raw] != canonical:
            raise ValueError('Ambiguous surveyor aliases require roster review')
        aliases[raw] = canonical
    return aliases


def number(value):
    try:
        result = float(value or 0)
    except (ValueError, TypeError) as error:
        raise ValueError('Invalid numeric master value') from error
    if not math.isfinite(result):
        raise ValueError('Invalid numeric master value')
    return result


def neighborhood(value):
    value = number(value)
    return int(value) if value.is_integer() and 1 <= value <= 99 else 0


def date_code(value, required=False):
    if not value:
        if required:
            raise ValueError('A survey date is required on every row')
        return 0
    parsed = date.fromisoformat(value)
    if not 2000 <= parsed.year <= 2099:
        raise ValueError('Source dates must fit the existing YYMMDD contract')
    return int(parsed.strftime('%y%m%d'))


def ordered_groups(values, previous, width):
    """Retain legacy row order for unchanged groups; append new keys deterministically."""
    old = [tuple(row[:width]) for row in previous]
    keys = [key for key in old if key in values] + sorted(values.keys() - set(old))
    return [list(key) + values[key] for key in keys]


def legacy_pdf(data):
    """Regenerate the all-period/all-surveyor artifact rather than retain stale data."""
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.platypus import LongTable, Paragraph, SimpleDocTemplate, TableStyle
    totals = defaultdict(lambda: [0] * 10)
    for row in data['S']:
        for j, value in enumerate(row[4:]):
            totals[row[2], row[3]][j] += value
    headers = ['Coordinator', 'Surveyor', 'Roster status', 'Survey rows', 'Interested',
               'Done', 'Assign FA', 'Outstanding', 'Cancel']
    statuses = ['Aktif', 'Resign', 'Pengawas']
    rows = [[data['kl'][kl], data['svs'][sv], statuses[data['st'][sv]], *values[:6]]
            for (kl, sv), values in sorted(totals.items())]
    styles = getSampleStyleSheet()
    styles['BodyText'].fontSize = 7
    styles['BodyText'].leading = 9
    p = lambda value: Paragraph(escape(str(value)), styles['BodyText'])
    stream = io.BytesIO()
    doc = SimpleDocTemplate(stream, pagesize=landscape(A4), leftMargin=24, rightMargin=24)
    table = LongTable([[p(value) for value in row] for row in [headers, *rows]],
                     repeatRows=1, splitInRow=1, colWidths=[(landscape(A4)[0]-48)/len(headers)]*len(headers))
    table.setStyle(TableStyle([('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#E8EFF5')),
                               ('VALIGN', (0, 0), (-1, -1), 'TOP')]))
    doc.build([Paragraph('All surveyors - unfiltered source report', styles['Title']),
               p('Survey dates: ' + data['meta']['tmin'] + ' - ' + data['meta']['tmax']),
               p('All available periods, areas and coordinators. Source row counts, not unique cohort metrics. Browser-local overrides and follow-ups are not included.'), table])
    return base64.b64encode(stream.getvalue()).decode()


def convert(baseline, intake, aliases, *, full_snapshot=False, bootstrap=False):
    if not full_snapshot:
        raise ValueError('Explicit full-snapshot confirmation is required; never append cumulative input')
    prepare(baseline)
    if intake.get('layout_version') != 2:
        raise ValueError('Re-run the version 2 workbook intake for recommendation and total arrears')
    if set(baseline['rec']) != RECORD_FIELDS:
        raise ValueError('Unreviewed baseline record columns; do not silently discard them')
    old_ids = baseline_ids(baseline)
    old_set = set(old_ids)
    if any(len(values) != len(old_ids) for values in baseline['rec'].values()):
        raise ValueError('Baseline record column lengths differ')
    survey, master = index_records(intake['survey']), index_records(intake['master'])
    if not old_set <= survey.keys():
        raise ValueError('Snapshot omits existing survey IDs; review deletions or incremental input')
    known_master = {pam for j, pam in enumerate(old_ids)
                    if baseline['dic']['mf'][baseline['rec']['mf'][j]]}
    if not known_master <= master.keys():
        raise ValueError('Snapshot omits known master IDs; review master coverage')
    data = deepcopy(baseline)
    if len(data['st']) != len(data['svs']) or any(type(s) is not int or not 0 <= s <= 2 for s in data['st']):
        raise ValueError('Invalid baseline roster status')
    areas = {(header(r), header(a)): j for j, (r, a) in enumerate(zip(data['reg'], data['abs']))}
    kels = {header(k): j for j, k in enumerate(data['kels'])}
    if len(areas) != len(data['abs']) or len(kels) != len(data['kels']):
        raise ValueError('Ambiguous normalized geography')
    svs = {name: j for j, name in enumerate(data['svs'])}
    if len(svs) != len(data['svs']) or any(value not in svs for value in aliases.values()):
        raise ValueError('Aliases must map to unique existing curated surveyors')
    coordinators = {}
    for row in data['S']:
        kl, sv = row[2:4]
        if not 0 <= kl < len(data['kl']) or sv in coordinators and coordinators[sv] != kl:
            raise ValueError('Ambiguous coordinator assignments require roster review')
        coordinators[sv] = kl

    def location(row, is_master=False):
        region, area = header(row['region']), header(row['area'])
        if is_master:
            region, area = region.removeprefix('regional '), area.removeprefix('ab ')
        try:
            return areas[region, area], kels[header(row['kelurahan'])]
        except KeyError as error:
            raise ValueError('Unmapped geography requires source review') from error

    # Extend reporting months, but retain the established first "s.d." bucket.
    for value in data['months']:
        date.fromisoformat(value + '-01')
    if any(data['months'][j+1] != next_month(value) for j, value in enumerate(data['months'][:-1])):
        raise ValueError('Reporting months must be consecutive')
    dates = [r[f] for r in survey.values() for f in ('survey_date', 'fa_date', 'meter_date') if r[f]]
    for value in dates:
        date_code(value)
    latest = max(dates)[:7]
    while data['months'][-1] < latest:
        data['months'].append(next_month(data['months'][-1]))
    month_index = {value: j for j, value in enumerate(data['months'])}
    month = lambda value: month_index.get(value[:7], 0)

    def code(field, value):
        value = text(value)
        try:
            return data['dic'][field].index(value)
        except (KeyError, ValueError) as error:
            raise ValueError('Unreviewed classification in field ' + field) from error

    groups = {name: defaultdict(lambda n=n: [0]*n)
              for name, n in [('A', 10), ('S', 10), ('K', 9), ('E', 2), ('P', 3), ('W', 3)]}
    rec = {key: [] for key in RECORD_FIELDS}
    # Preserve existing row order for stable customer references and parity checks.
    ordered_ids = old_ids + [pam for pam in survey if pam not in old_set]
    for pam in ordered_ids:
        row, m = survey[pam], master.get(pam)
        area, kel = location(row)
        raw = text(row['surveyor'])
        canonical = aliases.get(raw, raw)
        if canonical not in svs or svs[canonical] not in coordinators:
            raise ValueError('Unmapped surveyor/coordinator requires private roster review')
        sv = svs[canonical]
        t = date_code(row['survey_date'], required=True)
        fa, mt = date_code(row['fa_date']), date_code(row['meter_date'])
        c1, c2, status = text(row['result']), text(row['result_detail']), text(row['installation_status'])
        interested, uninterested = c1 == 'Berminat', c1 == 'Tidak Berminat'
        no_building, ptd = c2 == NO_BUILDING, c2 == PTD
        unknown = not any((interested, uninterested, no_building, ptd))
        af, done, outstanding, cancel = (status == label for label in ('Assign FA', 'Done', 'Outstanding', 'Cancel'))
        mf, sc = (text(m['master_flag']), text(m['customer_status'])) if m else ('', '')
        if not m:
            pr = 'Di luar Master Data'
        elif mf != 'POTENSI':
            pr = 'Non potensi (master)'
        elif interested:
            pr = 'Potensi, sudah berminat (dikeluarkan)'
        elif no_building or ptd:
            pr = 'Potensi, tapi Update: tidak ada bangunan atau PTD'
        else:
            pr = 'Potensi tersisa'
        values = dict(pam=int(pam), mi=month(row['survey_date']), t=t, ab=area, kel=kel, sv=sv,
                      fa=fa, mt=mt, tg=round(number(m['total_arrears'])) if m else 0,
                      mf=code('mf', mf), sc=code('sc', sc), pr=code('pr', pr))
        values.update({field: code(field, row[source]) for field, source in SURVEY_LABELS.items()})
        for key in rec:
            rec[key].append(values[key])
        stats = list(map(int, [1, interested, uninterested, unknown, ptd, no_building, af, done, outstanding, cancel]))
        bucket = values['mi']
        for name, key, measures in [
                ('A', (bucket, area), stats),
                ('S', (bucket, area, coordinators[sv], sv), [stats[j] for j in (0,1,7,6,8,9,2,3,5,4)]),
                ('K', (bucket, area, kel), list(map(int, [1, not no_building and not ptd, interested, done, af, outstanding, cancel, uninterested, unknown])))]:
            for j, value in enumerate(measures):
                groups[name][key][j] += value
        for field, col in [('fa_date', 0), ('meter_date', 1)]:
            if row[field]:
                groups['E'][month(row[field]), area][col] += 1
    sync = dict.fromkeys(('pot_master', 'deduct', 'deduct_tp', 'non_berm', 'outside',
                         'master_missing', 'ab_diff', 'kel_diff', 'nb', 'ptd', 'dp_b', 'berm_in'), 0)
    rt_bad = 0
    for pam, m in master.items():
        area, kel = location(m, True)
        code('mf', m['master_flag'])
        code('sc', m['customer_status'])
        row = survey.get(pam)
        interested = bool(row and text(row['result']) == 'Berminat')
        done = bool(interested and text(row['installation_status']) == 'Done')
        potential = text(m['master_flag']) == 'POTENSI'
        sync['master_missing'] += row is None
        sync['dp_b'] += text(m['potential_status']) == 'Berminat'
        sync['berm_in'] += interested
        sync['non_berm'] += interested and not potential
        if row:
            update_area, update_kel = location(row)
            # Legacy ab_diff compares area names, independently of region mismatch.
            sync['ab_diff'] += header(data['abs'][area]) != header(data['abs'][update_area])
            sync['kel_diff'] += kel != update_kel
        if not potential:
            continue
        rw, rt = neighborhood(m['rw']), neighborhood(m['rt'])
        rt_bad += not rw or not rt
        sync['pot_master'] += 1
        sync['deduct'] += interested
        sync['deduct_tp'] += done
        sync['nb'] += bool(row and text(row['result_detail']) == NO_BUILDING)
        sync['ptd'] += bool(row and text(row['result_detail']) == PTD)
        for name, key in [('P', (area, kel)), ('W', (area, kel, rw, rt))]:
            for j, value in enumerate([1, int(interested), int(done)]):
                groups[name][key][j] += value
    sync['outside'] = sum(text(r['result']) == 'Berminat' for pam, r in survey.items() if pam not in master)
    data['rec'] = rec
    for name, width in [('A', 2), ('S', 4), ('K', 3), ('E', 2), ('P', 2), ('W', 4)]:
        if name in data or name != 'K':
            data[name] = ordered_groups(groups[name], data.get(name, []), width)
    survey_dates = sorted(r['survey_date'] for r in survey.values())
    data['meta'].update(rows=len(survey), uniq=len(survey), tmin=survey_dates[0],
                        tmax=survey_dates[-1], rt_bad=rt_bad, sync=sync)
    changed = data != baseline
    if bootstrap and changed:
        raise ValueError('Alias bootstrap requires exact record, classification and aggregate parity')
    if changed and baseline.get('pdf'):
        data['pdf'] = legacy_pdf(data)
    prepare(data)
    return data, {'changed': changed, 'survey_rows': len(survey), 'master_rows': len(master),
                  'potential': sync['pot_master'], 'matched_interested': sync['deduct'],
                  'remaining': sync['pot_master']-sync['deduct'], 'alias_labels': len(aliases)}


def next_month(value):
    year, month = map(int, value.split('-'))
    return f'{year + (month == 12):04d}-{month % 12 + 1:02d}'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('encrypted_source', type=Path)
    parser.add_argument('intake', type=Path)
    parser.add_argument('contract_output', type=Path)
    parser.add_argument('--aliases', type=Path, required=True,
                        help='Private roster sidecar (existing input, or new bootstrap output)')
    parser.add_argument('--bootstrap-aliases', action='store_true')
    parser.add_argument('--full-snapshot', action='store_true')
    args = parser.parse_args()
    for path in (args.intake, args.contract_output, args.aliases):
        private_path(path)
    if args.contract_output.exists() or args.bootstrap_aliases and args.aliases.exists():
        raise ValueError('Choose new output paths; never overwrite private artifacts')
    account = os.environ.get('RPD_UPDATE_ACCOUNT') or input('Authorized source administrator ID: ')
    password = os.environ.get('RPD_UPDATE_PASSWORD') or getpass.getpass('Source password: ')
    baseline, role = decrypt_source(args.encrypted_source, account, password)
    if role != 'owner':
        raise ValueError('An authorized source administrator is required')
    intake = json.loads(args.intake.read_text())
    aliases = bootstrap_aliases(baseline, intake) if args.bootstrap_aliases else json.loads(args.aliases.read_text())
    data, summary = convert(baseline, intake, aliases, full_snapshot=args.full_snapshot,
                            bootstrap=args.bootstrap_aliases)
    write_private(args.contract_output, data)
    if args.bootstrap_aliases:
        write_private(args.aliases, aliases)
    print(json.dumps(summary))
    if not summary['changed']:
        print('Identical snapshot: skip encryption/publication; preserve the current publication timestamp.')


if __name__ == '__main__':
    main()
