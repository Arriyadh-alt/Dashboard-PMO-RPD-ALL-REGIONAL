"""Import-time, identity-preserving geography and encrypted report snapshots."""
from collections import Counter, defaultdict
import copy
import re

from backend.analytics import normalize_pam, prepare, record_view
from scripts.workbook_intake import header, text


def address_neighborhood(address):
    """Only explicit RT/RW labels. Never infer from unlabelled street numbers."""
    raw = text(address).upper()
    values = {'rt': set(), 'rw': set()}
    for rt, rw in re.findall(r'\bRT\s*[/&]\s*RW\s*[:.=-]?\s*(\d{1,3})\s*[/,-]\s*(\d{1,3})(?!\d)', raw):
        values['rt'].add(int(rt)); values['rw'].add(int(rw))
    for key in values:
        for match in re.finditer(r'\b' + key.upper() + r'\s*[.:=-]?\s*(\d{1,3})(?!\d)', raw):
            values[key].add(int(match[1]))
    if any(len(items)>1 for items in values.values()):
        return {'rt': 0, 'rw': 0}
    return {key: next(iter(items)) if len(items) == 1 and 0 < next(iter(items)) <= 99 else 0
            for key, items in values.items()}


def enhance(data, intake, survey, master, ordered_ids, location, neighborhood):
    """Survey territory stays approved Update D/E/I; master supplies location facts.

    Master stocks/deductions retain master territory. A territory discrepancy is
    reported, not treated as a failed identity join or rewritten survey territory.
    """
    places, enriched, address_conflicts = {}, set(), set()
    for pam, row in master.items():
        def column(kind):
            value=neighborhood(row[kind])
            explicit=re.fullmatch(kind+r'\s*[.:=-]?\s*(\d{1,3})',text(row[kind]),re.I)
            return value or (int(explicit[1]) if explicit and 0<int(explicit[1])<=99 else 0)
        rw, rt = column('rw'), column('rt')
        if not rw or not rt:
            extracted = address_neighborhood(row.get('address'))
            conflict = bool(rw and extracted['rw'] and rw != extracted['rw'] or rt and extracted['rt'] and rt != extracted['rt'])
            if conflict:
                address_conflicts.add(pam)
            else:
                new_rw, new_rt = rw or extracted['rw'], rt or extracted['rt']
                if (new_rw, new_rt) != (rw, rt):
                    enriched.add(pam)
                rw, rt = new_rw, new_rt
        places[pam] = rw, rt
    groups = defaultdict(lambda: [0] * 6)
    for pam, row in master.items():
        if header(row['master_flag']) == 'potensi':
            values = groups[*location(row, True), *places[pam]]
            values[0] += 1
            values[4] += bool(survey.get(pam) and header(survey[pam]['minat']) == 'berminat')
    totals, coverage = Counter(), defaultdict(Counter)
    conflicts, date_anomalies = [], []
    rec = data['rec']
    for key in ('rw', 'rt', 'ad', 'gc', 'ds', 'nt'):
        rec[key] = []
    addresses = sorted({text(row.get('address')) for row in master.values()} | {''})
    notes = sorted({text(row.get('incomplete_reason')) for row in survey.values()} | {''})
    data['dic']['ad'], data['dic']['nt'] = addresses, notes
    address_index, note_index = {v: i for i, v in enumerate(addresses)}, {v: i for i, v in enumerate(notes)}
    for pam in ordered_ids:
        row, matched = survey[pam], master.get(pam)
        area, kel = location(row)
        rw, rt = places.get(pam, (0, 0))
        mismatch = bool(matched and (area, kel) != location(matched, True))
        before_rw, before_rt = ((neighborhood(matched['rw']), neighborhood(matched['rt'])) if matched and not mismatch else (0, 0))
        quality = row.get('date_quality', 'valid' if row['survey_date'] else 'missing')
        rec['rw'].append(rw); rec['rt'].append(rt)
        rec['gc'].append(int(mismatch)); rec['ds'].append({'valid': 0, 'missing': 1, 'invalid': 2}[quality])
        rec['ad'].append(address_index[text(matched.get('address')) if matched else ''])
        rec['nt'].append(note_index[text(row.get('incomplete_reason'))])
        counts = {'survey_ids': 1, 'matched': int(matched is not None), 'unmatched': int(matched is None),
                  'valid_rt_rw_before': int(bool(before_rw and before_rt)), 'valid_rt_rw': int(bool(rw and rt)),
                  'missing_rt': int(not rt), 'missing_rw': int(not rw), 'address_enriched': int(pam in enriched),
                  'territory_conflicts': int(mismatch), 'address_conflicts': int(pam in address_conflicts)}
        totals.update(counts)
        coverage[data['reg'][area], data['abs'][area], data['kels'][kel]].update(counts)
        if mismatch:
            conflicts.append({'pam': row['pam_display'], 'survey': [data['reg'][area], data['abs'][area], data['kels'][kel]],
                              'master': [text(matched[key]) for key in ('region', 'area', 'kelurahan')], 'rw': rw, 'rt': rt})
        if quality != 'valid':
            date_anomalies.append({'pam': row['pam_display'], 'quality': quality})
        values = groups[area, kel, rw, rt]
        values[1] += 1; values[2] += header(row['minat']) == 'berminat'
        values[3] += header(row['installation_status']) == 'done'
        values[5] += header(row['installation_status']) == 'outstanding'
    data['G'] = [list(key) + value for key, value in sorted(groups.items())]
    def formatted(counts):
        return {**dict(counts), 'success_rate': counts['valid_rt_rw'] / counts['survey_ids'] if counts['survey_ids'] else None}
    layers = {}
    for level, width in [('regional', 1), ('area', 2), ('kelurahan', 3)]:
        rollup = defaultdict(Counter)
        for key, values in coverage.items(): rollup[key[:width]].update(values)
        layers[level] = [{'location': list(key), **formatted(counts)} for key, counts in sorted(rollup.items())]
    data['_admin_mapping_report'] = {'totals': {**formatted(totals), 'master_ids': len(master),
        'duplicate_master': intake['summary']['master']['duplicate_excess_rows'],
        'secondary_id_mismatches': intake['summary']['master_secondary_id_mismatches']},
        'coverage': layers, 'territory_conflicts': conflicts, 'date_anomalies': date_anomalies,
        'secondary_id_policy': 'PAM_ID2 is checked against normalized primary PAM_ID; differing IDs are not unverified aliases.',
        'territory_policy': 'Update D/E/I preserves approved operational territory; matched master RT/RW and address remain customer location facts. Master potential retains master territory.',
        'duplicate_policy': 'Invalid or duplicate normalized IDs reject publication; previous valid dataset is retained.'}
    data['meta'].update(v5=True, geographic_survey_unmapped=len(survey)-totals['valid_rt_rw'])
    data['meta']['metric_definitions']['geography'] = data['_admin_mapping_report']['territory_policy']
    preserve_snapshot(data, intake, survey)


def preserve_snapshot(data, intake, survey):
    stamp = intake.get('reporting_date')
    if not stamp:
        raise ValueError('V5 requires a verified reporting date for source snapshots')
    history = copy.deepcopy(data.get('outstanding_history', []))
    if history and stamp < max(entry['reporting_date'] for entry in history):
        raise ValueError('A reporting snapshot cannot move backwards')
    history = [entry for entry in history if entry['reporting_date'] != stamp]
    prepared = prepare(data)
    views = [record_view(data, prepared, row, {}) for row in prepared['rows']
             if row['status'].casefold() == 'outstanding']
    previous = history[-1] if history else None
    transitions = None
    if previous:
        before = {normalize_pam(row['pam']) for row in previous['rows']}
        after = {normalize_pam(row['pam']) for row in views}
        ended = before - after
        destinations = Counter(header(survey[pam]['installation_status']) if pam in survey else 'absent' for pam in ended)
        transitions = {'new': len(after-before), 'remaining': len(before & after), 'no_longer': len(ended),
                       'assign_fa': destinations['assign fa'], 'installed': destinations['done'], 'cancel': destinations['cancel'],
                       'other_or_absent': sum(n for status, n in destinations.items() if status not in ('assign fa','done','cancel'))}
    history.append({'reporting_date': stamp, 'workbook_sha256': intake['workbook_sha256'], 'rows': views, 'transitions': transitions})
    data['outstanding_history'] = history
