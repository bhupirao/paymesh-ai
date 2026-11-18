"""Opt-in local synthetic diagnostics; uses production prompt and transport unchanged.

Run from ai-service: .venv/bin/python -m scripts.diagnose_llm --output /tmp/paymesh-before.json
Never use this output-capturing tool with real customer evidence.
"""
import argparse
import json
import time
from pathlib import Path
from unittest.mock import patch

import httpx
from pydantic import ValidationError

from app.config import Settings
from app.schemas.investigation import InvestigationRequest
from app.services.investigation_service import investigate
from app.services.local_provider import LocalHTTPProvider
from app.services.rag_service import WordingSelection, approved_wording, enrich


def deterministic_facts_preserved(evidence, response):
    baseline = investigate(evidence).model_dump(mode='json', by_alias=True)
    candidate = json.loads(json.dumps(response))
    wording = approved_wording(investigate(evidence))
    assert candidate['customerView']['summary'] in wording['customer'].values()
    assert candidate['technicalView']['technicalExplanation'] in wording['technical'].values()
    for item in (baseline, candidate):
        for field in ('investigationId', 'generatedAt', 'analysisMode', 'generationStatus', 'knowledgeReferences'):
            item.pop(field)
        item['customerView'].pop('summary')
        item['technicalView'].pop('technicalExplanation')
    return baseline == candidate


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True)
    parser.add_argument('--matrix', action='store_true')
    parser.add_argument('--api-url', choices=['http://127.0.0.1:8000', 'http://127.0.0.1:8001'],
                        default='http://127.0.0.1:8000')
    args = parser.parse_args()
    config = Settings(_env_file=None, analysis_mode='RAG_LLM', generation_enabled=True,
                      inference_url='http://127.0.0.1:8082/v1/chat/completions',
                      model_name='paymesh-qwen', generation_timeout=30)
    original = json.loads(Path('tests/example-request.json').read_text())
    cases = {'PROCESSING': original}
    if args.matrix:
        for status in ('SUCCESS', 'FAILED'):
            cases[status] = dict(original, paymentStatus=status)
        for label, amount, status in [('PARTIAL_REFUND', '30.00', 'SUCCESS'),
                                       ('FULL_REFUND', '100.00', 'REFUNDED')]:
            cases[label] = dict(original, paymentStatus=status, refunds=[dict(
                refundId='22222222-2222-4222-8222-222222222222', paymentId=original['paymentId'],
                amount=amount, status='SUCCESS', createdAt=original['collectedAt'])])
        cases['RECONCILIATION_RECOVERY'] = dict(original, paymentStatus='SUCCESS', reconciliation=[dict(
            id='33333333-3333-4333-8333-333333333333', paymentId=original['paymentId'],
            outcome='SUCCESS', statusBefore='PROCESSING', statusAfter='SUCCESS',
            result='RESOLVED', createdAt=original['collectedAt'])])
    records = []
    real_client = httpx.Client
    for label, payload in cases.items():
        record = dict(case=label, request=payload)
        # Observe the exact production HTTP bytes, including usage/timings discarded by provider.
        def capture(response):
            response.read()
            record['model_request'] = json.loads(response.request.content)
            record['model_status'] = response.status_code
            record['model_response'] = response.json()
        def client_factory(**kwargs):
            return real_client(event_hooks={'response': [capture]}, **kwargs)
        evidence = InvestigationRequest.model_validate(payload)
        started = time.perf_counter()
        with patch('app.services.local_provider.httpx.Client', client_factory):
            result = enrich(evidence, config)
        record['elapsed_seconds'] = round(time.perf_counter() - started, 3)
        record['result'] = result.model_dump(mode='json', by_alias=True)
        record['deterministic_facts_preserved'] = deterministic_facts_preserved(evidence, record['result'])
        raw = record.get('model_response', {}).get('choices', [{}])[0].get('message', {}).get('content')
        if raw is not None:
            try:
                selection = WordingSelection.model_validate_json(raw)
                record['scenario_matches'] = selection.scenario == investigate(evidence).scenario
            except ValidationError as exc:
                record['validation_errors'] = exc.errors(include_url=False)
        records.append(record)
        Path(args.output).write_text(json.dumps(records, indent=2))
        print(label, result.analysis_mode, result.generation_status, record['elapsed_seconds'], flush=True)
    # Real HTTP route: do not replace the user's server or its configuration.
    with real_client(timeout=35, trust_env=False) as client:
        for record in records:
            started = time.perf_counter()
            try:
                response = client.post(args.api_url + '/api/v1/investigations', json=record['request'])
                record['fastapi'] = dict(status=response.status_code, response=response.json(),
                                         elapsed_seconds=round(time.perf_counter() - started, 3))
                if response.status_code == 200:
                    record['fastapi']['deterministic_facts_preserved'] = deterministic_facts_preserved(
                        InvestigationRequest.model_validate(record['request']), response.json())
            except httpx.HTTPError as exc:
                record['fastapi'] = dict(error=type(exc).__name__)
            Path(args.output).write_text(json.dumps(records, indent=2))
    # A refused loopback port exercises the real transport without stopping any server.
    unavailable = config.model_copy(update={'inference_url': 'http://127.0.0.1:1/v1/chat/completions'})
    started = time.perf_counter()
    result = enrich(InvestigationRequest.model_validate(original), unavailable, provider=LocalHTTPProvider(unavailable))
    records.append(dict(case='UNAVAILABLE', elapsed_seconds=round(time.perf_counter() - started, 3),
        deterministic_facts_preserved=deterministic_facts_preserved(
            InvestigationRequest.model_validate(original), result.model_dump(mode='json', by_alias=True)),
        result=result.model_dump(mode='json', by_alias=True)))
    Path(args.output).write_text(json.dumps(records, indent=2))


if __name__ == '__main__':
    main()
