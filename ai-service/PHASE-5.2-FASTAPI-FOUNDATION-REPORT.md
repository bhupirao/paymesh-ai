# Phase 5.2 — FastAPI foundation report

## 1. Environment verification

Working directory: `/Users/bhupirao/Developer/paymesh-ai/ai-service`.
Git root: `/Users/bhupirao/Developer/paymesh-ai`. Existing staged and unstaged Java
work was present and preserved. No applicable AGENTS.md files were found.
Existing `.venv/bin/python`: Python 3.13.10. Verified runtime packages: FastAPI
0.162.5, Uvicorn 0.54.0, Pydantic 2.14.3, Pydantic Settings 2.16.2. Test packages:
HTTPX 0.28.1, pytest 9.2.0. No dependencies installed or environment recreated.
Host environment supplied by user: Intel x86_64 MacBook Air, macOS 12.7.6, 8 GB RAM.

## 2. Exact files created

- `.env.example`
- `.gitignore`
- `README.md`
- `app/__init__.py`
- `app/api/__init__.py`
- `app/api/health.py`
- `app/api/investigations.py`
- `app/config.py`
- `app/main.py`
- `app/schemas/__init__.py`
- `app/schemas/investigation.py`
- `app/services/__init__.py`
- `app/services/investigation_service.py`
- `knowledge_base/README.md`
- `requirements-dev.txt`
- `requirements.txt`
- `tests/__init__.py`
- `tests/example-request.json`
- `tests/example-response.json`
- `tests/test_investigations.py`
- `PHASE-5.2-FASTAPI-FOUNDATION-REPORT.md` (this report)

Python/pytest also generated ignored cache/bytecode files during verification.

## 3. Architecture and decisions

FastAPI routing delegates to a pure snapshot investigation service. Pydantic v2
validates closed, bounded schemas; Settings uses PAYMESH_AI_ environment variables.
Loopback defaults, no CORS, no startup probes, no database drivers or model libraries.
Decimal arithmetic only; decimal strings/integers required for incoming money.
Responses contain generated investigation/payment IDs, timestamp, scenario, status,
customer and technical views, evidence paths, limitations and DETERMINISTIC mode.
Certainty is categorical; no fabricated confidence percentages.

## 4. Java API contract mapping

Inspected API-REFERENCE.md, root README, final Java backend report, payment/gateway/
refund DTOs, PaymentStatus, GatewayStatus, refund entity and migration, Observation,
WebhookPayload/Inbox, OutcomeApplier, ReconciliationService and settlement controller.
README contains the complete source-to-normalized-field table. No merchant/customer
IDs, authentication headers or raw webhook payload are accepted. collectedAt is
collector metadata. Webhook outcome is projected from parsed payload.status; audit
snake_case columns are converted to camelCase. Refund status supports only SUCCESS,
verified in both entity and database constraint. Unsupported hypothetical refund
statuses are rejected rather than presented as Java functionality.

## 5. Scenarios and precedence

Malformed/financially impossible evidence is rejected; conflicts are inconclusive.
Then incomplete REFUNDED evidence, successful partial/full refunds, supported SUCCESS
recovery (webhook before reconciliation), ordinary SUCCESS, CREATED, PROCESSING or
TIMEOUT, FAILED, then inconclusive fallback. CANCELLED remains inconclusive.
Known failure explanations translate actual INVALID_AMOUNT/UNSUPPORTED_CURRENCY codes;
unknown reasons remain explicit. A final SUCCESS row never implies historical TIMEOUT.
Missing optional evidence is unavailable, not proof an event never occurred.

## 6. Customer message examples

- “Your payment has been created but has not been processed yet.”
- “Your payment is taking longer than expected. Please wait for confirmation before making another payment.”
- “Your payment was completed successfully. You do not need to pay again.”
- “The refund was recorded as successful in the simulated payment system.”

## 7. Tests

`.venv/bin/python -m pip check`: No broken requirements found.
`.venv/bin/python -m pytest -q`: **44 passed, 1 warning**, 2.69 seconds on final run.
An initial test identified float refund input coercion; a validator fixed it before
this passing run. Tests cover endpoints/OpenAPI, lifecycle and recovery, absent
history, known/unknown failure, Decimal multiple-refund totals, unresolved refunds,
conflicting evidence, malformed UUIDs/money/status/timestamps, excess lengths,
duplicate/foreign rows, views, safe messages, configuration and offline behavior.
Socket connect/create_connection are blocked throughout tests; no database packages
are declared, imported or used. All evidence is synthetic.
Warning: installed Starlette deprecates HTTPX TestClient in favor of httpx2. The
requested HTTPX/TestClient works; no extra dependency was installed. pip also reports
an unwritable user cache (nonfatal).

## 8. Local smoke test

Sandbox initially denied loopback binding. After approved execution outside the
sandbox, port 8000 was verified free and only this Python process was started:

`.venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8000`

GET /health, GET /api/v1/health/readiness, GET /openapi.json and synthetic POST
/api/v1/investigations all returned **200**. Full synthetic request/response saved
in tests/example-request.json and tests/example-response.json. The owned Uvicorn
child was terminated and reaped (return code -15). No other process was stopped.

## 9. Known limitations

Local unauthenticated, supplied snapshot analysis only. No Java evidence retrieval,
cryptographic provenance, bank verification, persistence, request byte limit,
production auth/rate limiting, or external health assertions. List/string limits
apply after HTTP body parsing. Arbitrary text must be sanitized by a future collector;
validation errors may echo invalid input, so synthetic evidence only. Direct runtime
pins are not a transitive lock. Snapshot references are not authenticated citations.
Recovery evidence supports a mechanism, not an invented prior timeout or bank debit.
Pending/failed refund scenarios await real Java contract support. Incomplete audit
history and CANCELLED cannot establish an explanation. This is not production ready.

## 10. Exact user commands

```bash
cd ~/Developer/paymesh-ai/ai-service
source .venv/bin/activate
# Optional only if restoring dependencies:
python -m pip install -r requirements-dev.txt
.venv/bin/python -m pip check
.venv/bin/python -m pytest -q
.venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

In another terminal in ai-service:

```bash
curl -sS http://127.0.0.1:8000/health
curl -sS http://127.0.0.1:8000/api/v1/health/readiness
curl -sS http://127.0.0.1:8000/openapi.json
curl -sS http://127.0.0.1:8000/api/v1/investigations \
  -H 'Content-Type: application/json' --data-binary @tests/example-request.json
```

Swagger: http://127.0.0.1:8000/docs . Stop the manually started service with Ctrl-C.

## 11. Next-phase readiness

The independent validated evidence contract and deterministic service provide a
foundation for lightweight retrieval and local LLM explanations. No RAG, inference,
Ollama, Docker, paid API or heavy ML dependency was implemented or installed.
Integration must add authenticated Java retrieval and preserve financial rules.
Stop here before the next phase.

## 12. Preservation

Java was neither started nor stopped. No PostgreSQL connection or database command
was performed. Java backend, backend-backup and ZIP archives were not modified.
No git add, commit, push, reset or clean was run. Existing tracked working diff SHA256
remained `e3e10b89476e6f958ac80be530958322aba6b5a332be932d442cf9eeaa7d44c0`;
staged diff SHA256 remained
`aa7d246ee1f91e9d8521735fb684fd9663d6dfcd1b408c08ecc22960acb249c6` before/after.
All project deliverables are inside ai-service. The Git index was unchanged.
