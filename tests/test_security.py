import time

import pytest


@pytest.mark.parametrize('path',['/api/bootstrap','/api/analysis','/api/quality','/api/admin/audit','/api/reports/executive.csv','/api/legacy-report.pdf'])
def test_private_endpoints_require_session(client,path):
    assert client.get(path).status_code==401


def test_viewer_cannot_retrieve_customer_rows_or_change_admin_state(signed):
    client,boot=signed('guest')
    assert 'rec' not in boot['data'] and 'pdf' not in boot['data']
    assert 'FIXTURE SURVEYOR A' not in str(boot)
    assert client.post('/api/records/search',json={}).status_code==403
    assert client.get('/api/followups/nonexistent').status_code==403
    assert client.get('/api/admin/audit').status_code==403
    assert client.get('/api/legacy-report.pdf').status_code==403
    assert client.put('/api/admin/mappings',json={}).status_code==403
    assert client.post('/api/admin/targets',json={'month':'2026-11','target':10,'evidence':'fixture'}).status_code==403
    summary=client.get('/api/analysis').json()
    assert all('individuals' not in team for team in summary['teams'])
    report=client.get('/api/reports/outstanding.csv').content.decode('utf-8-sig')
    assert '10000006' not in report and 'FIXTURE SURVEYOR' not in report
    assert 'Source installation status,Outstanding survey rows' in report
    assert '\r\nCase reference,PAM ID,' not in report


def test_csrf_origin_and_role_escalation_are_rejected(signed):
    client,_=signed()
    assert client.post('/api/records/search',json={},headers={'origin':'https://attacker.invalid'}).status_code==403
    token=client.headers.pop('x-csrf-token')
    assert client.put('/api/admin/mappings',json={}).status_code==403
    client.headers['x-csrf-token']=token
    assert client.post('/api/records/search',json={'role':'owner'}).status_code==422
    assert client.post('/api/records/search',content=b'x'*32769).status_code==413


def test_logout_and_expiry_revoke_server_session(signed,app):
    client,_=signed()
    old=client.cookies.get('rpd_session')
    assert client.post('/api/logout').status_code==200
    assert client.get('/api/bootstrap',headers={'cookie':f'rpd_session={old}'}).status_code==401
    client.cookies.clear()
    client,_=signed()
    for session in app.state.sessions.values.values():
        session.created=time.monotonic()-3601
    assert client.get('/api/bootstrap').status_code==401


def test_static_surface_does_not_expose_source_or_backend(client):
    html=client.get('/')
    assert html.status_code==200 and 'id=enc' not in html.text
    assert '<script>' not in html.text
    for path in ['/backend/main.py','/.git/config','/tests/fixtures.py','/source.enc.json','/operations.sqlite3','/requirements.txt']:
        assert client.get(path).status_code==404
    assert "script-src 'self'" in html.headers['content-security-policy']
    assert html.headers['cache-control']=='no-store'


def test_invalid_credentials_are_generic_and_rate_limited(client,encrypted_source):
    for _ in range(10):
        response=client.post('/api/login',json={'account':'unknown-fixture','password':'not-a-production-secret'})
        assert response.status_code==401
    assert client.post('/api/login',json={'account':'fixture-admin','password':encrypted_source[1]}).status_code==429


def test_cookie_flags_and_validation_do_not_echo_passwords(client,encrypted_source):
    response=client.post('/api/login',json={'account':'fixture-admin','password':encrypted_source[1]})
    cookie=response.headers['set-cookie'].lower()
    assert 'httponly' in cookie and 'samesite=strict' in cookie
    # Local dev explicitly permits non-Secure cookies; production has Secure enabled.
    invalid=client.post('/api/login',json={'account':'fixture-admin','password':'sensitive-synthetic-value','unexpected':True})
    assert invalid.status_code==422 and 'sensitive-synthetic-value' not in invalid.text
