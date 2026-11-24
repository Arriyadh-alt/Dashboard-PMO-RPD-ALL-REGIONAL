"""Read the verified RPD XLSX/XLSB layout without executing Excel or macros.

Only dashboard-required columns are selected. Names, addresses, telephone numbers,
identity-document links, coordinates and free-text customer notes are not imported.
An intake is not a published contract or an assertion of workbook freshness.
"""
import argparse
from contextlib import closing, nullcontext
from collections import Counter
from datetime import date, datetime, timedelta
import hashlib
import io
import json
import math
import os
import re
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
    'recommendation': '17. Rekomendasi - PMO',
    'obstacle': 'Flag Kendala', 'fa_date': 'Tanggal Assign FA',
    'meter_date': 'Tanggal Meter Terpasang',
}
MASTER_COLUMNS = {
    'pam': 'PAM_ID', 'region': 'REGIONAL', 'area': 'AB', 'kelurahan': 'KLURAHAN',
    'rw': 'RW', 'rt': 'RT', 'master_flag': 'FINAL FLAG',
    'potential_status': 'Data Potensi', 'customer_status': 'STATCUST',
    'arrears': 'Tunggakan',
    'total_arrears': 'Total_Tunggakan_&_Denda',
}
V4_SURVEY_COLUMNS = {
    **SURVEY_COLUMNS,
    'minat': '13. Jika Bangunan/Properti masih ada, Bagaimana Minat ex PD ?',
    'flag_data': 'Flag Data', 'marketing_recommendation': '19. Rekomendasi - By Marketing',
    'admin_note': 'Catatan Admin', 'illegal_flag': 'Flag Illegal',
    'file_status': 'Status Berkas', 'incomplete_reason': 'Keterangan Alasan Tidak Lengkap',
}
V4_MASTER_COLUMNS = {
    **MASTER_COLUMNS, 'pam_secondary': 'PAM_ID2', 'supply': 'Good_Supply_Bad_Supply',
    'potential_1': 'FLAG POTENSI 1', 'marketing_survey': 'FLAG SURVEY MARKETING',
    'potential_2': 'FLAG POTENSI 2', 'potential_near_final': 'FLAG POTENSI HAMPIR FINAL',
    'ptd_flag': 'FLAG PTD',
}
# Positions are audit evidence, never the lookup: an inserted column is supported.
VERIFIED_POSITIONS = {'survey': {'survey_date': 1, 'region': 4, 'area': 5, 'surveyor': 6,
    'pam': 7, 'flag_data': 8, 'kelurahan': 9, 'minat': 17, 'recommendation': 21,
    'marketing_recommendation': 23, 'installation_status': 35, 'admin_note': 36,
    'illegal_flag': 37, 'result': 41, 'result_detail': 42, 'file_status': 43,
    'obstacle': 44, 'incomplete_reason': 45, 'fa_date': 47, 'meter_date': 49},
    'master': {'pam': 1, 'pam_secondary': 10, 'rt': 15, 'rw': 16, 'region': 19,
    'area': 20, 'kelurahan': 22, 'supply': 34, 'potential_status': 48, 'potential_1': 55,
    'marketing_survey': 56, 'potential_2': 59, 'potential_near_final': 60,
    'ptd_flag': 61, 'master_flag': 62}}


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
        record = reader.read_id()
        if record is None:
            # BrtWbProp is optional; its omitted f1904 defaults to false.
            return False
        length = reader.read_len()
        if length is None:
            raise ValueError('Truncated workbook record')
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


def cell_rows(sheet):
    if hasattr(sheet, 'iter_rows'):
        for index, row in enumerate(sheet.iter_rows(values_only=True)):
            yield index, {i: value for i, value in enumerate(row) if text(value)}
    else:
        for row in sheet.rows(sparse=True):
            if row:
                yield row[0].r, {cell.c: cell.v for cell in row if text(cell.v)}


def header_positions(first):
    positions = {}
    for index, value in first.items():
        name = header(value)
        if not name:
            continue
        if name in positions:
            raise ValueError('Duplicate workbook column header')
        positions[name] = index
    return positions


def selected_rows(sheet, columns):
    rows = iter(cell_rows(sheet))
    first = next(rows, None)
    if first is None or first[0] != 0:
        raise ValueError('The verified workbook requires a header in row 1')
    positions = header_positions(first[1])
    missing = [name for name in columns.values() if header(name) not in positions]
    if missing:
        raise ValueError('Missing verified columns: ' + ', '.join(missing))
    lookup = {field: positions[header(name)] for field, name in columns.items()}
    for index, cells in rows:
        if not cells:
            continue
        yield {'source_row': index + 1, **{field: cells.get(col) for field, col in lookup.items()}}


def profile(records):
    ids = Counter(normalize_pam(text(row['pam'])) for row in records)
    invalid = ids.pop('', 0)
    return {'rows': len(records), 'unique_valid_pam': len(ids),
            'invalid_pam_rows': invalid,
            'duplicate_excess_rows': sum(count - 1 for count in ids.values())}


def reconcile(survey, master):
    """Compare valid IDs; never silently choose one of several duplicate rows."""
    def index(records):
        counts, rows = Counter(), {}
        for row in records:
            pam = normalize_pam(text(row['pam']))
            if pam:
                counts[pam] += 1
                rows[pam] = row
        return set(counts), {pam: row for pam, row in rows.items() if counts[pam] == 1}
    survey_ids, survey_unique = index(survey)
    master_ids, master_unique = index(master)
    matched = survey_ids & master_ids
    compared = survey_unique.keys() & master_unique.keys()
    mismatches = {}
    for field, prefix in (('region', 'regional '), ('area', 'ab '), ('kelurahan', '')):
        mismatches[field] = sum(
            header(survey_unique[pam][field]).removeprefix(prefix) !=
            header(master_unique[pam][field]).removeprefix(prefix)
            for pam in compared)
    return {'matched_valid_ids': len(matched),
            'survey_ids_not_in_master': len(survey_ids - master_ids),
            'master_ids_not_in_survey': len(master_ids - survey_ids),
            'geography_compared_unique_ids': len(compared),
            'geography_withheld_duplicate_ids': len(matched - compared),
            'normalized_geography_mismatches': mismatches}


def read_intake(path, *, v4=False):
    """Read cached workbook values. CLI defaults to V4; v2 API stays reproducible."""
    path = Path(path).resolve()
    if path == ROOT or ROOT in path.parents:
        raise ValueError('Keep plaintext workbooks outside the repository')
    binary = path.suffix.lower() == '.xlsb'
    if not binary and path.suffix.lower() != '.xlsx':
        raise ValueError('Supported workbook formats: .xlsx and .xlsb')
    if binary:
        book_context, date1904 = open_workbook(path), date_system(path)
    else:
        from openpyxl import load_workbook
        book_context = closing(load_workbook(path, read_only=True, data_only=True))
        date1904 = False
    columns = {'survey': V4_SURVEY_COLUMNS if v4 else SURVEY_COLUMNS,
               'master': V4_MASTER_COLUMNS if v4 else MASTER_COLUMNS}
    candidates, position_audit = {'survey': [], 'master': []}, {}
    with book_context as book:
        if not binary:
            date1904 = book.epoch.year == 1904
        open_sheet = lambda name: book.get_sheet(name) if binary else nullcontext(book[name])
        for name in book.sheets if binary else book.sheetnames:
            with open_sheet(name) as sheet:
                first = next(iter(cell_rows(sheet)), None)
                cells = first[1] if first and first[0] == 0 else {}
                names = {header(value) for value in cells.values()}
                for kind in columns:
                    if all(header(label) in names for label in columns[kind].values()):
                        positions = header_positions(cells)
                        candidates[kind].append(name)
                        position_audit[kind] = {key: positions[header(label)] + 1
                                               for key, label in columns[kind].items() if header(label) in positions}
        if any(len(values) != 1 for values in candidates.values()):
            raise ValueError('Missing verified columns or ambiguous survey/master worksheets')
        updates, masters = candidates['survey'], candidates['master']
        with open_sheet(updates[0]) as sheet:
            survey = list(selected_rows(sheet, columns['survey']))
        with open_sheet(masters[0]) as sheet:
            master = list(selected_rows(sheet, columns['master']))
    if not survey or not master:
        raise ValueError('Both survey and master snapshots must contain records')
    for row in survey + master:
        raw = text(row['pam'])
        if v4:
            row['pam_display'] = raw
        row['pam'] = normalize_pam(raw)
        if raw and not row['pam']:
            row['pam_raw'] = raw
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
               'master_flag_counts': dict(Counter(text(row['master_flag']) for row in master)),
               'cross_sheet': reconcile(survey, master)}
    reporting_date = None
    if v4:
        for row in survey:
            # Keep only coverage bits, not customer free-text notes/reasons.
            for field in ('admin_note', 'incomplete_reason'):
                row[field + '_present'] = bool(text(row.pop(field)))
        summary['column_positions'] = position_audit
        summary['shifted_columns'] = {kind: [key for key, expected in values.items()
            if position_audit[kind].get(key) != expected] for kind, values in VERIFIED_POSITIONS.items()}
        summary['minat_counts'] = dict(Counter(text(row['minat']) for row in survey))
        summary['result_detail_counts'] = dict(Counter(text(row['result_detail']) for row in survey))
        summary['recommendation_counts'] = dict(Counter(text(row['recommendation']) for row in survey))
        summary['regional_counts'] = dict(Counter(text(row['region']) for row in survey))
        summary['interest_crosscheck_mismatches'] = sum((header(row['minat']) == 'berminat') !=
            (header(row['result']) == 'berminat') for row in survey)
        summary['status_partition_mismatches'] = sum((header(row['minat']) == 'berminat') !=
            (header(row['installation_status']) in {'done','assign fa','outstanding','cancel'}) for row in survey)
        summary['normalization_collisions'] = {}
        for kind, records in [('survey', survey), ('master', master)]:
            variants = {}
            for row in records:
                variants.setdefault(row['pam'], set()).add(row['pam_display'])
            summary['normalization_collisions'][kind] = sum(bool(key) and len(values)>1 for key, values in variants.items())
        summary['master_secondary_id_mismatches'] = sum(bool(text(row['pam_secondary'])) and
            normalize_pam(text(row['pam_secondary'])) != row['pam'] for row in master)
        # The report date is distinct from the last actual survey/event date.
        stamp = re.search(r'(?<!\d)(\d{2})(\d{2})(\d{4})(?!\d)', path.stem)
        if stamp:
            reporting_date = date(int(stamp[3]), int(stamp[2]), int(stamp[1])).isoformat()
    return {'layout_version': 4 if v4 else 2, 'workbook_sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
            **({'reporting_date': reporting_date} if v4 else {}),
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
    parser.add_argument('--legacy-layout', action='store_true', help='Reproduce the retained v2 intake only')
    args = parser.parse_args()
    intake = read_intake(args.workbook, v4=not args.legacy_layout)
    write_private(args.private_output, intake)
    print(json.dumps(intake['summary'], ensure_ascii=False, indent=2))
