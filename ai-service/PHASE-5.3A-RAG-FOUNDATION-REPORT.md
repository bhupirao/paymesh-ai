# Phase 5.3A — Lightweight RAG and local generation foundation

## Result and scope

Implemented lexical retrieval, eight curated knowledge documents, optional local
OpenAI-compatible provider transport, constrained wording validation and safe
fallback. Default analysis remains deterministic. **No real LLM inference has been
verified.** No runtime, model, CMake, Docker, vector store or ML library was installed
or downloaded. No paid/external AI API was used. This is not production ready.

## Preflight and baseline

Working directory: `/Users/bhupirao/Developer/paymesh-ai/ai-service`.
Repository root: `/Users/bhupirao/Developer/paymesh-ai`.
Read Phase 5.2 report, README, all existing schemas/routes/configuration/service,
tests and example request/response. Read Java API-REFERENCE.md, README-WEBHOOKS.md
and README-REFUNDS.md as read-only contract sources. Java enums, response DTOs,
settlement and refund implementation inspected in Phase 5.2 remain the factual basis.

Verified interpreter: existing `.venv`, Python 3.13.10, x86_64, macOS 12.7.6.
Verified FastAPI 0.162.5, Pydantic 2.14.3, Pydantic Settings 2.16.2, HTTPX 0.28.1,
pytest 9.2.0. Existing Uvicorn pin 0.54.0 retained. No dependency installation.
HTTPX moved from development to runtime requirements because the optional provider
uses it; this reuses its already installed verified version.
Baseline before modifications: **44 passed, 1 warning**, 1.59 seconds.

## Exact project files changed

- `.env.example`
- `README.md`
- `app/api/health.py`
- `app/api/investigations.py`
- `app/config.py`
- `app/main.py`
- `app/schemas/investigation.py`
- `app/services/investigation_service.py`
- `knowledge_base/README.md`
- `requirements.txt`
- `requirements-dev.txt`
- `tests/example-response.json`

New files:

- `app/api/body_limit.py`
- `app/services/local_provider.py`
- `app/services/rag_service.py`
- `app/services/retrieval.py`
- `knowledge_base/lifecycle.md`
- `knowledge_base/timeout.md`
- `knowledge_base/webhook.md`
- `knowledge_base/reconciliation.md`
- `knowledge_base/failure.md`
- `knowledge_base/refunds.md`
- `knowledge_base/idempotency.md`
- `knowledge_base/communication.md`
- `tests/test_rag.py`
- `tests/example-rag-response.json`
- `PHASE-5.3A-RAG-FOUNDATION-REPORT.md` (this report)

Original `tests/test_investigations.py` and the Phase 5.2 report were not edited.
Ignored Python/pytest caches were generated. A temporary project-local build helper
was removed after creating the implementation; it is not a deliverable.

## Architecture and authoritative boundaries

The route first validates evidence. `rag_service.enrich` always invokes the pure
financial rules before optional retrieval or generation. `Retriever` and `Provider`
protocols allow later embedding/provider replacement without changing financial
analysis. No arbitrary file paths, URLs or caller-selected model endpoints exist
in the investigation request. Server settings control mode.

Money, financial status, successful refund totals, recovery classification, certainty,
authorization boundaries and recommended actions remain deterministic. Existing
rule precedence and supplied-evidence trust boundaries are preserved. Root cause
is no longer copied from status text: processing observations can be CONFIRMED while
rootCauseCertainty is INCONCLUSIVE and the underlying cause explicitly unknown.
Known failure codes can support a confirmed mock failure explanation. Recovery
mechanism evidence does not invent historical timeout or bank settlement.

## Retrieval and curated knowledge

Eight Markdown documents carry stable document IDs, titles, scenarios and local
Java source references. Verified simulated behavior and general troubleshooting
are separately labeled. Only eight allowlisted local filenames load; symlinks and
oversized documents are excluded/rejected. No documents or URLs are fetched.

Standard-library TF-IDF uses smoothed inverse document frequency and cosine
similarity. This is **lexical retrieval for RAG**, not semantic vector search.
Queries use normalized status enums and deterministic scenario, never raw errors
or customer input strings. Chunks are at most 800 characters; IDs combine document
ID, ordinal and content hash. Identical documents produce identical IDs. Content
or boundary changes can invalidate affected IDs. Ranking ties use chunk ID.

Default top-k 3, maximum 5; threshold .12; serialized-context estimate budget 3000
characters, maximum 6000. Whole chunks are skipped if they do not fit. Prompt
serialization is separately checked against a total character budget. Empty or
irrelevant retrieval returns original deterministic views and skips generation.

Verified lexical examples with current corpus:

| Query | First document | Score | Stable chunk ID |
|---|---|---|---|
| GATEWAY TIMEOUT PROCESSING | PM-KB-TIMEOUT | 0.555376 | PM-KB-TIMEOUT:000:5d47f4ece619 |
| PARTIAL REFUND | PM-KB-REFUNDS | 0.539708 | PM-KB-REFUNDS:000:79c633e9c940 |
| WEBHOOK RECOVERY | PM-KB-WEBHOOK | 0.639923 | PM-KB-WEBHOOK:000:69ace23bcb66 |

Scores measure lexical relevance, not certainty about payment facts. Source paths
are knowledge references, separate from payment snapshot evidence references.

## Local provider contract and safeguards

`Provider.generate(messages)` returns JSON content or raises a safe GenerationFailure.
LocalHTTPProvider validates a literal loopback IP URL, exact /v1/chat/completions
path and explicit port; no DNS hostname, external URL, credentials, query or fragment.
Default http://127.0.0.1:8080/v1/chat/completions. IPv6 ::1 is supported. No API keys.
HTTPX trust_env=false and follow_redirects=false prevent proxy/redirect routing.

POST body: model, messages, temperature=.1, max_tokens (default128, range32–512),
response_format json_object and stream=false. HTTP timeout defaults10 seconds,
range1–30 per operation. Prompt context defaults12000 characters, range6000–24000.
Response requires HTTP200, choices[0].finish_reason=stop and string content.
Response bytes capped16384; content capped2048 characters. HTTP errors, missing
model, connection failures, timeout, invalid/truncated response and invalid output
fall back without exposing internal exception text or logging prompts/evidence.

No server was started and no actual model endpoint was contacted. HTTPX timeouts
are per operation, not a total deadline against a trickling server; concurrency and
real-model resource limits need later testing. Character budgets are not tokenizer
context-window guarantees. Actual model name and server compatibility remain pending.

## Prompt and output validation

Prompt contains a privacy-minimized validated evidence projection, deterministic
result, approved alternatives and retrieved chunks. IDs, arbitrary payment method,
raw error messages, authentication and personal fields are omitted. Evidence and
retrieval text are explicitly data, never instructions.

The output is deliberately constrained to exactly these fields:

```json
{"scenario":"PROCESSING","customer_variant":"PLAIN","technical_variant":"CONCISE"}
```

Pydantic strict validation rejects extras and unsupported selectors. Scenario must
match the deterministic result. Approved server templates render summaries and
technical wording; title, what happened, next action, money and certainty remain
authoritative. Unsupported free text, invented amounts, claimed status/recovery,
bank claims or retry actions cannot be rendered through this contract. This is
model-assisted wording selection, not arbitrary narrative generation. Arbitrary
LLM hallucinations cannot be claimed eliminated; broader free-text generation is
intentionally deferred and would need further safeguards/evaluation.

## Modes, compatibility and fallback

DETERMINISTIC is default; no KB or model call. RAG_ASSISTED means successful lexical
retrieval with deterministic views. RAG_LLM is emitted only after provider success
and validated selection. RAG_LLM configuration requires generation_enabled=true;
setting the flag alone in deterministic/retrieval mode does not call a model.
Generation failure retains original deterministic views, useful references and
RAG_ASSISTED mode; missing/failed retrieval uses DETERMINISTIC. Fallback is never
labeled model-generated.

The existing request shape stays unchanged. Additive response fields:
knowledgeReferences, generationStatus and technicalView.rootCauseCertainty.
analysisMode now allows three values; closed-enum clients need that enum extension.
Safe reason codes are documented in README. Health endpoints preserve status and
service fields, reflect configured mode and add configuredAnalysisMode plus
modelConnectivity=NOT_VERIFIED. Health never claims a connected model; readiness
covers the always-available deterministic fallback.

## Customer and technical messages

For PROCESSING without gateway evidence:

- Title: Your payment is still being processed
- Summary: Your payment is taking longer than expected. Please wait for confirmation before making another payment.
- What happened: We are still waiting for the final payment confirmation.
- Next action: Please wait for an update. If your payment remains unresolved, contact support.

Technical observedPaymentStatus=PROCESSING and certainty=CONFIRMED.
rootCause="The underlying cause could not be determined from the supplied evidence."
rootCauseCertainty=INCONCLUSIVE. technicalExplanation retains the snapshot status.
Customer recovery explanations say confirmation followed an additional check;
technical views retain webhook/reconciliation details. Refund amounts use Decimal
and do not establish bank arrival. No technical status constants or exception codes
are inserted into customer explanations.

## Request security

ASGI middleware counts bytes before JSON parsing, including bodies with missing
Content-Length and streamed chunks. Default cap131072 bytes, configurable1024–262144;
oversize returns413 without invoking the downstream parser. Invalid evidence and
malformed JSON return generic422 without raw input, attacker-controlled locations,
Pydantic contexts or internal exception messages. Tests verify redaction. Deployment
remains loopback/internal/synthetic-only; no authentication, financial mutations or
Java retrieval. Free text is not a secret detector. No unrestricted CORS was added.

## Test and fake-generation verification

Final functional run: `.venv/bin/python -m pytest -q` → **95 passed, 1 warning**,
2.24 seconds. All original44 tests plus51 focused tests pass. pip check:
**No broken requirements found.**

New tests cover messages and unknown cause, loading/chunk identity, relevant/empty/
irrelevant retrieval, deterministic ties, context bounds, prompt projection,
fake success, invalid JSON, conflicting status/recovery, invented amounts, unsafe
actions, provider unavailable/timeout, disabled generation, safe fallback, configured
mode, loopback URLs, request byte limits including no Content-Length, malformed
JSON and sensitive validation errors. HTTPX MockTransport verifies request shape,
proxy/redirect disabling, missing model, response caps and truncation handling.
Real socket connections are blocked during automated tests. A context-limit test
initially used a fixture that fit the budget; its corrected fuller context now
verifies the intended no-call fallback.

Warning is the existing installed Starlette TestClient HTTPX deprecation notice
(recommends httpx2). No replacement package was installed. pip emits a nonfatal
unwritable-user-cache warning. No live model inference, performance, quality or
hardware compatibility result is inferred from fake-provider/mock-transport tests.

## Exact commands and next step

```bash
cd ~/Developer/paymesh-ai/ai-service
source .venv/bin/activate
.venv/bin/python -m pip check
.venv/bin/python -m pytest -q
# Retrieval only, without a model runtime:
PAYMESH_AI_ANALYSIS_MODE=RAG_ASSISTED .venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

In another terminal in ai-service:

```bash
curl -sS http://127.0.0.1:8000/health
curl -sS http://127.0.0.1:8000/api/v1/investigations \
  -H 'Content-Type: application/json' --data-binary @tests/example-request.json
```

Swagger: http://127.0.0.1:8000/docs . Ctrl-C stops the manually started Python service.
These start commands are user instructions; no listener or model was started this
phase. Example responses were generated in-process from synthetic evidence.

Remaining blockers for real inference: select and install a compatible lightweight
runtime/model for Intel AVX2/macOS12.7.6, available8GB RAM and approximately3.5GB free
disk; verify artifact size, memory use, context window, latency, server contract and
JSON selection reliability. No model recommendation/download or runtime installation
was attempted in this phase. Authenticated Java retrieval remains a separate future
integration. The foundation is ready for those checks, not a production deployment.

## Preservation and external Git-index change

All edits/actions by this implementation were within ai-service. Java and backups/
ZIPs were not modified. PostgreSQL was not accessed. Java was not started or stopped.
No git add, commit, push, reset, clean or publication command was run.

The server interruption coincided with an external Git-index change that staged
some in-progress ai-service files. It was preserved; no attempt was made to reverse
or restage it. Full staged-diff SHA256 changed from preflight
`a55cd701e90850cc806ae9dad4fc605decb06daaf226549cc058be812a466f52` to observed
`b052ff27bc74033beb404a099e43cd37a799faf280a2960455158dbaed4b5ab2`.
Therefore repository-wide index identity is not claimed. No index mutation was
performed by this implementation. Java working-diff SHA256 remains exactly the
preflight value `e3e10b89476e6f958ac80be530958322aba6b5a332be932d442cf9eeaa7d44c0`.
Existing staged and unstaged changes were preserved.
