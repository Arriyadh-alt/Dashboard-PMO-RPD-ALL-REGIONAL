from backend.analytics import build_analysis, prepare
from backend.store import Store
from tests.fixtures import fixture_data


def test_status_filtered_trends_evaluate_conflicts_inside_each_bucket(tmp_path):
    data=fixture_data()
    for day,month,status in [(261005,1,1),(261105,2,3)]:
        for values in data['rec'].values(): values.append(values[0])
        for key,value in {'pam':10000012,'t':day,'mi':month,'c1':1,'kf':status}.items(): data['rec'][key][-1]=value
    prepared=prepare(data)
    store=Store(tmp_path/'state.sqlite3')
    wide=build_analysis(data,prepared,{'statuses':['Done']},store,'owner')
    for unit,period,filters in [
        ('monthly','2026-10',{'m0':1,'m1':1}),
        ('weekly','2026-W41',{'start':'2026-10-05','end':'2026-10-11'}),
        ('daily','2026-10-05',{'start':'2026-10-05','end':'2026-10-05'})]:
        narrow=build_analysis(data,prepared,{**filters,'statuses':['Done']},store,'owner')
        actual=next(row for row in wide['trend_series'][unit] if row['month']==period)
        assert actual['interested']==narrow['metrics']['interested']
        assert actual['installed']==narrow['metrics']['installed']
