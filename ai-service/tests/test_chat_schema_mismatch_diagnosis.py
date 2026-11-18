"""Synthetic ambiguity reproduction, not a reconstruction of private model output.

The retained coarse reason cannot identify a failed field. Preserve strict rejection
and approved successful responses; never infer a model fix from these fixtures.
"""
import json
import pytest
from app.services import chat_service as chat
from app.services.local_provider import GenerationFailure, LocalHTTPProvider
from app.services.chat_validation_diagnostics import SCHEMA_FAILURE_CODES
from tests.test_chat_validation_diagnostics import (
    offline, sink, configuration, request, Provider, reasons, CID, DATA, VALID,
)

@pytest.mark.parametrize('value', [
    {k:v for k,v in VALID.items() if k!='intent'},
    {k:v for k,v in VALID.items() if k!='variant'},
    {k:v for k,v in VALID.items() if k!='evidence'},
    {k:v for k,v in VALID.items() if k!='knowledge'},
    VALID | {'intent':17},
    VALID | {'intent':None},
    VALID | {'evidence':'E0'},
    VALID | {'knowledge':'K0'},
    VALID | {'evidence':None},
    VALID | {'evidence':[{'ref':'E0'}]},
    VALID | {'knowledge':{'refs':['K0']}},
    VALID | {'knowledge':[17]},
    VALID | {'untrusted_extra_field':'SYNTHETIC_ONLY'},
    [],
    'SYNTHETIC_ROOT_STRING',
    {k:v for k,v in (VALID | {'variant':'INVALID'}).items() if k!='intent'},
])
def test_distinct_schema_failures_preserve_coarse_reason_with_fixed_category(sink,value):
    with pytest.raises(GenerationFailure) as error:
        chat._validated_selection(json.dumps(value),'PAYMENT_STATUS',DATA,configuration(sink),CID)
    assert error.value.reason=='VALIDATION_FAILED'
    row=reasons(sink)[0]
    assert row['correlationId']==CID and row['reasonCode']=='SCHEMA_MISMATCH'
    assert row['schemaFailureCode'] in SCHEMA_FAILURE_CODES
    assert 'SYNTHETIC' not in sink.read_text()

@pytest.mark.parametrize('variant',['BASE','EXPLAIN'])
def test_valid_structured_selection_still_passes_without_diagnostic(sink,variant):
    value=VALID | {'variant':variant}
    assert chat._validated_selection(json.dumps(value),'PAYMENT_STATUS',DATA,configuration(sink),CID).model_dump()==value
    assert sink.read_text()==''


def test_valid_local_provider_response_format_contains_strict_schema(sink):
    schema=chat.Selection.model_json_schema()
    assert set(schema['required'])=={'intent','variant','evidence','knowledge'}
    assert schema['additionalProperties'] is False
    assert schema['properties']['intent']['type']=='string'
    assert schema['properties']['variant']['enum']==['BASE','EXPLAIN']
    for field in ('evidence','knowledge'):
        assert schema['properties'][field]['type']=='array'
        assert schema['properties'][field]['items']['type']=='string'
    provider=LocalHTTPProvider(configuration(sink),output_schema=schema)
    assert provider.response_format=={'type':'json_object','schema':schema}


def test_coarse_schema_diagnostic_keeps_public_fallback_unchanged(sink):
    req=request()
    invalid=Provider(json.dumps({'intent':'KNOWLEDGE'}))
    before=chat.converse(req,configuration(),provider=invalid)
    after=chat.converse(req,configuration(sink),provider=invalid)
    assert before.model_dump()==after.model_dump()
    assert after.generation_status=='VALIDATION_FAILED'
    assert reasons(sink)==[{'correlationId':CID,'reasonCode':'SCHEMA_MISMATCH','schemaFailureCode':'REQUIRED_FIELD_MISSING'}]
