"""Fixed category diagnostics only; network blocked and all values synthetic."""
import json
from uuid import uuid4
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.api.chat import get_chat_settings
from app.services import chat_service as chat
from app.services import chat_validation_diagnostics as diag
from app.services.local_provider import GenerationFailure
from tests.test_chat_validation_diagnostics import (
    offline, sink, configuration, request, Provider, reasons, CID, DATA, VALID, MARKER,
)

CASES = [
    ({k:v for k,v in VALID.items() if k!='intent'}, 'REQUIRED_FIELD_MISSING','SCHEMA_MISMATCH'),
    (VALID | {'intent':17}, 'FIELD_TYPE_MISMATCH','SCHEMA_MISMATCH'),
    (VALID | {MARKER:MARKER}, 'EXTRA_FIELD_FORBIDDEN','SCHEMA_MISMATCH'),
    (VALID | {'variant':MARKER}, 'ENUM_VALUE_INVALID','INVALID_VARIANT'),
    (VALID | {'evidence':[{'secret':MARKER}]}, 'NESTED_STRUCTURE_INVALID','SCHEMA_MISMATCH'),
    ([MARKER], 'ROOT_STRUCTURE_INVALID','SCHEMA_MISMATCH'),
    ({k:v for k,v in (VALID | {'variant':MARKER}).items() if k!='intent'},'MULTIPLE_SCHEMA_FAILURES','SCHEMA_MISMATCH'),
]

@pytest.mark.parametrize('value,expected,coarse',CASES)
def test_actual_strict_errors_map_to_fixed_categories(sink,value,expected,coarse,caplog,capsys):
    with pytest.raises(GenerationFailure):chat._validated_selection(json.dumps(value),'PAYMENT_STATUS',DATA,configuration(sink),CID)
    assert reasons(sink)==[{'correlationId':CID,'reasonCode':coarse,'schemaFailureCode':expected}]
    assert MARKER not in sink.read_text()+caplog.text+str(capsys.readouterr())

@pytest.mark.parametrize('issues',[
    [],None,{},[None],[{'type':'future_rule','loc':('intent',),'msg':MARKER}],
    [{'type':'string_type','loc':(MARKER,)}],
    [{'type':'string_type','loc':('evidence',False)}],
    [{'type':'string_type','loc':('evidence',0,MARKER)}],
    [{'type':'missing','loc':['intent']}],
    [{'type':'missing','loc':('intent',)}]*33,
])
def test_unknown_malformed_or_oversized_error_sets_are_fixed_unknown(issues):
    assert diag.schema_failure_code(issues)=='UNKNOWN_SCHEMA_FAILURE'

@pytest.mark.parametrize('code',sorted(diag.SCHEMA_FAILURE_CODES))
def test_writer_accepts_only_fixed_codes_without_field_data(sink,code):
    assert diag.record(configuration(sink),'SCHEMA_MISMATCH',CID,code)
    assert reasons(sink)==[{'correlationId':CID,'reasonCode':'SCHEMA_MISMATCH','schemaFailureCode':code}]

@pytest.mark.parametrize('code',[MARKER,'',[MARKER],{'field':MARKER},123])
def test_writer_rejects_non_allowlisted_codes(sink,code):
    assert not diag.record(configuration(sink),'SCHEMA_MISMATCH',CID,code)
    assert sink.read_text()==''

@pytest.mark.parametrize('cid',[None,'',MARKER])
def test_missing_or_malformed_correlation_cannot_write_schema_diagnostics(sink,cid):
    assert not diag.record(configuration(sink),'SCHEMA_MISMATCH',cid,'REQUIRED_FIELD_MISSING')
    assert sink.read_text()==''


def test_schema_code_not_permitted_on_unrelated_coarse_reason(sink):
    assert not diag.record(configuration(sink),'INVALID_JSON',CID,'REQUIRED_FIELD_MISSING')
    assert sink.read_text()==''


def test_unknown_schema_failure_is_recorded_without_dynamic_labels(sink):
    code=diag.schema_failure_code([{'type':MARKER,'loc':(MARKER,),'msg':MARKER,'input':MARKER}])
    assert diag.record(configuration(sink),'SCHEMA_MISMATCH',CID,code)
    assert reasons(sink)[0]['schemaFailureCode']=='UNKNOWN_SCHEMA_FAILURE'
    assert MARKER not in sink.read_text()


def test_same_category_multiple_errors_do_not_add_field_names():
    issues=[{'type':'missing','loc':('intent',)},{'type':'missing','loc':('variant',)}]
    assert diag.schema_failure_code(issues)=='REQUIRED_FIELD_MISSING'

@pytest.mark.parametrize('value,expected,coarse',CASES)
def test_public_fallback_does_not_change_for_schema_categories(sink,value,expected,coarse):
    req=request();provider=Provider(json.dumps(value))
    before=chat.converse(req,configuration(),provider=provider)
    after=chat.converse(req,configuration(sink),provider=provider)
    assert before.model_dump()==after.model_dump()
    assert after.generation_status=='VALIDATION_FAILED'


def test_public_route_does_not_expose_schema_diagnostics(sink,monkeypatch,caplog):
    import app.api.chat as route
    app.dependency_overrides[get_chat_settings]=lambda:configuration(sink)
    monkeypatch.setattr(route,'converse',lambda req,cfg:chat.converse(req,cfg,provider=Provider(json.dumps({MARKER:MARKER}))))
    response=TestClient(app).post('/api/v1/chat',json=request().model_dump(mode='json',by_alias=True),headers={'X-PayMesh-AI-Chat-Token':'T'*64})
    assert response.status_code==200 and response.json()['generationStatus']=='VALIDATION_FAILED'
    for value in (MARKER,'schemaFailureCode','MULTIPLE_SCHEMA_FAILURES',str(sink)):
        assert value not in response.text+caplog.text
    assert set(reasons(sink)[0])=={'correlationId','reasonCode','schemaFailureCode'}


def test_concurrent_schema_records_remain_request_correlated(sink):
    from concurrent.futures import ThreadPoolExecutor
    config=configuration(sink)
    pairs=[(str(uuid4()),code) for code in sorted(diag.SCHEMA_FAILURE_CODES)]
    expected=dict(pairs)
    with ThreadPoolExecutor(max_workers=8) as pool:
        list(pool.map(lambda pair:diag.record(config,'SCHEMA_MISMATCH',pair[0],pair[1]),pairs))
    rows=reasons(sink);assert rows
    assert all(row['schemaFailureCode']==expected[row['correlationId']] for row in rows)
    assert len({row['correlationId'] for row in rows})==len(rows)
