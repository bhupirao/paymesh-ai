# Phase 6.3 — Payment creation and processing

Implemented November 14, 2026. Frontend only; no live financial mutations executed. Phase 6.4 gateway history, refunds and investigation screens remain unimplemented.

## Source inspection and actual backend behavior

Reused Phase 6.1/6.2 reports, frontend README, HTML/CSS, application/controller modules, session lifecycle, central API client/configuration, safe payment renderer, fixtures and existing tests. Inspected PaymentController, PaymentRequest, secured PaymentServiceImpl, FinancialPaymentOperations, PaymentRequestHasher, BusinessProcessingClaims, PaymentRepository claim predicates, PaymentOrchestrationServiceImpl, PaymentStatusTransitionValidator, GatewayRouter, mock gateways and backend/API-REFERENCE.md.

Actual creation: `POST /api/v1/payments`, Bearer JWT and required nonblank Idempotency-Key (1–255 characters). JSON fields: merchantId, amount, currency, customerId, paymentMethod. String fields are nonblank; DTO has no enum for paymentMethod. Amount is BigDecimal, minimum 0.01, at most 12 integer digits and 2 fractional digits. The UI intentionally supports INR and USD and allows a nonblank payment method label rather than inventing a backend method enumeration. Merchant ID is entered explicitly; no name/UUID inference, hardcoded merchant or merchant-list API.

Creation authorization remains Java-owned: MERCHANT needs active membership in an active verified merchant; ADMIN still needs an existing active verified creation merchant. Core idempotency is scoped by merchant ID and key, comparing a canonical request hash (decimal trailing zeros normalized). Same key plus exact intent returns 200 and the current persisted payment; new creation returns 201. Changed request with that key conflicts with 409. A 200 replay may already be SUCCESS/PROCESSING/etc.; it must not be forced to CREATED.

Actual processing: `POST /api/v1/payments/{UUID}/process`, Bearer JWT, no body and no Idempotency-Key. Java authorizes and atomically claims only CREATED → PROCESSING. PROCESSING and all terminal statuses cannot be claimed again. Gateway SUCCESS maps to SUCCESS, FAILED to FAILED and TIMEOUT leaves PROCESSING. Exceptions can leave an uncertain PROCESSING state and return 503; network failure never establishes payment failure. A concurrent asynchronous outcome can cause another actual terminal state to be returned. UI shows only validated backend statuses CREATED, PROCESSING, SUCCESS, FAILED, CANCELLED or REFUNDED.

Routing is backend-controlled: INR → MOCK_RAZORPAY, USD → MOCK_STRIPE. Guidance is labeled expected routing, not gateway history or evidence that a transaction occurred. No fallback provider behavior is invented. All outcomes remain simulated; bank debit, settlement and refund arrival are unverified.

## Implemented UI

Functional Payment lookup / Create payment navigation switches sections inside the single HTML entry. Login and memory-session continuity are preserved. Creation has visible labels, exact-decimal input, currency selector, customer and method fields, required validation, routing guidance and a review panel with all five exact intent fields. Confirming creation is a separate explicit button. Fields lock while an intent exists, preventing silent edits against an existing key. A new-payment action starts a separate intent and unlocks/resets the form.

Successful creation/replay shows actual returned payment details and UUID with a clipboard copy control and manual-copy fallback. New creation never automatically processes. CREATED results and eligible lookup records expose Review processing. Confirmation shows payment UUID, merchant, amount, currency and remaining actual record fields, followed by an explicit simulated-processing button. PROCESSING and terminal states do not expose processing controls. While processing, duplicate processing and lookup submissions are blocked. An uncertain processing attempt is blocked locally until a fresh authorized lookup; only a returned CREATED record can then be reconsidered with a new review.

Loading, success, validation, denial, conflict and uncertainty messages are fixed safe text. Inputs and controls use existing responsive Bootstrap/local CSS, keyboard behavior and focus styles; notices and results never depend on color alone. The review panel receives focus after successful form review. No external assets or dependencies added. Optional recent activity was not added: the workspace only displays records created/retrieved explicitly, without suggesting a full transaction history.

## Exact decimal handling

`api/decimal.js` validates decimal strings without conversion to Number or arithmetic: canonical unsigned whole part (0 or 1–12 digits without leading zeros), optional one/two fractional digits, and positive amount. It rejects zero, signs, whitespace, exponents, commas, excessive precision and oversized integer parts. Valid input normalizes to two decimals using string padding. This is deliberately stricter presentation syntax than BigDecimal's general parser.

Creation serialization emits the validated decimal string as a JSON **number token**, e.g. `"amount":999999999999.99`, while JSON.stringify escapes each text field. It never converts that amount through a JavaScript Number. Payload size is checked against the unchanged proxy's 16 KiB limit before review acceptance.

Payment responses on creation, processing and lookup use a small JSON token scanner to preserve amount numeric lexemes as strings before JSON.parse can round them. It respects escaped JSON strings and leaves non-amount tokens alone; final JSON.parse still validates syntax. Tests cover maximum-scale values and escaped content/nested amount fields. Response amounts are normalized and compared as decimal strings. No binary floating-point financial arithmetic is used. Existing generic API calls retain normal response parsing and return shapes.

Before success, response shape, canonical payment UUID, parseable date, known status, amount constraints and all matching intent fields are validated. Creation accepts only 200/201, and 201 must return CREATED. Processing validates UUID, merchant/currency/customer/method/amount against its review and refuses a CREATED “success” response. Invalid/mismatched responses are treated as uncertain, never success. Default API behavior remains compatible; opt-in response metadata preserves HTTP 200 versus 201.

## Idempotency, uncertainty and recovery

Each reviewed intent receives crypto.randomUUID(), generated with browser cryptographic randomness. There is no fallback to Math.random. The frozen exact body and key remain together in memory through explicit confirmation, pending state and a deliberate retry. Retries send the same serialized bytes and same key, including after timeout, network loss, proxy 502/504, service 503, or malformed/mismatched success response. Nothing automatically retries a financial mutation. Request and controller guards prevent duplicate pending operations.

409 creation conflicts retain the intent and block blind resubmission; the message instructs investigation. Rejected 400/403/404/413 requests retain the locked intent; operator can deliberately retry it unchanged or explicitly start a new intent. Unresolved/conflicting intent replacement requires a visible checkbox acknowledgment that the original payment may already exist and a new intent may duplicate it. Pending operations cannot be replaced. New intents always receive new keys.

**Refresh, logout, expiry and session replacement discard memory-only creation recovery state.** After losing an uncertain intent, the UI cannot recover its unknown payment UUID or reproduce its key. Do not assume a refresh or another new request is safe; investigate through existing authorized operational records before creating another payment. There is no payment-list or idempotency-key lookup API to invent here. Once a UUID is known, use authorized payment lookup.

Processing never uses a fabricated idempotency header. Any uncertain processing response, conflict or rejected processing action removes its confirmation and requires a fresh lookup before reconsideration. No network error is converted into FAILED. Actual PROCESSING response instructs lookup later, without retrying processing. UI controls are guidance; Java's persisted lifecycle/claim remains the security and duplicate-charge boundary.

## Session and security preservation

The session module and its timers/listeners are unchanged. All workflow private state, intents, keys, confirmations, results, blocked-operation markers and form values clear on session notifications. Async results check session version and operation sequence; late successes/errors, including 401 from an old session, cannot populate or clear a replacement session. Logout is local clearing, not JWT revocation. Role presentation remains advisory; Java performs authorization on every operation.

Error handling covers 400, 401, 403, 404, 409, 413, 502, 503, 504, malformed responses and network/timeout failures. No raw response bodies/stacks enter messages. No credentials/tokens logged or embedded. Safe createElement/textContent rendering is used for intent, confirmation and actual payment fields. Existing JWT, proxy route/method allowlist, CSP, Host/Origin/path validation, size limits and header policy are unchanged. No direct Python/LLM, database, settlement-token or signing operations are exposed. Browser persistent storage remains unused.

## Files changed or created

Changed: index.html; assets/css/app.css; assets/js/app.js; assets/js/api/client.js; assets/js/features/workspace.js (lossless lookup/validation); assets/js/components/payment.js (shared intent renderer); assets/js/features/README.md; README.md.

Created: assets/js/api/decimal.js; assets/js/features/payments.js; assets/js/features/payments-view.js; assets/js/payment-tests.html; assets/js/payment-tests.js; this report.

Unchanged: dev_server.py, session.js, API config/allowlist, test fixtures and existing JavaScript/proxy test files, Bootstrap assets and historical reports. No backend changes.

## Tests and verification

- Existing Python proxy suite: **12 passed**, 0.608 seconds, temporary loopback test listener and mocked upstream. Existing server was not replaced.
- Existing API browser-module regression suite: **10 assertions passed**.
- Existing authentication browser-module suite: **34 assertions passed**.
- New payment workflow suite: **94 assertions passed**. Covers valid/invalid exact decimal input, required fields, currency and size constraints, actual method contract, lossless JSON, no submission on review, crypto key generation, locked intent, correct URL/method/body/auth/key, 201, 200 replay, stable exact retry, new key, duplicate and pending replacement prevention, error/conflict/authorization cases, malformed/mismatched responses, processing confirmation/body/header rules, lifecycle eligibility, actual SUCCESS/FAILED/PROCESSING rendering, uncertain gateway outcomes and fresh lookup requirement, timeout, session clearing, late responses and safe DOM rendering.

JavaScript suites ran as native modules in the available JavaScript runtime with mocked fetch and minimal DOM/event doubles; no project Node build/package/dependency was introduced. They do not certify native browser layout, clipboard permissions, form validation or focus behavior. Browser skill connection returned unavailable, so Phase 6.3 full browser/mobile/visual checks remain manual. User-confirmed earlier browser passes are historical results, not claimed fresh verification.

Read-only live checks: updated main HTML and new payment test page serve on the existing frontend server; payment health RUNNING; Java readiness UP; Python health UP with configured RAG_LLM and modelConnectivity NOT_VERIFIED; llama.cpp status ok. No live credentials or protected business mutations used. No backend/database test suites rerun because backend files were untouched.

## Exact startup and manual verification

Reuse the already running http://127.0.0.1:5500 server and reload the page to load static asset changes. Do not stop/restart existing services. Only in a later session with no frontend listener, run `python3 frontend/dev_server.py` from the repository root.

```bash
python3 -m unittest discover -s frontend/tests -v
curl --fail http://127.0.0.1:5500/ -o /dev/null
curl --fail http://127.0.0.1:5500/api/v1/payments/health
```

Open these independent mocked test pages; they never send live financial requests:

1. http://127.0.0.1:5500/assets/js/tests.html — PASS: 10 assertions.
2. http://127.0.0.1:5500/assets/js/auth-tests.html — PASS: 34 assertions.
3. http://127.0.0.1:5500/assets/js/payment-tests.html — PASS: 94 assertions.

Nonmutating main-screen review:

1. Reload and privately sign in using a provisioned account. Confirm normal role/expiry behavior and navigate between Payment lookup and Create payment without losing login.
2. Enter a known authorized merchant ID explicitly, amount 0.01, INR, a customer label and a nonblank method such as UPI. Select Review payment; confirm the exact values, locked fields and separate confirmation control. **Do not click Confirm simulated creation during a review-only check.** Starting a new unsubmitted intent resets fields.
3. Try zero, three decimals, exponent notation and 13 integer digits; invalid input must not produce a creation request. Review `999999999999.99` without submitting and verify exact digits. Change INR to USD in a fresh intent; guidance must change to MOCK_STRIPE and remain explicitly expected routing.
4. Use existing authorized SUCCESS/REFUNDED records in lookup to confirm no processing button appears for terminal states. Known Merchant A records: c072351f-4646-4288-b8ca-6758d4e521f3 and f1c5e798-fa14-438c-972d-d1a6247a5ffb. Merchant B c6f797c0-c810-4730-bac2-19cb8504a87d remains inaccessible to Merchant A; do not infer access from UI role labels.
5. Sign out or let the session expire with an unsubmitted review open. Confirm private form/review/results clear. Refresh requires fresh login. Verify keyboard-only navigation and focus, screen-reader announcements, and layout at approximately 375px and desktop widths.

Full creation/processing behavior is exercised by the mocked payment test page. Live mutation smoke tests were deliberately not performed; any later operator-approved live demo test must use an explicit new simulated intent, retain its returned UUID, separately review processing, and verify actual backend status by lookup. Never use existing reconciliation/refund examples as processing candidates or deliberately stop services to induce errors. No gateway-history/refund/AI UI is part of this phase.

## Remaining limits and next phase

Memory-only uncertain creation recovery is lost on page reload/session loss. No automatic recovery, listing, statistics, merchant discovery or idempotency lookup API exists. Optional current-session activity was omitted. Browser/mobile/native clipboard/accessibility QA and controlled live mutation smoke tests are unverified. Actual financial/provider/bank behavior remains simulated. Phase 6.4 gateway transaction history awaits instruction; no refund or investigation screen was started.

## Preservation audit

All agent edits were confined to frontend/. Non-frontend unstaged binary diff matches the starting snapshot. No Java/Python implementation, migration, schema, database, protected configuration, backup or archive was modified. No database connections or original paymesh_db/port 8080 access occurred. No live creation, processing, refund or investigation was performed.

All listener PIDs are unchanged: frontend 85275/5500; Java 83515/18080; Python 80995/8000; llama.cpp 79855/8082. Existing static serving was reused without restarting any service. Application entry also initialized successfully with DOM test doubles; this is a wiring check, not a visual browser verification.

**Git index changed concurrently outside agent-issued operations.** Initial index SHA-256 was `b1520b2e8de23f70fe3ecd1730359027f76d28da4cb019bc576461fa7f5b3187`; final observed index was `8b4a4254f236509e3310aee7d8d3dfd93e2560a096d5f930a16f866592e5b854`. Initial staged binary diff SHA-256 was `dc76251c1d38002ad665e1cb88e23ea985389cb05303742fa7aca8cd6c9d0227`; final observed staged diff was `73cf2bed810b11a283917413feb7cbdf42ca43f3db2f8b47beabf3870287d08f`. Newly staged files include files initially untracked during this turn. The agent issued no git add/commit/push/reset/clean or other index mutation and did not restore or alter the concurrently updated index. Therefore this report does not claim byte-for-byte index preservation across the turn; it confirms that agent work left staging untouched.

Final JavaScript rerun after renderer/UI refinements: payment 94, authentication 34 and API 10 assertions passed. Phase 6.3 stops here.
