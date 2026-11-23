"""Synthetic end-to-end mapping: legacy units, curated roster and encrypted update."""
import base64
from copy import deepcopy
import json
import secrets

import pytest

from backend.analytics import build_analysis, prepare
from backend.auth import decrypt_source
from backend.browser_api import LocalEvents
from scripts.update_encrypted import update
from scripts.workbook_contract import bootstrap_aliases, convert, private_path
from scripts.workbook_intake import write_private
from tests.fixtures import encrypted_fixture


def matching_snapshot():
    dictionaries = {
        'c1': ['', 'Berminat', 'Belum Diketahui', 'Tidak Berminat'],
        'c2': ['', 'Meter Terpasang', 'Permanent Total Disconnection (PTD)', 'Tidak Berminat', 'Potensi Reconnection'],
        'kf': ['', 'Done', 'Assign FA', 'Outstanding', 'Cancel'], 'kd': [''],
        'rp': ['', 'Potensi Reconnection', 'Permanent Total Disconnection (PTD)'],
        'mf': ['', 'POTENSI', 'NON POTENSI'], 'sc': ['', 'TOTAL'],
        'pr': ['', 'Di luar Master Data', 'Non potensi (master)', 'Potensi tersisa',
               'Potensi, sudah berminat (dikeluarkan)', 'Potensi, tapi Update: tidak ada bangunan atau PTD']}
    baseline = {
        'months': ['2026-09', '2026-10', '2026-11'], 'abs': ['Fixture Area'], 'reg': ['Fixture Region'],
        'kels': ['FIXTURE KEL'], 'svs': ['Fixture Surveyor A', 'Fixture Surveyor B'], 'st': [0, 1],
        'kl': ['Fixture Team A', 'Fixture Team B'], 'dic': dictionaries,
        'rec': {'pam': [101, 102, 103], 'mi': [1, 0, 2], 't': [261001, 260901, 261101],
                'ab': [0, 0, 0], 'kel': [0, 0, 0], 'sv': [0, 1, 0],
                'fa': [240608, 0, 0], 'mt': [261102, 0, 0], 'tg': [150, 200, 0],
                'c1': [1, 2, 3], 'c2': [1, 2, 3], 'kf': [1, 0, 0], 'kd': [0, 0, 0],
                'rp': [1, 2, 0], 'mf': [1, 1, 0], 'sc': [1, 1, 0], 'pr': [4, 5, 1]},
        'A': [[1, 0, 1,1,0,0,0,0,0,1,0,0], [0, 0, 1,0,0,0,1,0,0,0,0,0], [2, 0, 1,0,1,0,0,0,0,0,0,0]],
        'S': [[1,0,0,0, 1,1,1,0,0,0,0,0,0,0], [0,0,1,1, 1,0,0,0,0,0,0,0,0,1], [2,0,0,0, 1,0,0,0,0,0,1,0,0,0]],
        'K': [[1,0,0, 1,1,1,1,0,0,0,0,0], [0,0,0, 1,0,0,0,0,0,0,0,0], [2,0,0, 1,1,0,0,0,0,0,1,0]],
        'E': [[0,0,1,0], [2,0,0,1]], 'P': [[0,0,3,1,1]],
        'W': [[0,0,1,2,1,1,1], [0,0,0,0,1,0,0], [0,0,2,3,1,0,0]],
        'meta': {'rows': 3, 'uniq': 3, 'tmin': '2026-09-01', 'tmax': '2026-11-01',
                 'korlaps': ['Fixture Team A', 'Fixture Team B'], 'rt_bad': 1,
                 'sync': {'pot_master': 3, 'deduct': 1, 'deduct_tp': 1, 'non_berm': 0, 'outside': 0,
                          'master_missing': 1, 'ab_diff': 0, 'kel_diff': 0, 'nb': 0, 'ptd': 1, 'dp_b': 0, 'berm_in': 1}},
        'pdf': base64.b64encode(b'%PDF-1.4\n% Synthetic prior artifact\n%%EOF').decode()}
    survey = []
    for j, pam in enumerate(baseline['rec']['pam']):
        d = baseline['rec']
        def iso(value):
            return f'20{value//10000:02d}-{value//100%100:02d}-{value%100:02d}' if value else None
        survey.append(dict(pam=str(pam), survey_date=iso(d['t'][j]), region='Fixture Region', area='Fixture Area',
                           kelurahan='Fixture Kel', surveyor='Fixture Raw Alias' if j != 1 else 'Fixture Surveyor B',
                           result=dictionaries['c1'][d['c1'][j]], result_detail=dictionaries['c2'][d['c2'][j]],
                           installation_status=dictionaries['kf'][d['kf'][j]], obstacle='',
                           recommendation=dictionaries['rp'][d['rp'][j]], fa_date=iso(d['fa'][j]), meter_date=iso(d['mt'][j])))
    master = [dict(pam=str(p), region=' Regional  Fixture Region ', area='AB Fixture Area', kelurahan='fixture kel',
                   rw=rw, rt=rt, master_flag='POTENSI', potential_status='Data Potensi', customer_status='TOTAL',
                   arrears=100, total_arrears=total) for p,rw,rt,total in [(101,1,2,150), (102,None,150,200), (104,2,3,300)]]
    return baseline, {'layout_version': 2, 'survey': survey, 'master': master}


def test_identical_snapshot_keeps_every_record_group_roster_and_legacy_pdf():
    baseline, intake = matching_snapshot()
    before = deepcopy((baseline, intake))
    aliases = bootstrap_aliases(baseline, intake)
    data, summary = convert(baseline, intake, aliases, full_snapshot=True, bootstrap=True)
    assert data == baseline
    assert summary == dict(changed=False, survey_rows=3, master_rows=3, potential=3,
                           matched_interested=1, remaining=2, alias_labels=2)
    assert (baseline, intake) == before
    # Input row order never changes the contract or alias association.
    intake['survey'].reverse()
    assert convert(baseline, intake, aliases, full_snapshot=True)[0] == baseline


def test_changed_snapshot_extends_event_and_cohort_months_and_reencrypts_without_rekey(tmp_path):
    baseline, intake = matching_snapshot()
    aliases = bootstrap_aliases(baseline, intake)
    new = {**intake['survey'][0], 'pam': '104', 'survey_date': '2026-12-02',
           'installation_status': 'Assign FA', 'result_detail': 'Potensi Reconnection',
           'fa_date': '2026-12-03', 'meter_date': None}
    intake['survey'].append(new)
    data, summary = convert(baseline, intake, aliases, full_snapshot=True)
    assert summary['changed'] and summary['remaining'] == 1
    assert data['months'][-1] == '2026-12'
    assert data['rec']['pam'] == [101, 102, 103, 104]
    assert data['rec']['tg'][-1] == 300  # Total including fines, NOT bare Tunggakan.
    assert data['rec']['mi'][-1] == 3
    assert data['E'] == [[0,0,1,0], [2,0,0,1], [3,0,1,0]]
    assert data['P'] == [[0,0,3,2,1]]
    assert data['meta']['sync']['master_missing'] == 0
    for key in ('svs', 'st', 'kl'):
        assert data[key] == baseline[key]
    assert data['meta']['korlaps'] == baseline['meta']['korlaps']
    assert data['pdf'] != baseline['pdf'] and base64.b64decode(data['pdf']).startswith(b'%PDF-')
    analysis = build_analysis(data, prepare(data), {}, LocalEvents(), 'owner')
    assert {k: analysis['metrics'][k] for k in ('canvassed', 'interested', 'installed')} == dict(canvassed=4, interested=2, installed=1)
    password = secrets.token_urlsafe(24)
    envelope = encrypted_fixture(baseline, {'admin': (password, 'a')})
    source, plain, output = (tmp_path/name for name in ('source.enc.json', 'contract.json', 'new.enc.json'))
    source.write_text(json.dumps(envelope))
    write_private(plain, data)
    assert update(source, plain, output, 'admin', password) == dict(canvassed=4, interested=2, installed=1)
    actual = json.loads(output.read_text())
    assert actual['u'] == envelope['u'] and actual['i'] != envelope['i']
    assert decrypt_source(output, 'admin', password)[0] == data


def test_bootstrap_cannot_learn_aliases_from_a_changed_snapshot():
    baseline, intake = matching_snapshot()
    aliases = bootstrap_aliases(baseline, intake)
    intake['master'][0]['total_arrears'] = 999
    with pytest.raises(ValueError, match='exact record'):
        convert(baseline, intake, aliases, full_snapshot=True, bootstrap=True)
    intake['survey'][1]['surveyor'] = 'Fixture Raw Alias'
    with pytest.raises(ValueError, match='Ambiguous surveyor'):
        bootstrap_aliases(baseline, intake)


@pytest.mark.parametrize('change,match', [
    (lambda i: i['survey'].pop(), 'omits existing survey'),
    (lambda i: i['master'].pop(0), 'omits known master'),
    (lambda i: i['survey'].append(i['survey'][0]), 'duplicate PAM'),
    (lambda i: i['master'].append(i['master'][0]), 'duplicate PAM'),
    (lambda i: i['survey'][0].update(pam='invalid'), 'Invalid or duplicate'),
    (lambda i: i['survey'][0].update(surveyor='Unreviewed Person'), 'Unmapped surveyor'),
    (lambda i: i['survey'][0].update(area='Unreviewed Area'), 'Unmapped geography'),
    (lambda i: i['survey'][0].update(installation_status='Unreviewed Status'), 'Unreviewed classification'),
    (lambda i: i['master'][0].update(total_arrears=float('nan')), 'Invalid numeric'),
    (lambda i: i.update(layout_version=1), 'version 2'),
])
def test_unsafe_or_unmapped_inputs_fail_without_silent_repairs(change, match):
    baseline, intake = matching_snapshot()
    aliases = bootstrap_aliases(baseline, intake)
    change(intake)
    with pytest.raises(ValueError, match=match):
        convert(baseline, intake, aliases, full_snapshot=True)


def test_explicit_snapshot_confirmation_and_private_paths_are_required():
    baseline, intake = matching_snapshot()
    with pytest.raises(ValueError, match='full-snapshot confirmation'):
        convert(baseline, intake, {})
    from scripts.build_pages import ROOT
    with pytest.raises(ValueError, match='outside the repository'):
        private_path(ROOT/'customer-contract.json')
