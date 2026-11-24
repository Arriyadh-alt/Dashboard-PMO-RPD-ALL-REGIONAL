"""Publishable, identity-free daily cubes for the two aggregate workspaces.

Additive cubes are valid only for snapshots with one valid source row per PAM.
Reject duplicates rather than changing the existing unique-customer definitions.
No identifier, staff mapping, free text, case history or customer field is retained.
"""
from collections import defaultdict

from .analytics import area_key, prepare


def project(data):
    prepared = prepare(data)
    seen, daily, installed = set(), defaultdict(lambda: [0, 0, 0, 0]), defaultdict(int)
    dates = []
    for row in prepared['rows']:
        if not row['valid']:
            continue
        if row['pam'] in seen or row['pam'] in prepared['ambiguous']:
            raise ValueError('Aggregate publication requires reconciled unique PAM IDs')
        seen.add(row['pam'])
        day = row['date'].isoformat()
        dates.append(day)
        values = daily[(row['ab'], row['kel'], day)]
        values[0] += 1
        values[1] += int(row['interest'])
        values[2] += int(row['interest'] and row['installed'])
        values[3] += int(row['interest'] and not row['installed'] and not row['cancelled'])
        if row['installed'] and row['install_date']:
            installed[(row['ab'], row['kel'], row['install_date'].isoformat())] += 1
    return {
        'aggregate_version': 1,
        'months': data['months'], 'abs': data['abs'], 'reg': data['reg'], 'kels': data['kels'],
        'P': [row[:5] for row in data['P']],
        'days': [list(key) + value for key, value in sorted(daily.items())],
        'install_days': [list(key) + [value] for key, value in sorted(installed.items())],
        'area_keys': [area_key(data, index) for index in range(len(data['abs']))],
        'coverage': [min(dates), max(dates)] if dates else [None, None],
        'meta': {key: data['meta'].get(key) for key in ('tmin', 'tmax')},
    }
