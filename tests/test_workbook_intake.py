"""Synthetic binary fixtures exercise the actual XLSB reader, not Excel automation."""
from datetime import date
import json
from pathlib import Path
import struct
from types import SimpleNamespace
import zipfile

import pytest
from pyxlsb import biff12

from scripts.workbook_intake import (MASTER_COLUMNS, SURVEY_COLUMNS, date_system,
                                     excel_date, profile, read_intake, reconcile,
                                     selected_rows, write_private)


def record(kind, body=b''):
    size = len(body)
    length = []
    while size > 127:
        length.append((size & 127) | 128)
        size >>= 7
    length.append(size)
    return kind.to_bytes(1 if kind < 128 else 2, 'little') + bytes(length) + body


def string(value):
    encoded = value.encode('utf-16le')
    return struct.pack('<I', len(encoded) // 2) + encoded


def binary_fixture(path, date1904=False, missing=None, survey_pam='000000123'):
    """Minimal, valid BIFF12 parts sufficient for pyxlsb's real streaming parser."""
    strings = []
    def sheet(columns, values):
        headers = list(reversed(list(columns.values())))
        if missing:
            headers = [name for name in headers if name != missing]
        rows = [headers, [values.get(name) for name in headers]]
        body = record(biff12.DIMENSION, struct.pack('<IIII', 0, 1, 0, len(headers)-1))
        body += record(biff12.SHEETDATA)
        for number, row in enumerate(rows):
            body += record(biff12.ROW, struct.pack('<I', number))
            for column, value in enumerate(row):
                if value is None:
                    continue
                prefix = struct.pack('<II', column, 0)
                if isinstance(value, (int, float)):
                    body += record(biff12.FLOAT, prefix + struct.pack('<d', value))
                else:
                    strings.append(value)
                    body += record(biff12.STRING, prefix + struct.pack('<I', len(strings)-1))
        return body + record(biff12.SHEETDATA_END)
    survey = {name: '' for name in SURVEY_COLUMNS.values()}
    survey.update({'1. Tanggal Survey': 45658, '2. Regional': 'Fixture Region',
                   '3. Area Bisnis': 'Fixture Area', '4. Nama Surveyor': 'Fixture Surveyor',
                   '5. PAM ID': survey_pam, 'Hasil Canvasing': 'Berminat',
                   'Kelurahan': 'FIXTURE KEL', 'Konfirmasi Pemasangan': 'Done'})
    survey['Customer name - NEVER import'] = 'SYNTHETIC SECRET CUSTOMER'
    columns = {**SURVEY_COLUMNS, 'not_selected': 'Customer name - NEVER import'}
    survey_part = sheet(columns, survey)
    master = {name: '' for name in MASTER_COLUMNS.values()}
    master.update({'PAM_ID': '000000123', 'FINAL FLAG': 'POTENSI', 'Tunggakan': 1000})
    master_part = sheet(MASTER_COLUMNS, master)
    wb = b'' if date1904 is None else record(biff12.WORKBOOKPR, struct.pack('<I', int(date1904)))
    wb += record(biff12.SHEETS)
    for i, name in enumerate(('Update data TEST', 'MASTER DATA'), 1):
        wb += record(biff12.SHEET, struct.pack('<II', 0, i) + string('rId'+str(i)) + string(name))
    wb += record(biff12.SHEETS_END)
    sst = record(biff12.SST, struct.pack('<II', len(strings), len(strings)))
    sst += b''.join(record(biff12.SI, b'\0' + string(value)) for value in strings)
    sst += record(biff12.SST_END)
    with zipfile.ZipFile(path, 'w') as archive:
        archive.writestr('xl/workbook.bin', wb)
        archive.writestr('xl/sharedStrings.bin', sst)
        archive.writestr('xl/_rels/workbook.bin.rels', '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Target="worksheets/sheet1.bin"/><Relationship Id="rId2" Target="worksheets/sheet2.bin"/></Relationships>')
        archive.writestr('xl/worksheets/sheet1.bin', survey_part)
        archive.writestr('xl/worksheets/sheet2.bin', master_part)


def test_real_binary_reader_uses_headers_and_excludes_unneeded_personal_fields(tmp_path):
    source = tmp_path/'synthetic.xlsb'
    binary_fixture(source)
    result = read_intake(source)
    assert result['date_system'] == '1900'
    assert result['summary']['survey'] == dict(rows=1, unique_valid_pam=1,
                                               invalid_pam_rows=0, duplicate_excess_rows=0)
    assert result['summary']['dates']['survey_date'] == {'min':'2025-01-01', 'max':'2025-01-01'}
    assert result['survey'][0]['pam'] == '123'
    assert result['survey'][0]['source_row'] == 2
    assert result['master'][0]['arrears'] == 1000
    assert 'SYNTHETIC SECRET CUSTOMER' not in json.dumps(result)
    output = tmp_path/'private.json'
    write_private(output, result)
    assert output.stat().st_mode & 0o777 == 0o600
    with pytest.raises(FileExistsError):
        write_private(output, result)


def test_missing_layout_columns_stop_instead_of_guessing_positions(tmp_path):
    source = tmp_path/'synthetic.xlsb'
    binary_fixture(source, missing='Hasil Canvasing')
    with pytest.raises(ValueError, match='Missing verified columns'):
        read_intake(source)


def test_actual_workbook_date_system_is_respected(tmp_path):
    source = tmp_path/'synthetic.xlsb'
    binary_fixture(source, date1904=True)
    assert date_system(source) is True
    assert read_intake(source)['date_system'] == '1904'
    assert excel_date(1, date1904=True) == '1904-01-02'
    assert excel_date(45658.75) == '2025-01-01'
    assert excel_date(None) is None
    assert excel_date('2026-11-23') == '2026-11-23'
    with pytest.raises(ValueError):
        excel_date(float('nan'))
    with pytest.raises(ValueError):
        excel_date('ambiguous date')


def test_late_timestamps_cannot_round_into_the_next_calendar_day():
    assert excel_date(45658 + 86399.9 / 86400) == '2025-01-01'
    assert excel_date(45658 + 86399.999 / 86400, date1904=True) == excel_date(45658, date1904=True)


def test_omitted_optional_workbook_properties_default_to_1900(tmp_path):
    source = tmp_path/'synthetic.xlsb'
    binary_fixture(source, date1904=None)
    assert date_system(source) is False
    intake = read_intake(source)
    assert intake['date_system'] == '1900'
    assert intake['survey'][0]['survey_date'] == '2025-01-01'


def test_reconciliation_normalizes_ids_and_labels_without_choosing_duplicate_rows():
    def row(pam, region='Barat', area='Sunter', kel='A'):
        return dict(pam=pam, region=region, area=area, kelurahan=kel)
    survey = [row(123), row('000000124'), row(125), row('000000125'),
              row('invalid'), row(127)]
    master = [row('000000123', ' Regional  BARAT ', ' AB  Sunter '),
              row(124, 'Regional Pusat', 'AB Jatibaru', 'B'), row(125), row(126)]
    assert reconcile(survey, master) == {
        'matched_valid_ids':3, 'survey_ids_not_in_master':1, 'master_ids_not_in_survey':1,
        'geography_compared_unique_ids':2, 'geography_withheld_duplicate_ids':1,
        'normalized_geography_mismatches':{'region':1, 'area':1, 'kelurahan':1},
    }
    assert profile(survey) == {'rows':6, 'unique_valid_pam':4,
                               'invalid_pam_rows':1, 'duplicate_excess_rows':1}


@pytest.mark.parametrize('pam,raw', [('12X3','12X3'), (0,'0'), (None,None)])
def test_malformed_ids_remain_distinguishable_from_missing_ids(tmp_path, pam, raw):
    source = tmp_path/'synthetic.xlsb'
    binary_fixture(source, survey_pam=pam)
    intake = read_intake(source)
    assert intake['survey'][0]['pam'] == ''
    assert intake['survey'][0].get('pam_raw') == raw
    assert intake['summary']['survey']['invalid_pam_rows'] == 1


def test_plaintext_repository_paths_are_refused():
    root = Path(__file__).resolve().parents[1]
    with pytest.raises(ValueError, match='outside the repository'):
        write_private(root/'forbidden.json', {})
    with pytest.raises(ValueError, match='outside the repository'):
        read_intake(root/'forbidden.xlsb')


def test_empty_cached_formula_rows_are_not_records_but_zero_ids_remain_visible():
    def cell(row, value):
        return SimpleNamespace(r=row, c=0, v=value)
    sheet = SimpleNamespace(rows=lambda sparse: iter([
        [cell(0, 'PAM_ID')], [cell(1, '')], [cell(2, '  ')],
        [cell(3, None)], [cell(4, 0)], [cell(5, '000000123')],
    ]))
    assert list(selected_rows(sheet, {'pam':'PAM_ID'})) == [
        {'source_row':5, 'pam':0}, {'source_row':6, 'pam':'000000123'},
    ]
