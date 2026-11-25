"""Survey-calendar aging, shared by screen, filtered exports and snapshots.

Jakarta has no DST: UTC+07:00 also works in the browser's Python runtime without
an operating-system timezone database. Operational status is imported, not live.
"""
from collections import Counter
from datetime import date, datetime, timedelta, timezone

BUCKETS = ('0–7', '8–14', '15–30', '31–60', '61–90', '>90', 'Tanggal Belum Valid')
SEARCH_FIELDS = {'pam','survey_date','regional','area','kelurahan','rw','rt','surveyor','survey_age_days','file_status','obstacle','notes','address','aging_bucket'}


def query_matches(row, query):
    return query.strip().casefold() in ' '.join(str(row.get(key)) if row.get(key) is not None else '' for key in SEARCH_FIELDS).casefold()


def jakarta_today():
    return datetime.now(timezone(timedelta(hours=7), 'Asia/Jakarta')).date()


def reference_date(filters):
    value = date.fromisoformat(filters['aging_date']) if filters.get('aging_date') else jakarta_today()
    if value > jakarta_today():
        raise ValueError('Tanggal aging tidak boleh setelah hari ini di Asia/Jakarta')
    return value


def aged(view, reference):
    value = {**view}
    try:
        surveyed = date.fromisoformat(view.get('survey_date') or '')
        days = (reference-surveyed).days
        anomaly = 'future' if days < 0 else ''
    except (TypeError, ValueError):
        days = None
        anomaly = 'invalid' if view.get('survey_date_quality') == 'invalid' else 'missing'
    if anomaly:
        days, bucket = None, BUCKETS[-1]
    else:
        bucket = next((label for limit, label in zip((7,14,30,60,90), BUCKETS) if days <= limit), '>90')
    value.update(survey_age_days=days, aging_bucket=bucket, date_anomaly=anomaly, aging_as_of=reference.isoformat())
    return value


def selected_snapshot(data, filters):
    stamp = filters.get('snapshot') or data['meta'].get('reporting_date')
    history = data.get('outstanding_history', [])
    selected = next((entry for entry in history if entry['reporting_date'] == stamp), None)
    if filters.get('snapshot') and not selected:
        raise ValueError('Snapshot laporan tidak tersedia; status historis tidak direkonstruksi')
    return selected


def records(data, prepared, filters, overrides, actions, *, bucket=True, reference=None, snapshot=None):
    from .analytics import period_bounds, record_view
    reference = reference or reference_date(filters)
    chosen = snapshot or selected_snapshot(data, filters)
    historic = chosen is not None and chosen['reporting_date'] != data['meta'].get('reporting_date')
    if historic:
        views = chosen['rows']
    else:
        views = [record_view(data, prepared, row, overrides, actions.get(row['ref']))
                 for row in prepared.get('outstanding_rows', prepared['rows'])
                 if row['valid_location'] and row['status'].casefold() == 'outstanding']
    start, end = period_bounds(data, filters)
    bounded = bool(start or filters.get('end') or int(filters.get('m1', len(data['months'])-1)) < len(data['months'])-1)
    area, kel = int(filters.get('ab', -1)), int(filters.get('kel', -1))
    result = []
    for view in views:
        if filters.get('reg') and view['regional'] != filters['reg']: continue
        if area >= 0 and (view['regional'], view['area']) != (data['reg'][area], data['abs'][area]): continue
        if kel >= 0 and view['kelurahan'] != data['kels'][kel]: continue
        if any(int(filters.get(key, -1)) >= 0 and view.get(key, 0) != int(filters[key]) for key in ('rw', 'rt')): continue
        if filters.get('coordinator') and view['coordinator'] != filters['coordinator']: continue
        if filters.get('statuses') and view['status'] not in filters['statuses']: continue
        if filters.get('out_surveyor') and view['surveyor'] != filters['out_surveyor']: continue
        if filters.get('out_obstacle') and view['obstacle'] != filters['out_obstacle']: continue
        surveyed = date.fromisoformat(view['survey_date']) if view.get('survey_date') else None
        if surveyed and ((start and surveyed < start) or surveyed > end): continue
        if not surveyed and bounded: continue
        value = aged(view, reference)
        value['historical'] = historic
        if bucket and filters.get('aging_bucket') and value['aging_bucket'] != filters['aging_bucket']: continue
        if filters.get('out_query') and not query_matches(value,filters['out_query']): continue
        result.append(value)
    return result


def statistics(views):
    values = [row['survey_age_days'] for row in views if row['survey_age_days'] is not None]
    distribution = Counter({key: 0 for key in BUCKETS})
    distribution.update(row['aging_bucket'] for row in views)
    return {'survey_rows': len(views), 'aging': dict(distribution),
            'average_aging': sum(values)/len(values) if values else None,
            'maximum_aging': max(values) if values else None, 'excluded_dates': len(views)-len(values),
            'over_30': sum(value > 30 for value in values), 'over_90': sum(value > 90 for value in values),
            'date_anomalies': dict(Counter(row['date_anomaly'] for row in views if row['date_anomaly']))}


def summary(data, prepared, filters, overrides, actions):
    reference = reference_date(filters)
    views = records(data, prepared, {**filters,'out_query':''}, overrides, actions, bucket=False, reference=reference)
    snapshot = selected_snapshot(data, filters)
    stamp = snapshot['reporting_date'] if snapshot else data['meta'].get('reporting_date')
    previous = [entry for entry in data.get('outstanding_history', []) if entry['reporting_date'] < stamp]
    comparison = None
    if previous:
        prior = previous[-1]
        prior_stats = statistics(records(data, prepared, filters, overrides, {}, bucket=False,
                                 reference=date.fromisoformat(prior['reporting_date']), snapshot=prior))
        comparison = {'reporting_date': prior['reporting_date'], 'aging_as_of': prior['reporting_date'], **prior_stats}
    return {**statistics(views), 'aging_model': 'survey_calendar_jakarta', 'aging_as_of': reference.isoformat(),
            'geography_options': [list(key) for key in sorted({(row['regional'],row['area'],row['kelurahan'],row.get('rw',0),row.get('rt',0)) for row in (snapshot['rows'] if snapshot else views)})],
            'reporting_date': stamp, 'available_snapshots': [entry['reporting_date'] for entry in data.get('outstanding_history', [])],
            'comparison': comparison, 'transitions': snapshot.get('transitions') if snapshot else None,
            'aging_rule': 'Hari kalender Asia/Jakarta sejak Tanggal Survey. Ambang pemantauan, bukan SLA. Status mengikuti snapshot impor yang dipilih.',
            'status_basis': 'snapshot' if filters.get('snapshot') else 'latest_import',
            'by_status': dict(Counter(row['status'] for row in views)),
            'by_region': dict(Counter(row['regional'] for row in views)),
            'by_obstacle': dict(Counter(row['obstacle'] or 'Tidak tercatat' for row in views)),
            'by_file_status': dict(Counter(row['file_status'] or 'Tidak tercatat' for row in views)),
            'by_illegal_flag': dict(Counter(row.get('illegal_flag') or 'Tidak tercatat' for row in views)),
            'case_references': len(views), 'active_references': len(views)}


def search(data, prepared, filters, overrides, actions, body):
    query, sort, descending = body.get('query', ''), body.get('sort', '') or 'survey_age_days', body.get('descending', True)
    allowed = {'survey_age_days', 'pam', 'survey_date', 'regional', 'area', 'kelurahan', 'rw', 'rt', 'surveyor', 'file_status', 'obstacle', 'notes'}
    if not isinstance(query, str) or len(query)>150 or sort not in allowed or type(descending) is not bool:
        raise ValueError('Invalid Outstanding search or sort')
    values = records(data, prepared, filters, overrides, actions)
    query = query.strip().casefold()
    if query:
        values = [row for row in values if query_matches(row,query)]
    if sort == 'survey_age_days':
        values.sort(key=lambda row: (row['survey_age_days'] is None, (-1 if descending else 1)*(row['survey_age_days'] or 0), row['pam']))
    else:
        values.sort(key=lambda row: (int(row['pam']) if sort=='pam' else row.get(sort) or 0 if sort in ('rw','rt') else str(row.get(sort) or '').casefold()), reverse=descending)
    offset, limit = body.get('offset', 0), body.get('limit', 50)
    return {'rows': values[offset:offset+limit], 'total': len(values), 'offset': offset, 'limit': limit}
