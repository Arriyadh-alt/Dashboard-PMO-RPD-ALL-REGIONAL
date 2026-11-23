import pytest


@pytest.mark.parametrize('scope',[{'ab':99},{'kel':99}])
def test_removed_preset_geography_is_an_explicit_scope_error(signed,scope):
    client,_=signed()
    assert client.get('/api/analysis',params=scope).status_code==422
    assert client.get('/api/reports/executive.csv',params=scope).status_code==422
    assert client.post('/api/records/search',json={'scope':scope}).status_code==422
