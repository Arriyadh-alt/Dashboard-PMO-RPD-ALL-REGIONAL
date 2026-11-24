"""Strict public-release contract: five KPIs, regional totals and monthly trends.

No operational cube, area/kelurahan, staff, customer, free text or credentials.
Generate only as part of an explicitly approved public snapshot publication.
"""
import re

from backend.analytics import build_analysis, prepare
from backend.browser_api import LocalEvents


METRICS = {'potential', 'canvassed', 'interested', 'installed', 'remaining'}
TREND = {'month', 'canvassed', 'interested', 'installation_events'}


def validate(value):
    required = {'public_version', 'snapshot_pair', 'survey_through', 'metrics', 'regions', 'trends'}
    if not isinstance(value, dict) or not required <= set(value) or set(value) - required - {'reporting_date'}:
        raise ValueError('Public summary must contain only the approved release fields')
    if value['public_version'] != 1 or not re.fullmatch(r'[0-9a-f]{32}', value['snapshot_pair']):
        raise ValueError('Invalid public snapshot identity')
    if value['survey_through'] is not None and not re.fullmatch(r'\d{4}-\d{2}-\d{2}', value['survey_through']):
        raise ValueError('Invalid survey coverage')
    if 'reporting_date' in value and not re.fullmatch(r'\d{4}-\d{2}-\d{2}', value['reporting_date']):
        raise ValueError('Invalid report date')

    def metrics(row, keys):
        if not isinstance(row, dict) or set(row) != keys:
            raise ValueError('Unapproved public field')
        for key in METRICS & keys:
            if type(row[key]) is not int or row[key] < 0:
                raise ValueError('Public metrics must be nonnegative counts')

    metrics(value['metrics'], METRICS)
    if not isinstance(value['regions'], list) or not isinstance(value['trends'], list):
        raise ValueError('Invalid public series')
    seen = set()
    for row in value['regions']:
        metrics(row, METRICS | {'name'})
        if not isinstance(row['name'], str) or not 0 < len(row['name']) <= 100 or row['name'] in seen:
            raise ValueError('Invalid public regional label')
        seen.add(row['name'])
    for key in METRICS:
        if sum(row[key] for row in value['regions']) != value['metrics'][key]:
            raise ValueError('Public regional totals do not reconcile')
    seen = set()
    for row in value['trends']:
        if not isinstance(row, dict) or set(row) != TREND or not re.fullmatch(r'\d{4}-\d{2}', row['month']) or row['month'] in seen:
            raise ValueError('Invalid public monthly trend')
        seen.add(row['month'])
        if any(type(row[key]) is not int or row[key] < 0 for key in TREND - {'month'}):
            raise ValueError('Invalid public trend count')
    for key in ('canvassed', 'interested'):
        if sum(row[key] for row in value['trends']) != value['metrics'][key]:
            raise ValueError('Public trends do not reconcile')
    return value


def project(data, pair, analysis=None):
    analysis = analysis or build_analysis(data, prepare(data), {}, LocalEvents(), 'owner')
    public = {
        'public_version': 1, 'snapshot_pair': pair,
        **({'reporting_date': data['meta']['reporting_date']} if data['meta'].get('reporting_date') else {}),
        'survey_through': data['meta'].get('tmax'),
        'metrics': {**{key: analysis['metrics'][key] for key in ('canvassed', 'interested', 'installed')},
                    **{key: analysis['master'][key] for key in ('potential', 'remaining')}},
        'regions': [{key: row[key] for key in METRICS | {'name'}} for row in analysis['regions']],
        'trends': [{key: row[key] for key in TREND} for row in analysis['trends']],
    }
    return validate(public)
