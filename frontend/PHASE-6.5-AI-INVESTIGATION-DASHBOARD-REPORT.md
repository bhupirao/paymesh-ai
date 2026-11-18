# Phase 6.5 — AI Investigation Dashboard

Implemented November 14, 2026. Frontend only. No live protected business request or investigation POST was issued. Existing services were not restarted. No backend, deployment or Git commit work is included.

## Inspection and actual contract

Inspected frontend Phase 6.1–6.4 reports, README, HTML/CSS, app/workspace/payment/refund/decimal/session modules, API client/configuration, proxy allowlist and existing tests. Inspected Phase 5.4 Java/Python integration report, including its final November 14 live verification section, backend/API-REFERENCE.md, InvestigationController, EvidenceCollector, AiInvestigationClient, InvestigationResponseValidator, InvestigationErrors, BusinessAccess authorization, Python investigation schemas, deterministic investigation service, RAG enrichment and generation status paths. No separate final live verification artifact was found; the completed live results are recorded in the Phase 5.4 report.

Actual endpoint: **POST `/api/v1/payments/{UUID}/investigate`**, Bearer JWT, no request body and no Idempotency-Key. Browser calls the existing same-origin `/api/v1` proxy, never Python or llama.cpp. The actual internal Java-to-Python route is `/api/v1/investigations`; it is not a browser endpoint. Existing proxy route/method policy is unchanged.

Java authorizes through BusinessAccess before collecting any evidence or calling Python, including disabled/busy cases. ADMIN can use supported cross-merchant business access; MERCHANT must have active access to the payment's active verified merchant. Missing/inaccessible payments use 404. The collector uses a read-only REPEATABLE_READ transaction with a 5-second transaction timeout, detaches a privacy-minimized snapshot, and releases the database transaction before remote generation. One investigation per Java process is admitted with no queue or automatic retry. Supported collection sizes are at most 100 records each; unsupported stored evidence is withheld as an entire unavailable collection, never a partial financial total.

200 returns exactly:

```text
{
  evidenceProvenance: {
    source: "JAVA_AUTHORIZED_DATABASE_SNAPSHOT",
    collectedAt: ISO instant,
    unavailableEvidence: { collectionName: explanationString, ... },
    scope: string
  },
  investigation: {
    investigationId: UUID, paymentId: UUID,
    investigationStatus: COMPLETED | INCONCLUSIVE,
    scenario: enum, generatedAt: aware ISO timestamp,
    customerView: {
      title, summary, whatHappened, nextAction: nonblank strings,
      requiresUserAction: boolean
    },
    technicalView: {
      observedPaymentStatus: CREATED | PROCESSING | SUCCESS | FAILED | CANCELLED | REFUNDED,
      rootCause: string,
      rootCauseCertainty: CONFIRMED | LIKELY | INCONCLUSIVE,
      supportingEvidence: string[], technicalExplanation: string,
      recommendedActions: string[], certainty: CONFIRMED | LIKELY | INCONCLUSIVE
    },
    evidenceReferences: string[], limitations: string[],
    analysisMode: DETERMINISTIC | RAG_ASSISTED | RAG_LLM,
    knowledgeReferences: [ { documentId, chunkId, title: strings, sources: string[], score: finite number } ],
    generationStatus: enum
  }
}
```

All supported scenarios are rendered from the response: CREATED, PROCESSING, GATEWAY_TIMEOUT, SUCCESS, WEBHOOK_RECOVERY, RECONCILIATION_RECOVERY, FAILED, PARTIAL_REFUND, FULL_REFUND, UNRESOLVED_REFUND and INCONCLUSIVE. No scenario is inferred from currency, gateway status, refund totals or frontend arithmetic. All six valid payment states can be investigated; backend evidence validation may still return a safe error for unsupported/inconsistent evidence.

Application investigation errors use ApiErrorResponse (`timestamp,status,error,message,fieldErrors,path`); security/proxy errors may instead be `{status,message}`. Backend-specific failures include 401/403 authorization, 404 unavailable payment, 422 unsupported/excessive/inconsistent evidence, 502 upstream timeout/non-2xx/invalid response, and 503 disabled/busy/unavailable evidence. UI additionally handles 400, 429, proxy 504, network/client timeout and invalid JSON/schema safely. No raw error body, model prompt or raw evidence payload is rendered.

## Dashboard and lifecycle

Added AI Investigation to sidebar and payment-detail section navigation. The sidebar entry focuses the investigation section for a selected payment or directs the operator to authorized lookup first. Payment loading, creation, processing and refund completion **never** launch an investigation. Investigate with AI is an explicit action only.

The section shows the selected payment UUID, merchant, amount, currency, method and latest authorized lookup status. Authorized overview data is now exposed independently of refund-summary eligibility: an invalid/unavailable refund history still blocks refunds but does not prevent Java from investigating an otherwise authorized payment, including an unresolved refund scenario. No refund eligibility or decimal constraint was weakened.

Lifecycle states: Ready, Loading, Completed, Inconclusive, Failed or unavailable. Loading displays a local spinner, accessible status text, elapsed seconds and a several-seconds/typically 10–45 second explanation. No progress percentage or invented server stage is shown. The result region carries aria-busy; the separate live status remains announceable. Elapsed seconds are not announced every second. Actual COMPLETED and INCONCLUSIVE control the completed result lifecycle; INCONCLUSIVE is not treated as a request failure. Failed requests expose an explicit retry button. Every new run, including re-investigation after success, requires a deliberate click.

Results use responsive cards and safe semantic definition lists/lists for:

- Summary: actual investigation UUID/payment UUID/status/scenario, generatedAt, analysisMode and generationStatus.
- Customer view: exact title, summary, whatHappened, nextAction and requiresUserAction. The frontend does not author replacement financial advice.
- Technical view: exact observedPaymentStatus, rootCause, technicalExplanation, supportingEvidence and recommendedActions, with separate observed-state/explanation certainty (`certainty`) and rootCauseCertainty labels. Labels never become percentages.
- Evidence/provenance: source, collectedAt, scope, every unavailableEvidence entry, evidence references and all returned limitations. Collection and generation timestamps have distinct labels.
- Knowledge: document/chunk IDs, title, source strings and actual retrieval relevance score. Sources remain plain text, never automatically converted to links. Empty references are explicit. Scores are not correctness probabilities or cause confidence.

The fixed simulation/trust notices remain. Java provenance attests to authorized database collection, not bank debit/settlement/refund arrival. Python's returned limitation about supplied unauthenticated input is preserved: it describes Python's own boundary, while Java's envelope describes authorized collection. Unavailable evidence is not proof an event never occurred. A current mutable SUCCESS gateway row does not establish a past timeout. Only returned evidence/explanations may identify webhook/reconciliation recovery.

## Validation, RAG and generation status

schema.js validates the complete envelope before rendering anything: exact required object keys matching Java's validator, canonical UUIDs and selected payment match, valid aware ISO dates/calendar values, enums, string/boolean types, arrays, nested objects, unavailable-evidence map and finite numeric retrieval scores. Invalid/mismatched envelopes expose no partial result. A validated copy is deeply frozen in memory.

Generation statuses displayed exactly: DISABLED, NOT_ATTEMPTED, SUCCEEDED, NO_RELEVANT_CONTEXT, RETRIEVAL_UNAVAILABLE, TIMEOUT, UNAVAILABLE, INVALID_RESPONSE, VALIDATION_FAILED and CONTEXT_LIMIT. Each receives a fixed descriptive caption. The actual Java constraint is **RAG_LLM implies SUCCEEDED**, which the frontend mirrors. It does not invent additional reverse implications absent from Java's validator. The Python service normally emits SUCCEEDED only after accepted local wording selection; all non-RAG_LLM modes are described without claiming successful LLM-assisted analysis, even if an unusual validator-permitted combination were returned.

DETERMINISTIC is deterministic analysis; RAG_ASSISTED is knowledge-assisted analysis/fallback; only RAG_LLM + SUCCEEDED is labeled successful local LLM-assisted analysis. DISABLED/NOT_ATTEMPTED are not described as proof a model ran. Generation timeout/invalid/unavailable/validation failures are shown as non-successful generation rather than disguising fallback as live LLM success.

The real local Qwen path selects approved customer/technical wording variants and echoes a deterministic scenario under constrained validation. It does not autonomously decide payment state, amounts, refunds, authorization, root cause or financial actions. No confidence values, sources, scenarios or financial outcomes are fabricated by the frontend.

## Session, selection and operation protection

Existing in-memory token storage, expiry timers/focus checks and API session versioning remain. Logout/expiry/session replacement clears investigation context, results, timer display and pending UI state. Async completions check both session version and local selection/evidence sequence; late success/errors cannot populate another selection, and the central client's version check prevents an old 401 clearing a replacement session.

The observer tracks authorized payment fields, complete refund/gateway histories and their loading/availability state. Switching payment, refreshing details/history, observing changed fields or starting a financial intent clears the old investigation; it does not automatically re-investigate. This conservative policy can clear an unchanged historical result simply because a refresh started. Results are snapshots, not a live view; external changes remain unknown until observed by a refresh.

Unresolved creation/refund intents, processing reviews, uncertain processing and active financial requests block investigation. A pending investigation blocks new payment/refund reviews and confirmations, while allowing read-only lookup/selection and refresh. Switching or refreshing during analysis invalidates the pending result and retains duplicate admission until that request settles. Its result is discarded; server work may still continue. This separation avoids weakening existing payment/refund idempotency while permitting safe read navigation. Refund-history/remaining calculations remain BigInt-based and Java remains authoritative.

No localStorage, sessionStorage, IndexedDB, cookies, URL tokens or persistent caching was added. No credentials/tokens, prompts or raw evidence are logged. All returned text uses createElement/textContent; source strings do not become anchors.

## Timeouts and error behavior

Reused exact existing settings: browser API investigation timeout **65000 ms**, proxy Java socket timeout **55 s**, Java AI default connect timeout **2000 ms** and response timeout **45000 ms**. Proxy socket timeouts are idle I/O bounds, not a new guaranteed total deadline. The live process's private environment was not read or changed; the Java figures are source defaults/documented configuration, not a new runtime configuration attestation.

Client timeout uses the existing AbortController; it ends browser waiting, not necessarily Java/Python/LLM work. 504 and network/timeout notices explicitly warn that the request may still be completing. Busy 503/429 instruct waiting and explicit retry. No automatic retries, model prompts, raw upstream bodies or stack traces appear. The API client gained safe error-reason metadata for network, timeout and invalid JSON without changing existing call return shapes or error statuses.

## Files created and changed

Created:

- assets/js/investigation/schema.js — exact response validation and mode/generation descriptions.
- assets/js/investigation/model.js — explicit lifecycle, guards and snapshot invalidation.
- assets/js/investigation/render.js — safe customer/technical/provenance/knowledge rendering.
- assets/js/investigation/view.js — accessible controls, elapsed display and shared lock observation.
- assets/js/investigation/fixtures.js — synthetic schema fixtures imported only by tests; never fallback application content.
- assets/js/investigation-tests.html and investigation-tests.js — mocked investigation tests.
- PHASE-6.5-AI-INVESTIGATION-DASHBOARD-REPORT.md — this report.

Changed:

- index.html, assets/css/app.css — investigation navigation, section, responsive cards and labeled lifecycle styling.
- assets/js/app.js — connect investigation observer to authorized details and financial locks.
- assets/js/api/client.js — safe reason metadata for timeout/network/invalid JSON; no new route or retry.
- assets/js/features/refunds.js — separate read/mutation busy guards and authorized overview independent of refund totals; refund eligibility still requires valid fresh summary.
- assets/js/features/refunds-view.js — details-state observer and investigation-aware mutation lock.
- assets/js/features/payments.js — explicit uncertain-processing presentation flag, cleared by authorized lookup.
- assets/js/features/payments-view.js — investigation-aware financial controls and unresolved-intent guard.
- README.md and assets/js/features/README.md — current scope and verification instructions.

Unchanged by this phase: Java/Python implementation, API config/route allowlist, dev_server.py/security/CSP, session.js, exact decimal utilities, existing test pages/files and historical phase reports. Pre-existing staged/unstaged work remains in place.

## Automated QA and browser distinction

| Suite | Fresh result |
|---|---|
| Python proxy regressions | 12 tests passed, 0.580 s; mocked upstream and temporary loopback listener |
| API client | 10 assertions passed |
| Authentication | 34 assertions passed |
| Payment creation/processing | 94 assertions passed |
| Gateway/refunds | 125 assertions passed |
| AI investigation | 149 assertions passed |

New tests cover full valid/malformed/mismatched envelopes, UUID/calendar/offset/nested validation, deep freezing, every scenario/payment status/mode/generation status, invalid RAG_LLM combinations, actual customer/technical fields, separate certainty labels, provenance/unavailable evidence, knowledge/relevance/empty references, limitations and safe DOM, correct same-origin bodyless authorized POST with no key, explicit action and duplicate protection, actual 65-second client timer plus fired AbortController, COMPLETED/INCONCLUSIVE, safe HTTP error matrix, network/timeout/invalid JSON, deliberate retry, snapshot invalidation, all session/selection races, late 401, and real financial controller guards.

JavaScript ran as native browser modules in the available JavaScript runtime with mocked fetch and minimal DOM/event doubles. No Node project/build/dependency was introduced. The timeout test uses a portable synthetic AbortError; no live delay/failure was induced. An integrated mocked entry check verified: lookup sends zero investigation POSTs; explicit action sends one; loading locks refunds while lookup remains available; valid result renders; financial controls restore; refresh and logout clear results.

The browser skill connection returned unavailable. Actual Phase 6.5 browser rendering, desktop/mobile/focus/screen-reader QA and real Java/Python/LLM investigation calls are **not freshly verified by the agent**. Earlier user-confirmed browser results are historical. No live protected request or financial mutation was used for this phase. The manual plan below covers that remaining verification.

Public read-only checks passed: updated frontend HTML and investigation-tests.html served; proxied payment health RUNNING; Java readiness UP; Python health UP/configured RAG_LLM (health's modelConnectivity remains NOT_VERIFIED); llama.cpp status ok. These checks do not establish successful live generation. Backend suites were not rerun because backend implementation is unchanged.

## Exact startup and browser test URLs

Reuse http://127.0.0.1:5500 and reload static assets. Do not restart any service or launch a duplicate frontend listener. Only in a later session with no frontend server, start from repository root with `python3 frontend/dev_server.py`.

```bash
python3 -m unittest discover -s frontend/tests -v
curl --fail http://127.0.0.1:5500/ -o /dev/null
curl --fail http://127.0.0.1:5500/api/v1/payments/health
```

Open each test page in a separate browser tab. They use synthetic fixtures and mocked fetch only:

- http://127.0.0.1:5500/assets/js/tests.html — PASS: 10 assertions.
- http://127.0.0.1:5500/assets/js/auth-tests.html — PASS: 34 assertions.
- http://127.0.0.1:5500/assets/js/payment-tests.html — PASS: 94 assertions.
- http://127.0.0.1:5500/assets/js/refund-tests.html — PASS: 125 assertions.
- http://127.0.0.1:5500/assets/js/investigation-tests.html — PASS: 149 assertions.

## Planned user-operated live verification

These are instructions for the user, **not actions performed by or authorization for the agent**. Use existing provisioned credentials privately. Do not copy tokens/passwords into console, commands, screenshots or reports. Do not create/process/refund payments, modify evidence or stop services. Run investigations serially because Java admits one per process. A difference from the expected scenario is a result to inspect, never a reason to force the expected text.

For each authorized scenario:

1. Reload/sign in, look up the exact UUID and verify actual merchant, amount, method, current payment status, gateway and refund history. Wait until details loading ends; resolve any unsubmitted/uncertain financial intent first.
2. Use the AI Investigation detail link. Confirm the selected UUID and metadata. Merely loading the payment must not send an investigation request.
3. Click Investigate with AI once. Verify loading text/elapsed time and disabled duplicate submission, without fabricated progress. Expect several seconds, typically 10–45; do not deliberately issue duplicates or induce outages.
4. Inspect the actual returned scenario/status, customer and technical text, both certainty fields, analysisMode/generationStatus, provenance source/scope, collectedAt separately from generatedAt, unavailable evidence, evidence references, actual document/chunk/source/relevance metadata and all limitations. RAG_LLM/SUCCEEDED is expected only if live local generation succeeds; genuine DETERMINISTIC/RAG_ASSISTED fallback must be labeled accurately. INCONCLUSIVE remains a valid analysis result.
5. Record only nonsensitive observed results as needed before refreshing. Refresh payment & refunds after investigation and confirm authorized payment/refund state remains unchanged. Refresh clears the historical investigation by design; it must not automatically run another one. Confirm bank debit/settlement/refund arrival is never claimed as verified.

Scenario A — Merchant A successful USD:

- UUID **842b460e-2451-4294-abc7-62c5525bc180**.
- Expected pre-state: DEMO_MERCHANT_A, 25.00 USD, CARD, MOCK_STRIPE, SUCCESS, no refunds.
- Expected actual investigation scenario: **SUCCESS**. Confirm no invented historical timeout/recovery. A confirmed observed SUCCESS need not establish a confirmed root cause. Afterward keep the payment SUCCESS/no refunds.

Scenario B — Merchant A full INR refund:

- UUID **96829409-bb1a-4f82-b113-4bc9694bd2c0**.
- Expected pre-state: DEMO_MERCHANT_A, 500.00 INR, MOCK_RAZORPAY, REFUNDED, actual successful refunds 200.00 + 300.00, remaining 0.00.
- Expected scenario: **FULL_REFUND**. Verify the explanation and evidence references acknowledge actual refund evidence, with bank arrival unverified. Afterward REFUNDED, both records and remaining 0.00 must be unchanged. Do not initiate another refund.

Scenario C — Merchant A webhook recovery:

- UUID **c072351f-4646-4288-b8ca-6758d4e521f3**.
- Expected pre-state: DEMO_MERCHANT_A, 200.00 INR, SUCCESS.
- Expected scenario: **WEBHOOK_RECOVERY**, supported by the actual returned explanation/references. A matching processed webhook can support confirmation; it does not establish a previous timeout. Preserve a returned inconclusive root cause even if observed-state certainty is CONFIRMED. Payment state must remain unchanged.

Scenario D — Merchant B reconciliation recovery and isolation:

- UUID **c6f797c0-c810-4730-bac2-19cb8504a87d**.
- While still Merchant A, attempt lookup: expect missing/inaccessible feedback and no Merchant B details or investigation result. Verify no previous private result remains attached to that UUID. The UI must not offer investigation of an inaccessible selection. Existing backend authorization tests/Phase 5.4 checks cover the protected investigation route itself; do not extract tokens to force browser console requests.
- Sign out and privately sign in as Merchant B or ADMIN. Look up D and verify DEMO_MERCHANT_B, 25.00 USD, SUCCESS.
- Explicitly investigate. Expected scenario: **RECONCILIATION_RECOVERY**, only when returned from actual supporting reconciliation evidence. Inspect returned rootCauseCertainty independently from observed-state certainty. Verify matching UUID/provenance/references/limitations and unchanged payment state afterward.

Finish by signing out and checking private investigation data disappears. In mocked test tabs verify replacement/expiry/switch/late responses. At approximately 375px and desktop widths, verify wrapping UUIDs, readable cards, keyboard navigation/focus, live status, no automatic source links and no horizontal page clipping. Do not stop live services to test failures; use the mocked suite.

## Proposed final frontend QA / project completion plan (not executed)

1. Run all five test pages in the user's actual browser and record current results separately from mocked runtime results; inspect browser console only for sanitized errors and never print tokens/credentials.
2. Complete the four serial user-operated scenarios and authorization isolation checks above, confirming unchanged financial state. Verify fallback labels if naturally observed; do not induce service outages.
3. Complete desktop/375px keyboard, screen-reader, focus, long-content, empty/error/expiry and responsive QA across login, creation/processing, details/refunds and investigation. Fix findings within the authorized frontend scope before declaring final QA complete.
4. Reconcile root project status/documentation and remaining production limitations in a separately authorized finalization phase. Current loopback HTTP server is development-only; no production deployment/certification is implied.
5. Review the complete working tree and concurrent staging with the user before any separately instructed final commit/push/deployment. No final Git operation is part of Phase 6.5.

## Remaining limitations

Live Phase 6.5 LLM/authorization/browser/visual results remain manual verification tasks. Evidence snapshots cannot establish real bank behavior, and external state changes are only noticed when the frontend observes a refresh. Clearing or timing out a request does not prove server cancellation. Java may reject excessive/inconsistent evidence with 422; the frontend does not invent a partial result. Validation intentionally follows the frozen current schema and must be updated if backend contracts change. Memory-only state is lost on reload/session loss. No persistent cache, automatic retries, polling, new backend feature or deployment was added.

## Final security and preservation audit

All agent writes are under frontend/. Non-frontend unstaged binary diff matches the initial snapshot. No Java/Python implementation, migrations/schema, protected configuration, credentials, backups or archives were changed. No direct database connection or original paymesh_db/port 8080 access occurred. No live protected business GET/POST, payment mutation, webhook, settlement or investigation was issued. Mocked tests never reached the live backend; live checks were public health/static GETs only.

Service listener PIDs are unchanged from the initial observation: frontend 85275/5500, Java 83515/18080, Python 80995/8000, llama.cpp 79855/8082. Existing frontend serving was reused without restart. HTML checks found zero duplicate IDs and zero missing literal application element references. Source checks found no innerHTML, console logging, localStorage/sessionStorage or IndexedDB use in the frontend modules.

Initial and final observed `.git/index` SHA-256: `c7cbbae42c5fb48feef96a4b7aa7e8320d865b9c236211d95a167ebc7ddbfbbb`.
Initial and final observed staged binary diff SHA-256: `956c213749be687af219bae2fda32b5132499cb1842ebd127af1415534207d7e`.
Both observations match; no concurrent staging change was detected in this phase. No git add/commit/push/reset/clean or other index mutation was issued. Pre-existing staged and unstaged content remains intact.

Final JavaScript rerun: investigation 149, API 10, authentication 34, payment workflow 94, gateway/refund 125 assertions passed. Python proxy suite: 12 tests passed. These counts are fresh mocked/runtime results; actual browser verification remains explicitly pending. Stop after Phase 6.5. No deployment, new backend feature or final commit was implemented.
