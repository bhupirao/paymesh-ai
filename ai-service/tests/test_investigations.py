import socket
from copy import deepcopy
from uuid import uuid4
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.config import Settings

client = TestClient(app)
STAMP = '2026-11-13T00:00:00Z'

@pytest.fixture(autouse=True)
def offline(monkeypatch):
    def deny(*args, **kwargs):
        raise AssertionError('Network access forbidden')
    monkeypatch.setattr(socket.socket, 'connect', deny)
    monkeypatch.setattr(socket, 'create_connection', deny)

@pytest.fixture
def evidence():
    return dict(paymentId=str(uuid4()), amount='100.00', currency='INR', paymentStatus='CREATED', paymentMethod='UPI', collectedAt=STAMP)

def gateway(e, status='SUCCESS', **kwargs):
    return dict(id=str(uuid4()), paymentId=e['paymentId'], gatewayName='MOCK_RAZORPAY', gatewayTransactionId=str(uuid4()), status=status, createdAt=STAMP, updatedAt=STAMP, **kwargs)

def refund(e, amount):
    return dict(refundId=str(uuid4()), paymentId=e['paymentId'], amount=amount, status='SUCCESS', createdAt=STAMP)

def post(e):
    response = client.post('/api/v1/investigations', json=e)
    assert response.status_code == 200, response.text
    return response.json()

@pytest.mark.parametrize('path', ['/health', '/api/v1/health/readiness', '/openapi.json'])
def test_health(path):
    r = client.get(path)
    assert r.status_code == 200
    if path != '/openapi.json':
        assert r.json()['mode'] == 'deterministic'
        assert r.json()['status'] == 'UP'

@pytest.mark.parametrize('status,scenario', [('CREATED','CREATED'), ('PROCESSING','PROCESSING'), ('SUCCESS','SUCCESS'), ('FAILED','FAILED'), ('CANCELLED','INCONCLUSIVE'), ('REFUNDED','UNRESOLVED_REFUND')])
def test_states(evidence, status, scenario):
    evidence['paymentStatus'] = status
    r = post(evidence)
    assert r['scenario'] == scenario
    assert r['customerView'] and r['technicalView']
    assert r['analysisMode'] == 'DETERMINISTIC'

def test_timeout(evidence):
    evidence.update(paymentStatus='PROCESSING', gatewayTransactions=[gateway(evidence, 'TIMEOUT')])
    r = post(evidence)
    assert r['scenario'] == 'GATEWAY_TIMEOUT'
    assert 'wait for confirmation' in r['customerView']['summary']
    assert 'retry' not in str(r).lower()

def test_success_no_history(evidence):
    evidence.update(paymentStatus='SUCCESS', gatewayTransactions=[gateway(evidence)])
    r = post(evidence)
    assert r['scenario'] == 'SUCCESS'
    assert 'Confirmation was completed through' not in r['customerView']['summary']

@pytest.mark.parametrize('matched', [True, False])
def test_webhook(evidence, matched):
    g = gateway(evidence)
    evidence.update(paymentStatus='SUCCESS', gatewayTransactions=[g], webhooks=[dict(id=str(uuid4()), paymentId=evidence['paymentId'], gatewayTransactionId=g['gatewayTransactionId'] if matched else str(uuid4()), status='PROCESSED', outcome='SUCCESS', occurredAt=STAMP)])
    assert post(evidence)['scenario'] == ('WEBHOOK_RECOVERY' if matched else 'SUCCESS')

def test_reconciliation(evidence):
    evidence.update(paymentStatus='SUCCESS', reconciliation=[dict(id=str(uuid4()), paymentId=evidence['paymentId'], outcome='SUCCESS', statusBefore='PROCESSING', statusAfter='SUCCESS', result='RESOLVED', createdAt=STAMP)])
    assert post(evidence)['scenario'] == 'RECONCILIATION_RECOVERY'

@pytest.mark.parametrize('code,expected', [('UNSUPPORTED_CURRENCY', 'does not support'), ('OTHER', 'exact reason could not be determined'), (None, 'exact reason could not be determined')])
def test_failure(evidence, code, expected):
    evidence.update(paymentStatus='FAILED', gatewayTransactions=[gateway(evidence, 'FAILED', errorCode=code)])
    assert expected in post(evidence)['customerView']['summary']

@pytest.mark.parametrize('amounts,status,scenario,total', [(['30.00'],'SUCCESS','PARTIAL_REFUND','30.00'), (['100.00'],'REFUNDED','FULL_REFUND','100.00'), (['0.10','0.20'],'SUCCESS','PARTIAL_REFUND','0.30')])
def test_refunds(evidence, amounts, status, scenario, total):
    evidence.update(paymentStatus=status, refunds=[refund(evidence,a) for a in amounts])
    r = post(evidence)
    assert r['scenario'] == scenario
    assert f'successful refunds: {total}' in r['customerView']['whatHappened']
    assert 'days' not in str(r)
    assert 'has arrived' not in str(r)
    assert 'was debited' not in str(r)

def test_missing(evidence):
    assert any('unavailable' in s for s in post(evidence)['limitations'])

@pytest.mark.parametrize('status,gstatus', [('SUCCESS','FAILED'), ('FAILED','SUCCESS'), ('CREATED','TIMEOUT'), ('PROCESSING','SUCCESS')])
def test_conflicts(evidence, status, gstatus):
    evidence.update(paymentStatus=status, gatewayTransactions=[gateway(evidence,gstatus)])
    assert post(evidence)['investigationStatus'] == 'INCONCLUSIVE'

@pytest.mark.parametrize('field,value', [('paymentId','bad'), ('amount','-1'), ('amount','NaN'), ('amount','1.001'), ('amount',1.2), ('paymentStatus','PENDING'), ('paymentMethod','x'*101), ('currency','bad'), ('collectedAt','2026-11-13'), ('jwt','secret'), ('gatewayTransactions',[{}]*101)])
def test_invalid(evidence, field, value):
    evidence[field] = value
    assert client.post('/api/v1/investigations', json=evidence).status_code == 422

@pytest.mark.parametrize('kind', ['excess','duplicate','foreign','pending','future','float'])
def test_invalid_refunds(evidence, kind):
    evidence.update(paymentStatus='SUCCESS', refunds=[refund(evidence,'10.00')])
    r=evidence['refunds'][0]
    if kind=='excess': r['amount']='101.00'
    if kind=='duplicate': evidence['refunds'].append(deepcopy(r))
    if kind=='foreign': r['paymentId']=str(uuid4())
    if kind=='pending': r['status']='PENDING'
    if kind=='future': r['createdAt']='2027-01-01T00:00:00Z'
    if kind=='float': r['amount']=0.1
    assert client.post('/api/v1/investigations', json=evidence).status_code == 422

def test_config(monkeypatch):
    monkeypatch.setenv('PAYMESH_AI_PORT','8123')
    assert Settings(_env_file=None).port == 8123

def test_no_database_dependencies():
    from pathlib import Path
    deps=Path('requirements.txt').read_text().lower()
    assert all(name not in deps for name in ['psycopg','sqlalchemy','asyncpg'])
