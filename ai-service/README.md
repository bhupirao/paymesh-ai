# PayMesh AI internal analysis service

**Phase6.9.1 conversational engine implemented and automated-verified; not live activated.**
229 Python tests passed (102 existing +127 new). No new live inference, service restart,
Java chat integration, frontend chat or database access occurred. The existing local Qwen/
llama.cpp investigation integration is preserved. See
[Phase6.9.1 report](PHASE-6.9.1-CONVERSATIONAL-AI-REPORT.md) for exact contracts/limits,
security boundaries, tests and the pending opt-in local diagnostic.

Internal `POST /api/v1/chat` accepts bounded question/history plus a minimized supplied
snapshot; role/source labels are NOT authentication. The future Java caller must authorize
all records and scope before sending evidence. Keep Python loopback/private; no public
proxy route was added. Deterministic facts/exact minor-unit arithmetic, existing local
TF-IDF retrieval and schema-validated approved wording selection are used. No financial
tools or conversation persistence. Chat/investigation share one nonblocking inference slot.

Tests (no live inference/network):

```bash
cd "$HOME/Developer/paymesh-ai/ai-service"
.venv/bin/python -m pytest -q
.venv/bin/python -m compileall -q app scripts tests
```

Do not restart the existing service for this development batch. External future Uvicorn
launchers must use loopback and `--no-access-log`; the module launcher now disables access
logging. Optional new **knowledge-only** local inference diagnostic, only after separate
operator approval, without starting a server:

```bash
.venv/bin/python -m scripts.diagnose_chat --confirm-local-inference
```

This was NOT run. Uses only the already-running approved127.0.0.1:8082 llama.cpp and existing
paymesh-qwen alias. No real evidence/accounts or downloads. Fallback is not LLM success.

## Historical Phase5.3A notes

The original foundation notes below are retained as history; statements about missing
live model/Java integration are superseded by later Phase5.3B/5.4 reports and the current
project baseline. They are not claims that this batch reran live integration.

# PayMesh AI investigation service — Phase 5.3A

Local synthetic-evidence investigation with deterministic financial analysis,
optional lexical retrieval and a disabled-by-default local model provider.
No real LLM inference has been verified. No model, runtime or ML dependency was
installed. This service is not production ready and has no authenticated Java integration.

## Run and test

```bash
cd ~/Developer/paymesh-ai/ai-service
source .venv/bin/activate
# Only needed when restoring the already-installed dependencies:
python -m pip install -r requirements-dev.txt
.venv/bin/python -m pip check
.venv/bin/python -m pytest -q
.venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Swagger: http://127.0.0.1:8000/docs ; OpenAPI: http://127.0.0.1:8000/openapi.json .
Use the existing .venv. Direct dependency versions are verified pins, not a full
transitive lock. HTTPX 0.28.1 is now a runtime dependency; no new package is needed.
Settings optionally read `.env`, using the `PAYMESH_AI_` prefix. `python -m app.main`
uses configured host/port; explicit Uvicorn options control its listener directly.
Keep the listener on loopback. Java/database/model connectivity is never required
at startup. Health remains UP while optional retrieval/generation can fall back.

## Architecture and structure

`app/api/investigations.py` validates requests then calls `rag_service.enrich`.
The independent `investigation_service.investigate` always creates authoritative
facts, money totals, scenario, safe actions and certainty first. The RAG service
optionally retrieves knowledge, builds a privacy-minimized prompt, calls a provider
and validates its constrained wording selection. The model cannot replace facts.

- `app/config.py`: typed, bounded settings and literal loopback-IP URL validation.
- `app/api/body_limit.py`: ASGI investigation body bound before JSON parsing.
- `app/schemas/investigation.py`: evidence and response contracts.
- `app/services/retrieval.py`: Retriever protocol, fixed corpus loader, TF-IDF.
- `app/services/local_provider.py`: Provider protocol and HTTPX local transport.
- `app/services/rag_service.py`: prompt, approved wording, validation and fallback.
- `knowledge_base/`: eight curated Markdown documents and metadata conventions.
- `tests/`: original tests, focused RAG/security tests and synthetic examples.

## Modes and compatible response extensions

| Configured mode | Behavior | Actual response analysisMode |
|---|---|---|
| DETERMINISTIC (default) | Rules only; no KB/model calls | DETERMINISTIC |
| RAG_ASSISTED | Rules plus relevant knowledge references; text remains deterministic | RAG_ASSISTED if retrieval succeeds, otherwise DETERMINISTIC |
| RAG_LLM | Retrieval plus enabled local wording selection | RAG_LLM only after provider success and output validation; otherwise RAG_ASSISTED or DETERMINISTIC |

RAG_LLM configuration also requires `PAYMESH_AI_GENERATION_ENABLED=true`; invalid
combinations fail configuration validation. generation_enabled alone does not
activate calls in another mode. Set `PAYMESH_AI_ANALYSIS_MODE=RAG_ASSISTED` for
retrieval without a runtime. Modes are server configuration, not caller options.

Existing request fields and response views remain. Response analysisMode now permits
three values; clients with a closed enum must update. Additive response fields:
`knowledgeReferences` (document/chunk IDs, title, source references, score),
`generationStatus` and `technicalView.rootCauseCertainty`. `certainty` still describes
the snapshot observation; rootCauseCertainty describes only the causal explanation.
For PROCESSING without gateway evidence: certainty=CONFIRMED, rootCauseCertainty=
INCONCLUSIVE, rootCause="The underlying cause could not be determined from the supplied evidence."
The root cause is no longer a repeated payment state. Customer messages contain no
internal state codes; technicalExplanation retains detailed status and audit evidence.

`generationStatus` is DISABLED, NOT_ATTEMPTED, SUCCEEDED, NO_RELEVANT_CONTEXT,
RETRIEVAL_UNAVAILABLE, TIMEOUT, UNAVAILABLE, INVALID_RESPONSE, VALIDATION_FAILED or
CONTEXT_LIMIT. These are safe reason codes, never internal exception messages.
Fallback preserves original deterministic views; retrieval metadata can remain.
Never describe fallback wording as model generated. RAG_LLM denotes validated
model-selected approved wording, not open-ended narrative generation.

Health `/health` and `/api/v1/health/readiness` preserve existing fields and add
configuredAnalysisMode and modelConnectivity=NOT_VERIFIED. `mode` reflects the
configured mode in lowercase; it does not assert that generation succeeded.
No model availability probe or connectivity claim is made.

## Knowledge and lexical retrieval

The corpus covers lifecycle, timeouts, webhooks, reconciliation, failure reasons,
refunds, idempotency and communication. Each document distinguishes verified PayMesh
behavior from general guidance, with stable IDs and local Java source references.
No real gateway or bank integration is claimed.

The standard-library retriever uses term counts weighted by smoothed IDF and cosine
similarity. This is lexical RAG retrieval, not semantic vector search. Query terms
come only from deterministic scenario, payment state and gateway status enums, never
arbitrary error text. Chunks are at most 800 characters with document ID, ordinal and
content hash; IDs stay stable across unchanged loads. Ranking uses descending score,
then chunk ID. Default threshold .12; default top-k 3 (maximum 5); total context
budget 3000 characters (maximum 6000), including text and metadata. Whole chunks
that do not fit are skipped. Empty/irrelevant context safely skips generation.
Scores are retrieval relevance, not financial confidence. Fixed filenames only;
there is no path/URL parameter or document upload endpoint. Replacing Retriever
with an embedding implementation later does not change financial analysis.

Example retrieval: `GATEWAY TIMEOUT PROCESSING` ranks PM-KB-TIMEOUT first
(score 0.555376); `PARTIAL REFUND` ranks PM-KB-REFUNDS first (0.539708);
`WEBHOOK RECOVERY` ranks PM-KB-WEBHOOK first (0.639923).

## Local provider contract (future runtime)

No runtime is installed or started by Python. Future compatible servers must accept
POST `/v1/chat/completions` with model, messages, temperature=.1, bounded max_tokens,
stream=false and response_format={"type":"json_object"}. Successful responses must
have choices[0].finish_reason="stop" and a string message.content. Compatibility and
quality with an actual llama.cpp build remain unverified.

| Setting suffix (prefix PAYMESH_AI_) | Default | Bound |
|---|---|---|
| INFERENCE_URL | http://127.0.0.1:8080/v1/chat/completions | HTTP literal loopback IPv4/IPv6 only, explicit port, exact path; no DNS names, credentials, query or fragment |
| MODEL_NAME | local-model | 1–100 safe identifier characters |
| GENERATION_TIMEOUT | 10 seconds | 1–30 seconds per HTTPX timeout operation |
| MAX_OUTPUT_TOKENS | 128 | 32–512 |
| CONTEXT_CHARS | 12000 | 6000–24000 characters for serialized prompt content |
| RETRIEVAL_TOP_K | 3 | 1–5 |
| RETRIEVAL_CONTEXT_CHARS | 3000 | 100–6000 |
| RETRIEVAL_THRESHOLD | .12 | greater than zero, at most one |
| REQUEST_BODY_BYTES | 131072 | 1024–262144 |

`localhost` DNS names are deliberately rejected; use 127.0.0.1 or [::1]. Redirects
and HTTPX environment proxies are disabled; no API keys or authorization header.
Response bytes are capped at 16384 and model content at 2048 characters. Timeout,
connection error, unavailable model, bad HTTP/JSON and truncated output fall back.
The context setting is a character budget, not a tokenizer-accurate model context
window; actual server context/token limits must be selected and tested next phase.
HTTPX timeout is not a total wall-clock deadline against a trickling local server.

## Prompt and output validation

Evidence and retrieved text are explicitly marked as data. Prompts omit UUIDs,
raw error messages, customer/payment-method strings and authentication data. Only a
minimal validated projection, deterministic conclusions, approved wording and local
KB chunks are included. No full prompts/evidence are logged.

The model returns exactly:

```json
{"scenario":"PROCESSING","customer_variant":"PLAIN","technical_variant":"CONCISE"}
```

Pydantic forbids extra fields, limits selectors to BASE/PLAIN and BASE/CONCISE and
requires a matching deterministic scenario. Any free text, amounts, invented status,
recovery or action fields fail validation. Approved server-side templates render the
chosen variants; the model cannot author arbitrary explanations, amounts, actions or
certainty. Customer title/whatHappened/nextAction and all financial facts stay fixed.
The approved variants are shown in the prompt. This deliberately narrow foundation
trades expressive freedom for inspectable output. Prompt instructions alone cannot
eliminate arbitrary hallucinations; template validation blocks them from rendering
here. Future free-text generation would need additional safeguards and evaluation.

## Customer and technical example

Processing customer view:

- Title: Your payment is still being processed
- Summary: Your payment is taking longer than expected. Please wait for confirmation before making another payment.
- What happened: We are still waiting for the final payment confirmation.
- Next action: Please wait for an update. If your payment remains unresolved, contact support.

Technical view: observedPaymentStatus=PROCESSING; certainty=CONFIRMED;
rootCauseCertainty=INCONCLUSIVE. Explanation: "No final outcome is confirmed. The
payment is PROCESSING." This confirms the supplied observation, not the cause of delay.

```bash
curl -sS http://127.0.0.1:8000/api/v1/investigations \
  -H 'Content-Type: application/json' --data-binary @tests/example-request.json
```

The request uses a synthetic UUID, amount "100.00", currency INR, paymentStatus
PROCESSING, paymentMethod UPI and collectedAt ISO instant. Complete examples:
`tests/example-request.json`, `tests/example-response.json` (default) and
`tests/example-rag-response.json` (retrieval only). No fake output is presented as
real local inference.

## Java mapping and financial rules

| Normalized evidence | Java source | Semantics |
|---|---|---|
| paymentId, amount, currency, paymentMethod | PaymentResponse, GET `/api/v1/payments/{id}` | Same fields; omit merchantId/customerId as unnecessary identity data |
| paymentStatus | PaymentResponse.status | CREATED, PROCESSING, SUCCESS, FAILED, CANCELLED, REFUNDED |
| gatewayTransactions[] | GatewayTransactionResponse, GET `/api/v1/payments/{id}/gateway-transactions` | Same field names, including nullable gatewayTransactionId/error fields; SUCCESS, FAILED, TIMEOUT |
| refunds[] | RefundResponse, GET `/api/v1/payments/{id}/refunds` | Same fields; only SUCCESS is supported by current Java code and V5 constraint |
| webhooks[].id/paymentId/status/occurredAt | Settlement webhook audit rows | Map snake_case columns to camelCase; inbox status RECEIVED, PROCESSED, IGNORED, DEFERRED, FAILED |
| webhooks[].gatewayTransactionId/outcome | Parsed webhook row payload.gatewayTransactionId/status | Flatten only these fields; outcome is Observation SUCCESS, FAILED, TIMEOUT, UNKNOWN; never forward raw payload |
| reconciliation[].id/paymentId/outcome/statusBefore/statusAfter/result/createdAt | Settlement reconciliation audit rows | Map snake_case columns; result RESOLVED, RETRY, EXHAUSTED, SKIPPED; this is audit evidence, not reconciliation job status |
| collectedAt | Collector metadata, not a Java response field | Time the normalized snapshot was assembled |


No Java endpoint is called. Settlement audit rows come from the protected webhook
and reconciliation read routes; job status is not audit result or refund status.
Only SUCCESS refund records exist in Java; hypothetical PENDING/FAILED refund
statuses return 422. Money uses Decimal strings/integers; floats rejected. UUIDs,
aware timestamps, financial totals, foreign/duplicate rows, bounded strings and
maximum 100 rows per list are validated. Missing optional data is unavailable.

Deterministic precedence: reject malformed/financially impossible evidence; then
inconclusive lifecycle conflicts; incomplete REFUNDED evidence; partial/full refund
totals; SUCCESS recovery (matching processed webhook before resolved reconciliation)
or ordinary success; CREATED; PROCESSING/TIMEOUT; FAILED; inconclusive fallback.
CANCELLED remains inconclusive. Current SUCCESS alone never implies prior TIMEOUT.
No bank debit, bank arrival timeline, payment/refund execution or automatic retry.

## Security and current limitations

Internal loopback, synthetic supplied evidence only. No public authentication,
Java evidence retrieval, model connectivity verification, persistence or financial
mutations. The ASGI middleware buffers at most the configured body limit before JSON
parsing, counting streamed bytes even without Content-Length; excess returns 413.
Validation errors return a generic 422 without input, locations or exception context,
including malformed JSON. No unrestricted CORS. Free text is not a secret detector;
never submit credentials, JWTs, card/bank details or personal data. Prompt projection
omits arbitrary input strings; there is no production rate/concurrency control.

All original 44 tests remain unchanged. Additional tests use fake providers and
HTTPX MockTransport, with real socket connections blocked. TestClient emits the
existing installed Starlette HTTPX deprecation warning; tests pass without httpx2.
No real LLM inference has been verified. Real runtime/model installation, memory,
disk, Intel/macOS compatibility, context limits, latency and output quality are the
next phase, alongside later authenticated Java integration. No recommendation or
model download is performed in this phase.


## Phase 6.9.2 private chat transport boundary

HTTP POST `/api/v1/chat` is now disabled by default. Later reviewed activation requires
`PAYMESH_AI_CHAT_API_ENABLED=true` and protected `PAYMESH_AI_CHAT_SERVICE_TOKEN`
(64–128 high-entropy URL-safe characters) matching Java `paymesh.ai.chat.service-token`.
Exactly one `X-PayMesh-AI-Chat-Token` header is required; labels in JSON are not authentication.
No browser JWT/cookie is forwarded. Keep the listener private loopback. Existing investigation
HTTP contracts are unchanged; direct offline core tests need no HTTP token. No key or live
activation was performed. Java validates the finite answer contract independently.
After reviewed Python wording/knowledge changes, regenerate with
`.venv/bin/python -m scripts.export_chat_contract` and rerun Python/isolated Java tests.
See `frontend/PHASE-6.9.2-SECURE-AI-CHAT-API-REPORT.md` for exact contracts and limits.

## Step49.5A.1 — protected Qwen validation diagnostics (inactive)

The optional `PAYMESH_AI_CHAT_VALIDATION_DIAGNOSTICS_FILE` records fixed reason codes
only in an existing owner-only local JSONL file. It is disabled by default; public chat
responses, strict validation and grounded fallback remain unchanged. No raw prompt,
completion, exception, credential or financial evidence is recorded. The log is bounded
to64KiB and must satisfy mode700 directory/mode600 regular-file protections.

See [diagnostic patch report](STEP-49.5A.1-QWEN-VALIDATION-DIAGNOSTICS-REPORT.md) for
all eight reason codes,39 new tests, safe opt-in/Python-only reload and recovery limits.
Full Python suite276 passed; offline operational suite151 passed. No live restart,
inference, database, model/timeout/key change or diagnostic activation was performed.

## Step49.5A.4A — correlated diagnostic correction (reload pending)

Protected diagnostic rows now contain only a validated UUIDv4 `correlationId` and a fixed
`reasonCode`; public chat contracts and fallback behavior remain unchanged. The new operator
`internal-diagnostic` mode uses macOS binary launch snapshots, microsecond identity fences and
exact correlation matching, without whitespace-splitting process environments. It performs
one authenticated synthetic request, without retries or conversation/database writes.

See [correlated diagnostic report](STEP-49.5A.4A-CORRELATED-DIAGNOSTICS-REPORT.md) for offline
results, safe failure behavior and the separately approved Python-only reload/evidence plan.
Old activation evidence and old /tmp commands do not satisfy the new gates. No reload or
inference was performed for this correction.

Protected schema-category diagnostics now add a single allowlisted `schemaFailureCode` for
schema rejections only (diagnostic record version3). No field names or rejected/model values
are recorded, and public responses/strict validation remain unchanged. See the
[schema-category report](STEP-49.5A.5-SCHEMA-CATEGORY-DIAGNOSTICS-REPORT.md) for the eight codes,
351 Python/234 mocked operational passes, correlation/privacy guarantees and required separate
Python-only reload review. The existing pinned launcher must be reviewed against the current
process before execution; no reload or inference occurred during this patch.
