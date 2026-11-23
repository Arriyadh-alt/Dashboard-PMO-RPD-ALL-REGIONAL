def test_one_client_cannot_bypass_throttle_by_rotating_accounts(client):
    for index in range(100):
        assert client.post('/api/login',json={'account':f'unknown-{index}','password':'synthetic-invalid-password'}).status_code==401
    assert client.post('/api/login',json={'account':'unknown-101','password':'synthetic-invalid-password'}).status_code==429
