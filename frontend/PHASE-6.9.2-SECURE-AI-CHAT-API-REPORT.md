# Phase 6.9.2 — Secure Java AI Chat APIs

Implementation and automated verification; live activation and native browser verification are NOT performed. No Phase693 UI, conversation persistence, migration, financial/account mutation or live Python/LLM call is included. Live remains the operator-reported V11; V12/V13 activation is pending. Phase681 dashboard/browser/disposable-password/final audit, Phase682/683 activation/browser verification and Phase691 live LLM verification remain pending. Phase673/674 documented evidence limitations remain unchanged.

## Architecture and authorization

Three bearer-authenticated Java controllers use the existing endpoint catalog, JWT decoder, account authorization version, persistent-session validation, BusinessAccess, MerchantPortal and MerchantAdministration. Merchant chat requires an enabled ACTIVE exact MERCHANT account, exactly one authorized active membership, verified active registry and ACTIVE business lifecycle. Admin chat requires the current ACTIVE enabled ADMIN identity. The payment route applies existing BusinessAccess ownership/Admin access, with MerchantPortal's current lifecycle checks for Merchant callers. An Admin does not gain the Merchant endpoint's privileges.

`ChatEvidenceBuilder` acquires the existing account administration advisory lock in a short READ_COMMITTED authorization transaction. It re-decodes the original signed JWT (including current session/account validation), authorizes every explicit selector and invokes a separate REPEATABLE_READ read-only projection transaction. This obtains a consistent detached financial snapshot after authorization while the outer account lock remains held. Both transactions and the account lock end **before** the remote HTTP call. The transport rejects execution inside an active database transaction. After response validation, another short locked authorization transaction re-decodes the JWT and rechecks account version, role, membership, business lifecycle, session and selected payment ownership before returning the explanation. No Python invocation occurs for unauthorized selectors.

A response describes evidence at `collectedAt`, not continuously current financial state. An unavoidable authorization change after the final check cannot retract bytes already returned. Future UI code must also apply existing session-version/operation guards. Legacy signed JWTs without `sid` retain the existing authorization-version compatibility; per-session logout cannot inventory or revoke a legacy no-sid token independently of that account version. No stronger historical revocation certification is claimed.

## Public Java contract

All routes require `Authorization: Bearer <access token>`, `Content-Type: application/json`, have no query parameters and return no-store. They accept no Idempotency-Key and perform no financial action. JSON duplicate/unknown fields, type coercion, trailing JSON, invalid Unicode/NUL and unsupported selectors are rejected. Maximum public body: 32,768 actual bytes.

- `POST /api/v1/merchant/ai/chat`
- `POST /api/v1/admin/ai/chat`
- `POST /api/v1/payments/{paymentId}/ai/chat`

Payment-specific example (the path supplies the authorized payment context):

```json
{"question":"How much was refunded?","history":[{"role":"user","content":"What is the current payment status?"}]}
```

Merchant/general-context example:

```json
{"question":"Summarize payment statistics","history":[],"context":{"statistics":{"from":"2026-11-01T00:00:00Z","to":"2026-11-16T00:00:00Z","currency":"INR"}}}
```

Admin selected-Merchant example:

```json
{"question":"Summarize payment statistics","context":{"merchantId":"DEMO_MERCHANT_A","statistics":{"currency":"USD"}}}
```

The optional `context` has only `paymentId`, `paymentLinkId`, `merchantId` and `statistics`. Payment/link selectors are canonical lowercase UUID strings and are mutually exclusive. The payment-path route rejects either redundant payment/link selector. `merchantId` is Admin-only, syntax-bounded to 100 characters, checked against the database and enforced against any selected payment/link. No selector means no implicit resource discovery. A question mentioning an identifier does not select or authorize it; common raw IDs/contact/credential patterns are rejected from text. This heuristic is not a universal secret detector: callers must not put secrets or personal information in questions/history.

`statistics` permits only `from`, `to` and `currency` (INR/USD). Existing DashboardAnalytics UTC semantics apply: default last 30 UTC days, day-aligned boundaries, end exclusive, maximum 93 days; omitted currency explicitly covers INR and USD separately. Aggregates use complete parameterized SUM/COUNT GROUP BY queries, never recent-five previews. Payment groups use payment creation time; refund groups use refund creation time. A selected payment narrows the aggregate Merchant scope, not the aggregate to a single transaction. Empty complete scopes have explicit zero aggregates. The returned provenance states the window/scope. Invalid date ranges return 400.

Question: 1–1,000 Unicode code points, nonblank. History: at most 8 user/assistant messages, each at most 1,000 code points, at most 6,000 total. History is untrusted context; only current database evidence supplies facts. No server conversation state or persistence. Phase696 owns any later persistence and conversation ownership design.

Response example shape (values below illustrate the contract, not a live observation):

```json
{
  "correlationId": "00000000-0000-4000-8000-000000000001",
  "answer": "The supplied current payment status is SUCCESS. A successful simulated payment is recorded; no prior failure, timeout or recovery is inferred.",
  "intent": "PAYMENT_STATUS",
  "evidenceProvenance": {
    "source": "JAVA_AUTHORIZED_DATABASE_SNAPSHOT",
    "collectedAt": "2026-11-15T00:00:00Z",
    "scope": "MERCHANT_OWNED",
    "limitations": [],
    "statisticsRange": null
  },
  "evidenceReferences": [
    {
      "reference": "payment:selected",
      "resourceType": "PAYMENT",
      "resourceId": "00000000-0000-4000-8000-000000000002"
    }
  ],
  "knowledgeReferences": [],
  "limitations": [
    "Python analyzes supplied evidence; it does not authenticate, authorize or independently fetch Java records.",
    "Java alone must enforce ownership, current eligibility and financial actions.",
    "Simulated records do not establish bank debit, settlement, balance, profit or refund arrival.",
    "Previous assistant messages are not authoritative financial evidence.",
    "CHECKOUT evidence is unavailable; it is not proof that no event occurred.",
    "STATISTICS evidence is unavailable; it is not proof that no event occurred.",
    "This explanation is a dated evidence snapshot, not a live financial instruction or current authorization."
  ],
  "suggestedFollowUps": [
    "What does the current payment status mean?",
    "How much was refunded?",
    "What does the gateway evidence show?"
  ],
  "moneyFacts": [],
  "analysisMode": "DETERMINISTIC",
  "generationStatus": "DISABLED"
}
```

This synthetic SUCCESS example assumes complete empty refund/gateway histories and no checkout/statistics selectors. The complete fixed arrays are in `backend/src/main/resources/ai-chat/contract.json` and Python `chat_service.py` (responses include all required limitations plus Java snapshot limitations). Money facts have `kind`, canonical exact decimal-string `amount`, `currency` and nullable integer `count`. Knowledge references contain `documentId`, `chunkId`, `title`, `sources`, `score`; sources are text, not trusted URLs, and scores are retrieval relevance, not confidence. Public evidence references disclose only the selected authorized payment/link UUID where useful; refund/gateway/statistics references have null `resourceId`. No unfiltered Python object is returned.

Supported intents: PAYMENT_STATUS, PAYMENT_FAILURE, PROCESSING, REFUND_SUMMARY, GATEWAY, STATISTICS, CHECKOUT, KNOWLEDGE, INSUFFICIENT_EVIDENCE and UNSUPPORTED. Ambiguous/insufficient evidence can return 200 with an honest explanatory answer. Financial actions are refused, not executed.

## Evidence, privacy and exact money

Java creates request-scoped aliases (`payment:selected`, `refund:r0`, `gateway:g0`, `statistics:s0`, `checkout:selected`). Alias-to-resource mappings remain only in the Java request context. The database projection sends no raw user, Merchant, payment, refund, gateway or link UUIDs, checkout tokens, customer/order details, contact data, audit metadata, browser credentials or internal raw error strings. Gateway observations include the actual allowlisted gateway/status; raw error text is intentionally excluded rather than guessed safe. No role label from the browser is accepted.

Payment and checkout amounts use BigDecimal, two exact decimals, existing 12-integer-digit payment limits. Aggregate amounts permit the actual Python 24-integer-digit exact-string contract; counts are bounded per group. Java independently verifies refund/statistics arithmetic using integer minor units/BigDecimal; currencies and PAYMENT/REFUND groups remain separate. No balance/settlement/revenue/profit/bank-arrival claims are inferred.

Refund detail is complete only if all rows fit the Python maximum 20 and supported successful-refund schema. The query reads up to 21 to detect overflow. Otherwise the **entire** refund list is withheld, `refundHistoryComplete=false`, REFUNDS is unavailable and no authoritative refund total or remaining amount is computed. Gateway detail uses the same 20/21 bounded completeness approach. More than 24 aggregate groups, unsupported currency/state/precision or inconsistent totals fail closed. Daily/method analytics and detailed reasons are not fields in the actual Phase691 Python schema; they are not fabricated. Snapshot limitations declare this boundary.

Checkout context derives effective recorded link/attempt states with existing V12/V13 tables, exposes no share token and performs no initiation/reconciliation/update. These selectors require the pending V12/V13 schema activation; missing tables return safe evidence-unavailable errors. Chat introduces no migration.

The final serialized UTF-8 Python request, including all aliases/history/evidence, must fit 32,768 bytes. Oversized snapshots fail safely (422); no monetary rows are silently truncated. Bounded detail can be unavailable while complete aggregate queries remain authoritative.

## Private Python transport and validation

The Java client uses the reviewed fixed IPv4 loopback Python origin and fixed POST `/api/v1/chat`; it rejects credentials, query/fragment/path components and forbidden internal ports. No redirects, HTTP proxy, cookies or user JWTs are forwarded. New chat-only internal authentication is required: `X-PayMesh-AI-Chat-Token`, exactly one header, constant-time comparison in Python. Existing investigation contract is unchanged.

Both chat HTTP features are disabled by default. For a later separately reviewed deployment, Java requires `paymesh.ai.chat.enabled=true` and protected `paymesh.ai.chat.service-token`; Python requires `PAYMESH_AI_CHAT_API_ENABLED=true` and matching protected `PAYMESH_AI_CHAT_SERVICE_TOKEN`. The token must be 64–128 URL-safe high-entropy characters, generated privately by the operator and stored outside Git. Missing/invalid keys fail closed. No key was generated, no configuration secret was changed and no service was activated in this phase. Existing Python core offline tests/diagnostics can still call the engine without enabling HTTP. This shared secret plus loopback is a local service trust boundary, not production TLS/service-identity deployment certification.

Internal request fields exactly match Phase691: server `correlationId`, derived `callerRole`, `question`, `history`, optional aliased `paymentContext`, and `evidence` containing source/scope/collection time, optional payment/refunds/gateways/statistics/checkout, completeness flags and unavailable evidence. Roles/provenance labels alone are not authentication.

Internal JSON example (synthetic, all identifiers are request-scoped aliases):

```json
{"correlationId":"00000000-0000-4000-8000-000000000001","callerRole":"MERCHANT","question":"What is the current payment status?","history":[],"paymentContext":"payment:selected","evidence":{"source":"JAVA_AUTHORIZED_SNAPSHOT","scope":"MERCHANT_OWNED","collectedAt":"2026-11-15T00:00:00Z","payment":{"ref":"payment:selected","status":"SUCCESS","amount":"100.00","currency":"INR","paymentMethod":"UPI"},"refunds":[],"refundHistoryComplete":true,"gateways":[],"statisticsComplete":false,"unavailableEvidence":["CHECKOUT","STATISTICS"]}}
```

Internal response uses `evidenceCollectedAt` (not public `evidenceProvenance`), string alias arrays (not public resource reference DTOs), and the validated answer/intent/knowledge/limitations/follow-ups/money/mode/status fields. Java creates the public provenance and reference mapping itself.


Java verifies strict response fields, duplicate JSON keys, correlation and evidence timestamp equality, recognized expected intent, exact used aliases, known local document/chunk/title/source tuples, relevance bounds, exact money facts, fixed limitations/follow-ups and mode/status combinations. It independently reconstructs the finite approved Python answer. Only the actual BASE answer or approved EXPLAIN suffix for successful constrained generation is accepted. Schema-valid arbitrary prose, fabricated financial claims, mismatched facts or unrelated citations return 502. This deliberately limits expressive freedom: future Python wording/schema/KB changes require coordinated contract regeneration and review, not looser validation.

Offline deterministic manifest/fixture regeneration (no service calls):

```sh
cd "$HOME/Developer/paymesh-ai/ai-service"
.venv/bin/python -m scripts.export_chat_contract
```

The Python drift test compares regenerated artifacts byte-for-byte; the Java oracle test compares independent rules against actual Python deterministic fixtures. No raw model prompts/outputs are exposed.

Modes: DETERMINISTIC requires no knowledge and DISABLED/NOT_ATTEMPTED/NO_RELEVANT_CONTEXT/RETRIEVAL_UNAVAILABLE. RAG_ASSISTED requires known knowledge and NOT_ATTEMPTED/DISABLED/TIMEOUT/UNAVAILABLE/INVALID_RESPONSE/VALIDATION_FAILED/CONTEXT_LIMIT. RAG_LLM requires known knowledge and SUCCEEDED. Fallback is never labeled successful generation.

## Capacity, timing and safe errors

Shared nonqueued Java capacity is 1 across investigation/chat. Python's existing shared inference slot is also 1. A busy Java slot returns 503 AI_CAPACITY. No automatic retries. Java defaults: connect 2 seconds; chat response/read timeout 25 seconds; response max 65,536 bytes (configurable bounded 4–128 KiB). Python chat inference is capped at 15 seconds, 128 output tokens and 8,000 context characters under existing local configuration. These are configured budgets, not measured live inference timing or a claim that client cancellation stops backend/model work. Frontend proxy chat timeout is 40 seconds; Phase693 should use a deliberate client timeout above that (for example 45 seconds) and explain timeout uncertainty. Long-running remote work can finish after an HTTP timeout.

400 INVALID_INPUT/SENSITIVE_TEXT; 401 authentication expired/revoked; 403 current authorization denied; 404 CONTEXT_UNAVAILABLE for missing/inaccessible selectors; 413 public body limit; 415 wrong media type; 422 UNSUPPORTED_EVIDENCE/EVIDENCE_TOO_LARGE; 502 INVALID_AI_RESPONSE or upstream protocol/auth failure; 503 AI_UNAVAILABLE/AI_CAPACITY/EVIDENCE_UNAVAILABLE; 504 AI_TIMEOUT. Errors contain safe fixed message/code and server correlation ID. Logs contain only code, correlation and status, no question/history/evidence/raw exception. Existing security filters retain their established safe 401/403 responses.

Proxy adds only the three exact Java POST paths, no query strings, bounded UUID/path/body and 40-second timeout. It forwards the access bearer to Java only; refresh Cookie, Set-Cookie and internal chat token headers are stripped. Existing Origin, Host, CSP, fixed-upstream and response-limit policies remain. Python chat, llama.cpp, actuator and signing operations are not exposed. No frontend chat UI/client routes were added.

## Automated verification

Final results are recorded below after the implementation batch. Inference uses mocks; PostgreSQL is a disposable isolated cluster started only by the established script. Mocked JS DOM assertions are not actual browser verification.

Executed commands and non-Java results:

- `cd ai-service && .venv/bin/python -m pytest -q`: **237 passed**, one existing Starlette/HTTPX deprecation warning. Includes 8 new private-authentication/manifest-drift cases. Network/inference are mocked or blocked.
- `python3 -m unittest discover -s frontend/tests -p 'test_*.py'`: **46 passed**, including 3 new chat proxy cases. Temporary mock loopback listeners only.
- All 15 existing browser-compatible JS suites executed in a Node mocked DOM with mocked fetch: **1,043 assertions passed** (10 API,34 auth,94 payment,125 refund,149 investigation,18 QA,73 portals,39 registration,67 sessions,113 Admin,97 Merchant,46 analytics/switch,51 pagination,70 links,57 checkout). Therefore total frontend checks **1,089** (1,043 JS +46 proxy), not actual browser verification.
- `python3 -m unittest discover -s backend/scripts -p 'test_*.py'`: **119 passed**, unchanged suite actually rerun.
- Python `compileall` passed for ai-service app/tests/scripts, frontend and backend/scripts; `bash -n backend/scripts/test-isolated.sh` passed. All **56** frontend ES-module files parsed with Node VM syntax checks.

The first full isolated Java run executed386 tests with one mock-restubbing setup error (not a production failure). The mock was corrected using `doThrow`, and two additional authorization tests were added before the complete final rerun. The final runner uses a fresh disposable database; its installed `pg_config` selected PostgreSQL **14.20**. This is not live PostgreSQL16 verification. No bare Maven test command or demo database test was used.


## Preservation observations

The initial staged-content snapshot was captured before implementation. A later read-only comparison detected concurrent external staging of 16 new chat implementation/resource/test/proxy entries. The agent used no staging/index mutation command, did not restore the index and left those external changes untouched. Therefore byte-identical index preservation cannot be asserted; existing staged work was not deliberately altered by the agent. Final hashes/status are recorded with the verification results. Existing unrelated working-tree files and protected historical evidence were left in place.

Only disposable isolated PostgreSQL and local mock HTTP listeners were started by tests. No live demo/original database access, service restart, live inference, financial/password/account operation, OTP activation, historical migration edit or dependency installation occurred. Protected configuration and old phase verification gaps remain unchanged.

## Final isolated Java result

`cd backend && bash scripts/test-isolated.sh`: **388 tests passed; zero failures, errors or skips**. This includes all361 previous Java tests and27 new tests (19 integration,6 transport,2 contract/input). The disposable database was stopped successfully by the runner. Existing investigation regression passed. No database transaction was active during mocked remote calls; authorization/session/membership changes during inference suppressed answers. The nine financial/account/audit tables explicitly compared by the read-only chat integration test remained unchanged.

Final staging observation: 472 working-tree status entries. Initial staged-content SHA256 `b3e29e9bbb85a8c24691b00cfe72ad268870c9e3de072f970d06040cae0219cc`; final observed SHA256 `ad81a946a4acc092f7b48fac5497ea7df2ef98cb4cb8a9032e478f9b664d3fe7`. The difference reflects externally staged entries observed during implementation, left untouched. No git add/commit/push/reset/clean/restore command was issued. `git diff --check` passed.

## Files

Created Java: `chat/{ChatController,ChatDtos,ChatFailure,ChatRules,ChatResponseValidator,AiChatClient}.java`; `security/accounts/{ChatEvidenceBuilder,ChatProjectionQueries}.java`; `investigation/AiRequestBudget.java`; main `resources/ai-chat/contract.json`; test `chat/{ChatContractTest,AiChatClientTest}.java`, `security/auth/ChatIntegrationTest.java`, test `resources/ai-chat/python-fixtures.json`.

Modified Java: `security/auth/BusinessEndpointCatalog.java`, `security/BoundedRequestBodyFilter.java`, `investigation/InvestigationController.java`. No historical migration, payment/refund/account mutation implementation or dependency changes.

Python: modified `app/config.py`, `app/api/chat.py`, `tests/test_chat.py`; created `scripts/export_chat_contract.py`. Frontend proxy: created `chat_proxy.py`, `tests/test_ai_chat_proxy.py`; modified `dev_server.py`. Documentation: this report, root README/PROGRESS, frontend README, ai-service README and backend API reference.

## Phase693 handoff and remaining limits

Implement UI only in a future approved phase. Use the three Java APIs through the same-origin proxy; add exact central-client catalog/timeout support then, not direct Python calls. Keep questions/history/context memory-only, history bounds, no secret/PII entry, manual send, no automatic retries and existing session/operation locks. Clear chat on logout/session replacement/selection change, discard stale responses and label dated provenance/fallback honestly. Render strings with safe DOM APIs and source citations as text. Do not treat an answer as permission to mutate a payment.

No deployment command was executed or prepared to silently modify old activation scripts. Later combined deployment must review protected shared-token configuration, enable both Java/Python chat endpoints together, preserve OTP disabled and first activate the separately approved V12/V13 schema for link context. Native browser, local model compatibility and actual timing remain pending. No Phase693 implementation or prior phase closeout occurred.


## Packaging and final handoff

`cd backend && mvn package -DskipTests` passed after the successful full isolated suite. The runnable JAR contains `ChatController.class` and the reviewed `ai-chat/contract.json`; packaging did not rerun tests or start the application. Final `git diff --check` passed. No application activation, schema change, live credential use or Phase693 work followed.

Final totals: **388 isolated Java tests;237 Python tests;1,089 frontend checks (1,043 mocked JavaScript +46 proxy);119 operational mocked tests**. All final suites passed. Native browser/LLM testing remains pending; the isolated runner used PostgreSQL14.20, not live PostgreSQL16. Production service identity/TLS, broader languages/free-form generation, conversation persistence, and richer daily/method evidence require separate reviewed work.
