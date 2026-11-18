"""Offline synthetic output diagnostics; no real inference, credentials or filesystem outside tmp."""
import json
import os
from pathlib import Path
import socket
from types import SimpleNamespace
from uuid import uuid4

import pytest
from pydantic import ValidationError
from fastapi.testclient import TestClient
from app.config import Settings
from app.main import app
from app.api.chat import get_chat_settings
from app.schemas.chat import ChatRequest
from app.services import chat_service as chat
from app.services import chat_validation_diagnostics as diag
from app.services.local_provider import GenerationFailure

CID = '8d447340-43f2-4a84-a1a9-83f5af5b2694'

MARKER = 'PRIVATE_GENERATED_TEXT_MUST_NOT_APPEAR'
DATA = {'evidence': ['E0'], 'knowledge': ['K0']}
VALID = {'intent': 'PAYMENT_STATUS', 'variant': 'BASE', 'evidence': ['E0'], 'knowledge': ['K0']}

@pytest.fixture(autouse=True)
def offline(monkeypatch):
    def deny(*args, **kwargs):
        raise AssertionError('Real network forbidden')
    monkeypatch.setattr(socket.socket, 'connect', deny)
    monkeypatch.setattr(socket, 'create_connection', deny)
    yield
    app.dependency_overrides.clear()

@pytest.fixture
def sink(tmp_path, monkeypatch):
    monkeypatch.setattr(Path, 'home', classmethod(lambda cls: tmp_path.resolve()))
    root = tmp_path / '.config/paymesh-demo'
    root.mkdir(parents=True, mode=0o700)
    folder = root / 'diagnostic-test'
    folder.mkdir(mode=0o700)
    target = folder / diag.FILENAME
    target.touch(mode=0o600)
    return target

def configuration(path=None):
    return Settings(_env_file=None, analysis_mode='RAG_LLM', generation_enabled=True,
                    chat_api_enabled=True, chat_service_token='T'*64,
                    chat_validation_diagnostics_file=str(path) if path else None)

def reasons(path):
    return [json.loads(line) for line in path.read_text().splitlines()]

@pytest.mark.parametrize('output,code', [
    ('not JSON '+MARKER, 'INVALID_JSON'),
    ('{"intent":NaN}', 'INVALID_JSON'),
    ('{"intent":"'+MARKER+'","intent":"PAYMENT_STATUS"}', 'DUPLICATE_JSON_KEY'),
    (json.dumps(VALID | {'unexpected': MARKER}), 'SCHEMA_MISMATCH'),
    ('[]', 'SCHEMA_MISMATCH'),
    (json.dumps(VALID | {'variant': MARKER}), 'INVALID_VARIANT'),
    (json.dumps(VALID | {'intent': MARKER}), 'INTENT_MISMATCH'),
    (json.dumps(VALID | {'knowledge': [MARKER]}), 'KNOWLEDGE_ALIAS_MISMATCH'),
    (json.dumps(VALID | {'evidence': [MARKER]}), 'EVIDENCE_ALIAS_MISMATCH'),
])
def test_fixed_reason_only_for_each_rejection(sink, output, code, caplog, capsys):
    with pytest.raises(GenerationFailure) as error:
        chat._validated_selection(output, 'PAYMENT_STATUS', DATA, configuration(sink), CID)
    assert error.value.reason == 'VALIDATION_FAILED'
    expected={'correlationId': CID, 'reasonCode': code}
    if code in diag.SCHEMA_REASONS:
        expected['schemaFailureCode']='ENUM_VALUE_INVALID' if code=='INVALID_VARIANT' else ('ROOT_STRUCTURE_INVALID' if output=='[]' else 'EXTRA_FIELD_FORBIDDEN')
    assert reasons(sink) == [expected]
    assert MARKER not in sink.read_text() + caplog.text + str(capsys.readouterr())

@pytest.mark.parametrize('field', ['intent', 'variant', 'evidence', 'knowledge'])
def test_missing_or_wrong_typed_fields_remain_strict(sink, field):
    value = dict(VALID); value.pop(field)
    with pytest.raises(GenerationFailure):
        chat._validated_selection(json.dumps(value), 'PAYMENT_STATUS', DATA, configuration(sink), CID)
    assert reasons(sink) == [{'correlationId': CID, 'reasonCode': 'SCHEMA_MISMATCH', 'schemaFailureCode':'REQUIRED_FIELD_MISSING'}]

@pytest.mark.parametrize('field,aliases', [('evidence', []), ('evidence', ['E0','E0']), ('knowledge', []), ('knowledge', ['K0','K0'])])
def test_missing_and_duplicate_aliases_are_not_normalized(sink, field, aliases):
    with pytest.raises(GenerationFailure):
        chat._validated_selection(json.dumps(VALID | {field: aliases}), 'PAYMENT_STATUS', DATA, configuration(sink), CID)
    assert reasons(sink)[0]['reasonCode'] == field.upper()+'_ALIAS_MISMATCH'

def test_unexpected_validation_failure_is_fixed_and_preserves_exception(sink, monkeypatch, caplog):
    def broken(*args):raise RuntimeError(MARKER)
    monkeypatch.setattr(chat.Selection, 'model_validate', broken)
    with pytest.raises(RuntimeError):
        chat._validated_selection(json.dumps(VALID), 'PAYMENT_STATUS', DATA, configuration(sink), CID)
    assert reasons(sink) == [{'correlationId': CID, 'reasonCode':'OTHER_VALIDATION_FAILURE'}]
    assert MARKER not in sink.read_text()+caplog.text

class Provider:
    def __init__(self, output=None):self.output=output
    def generate(self, messages):
        if self.output is not None:return self.output
        data=json.loads(messages[-1]['content'])
        return json.dumps({'intent':data['intent'],'variant':'EXPLAIN','evidence':data['evidence'],'knowledge':data['knowledge']})

def request():
    return ChatRequest(correlationId=CID,callerRole='ADMIN',question='What is idempotency?')

def test_successful_structured_response_is_identical(sink):
    req=request()
    a=chat.converse(req,configuration(),provider=Provider())
    b=chat.converse(req,configuration(sink),provider=Provider())
    assert a.model_dump()==b.model_dump()
    assert b.analysis_mode=='RAG_LLM' and b.generation_status=='SUCCEEDED'
    assert sink.read_text()==''

@pytest.mark.parametrize('output', ['not JSON', '{"intent":"a","intent":"b"}', json.dumps(VALID | {'variant': MARKER})])
def test_public_fallback_unchanged_with_diagnostics(sink, output):
    req=request()
    before=chat.converse(req,configuration(),provider=Provider(output))
    after=chat.converse(req,configuration(sink),provider=Provider(output))
    assert before.model_dump()==after.model_dump()
    assert after.analysis_mode=='RAG_ASSISTED' and after.generation_status=='VALIDATION_FAILED'
    assert not any('diagnostic' in key.lower() for key in after.model_dump(by_alias=True))

def test_public_api_contains_no_diagnostic_reason_or_path(sink, monkeypatch, caplog):
    import app.api.chat as route
    app.dependency_overrides[get_chat_settings]=lambda:configuration(sink)
    monkeypatch.setattr(route,'converse',lambda req,cfg:chat.converse(req,cfg,provider=Provider('not JSON '+MARKER)))
    response=TestClient(app).post('/api/v1/chat',json=request().model_dump(mode='json',by_alias=True),headers={'X-PayMesh-AI-Chat-Token':'T'*64})
    assert response.status_code==200
    assert response.json()['generationStatus']=='VALIDATION_FAILED'
    for private in [MARKER,str(sink),'INVALID_JSON','reasonCode','T'*64]:assert private not in response.text+caplog.text
    assert reasons(sink)==[{'correlationId': CID, 'reasonCode':'INVALID_JSON'}]

def test_unexpected_exception_keeps_existing_unavailable_fallback(sink, monkeypatch):
    def broken(*args):raise RuntimeError(MARKER)
    monkeypatch.setattr(chat.Selection,'model_validate',broken)
    result=chat.converse(request(),configuration(sink),provider=Provider())
    assert result.generation_status=='UNAVAILABLE'
    assert reasons(sink)==[{'correlationId': CID, 'reasonCode':'OTHER_VALIDATION_FAILURE'}]

def test_disabled_diagnostics_write_nothing(sink):
    assert configuration().chat_validation_diagnostics_file is None
    assert not diag.record(configuration(),'INVALID_JSON',CID)
    assert sink.read_text()==''

def test_unknown_reason_not_written(sink):
    assert not diag.record(configuration(sink),MARKER,CID)
    assert sink.read_text()==''

@pytest.mark.parametrize('change', ['file-mode','directory-mode','file-symlink','directory-symlink','hardlink','missing','wrong-filename','outside','relative','owner'])
def test_unprotected_sinks_rejected_without_writing(sink, change, monkeypatch, tmp_path):
    target=sink
    if change=='file-mode':sink.chmod(0o644)
    elif change=='directory-mode':sink.parent.chmod(0o755)
    elif change=='file-symlink':
        old=sink.with_name('original');sink.rename(old);sink.symlink_to(old)
    elif change=='directory-symlink':
        old=sink.parent.with_name('original-dir');sink.parent.rename(old);sink.parent.symlink_to(old,target_is_directory=True)
    elif change=='hardlink':os.link(sink,sink.with_name('second-link'))
    elif change=='missing':sink.unlink()
    elif change=='wrong-filename':target=sink.with_name('secrets.env')
    elif change=='outside':target=tmp_path/diag.FILENAME
    elif change=='relative':target=Path(diag.FILENAME)
    elif change=='owner':monkeypatch.setattr(diag.os,'getuid',lambda:os.stat(sink).st_uid+1)
    with pytest.raises(ValidationError):configuration(target)

def test_runtime_permission_change_does_not_leak_or_change_fallback(sink, caplog):
    config=configuration(sink);sink.chmod(0o644)
    result=chat.converse(request(),config,provider=Provider('not JSON '+MARKER))
    assert result.generation_status=='VALIDATION_FAILED'
    assert sink.read_text()=='' and MARKER not in caplog.text

def test_bounded_sink_not_truncated_or_rotated(sink):
    config=configuration(sink);sink.write_text('x'*diag.MAX_BYTES)
    assert not diag.record(config,'INVALID_JSON',CID)
    assert len(sink.read_bytes())==diag.MAX_BYTES

def test_busy_or_unwritable_sink_never_logs_raw_errors(sink, monkeypatch, caplog, capsys):
    config=configuration(sink)
    monkeypatch.setattr(diag.fcntl,'flock',lambda *args:(_ for _ in ()).throw(BlockingIOError(MARKER)))
    assert not diag.record(config,'INVALID_JSON',CID)
    assert sink.read_text()=='' and MARKER not in caplog.text+str(capsys.readouterr())

@pytest.mark.parametrize('cid', [None, '', 'not-a-uuid', CID.upper(), 'x'*500, 123,
    '00000000-0000-0000-0000-000000000000', '8d447340-43f2-1a84-a1a9-83f5af5b2694'])
def test_invalid_or_missing_correlation_never_written(sink, cid):
    assert not diag.record(configuration(sink), 'INVALID_JSON', cid)
    assert sink.read_text() == ''


def test_request_correlation_reaches_protected_sink_only(sink):
    req = request()
    response = chat.converse(req,configuration(sink),provider=Provider('not JSON'))
    assert reasons(sink) == [{'correlationId': req.correlation_id, 'reasonCode':'INVALID_JSON'}]
    assert response.correlation_id == req.correlation_id  # Existing contract, unchanged.
    assert 'reasonCode' not in response.model_dump_json(by_alias=True)


def test_concurrent_request_correlations_do_not_mix(sink):
    from concurrent.futures import ThreadPoolExecutor
    config=configuration(sink)
    ids=[str(uuid4()) for _ in range(8)]
    def run(cid):
        req=ChatRequest(correlationId=cid,callerRole='ADMIN',question='What is idempotency?')
        return chat.converse(req,config,provider=Provider('invalid JSON')).generation_status
    with ThreadPoolExecutor(max_workers=8) as pool:
        assert list(pool.map(run,ids)) == ['VALIDATION_FAILED']*8
    # Nonblocking writer may omit busy records; every retained row remains attributable.
    rows=reasons(sink)
    assert rows
    assert all(set(row)=={'correlationId','reasonCode'} and row['correlationId'] in ids and row['reasonCode']=='INVALID_JSON' for row in rows)
    assert len({row['correlationId'] for row in rows}) == len(rows)
