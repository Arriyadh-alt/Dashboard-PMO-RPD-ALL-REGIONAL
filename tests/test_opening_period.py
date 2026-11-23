import pytest

from backend.analytics import build_analysis, prepare
from backend.store import Store
from tests.fixtures import fixture_data


@pytest.mark.parametrize('declared_start',['2026-08-01',260801])
def test_opening_bucket_uses_covered_actual_dates_not_its_month_label(tmp_path,declared_start):
    data=fixture_data()
    data['meta']['tmin']=declared_start
    data['rec']['t'][:2]=[260801,260808]
    report=build_analysis(data,prepare(data),{'start':'2026-08-08','end':'2026-08-14'},Store(tmp_path/'state.sqlite3'),'owner')
    assert report['previous'] is not None
    assert report['previous']['canvassed']==1
