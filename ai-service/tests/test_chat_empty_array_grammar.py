"""Outgoing schema compatibility; strict Python response validation is unchanged."""
import json
import httpx
import pytest
from app.services import chat_service as chat
from app.services.local_provider import LocalHTTPProvider
from tests.test_chat_validation_diagnostics import offline, configuration, request

BASE={'intent':'KNOWLEDGE','variant':'BASE','evidence':[],'knowledge':['K0']}
INVALID=[]
for field in BASE:
    INVALID.append({key:value for key,value in BASE.items() if key!=field})
for field,value in [('intent',17),('variant',17),('evidence','E0'),('knowledge','K0')]:
    INVALID.append(BASE | {field:value})
INVALID += [BASE | {'extra':'SYNTHETIC'},BASE | {'variant':'INVALID'},BASE | {'intent':'PAYMENT_STATUS'},
    BASE | {'evidence':[{'ref':'E0'}]},BASE | {'knowledge':[{'ref':'K0'}]},[],
    json.dumps('SYNTHETIC'),BASE | {'evidence':['E0']},BASE | {'knowledge':[]},
    BASE | {'knowledge':['K0','K0']},BASE | {'knowledge':['K9']},json.dumps(BASE)+'x',
    '{"intent":"KNOWLEDGE","intent":"KNOWLEDGE","variant":"BASE","evidence":[],"knowledge":["K0"]}']


def transport(monkeypatch,value=None,variant='BASE'):
    captured={};original_client=httpx.Client
    def handler(req):
        payload=json.loads(req.content);captured.update(payload)
        data=json.loads(payload['messages'][-1]['content'])
        output=({'intent':data['intent'],'variant':variant,'evidence':data['evidence'],'knowledge':data['knowledge']} if value is None else value)
        content=output if isinstance(output,str) else json.dumps(output)
        return httpx.Response(200,json={'choices':[{'finish_reason':'stop','message':{'content':content}}]})
    mock_transport=httpx.MockTransport(handler)
    def client(**kwargs):
        assert kwargs['timeout']==min(configuration().generation_timeout,15)
        assert kwargs['follow_redirects'] is False and kwargs['trust_env'] is False
        return original_client(transport=mock_transport,**kwargs)
    monkeypatch.setattr('app.services.local_provider.httpx.Client',client)
    return captured

@pytest.mark.parametrize('variant',['BASE','EXPLAIN'])
def test_actual_outgoing_empty_evidence_schema_and_valid_responses(monkeypatch,variant):
    before=chat.Selection.model_json_schema()
    captured=transport(monkeypatch,variant=variant)
    response=chat.converse(request(),configuration())
    assert response.analysis_mode=='RAG_LLM' and response.generation_status=='SUCCEEDED'
    schema=captured['response_format']['schema']
    assert captured['response_format']['type']=='json_object'
    assert schema['additionalProperties'] is False
    assert set(schema['required'])==set(schema['properties'])=={'intent','variant','evidence','knowledge'}
    assert schema['properties']['intent']['const']=='KNOWLEDGE'
    assert schema['properties']['variant']['enum']==['BASE','EXPLAIN']
    evidence=schema['properties']['evidence']
    assert evidence['type']=='array' and evidence['items']['type']=='string' and evidence['const']==[]
    assert 'minItems' not in evidence and 'maxItems' not in evidence
    knowledge=schema['properties']['knowledge']
    assert knowledge['minItems']==knowledge['maxItems']==1
    assert knowledge['items']=={'type':'string','enum':['K0']} and 'const' not in knowledge
    assert chat.Selection.model_json_schema()==before
    assert captured['model']==configuration().model_name and captured['max_tokens']==128
    assert captured['temperature']==0.1 and captured['stream'] is False

@pytest.mark.parametrize('aliases',[([],[]),([],['K0']),(['E0'],[]),(['E0','E1'],['K0','K1'])])
def test_schema_loop_handles_both_alias_arrays_without_zero_length_bounds(monkeypatch,aliases):
    # Mock only prompt data to cover both zero/nonzero branches, including future
    # zero-knowledge generation. Actual no-retrieval behavior remains unchanged.
    original=chat.prompt
    def prompt(result,config):
        messages,variants,data=original(result,config)
        data['evidence'],data['knowledge']=aliases
        messages[-1]['content']=json.dumps(data)
        return messages,variants,data
    monkeypatch.setattr(chat,'prompt',prompt)
    captured=transport(monkeypatch)
    result=chat.converse(request(),configuration())
    assert result.generation_status=='SUCCEEDED'
    schema=captured['response_format']['schema']
    for key,values in zip(('evidence','knowledge'),aliases):
        field=schema['properties'][key]
        if not values:
            assert field['const']==[] and 'minItems' not in field and 'maxItems' not in field
        else:
            assert 'const' not in field and field['minItems']==field['maxItems']==len(values)
            assert field['items']['enum']==values

@pytest.mark.parametrize('value',INVALID)
def test_invalid_synthetic_selections_still_fail_closed(monkeypatch,value):
    transport(monkeypatch,value=value)
    response=chat.converse(request(),configuration())
    assert response.analysis_mode=='RAG_ASSISTED'
    assert response.generation_status=='VALIDATION_FAILED'
