"""Read the verified RPD XLSB layout without executing Excel or extra personal fields.

Only dashboard-required columns are selected. Names, addresses, telephone numbers,
identity-document links, coordinates and free-text customer notes are not imported.
An intake is not a published contract or an assertion of workbook freshness.
"""
import argparse
from collections import Counter
from datetime import date, datetime, timedelta
import hashlib
import io
import json
import math
import os
from pathlib import Path
import zipfile

from pyxlsb import convert_date, open_workbook
from pyxlsb.biff12 import WORKBOOKPR
from pyxlsb.reader import BIFF12Reader

from backend.analytics import normalize_pam
from scripts.build_pages import ROOT


SURVEY_COLUMNS = {
    'survey_date': '1. Tanggal Survey', 'region': '2. Regional',
    'area': '3. Area Bisnis', 'surveyor': '4. Nama Surveyor', 'pam': '5. PAM ID',
    'kelurahan': 'Kelurahan', 'installation_status': 'Konfirmasi Pemasangan',
    'result': 'Hasil Canvasing', 'result_detail': 'Hasil Canvasing 2',
    'obstacle': 'Flag Kendala', 'fa_date': 'Tanggal Assign FA',
    'meter_date': 'Tanggal Meter Terpasang',
}
MASTER_COLUMNS = {
    'pam': 'PAM_ID', 'region': 'REGIONAL', 'area': 'AB', 'kelurahan': 'KLURAHAN',
    'rw': 'RW', 'rt': 'RT', 'master_flag': 'FINAL FLAG',
    'potential_status': 'Data Potensi', 'customer_status': 'STATCUST',
    'arrears': 'Tunggakan',
}


def text(value):
    if value is None:
        return ''
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value).strip()


def header(value):
    return ' '.join(text(value).split()).casefold()


def date_system(path):
    """Read f1904 from BrtWbProp; pyxlsb does not expose this workbook flag."""
    with zipfile.ZipFile(path) as archive:
        raw = archive.read('xl/workbook.bin')
    reader = BIFF12Reader(io.BytesIO(raw))
    while True:
        record, length = reader.read_id(), reader.read_len()
        if record is None or length is None:
            raise ValueError('Workbook date system is unavailable')
        payload = reader._fp.read(length)
        if len(payload) != length:
            raise ValueError('Truncated workbook properties')
        if record == WORKBOOKPR:
            if len(payload) < 4:
                raise ValueError('Invalid workbook properties')
            return bool(int.from_bytes(payload[:4], 'little') & 1)


def excel_date(value, date1904=False):
    if value in (None, '', 0):
        return None
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, (float, int)) and not isinstance(value, bool):
        if not math.isfinite(value) or value <= 0:
            raise ValueError('Invalid Excel date serial')
        if date1904:
            return (date(1904, 1, 1) + timedelta(days=int(value))).isoformat()
        # The library rounds fractional seconds, which can advance 23:59:59.9
        # into tomorrow. This adapter imports calendar dates, not timestamps.
        return convert_date(int(value)).date().isoformat()
    try:
        return date.fromisoformat(text(value)).isoformat()
    except ValueError as error:
        raise ValueError('Unexpected date format; review the workbook layout') from error


def selected_rows(sheet, columns):
    rows = iter(sheet.rows(sparse=True))
    first = next(rows, None)
    if first is None or first[0].r != 0:
        raise ValueError('The verified workbook requires a header in row 1')
    positions = {}
    for cell in first:
        name = header(cell.v)
        if not name:
            continue
        if name in positions:
            raise ValueError('Duplicate workbook column header')
        positions[name] = cell.c
    missing = [name for name in columns.values() if header(name) not in positions]
    if missing:
        raise ValueError('Missing verified columns: ' + ', '.join(missing))
    lookup = {field: positions[header(name)] for field, name in columns.items()}
    for row in rows:
        cells = {cell.c: cell.v for cell in row if text(cell.v)}
        if not cells:
            continue
        yield {'source_row': row[0].r + 1, **{field: cells.get(index) for field, index in lookup.items()}}


def profile(records):
    ids = Counter(normalize_pam(text(row['pam'])) for row in records)
    invalid = ids.pop('', 0)
    return {'rows': len(records), 'unique_valid_pam': len(ids),
            'invalid_pam_rows': invalid,
            'duplicate_excess_rows': sum(count - 1 for count in ids.values())}


def read_intake(path):
    path = Path(path).resolve()
    if path == ROOT or ROOT in path.parents:
        raise ValueError('Keep plaintext workbooks outside the repository')
    if path.suffix.lower() != '.xlsb':
        raise ValueError('This verified adapter accepts Excel Binary (.xlsb) only')
    date1904 = date_system(path)
    with open_workbook(path) as book:
        updates = [name for name in book.sheets if header(name).startswith('update ')]
        masters = [name for name in book.sheets if header(name) == 'master data']
        if len(updates) != 1 or len(masters) != 1:
            raise ValueError('Expected exactly one Update sheet and one MASTER DATA sheet')
        with book.get_sheet(updates[0]) as sheet:
            survey = list(selected_rows(sheet, SURVEY_COLUMNS))
        with book.get_sheet(masters[0]) as sheet:
            master = list(selected_rows(sheet, MASTER_COLUMNS))
    if not survey or not master:
        raise ValueError('Both survey and master snapshots must contain records')
    for row in survey:
        for field in ('survey_date', 'fa_date', 'meter_date'):
            row[field] = excel_date(row[field], date1904)
    dates = {field: sorted(row[field] for row in survey if row[field])
             for field in ('survey_date', 'fa_date', 'meter_date')}
    summary = {'survey': profile(survey), 'master': profile(master),
               'dates': {key: {'min': values[0] if values else None,
                               'max': values[-1] if values else None}
                         for key, values in dates.items()},
               'interest_counts': dict(Counter(text(row['result']) for row in survey)),
               'installation_counts': dict(Counter(text(row['installation_status']) for row in survey)),
               'master_flag_counts': dict(Counter(text(row['master_flag']) for row in master))}
    return {'layout_version': 1, 'workbook_sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
            'sheets': {'survey': updates[0], 'master': masters[0]},
            'date_system': '1904' if date1904 else '1900',
            'survey': survey, 'master': master, 'summary': summary}


def write_private(path, data):
    path = Path(path).resolve()
    if path == ROOT or ROOT in path.parents:
        raise ValueError('Plaintext output must be outside the repository')
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, 'w') as file:
        json.dump(data, file, ensure_ascii=False, allow_nan=False, separators=(',', ':'))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('workbook', type=Path)
    parser.add_argument('private_output', type=Path)
    args = parser.parse_args()
    intake = read_intake(args.workbook)
    write_private(args.private_output, intake)
    print(json.dumps(intake['summary'], ensure_ascii=False, indent=2))
