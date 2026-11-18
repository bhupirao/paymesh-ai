# Phase 6.9.1 — Internal conversational AI engine

**IMPLEMENTED AND AUTOMATED-VERIFIED. No live activation or inference verification in this batch.**
Python only; Java authorization/API adapter, conversation persistence and frontend chat are
NOT implemented. Phase681/682/683 live activation/browser verification and prior historical
evidence limitations remain pending/unchanged. V12/V13 were not activated; no database was
accessed. This is not production authentication or security certification.

## Architecture / reuse

Inspected FastAPI/main/body boundary, Pydantic evidence models, investigation rules,
RAG enrichment, fixed-corpus TF-IDF retrieval, LocalHTTPProvider/Qwen schema selection,
existing tests/knowledge and the Phase683 checkout report. Original investigation request/
response contracts, deterministic calculations, wording rules and eight-document retrieval
corpus remain. Chat extends the retriever with five separate allowlisted documents.

`chat_service.converse` is stateless: bounded English intent resolution → deterministic
facts/minor-unit arithmetic → optional topic retrieval → approved wording selection.
The model never classifies financial state, establishes ownership, computes money, decides
eligibility, fetches records or executes a tool. It selects BASE or EXPLAIN from two fully
constructed answers. This is deliberately constrained conversational explanation, not
unrestricted free-text financial advice or an autonomous agent.

The service stores no conversations. Current request history resolves only the question's
intent; assistant statements never become evidence. All facts come from the current typed
snapshot. There is no cross-request Merchant/account state. The only shared new state is a
single inference semaphore, containing no conversation content.

## Internal API — exact contract

`POST /api/v1/chat`, JSON only, no query parameters/trailing slash. Not added to any Java
endpoint or public frontend proxy. No chat Cookie/JWT/browser API was implemented.

**The endpoint currently has no service authentication, matching the existing internal
investigation boundary.** `callerRole`, `scope`, `source` and aliases are untrusted claims,
not credentials or authorization. Java MUST authenticate the user, revalidate current
session/account/membership, authorize every selected record/aggregate, and minimize the
projection before calling Python. Python cannot fetch or discover additional records.
Keep the service loopback/private; do not expose this endpoint publicly. Internal caller
transport authentication/network restrictions belong to the Phase692 review.

Synthetic schema example (not a real authorized collection):

```json
{
  "correlationId": "00000000-0000-4000-8000-000000000001",
  "callerRole": "MERCHANT",
  "question": "How much was refunded? Can I refund it again?",
  "history": [{"role":"user","content":"What is the current payment status?"}],
  "paymentContext": "payment:selected",
  "evidence": {
    "source":"JAVA_AUTHORIZED_SNAPSHOT",
    "scope":"MERCHANT_OWNED",
    "collectedAt":"2026-11-15T00:00:00Z",
    "payment":{"ref":"payment:selected","status":"SUCCESS","amount":"100.00","currency":"INR","paymentMethod":"UPI"},
    "refunds":[{"ref":"refund:r0","paymentRef":"payment:selected","amount":"20.00","status":"SUCCESS"}],
    "refundHistoryComplete":true
  }
}
```

Top level: required correlationId (lowercase canonical UUID-shaped36 characters),
callerRole MERCHANT/ADMIN, question1–1000 characters. Optional history<=8 messages, each
user/assistant only and1–1000 characters, total content<=6000; evidence nullable; paymentContext
nullable alias which must match the one selected payment. CamelCase is the wire convention;
snake_case aliases are also accepted, with duplicate/extra fields rejected. No system/tool/
developer message role, config, URL, SQL, raw token, Merchant/user ID or arbitrary record lookup.

Every nested model is strict and rejects unknown fields/coercion. Exact money is a JSON
**string** with two fractional digits, no sign/exponent/leading-zero variants. Payment/refund/
checkout amount limit12 integer digits; aggregate strings permit24, with additional count/
amount plausibility checks. Original selected payment/individual refund amounts must be
positive. NUL/control characters (except text newline/tab) and unpaired surrogates are rejected.
No actual resource UUID is needed: references are short caller-created aliases
`payment|refund|gateway|statistics|checkout:<1–32 ASCII letters/digits/_/->`.
Correlation identifiers, actual aliases, timestamps and roles are omitted from model input.

Evidence fields (all optional unless stated):

| Field | Contract |
| --- | --- |
| source | required JAVA_AUTHORIZED_SNAPSHOT label; NOT proof of authentication |
| scope | required MERCHANT_OWNED / ADMIN_AUTHORIZED; MERCHANT cannot claim Admin scope |
| collectedAt | required aware ISO8601 timestamp; caller-supplied, not independently verified |
| payment | ref,status(CREATED/PROCESSING/SUCCESS/FAILED/CANCELLED/REFUNDED),amount,currency(INR/USD),paymentMethod(UPI/CARD/OTHER) |
| refunds | nullable list<=20; ref,paymentRef,amount,status SUCCESS (actual Java persisted contract) |
| refundHistoryComplete | boolean defaultfalse; true requires provided history, including explicit empty[] |
| gateways | nullable list<=20; ref,paymentRef,gatewayName(MOCK_RAZORPAY/STRIPE/ROUTER),status(INITIATED/SUCCESS/FAILED/TIMEOUT/UNKNOWN); no raw errors/IDs |
| statistics | nullable list<=24 aggregate cells: ref,kind PAYMENT/REFUND,currency,status,count(integer0–1e9),amount; refund status SUCCESS only |
| statisticsComplete | defaultfalse; completeness is an assertion for the supplied scope, never Python verification |
| statisticsCurrencies | required when cells supplied: unique INR/USD list1–2; no cells outside declared currency scope |
| checkout | ref,status(ACTIVE/CANCELLED/EXPIRED/PROCESSING/UNCERTAIN/FAILED/PAID/UNAVAILABLE),amount,currency,paymentMethod; optional paymentRef |
| unavailableEvidence | unique list<=5 labels PAYMENT/REFUNDS/GATEWAYS/STATISTICS/CHECKOUT, default[]; cannot contradict supplied fields |

Duplicate aliases/aggregate groups, foreign payment associations, over-refunds, incompatible
complete refund/payment states and linked checkout/payment states reject422. Refund currency
comes only from the selected payment. Checkout enforces USD+CARD; legacy payment method OTHER
is a minimized explicit projection, not a new claim about historical gateway rules.
Gateway observations can conflict with a current payment state; the answer preserves that
observation/uncertainty rather than declaring a root cause or overriding the payment row.

### Response

`correlationId`, nullable `evidenceCollectedAt`, `answer`(<=6000), `intent`,
`evidenceReferences`(<=66 supplied aliases), `knowledgeReferences`(<=5), `limitations`(<=16),
`suggestedFollowUps`(<=3), `moneyFacts`(<=6), `analysisMode`, `generationStatus`.

Knowledge reference: documentId,chunkId,title,sources,score. Sources identify the actual local
KB document; scores are lexical relevance, not confidence/probability of correctness.
Money fact: kind ORIGINAL_PAYMENT/OBSERVED_SUCCESSFUL_REFUNDS/REMAINING_REFUNDABLE/
PAYMENT_AGGREGATE/REFUND_AGGREGATE/CHECKOUT_AMOUNT; exact amount string,currency,nullable count.
For the synthetic example:100.00 INR original,20.00 successful refunds,80.00 remaining.
These are snapshot facts/calculations, never permission to execute a refund.

200 is an analysis result, not financial success. Errors:400 unsupported query/framing,
405 wrong method,413>32768 actual UTF8 bytes,415 non-JSON,422 malformed/duplicate/nonfinite JSON,
invalid schema/Unicode/depth/associations,503 unexpected engine unavailability. Error bodies
are fixed and omit input/locations/raw exceptions. Sensitive responses/errors are no-store,
Pragma:no-cache, nosniff, no-referrer. Streamed bodies are bounded before JSON parsing.

## Intents / context / exact grounding

PAYMENT_STATUS, PAYMENT_FAILURE, PROCESSING, REFUND_SUMMARY, GATEWAY, STATISTICS,
CHECKOUT, KNOWLEDGE, INSUFFICIENT_EVIDENCE, UNSUPPORTED.

English keyword rules are intentionally finite/extensible: adding an intent requires schema,
routing, deterministic facts, approved policy/topic and tests. Explicit action/secret/system-
prompt/SQL/other-Merchant lookup requests are refused without model invocation. Unknown
questions receive a useful bounded clarification. Identifiers in questions never select data.

Follow-ups “Why did it fail?”, “How much was refunded?”, “Can I refund it again?”, “What about
the gateway?” and “Is it still processing?” use the current snapshot. Ambiguous “How much?”
can inherit an intent from bounded user history, not assistant claims. A generic “Why?” can
use the selected payment's current status. History cannot change the selected payment or
establish facts. General definitions are explicitly labelled general guidance, not observations.

Arithmetic uses Python integer minor units after exact-string validation: arbitrary precision,
no float operations, rounding or Decimal context loss. Successful refund sums cannot exceed
the original payment. Missing/incomplete refund history never becomes zero available refunds
or a guessed remaining amount. Ineligible payment lifecycle never receives a refundable-
remaining fact. Complete SUCCESS/REFUNDED history corroborates exact remaining arithmetic;
Java must still recheck cumulative limits and authorization at any later actual action.

Statistics are from supplied aggregate cells, not recent previews. Payment/refund counts and
amounts stay separate for INR/USD. Incomplete groups are labelled supplied-cell subtotals;
missing groups do not become zero. Explicit complete scope may establish empty groups as zero.
No balance, profit, revenue or bank-settlement value is calculated. Root cause, prior gateway
timeouts, recovery and bank arrival are never inferred from a current success alone.

Checkout answers preserve V13's unresolved attempt, definitive-failure retry, expiry/cancellation
and historical paid-link semantics. Describing implemented rules does not certify V12/V13 is
live. No public checkout token or raw order/customer description is accepted in the projection.

## Retrieval / local generation

The existing8 investigation documents/loader/order/chunk IDs are unchanged. Chat adds
routing.md,links.md,checkout.md,eligibility.md,statistics.md (13 unique document IDs total).
Existing lifecycle/timeout/refunds/idempotency/failure knowledge is reused. New documents
reference actual source and distinguish implemented V12/V13 behavior from live activation.
No customer records, credentials or real tokens are included.

Same standard-library TF-IDF/cosine retriever, fixed filename/root allowlist, no uploads,
external fetches, embeddings, vector DB or new ML dependencies. Symlinks/missing/oversized new
docs fail closed. Chunks<=800 characters; IDs contain document ID, ordinal and content hash,
stable for identical content. Query is a canonical topic, never raw user/history/evidence text.
Retrieval respects existing top-k1–5/context100–6000/threshold settings. Hits must match
currently loaded chunk/metadata exactly with unique IDs and finite0–1 relevance; selected
chunks must support the topic anchor. Reference titles are checked; source reference is the
actual known KB file. Hostile/unrecognized retrieved records cause safe retrieval fallback.

The model sees **no raw retrieved prose**, arbitrary questions, history, aliases, UUIDs,
roles, timestamps, contacts, descriptions, credentials or tokens. It sees a deterministic
intent, two approved answers and E0/K0-style ephemeral citation aliases. RAG supplies valid
topical provenance; policy summaries are approved server wording, not blindly reproduced
retrieval text. A malicious KB instruction cannot become an instruction or free generated claim.
This trades open-ended fluency for reliable behavior on the small local model.

Uses the existing Settings/LocalHTTPProvider, loopback HTTPX transport, schema-constrained
JSON, trust_env=False, redirect refusal and16KB transport/2048-character content caps.
No new model/API/package/download. Chat caps settings at128 output tokens,8000 prompt chars,
15-second HTTPX operation timeout; these are operation timeouts, not measured inference time
or a guaranteed end-to-end server cancellation deadline. Model work may continue after timeout.
Actual runtime/model remains the existing llama.cpp/Qwen deployment; no runtime was called.

A shared nonblocking single-slot semaphore now bounds real LocalHTTPProvider calls across
**chat and investigation**. Busy returns UNAVAILABLE/fallback instead of queueing inference;
the old investigation response enum/contracts remain. The permit is released on all exits.

Selection output has exactly intent,variant(BASE/EXPLAIN),evidence(all E aliases),knowledge
(all K aliases). The schema const/enums plus server validation reject wrong intent, duplicate/
foreign/missing references, extra claims, invalid variants, malformed/oversized output. No
model field can update money/status/facts or choose another record. Only fully validated
selection sets RAG_LLM/SUCCEEDED. All failures return the original useful grounded answer.

Modes: DETERMINISTIC (no retrieval/model), RAG_ASSISTED (real topical references, deterministic
text), RAG_LLM (only validated selection). Generation statuses: DISABLED for deterministic
mode; NOT_ATTEMPTED for RAG-only or policy/insufficient-intent bypass; NO_RELEVANT_CONTEXT,
RETRIEVAL_UNAVAILABLE, TIMEOUT, UNAVAILABLE (including busy), INVALID_RESPONSE,
VALIDATION_FAILED, CONTEXT_LIMIT, or SUCCEEDED. No fallback is marketed as LLM success.

## Security / privacy / limits

No SQL/network record lookup, financial tool, shell, dynamic file path, browsing tool or
arbitrary external API. Caller role is not authority. Java must not send passwords, JWTs,
refresh/reset/checkout tokens, card details, private contacts or unnecessary identifiers.
The strict projection excludes such fields, but text is **not a universal secret detector**;
questions/history must still be minimized upstream. Raw free-form question/history/retrieval prose is never placed in prompts,
answers, logs or model completion payloads. Validated enums and necessary exact monetary facts
are the deliberate structured exception. The response references only supplied aliases
and real retrieved chunks; limitations explicitly state the trust boundary.

No new application raw-content logging. `python -m app.main` disables Uvicorn access logging;
external launchers/reverse proxies must also disable/redact query/body access logs. Do not
put questions/secrets in URLs (queries reject400). The endpoint is not an authenticated
public service; ingress authentication/rate limits and production transport review remain.

The engine is English/keyword-based, one selected payment per snapshot, and has no arbitrary
causal diagnosis, date-range lookup or multi-record ownership inference. No raw gateway error
codes/reasons are projected, so specific failure causes remain unestablished without future
reviewed typed evidence. Snapshot time/completeness are supplied assertions, not live verification. Histories over20
refunds require a future reviewed aggregate projection or incomplete flag; never truncate
and falsely mark complete.
RAG is lexical relevance, not certainty. Approved wording selection is not unconstrained QA.

## Files created / changed

Created:
- app/schemas/chat.py
- app/api/chat.py, app/api/chat_boundary.py
- app/services/chat_service.py, app/services/generation_budget.py
- knowledge_base/routing.md,links.md,checkout.md,eligibility.md,statistics.md
- tests/test_chat.py
- scripts/diagnose_chat.py (opt-in synthetic knowledge-only diagnostic; not run)
- this report

Changed:
- app/main.py (new route/boundary; chat-safe errors; access_log=False for module launcher)
- app/services/local_provider.py (shared concurrency guard, transport contract unchanged)
- app/services/retrieval.py (separate chat loader, original investigation loader untouched)
- ai-service/README.md,knowledge_base/README.md; root README.md and PROGRESS.md.

No Java/frontend API/proxy/chat/schema/migration/configuration/requirements changes.
No protected evidence/backups, staging or unrelated work replaced.

## Automated verification / live procedure

Final actual totals and preservation observations are appended below. Automated inference is
mocked; socket connections are forbidden by test fixtures. No live service was started/restarted.

After separate operator approval only, optional existing local model verification (no server
restart, no protected business request, no real evidence):

```bash
cd "$HOME/Developer/paymesh-ai/ai-service"
.venv/bin/python -m scripts.diagnose_chat --confirm-local-inference
```

Requires the already-running approved llama.cpp endpoint127.0.0.1:8082 and existing public
model alias paymesh-qwen. No downloads. This sends only “What is idempotency?” with no evidence,
not a forged Java collection. It prints sanitized mode/status/reference-count metadata only.
Exit0 requires SUCCEEDED; fallback exits1 and must not be called successful live inference.
Omitting the confirmation makes no request. **Not executed in this batch.** This diagnostic
verifies the new core/adapter, not deployment of /chat on the old running Python process.
New API activation and Java/frontend live tests remain separate, later approved operations.

## Phase692 requirements (handoff only)

- Authenticate/revalidate current Java session/account and authorize every payment, refund,
  gateway, checkout and aggregate scope before Python. Never forward role labels as proof.
- Build this minimized alias-based DTO from real current evidence; no arbitrary user-supplied
  evidence, ownership, money or raw conversation assistant claims. Keep exact strings/currencies.
- Derive complete histories/aggregate coverage from real bounded authorized queries. Reject
  incomplete/ambiguous ownership; optional date/window semantics need a reviewed typed extension.
- Bind history/persistence to authenticated owner/current selected payment; send<=8/6000 chars;
  maintain current snapshot binding across follow-ups. No Python persistence added here.
- Review internal transport authentication/network isolation and bounded HTTP timeouts/response
  validation. Validate returned correlation, aliases, known citations, mode/status combinations.
- Render safe text/provenance/limitations. Never convert this explanation or suggested question
  into a payment/refund/action. No SQL/autonomous tools or public-proxy exposure.
- Share the resource budget with investigation; busy/timeouts are honest fallbacks, no automatic
  model/financial mutation retries. Plan native/local LLM verification separately.

No Phase692 implementation or previous phase closeout is included.

## Final executed verification — 2026-11-15

- **229 Python tests passed**,0 failures, including **102 existing investigation/RAG tests**
  and **127 new conversational/security/boundary tests**. Existing test files remain unchanged.
- One existing Starlette TestClient/HTTPX deprecation warning; no new dependency installed
  to suppress it. `pip check`: no broken requirements (sandbox pip-cache permission notice
  only; no package operation).
- `.venv/bin/python -m compileall -q app scripts tests`: passed.
- `git diff --check`: passed; final staging observation follows documentation.

Full command actually executed from ai-service: `.venv/bin/python -m pytest -q`. Earlier
runs passed220/226/227; the final229 adds recovery-policy topic coverage. All real socket
connects are blocked by tests; generation uses fake providers/MockTransport. No local LLM,
Java business API, database or live FastAPI endpoint was called. No inference timing or
native/live integration success is claimed. Diagnostic remains pending operator approval.
Java/frontend/operational suites were not rerun for this Python-only task; their previous
361/1086/119 results remain prior-phase evidence, not newly executed results.

The final suite includes actual existing corpus preservation, exact max-money subtraction,
strict/coercion/association/history limits, complete/incomplete currency aggregates, all
checkout statuses and pending payment uncertainty, hostile user/history/KB inputs, fake/
missing citations and output claims, fallback statuses, no-queue/shared inference capacity,
no raw exception logging, pre-JSON streamed/deep/duplicate/nonfinite body rejection and
opt-in diagnostic refusal without network. Webhook/reconciliation explanations are general
policy, never invented event evidence. This chat projection has no event-specific webhook/
reconciliation audit fields; use the existing authorized investigation or a later reviewed
projection extension to establish actual recovery.

Implementation complete; no Phase692 work, previous-phase closeout or live activation performed.

Final preservation observation: captured cached binary diff is unchanged,0 changed cached
patch blocks;454 Git status entries include existing unrelated work. No staging/commit/
reset/clean/restore performed. Protected configuration/evidence/backups are untouched.
