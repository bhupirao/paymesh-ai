# Phase 6.4 — Gateway transaction history and refund management

Implemented November 14, 2026. Frontend only. No live financial mutation, database connection or service restart was performed. AI investigation UI remains Phase 6.5.

## Inspection and implementation

Read frontend Phase 6.1–6.3 reports and README; inspected existing HTML/CSS, app/workspace/payment modules, decimal handling, session/API modules, fixtures, tests and proxy allowlist. Inspected backend API-REFERENCE.md, GatewayTransactionController, RefundController, response/request DTOs, secured/internal gateway and refund services, entities, repositories, BusinessAccess and payment lifecycle validator. Reused the single HTML entry, local Bootstrap, memory session, versioned API client, exact numeric lexeme parser and existing payment controls. No new dependencies, backend changes or proxy route/security changes.

Payment lookup now opens authorized payment details with Overview, Gateway transactions, Refund history and Refund management sections. Open payment details is also available on created/processed results, without re-entering the UUID. Details independently fetch Java-authorized payment/history endpoints rather than trusting a supplied client record. Selecting another payment clears the previous details immediately; late responses are rejected by selection and operation sequence. The existing creation, processing and lookup controllers remain in use. Their controls participate in a shared UI lock while a refund intent is active. Session notifications clear all details, refund fields, confirmations, results, cached observations and recovery intent.

History tables show actual records, UUIDs, statuses and UTC timestamps with responsive horizontal scrolling, table captions and column headers. Nullable provider UUID/error fields are represented explicitly. Empty history differs from unavailable/invalid history. All API strings use createElement/textContent. Stored gateway errorMessage is never rendered because the backend can persist exception messages; recognized codes receive fixed safe descriptions and other error details are withheld. There are no inferred timeout/retry/fallback/settlement events.

## Actual API contracts

All browser calls remain same-origin under `/api/v1`. Each protected route requires `Authorization: Bearer <JWT>` and ADMIN or MERCHANT role. Java checks current account/authorization state. MERCHANT requires access through active membership in the payment's active verified merchant; ADMIN business access may cross merchants and is audited. Out-of-scope resources use 404. UI roles remain presentation only.

| Endpoint | Request | Successful response | Relevant failures |
|---|---|---|---|
| GET `/api/v1/payments/{UUID}` | No body | 200 PaymentResponse: paymentId, merchantId, amount, currency, customerId, paymentMethod, status, createdAt | 400 malformed UUID, 401, 403, 404, auth/infrastructure 503 |
| GET `/api/v1/payments/{UUID}/gateway-transactions` | No body | 200 array of GatewayTransactionResponse; [] allowed; repository order createdAt descending | 400, 401, 403, 404, infrastructure failures |
| GET `/api/v1/payments/{UUID}/refunds` | No body | 200 complete array of RefundResponse in createdAt/refundId ascending order; [] means known empty | 400, 401, 403, 404, infrastructure failures |
| POST `/api/v1/payments/{UUID}/refund` | JSON `{amount:number}`, Content-Type application/json, required nonblank Idempotency-Key (1–255) | 201 new RefundResponse; 200 exact stored replay | 400 validation/header, 401, 403, 404, 409 amount/state/key conflict; proxy/security errors below |

GatewayTransactionResponse fields: `id:UUID`, `paymentId:UUID`, `gatewayName:string`, `gatewayTransactionId:UUID|null`, `status:string`, `errorCode:string|null`, `errorMessage:string|null`, `createdAt:Instant`, `updatedAt:Instant`. Actual persisted gateway statuses include INITIATED, SUCCESS, FAILED, TIMEOUT and UNKNOWN. UNKNOWN/GATEWAY_EXCEPTION is a possible stored gateway exception outcome. Gateway currency guidance is not history. Each row's IDs, association, status, nullable fields, timestamps and uniqueness are validated before display.

RefundResponse fields: `refundId:UUID`, `paymentId:UUID`, `amount:BigDecimal`, `status:string`, `createdAt:Instant`. **No currency field**; currency comes from the authorized payment. RefundRequest requires positive amount ≥0.01, at most **17 integer digits and 2 fractional digits**, unlike payment creation's 12 integer digits. The entity stores precision 19, scale 2; the service validates the same maximum and never rounds input. The UI uses exact JSON numeric tokens, not JSON strings for submission.

The existing GET `/.../refund` latest-refund endpoint is intentionally unused for totals. There is no pagination, refund-list aggregate, merchant discovery, payment listing, idempotency-key lookup or bank-arrival endpoint. The complete per-payment refund array is the source of refund totals.

API/security errors may use `{status,message}` or application `{timestamp,status,error,message,fieldErrors,path}`. UI messages are fixed rather than raw bodies. Implemented handling includes 400, 401, 403, 404, 409, 413, 415, 422, 429, 502, 503 and 504 as applicable; not all are intrinsic refund-controller statuses. 401 clears private state; 403 preserves authentication but denies the operation. Proxy limits remain 16 KiB business request bodies, 512 KiB responses, JSON-only bodies, fixed Java target and no redirects. Truncated, invalid or unavailable histories are never treated as empty.

## Eligibility, lifecycle and exact calculation

FinancialRefundOperations locks the payment before reading its refund key/total. It checks an existing `(paymentId, key)` **before** new-refund lifecycle eligibility, allowing exact replay even after a full refund. A changed amount for an existing key yields 409. A new key requires payment SUCCESS and amount no greater than original minus successful refunds. Partial refunds leave SUCCESS; consuming the remaining amount persists REFUNDED directly in the backend refund flow. CREATED, PROCESSING, FAILED, CANCELLED and fully REFUNDED payments cannot receive a new refund. Generic processing lifecycle rules are not used to infer refund status.

The current Refund constructor creates only SUCCESS records; the repository sum counts only SUCCESS. The frontend accepts that implemented contract. Any FAILED, pending or unknown refund status makes the history unsupported/insufficient and blocks further actions; it is not counted as success or silently treated as available funds. This conservative policy must be revisited against backend semantics if new statuses are implemented.

Extended decimal.js without changing payment-creation limits:

- refundDecimal validates canonical positive strings with up to 17 integer and 2 fraction digits; no exponent, comma, sign, whitespace, leading-zero variants or rounding.
- minorUnits converts validated decimal strings directly into BigInt cents. formatMinor formats BigInt back to two decimal places, including zero.
- Original amount uses the 12-digit authorized payment constraint. Successful refund amounts use the 17-digit refund constraint. Sum and subtraction use BigInt only.
- Remaining = original − sum(validated successful refund rows). No Number conversion or floating-point financial arithmetic. The pre-existing numeric-lexeme parser is used before JSON.parse on payment/refund responses.
- serializeRefund emits exact numeric JSON, e.g. `{"amount":200.00}`, from the frozen string. Tests also cover 99999999999999999.99 without precision loss.

History validation rejects non-arrays, missing records known from an earlier successful load, duplicate refund IDs, wrong payment association, invalid UUIDs/timestamps, pre-payment refund timestamps, numeric rather than preserved-string amounts, unsupported statuses and totals exceeding original. REFUNDED requires total equal original. SUCCESS requires positive remaining. Other payment states require no successful refunds. Previously observed immutable payment attributes and refund records cannot change or disappear during refresh. Valid history and payment state are both required; gateway availability is not a prerequisite for refund arithmetic.

A refund refresh reads payment → complete refund history → payment again, rejecting changes in payment state/fields during that interval. Snapshots expire after 30 seconds. Review re-reads state before freezing intent, and initial confirmation refuses an expired/changed review. Java's lock and cumulative limit remain authoritative at submission. Separate HTTP reads are **not an atomic database snapshot**, and cannot prove that an external partial refund did not occur immediately after the reads. The complete-array endpoint has no independent completeness token/version/count; a previously unknown, silently omitted row cannot be detected generically. The UI trusts the implemented full-array contract, checks all returned/previously known records, blocks reported failures, and relies on Java to reject races. It does not claim stronger consistency or fabricate missing totals.

## Refund workflow and recovery

The form presents selected UUID, original amount/currency, successful total, remaining amount, exact input and Use remaining amount. Review shows payment UUID, merchant, refund amount, currency, successful total at review and estimated remaining after the proposed refund. Expected remaining is labeled an estimate, never a persisted payment status. A separate Confirm simulated refund button is required.

Each reviewed intent freezes payment UUID, exact body/serialized bytes and crypto.randomUUID() key in memory. Fields lock while the intent exists. No automatic submission or retry occurs. Pending duplicate submissions and payment switching are blocked. An unsubmitted review can be canceled. An uncertain intent cannot be canceled/replaced with a new key: recovery is deliberate exact-key/exact-byte retry. This remains possible after refreshing a fully REFUNDED payment because backend replay precedes eligibility checks.

Success accepts only HTTP 201/200, then validates refund UUID, selected payment, exact amount, SUCCESS and timestamp. The confirmed record and HTTP status are shown separately from refreshed totals (200 explicitly labeled replay). A successful response triggers fresh authorized payment/history reads; the confirmed refund must appear unchanged in history. The final payment status comes from Java, never frontend subtraction. A missing confirmed record or refresh failure leaves the confirmed record visible, marks totals/status stale or unavailable and blocks new refunds. Refresh can restore availability once authoritative data is valid.

Timeout, network failure, malformed/mismatched response and 502/503/504 preserve the original uncertain intent and key, with explicit no-new-refund recovery guidance. A 409 is not blindly resubmitted. Known rejected requests (400/403/404/409/413/415/422/429) retain their intent until the operator chooses Refresh & clear rejected intent; this only clears after a successful authorized state/history refresh. This explicit rejected-intent path does not discard an uncertain request. After confirmation, a separately reviewed new intent receives a new key.

Refresh, sign-out, expiry or session replacement loses the memory-only intent/key. After such loss, inspect authorized payment and complete refund history before creating another refund; no API can recover the original key. Browser refresh does not establish that an uncertain request failed. A confirmed simulated refund record does not prove bank refund arrival. Sign-out is local clearing, not server JWT revocation.

## Files created and changed

Created:

- assets/js/features/refunds.js — validation, BigInt totals, selection/read sequencing and refund state/recovery.
- assets/js/features/refunds-view.js — detail sections, review/confirmation, freshness and shared UI lock.
- assets/js/components/history.js — accessible safe tables/pairs and sanitized gateway error descriptions.
- assets/js/refund-tests.html and refund-tests.js — mocked gateway/refund test page.
- PHASE-6.4-GATEWAY-HISTORY-REFUNDS-REPORT.md — this report.

Changed:

- index.html and assets/css/app.css — detail navigation, responsive tables, summary and form/review markup/styles.
- assets/js/api/decimal.js — separate refund precision and BigInt utilities.
- assets/js/api/client.js — exact refund serializer on the existing allowed POST refund route only.
- assets/js/features/payments-view.js and assets/js/app.js — detail navigation, authoritative overview updates and shared mutation locks.
- assets/js/features/README.md and frontend README — current scope and test/runbook links.

Unchanged by this phase: session.js, workspace.js, payment-workflow model, existing test files, API configuration/allowlist, dev_server.py, CSP/proxy policies, local Bootstrap and all backend files. Existing staged/unstaged frontend changes from earlier phases remain intact.

## Automated QA and read-only checks

| Suite | Result |
|---|---|
| Python proxy regressions | 12 tests passed; 0.579 s; ephemeral loopback listener, mocked Java |
| API client | 10 assertions passed |
| Authentication/session | 34 assertions passed |
| Creation/processing workflows | 94 assertions passed |
| Gateway/refund workflows | 125 assertions passed |

New tests cover the actual gateway endpoint/auth, all five statuses, nullable fields, malformed/mismatched/duplicate records, fixed safe error information, complete refund route, empty history, exact partial/full/max arithmetic, lifecycle/unknown-status blocking, invalid amounts and over-refunds, fresh review/no POST, explicit confirmation, exact JSON/auth/key, 201 and 200, stable bytes/key, retry/refresh race prevention, new intent key, duplicate/pending/switch guards, conflict and error matrix, malformed/mismatched/uncertain responses, full-refund replay after REFUNDED, post-confirmation refresh/failure, confirmed-record inclusion, actual payment status rendering, immutable history/payment checks, stale review, failed review refresh, expiry/logout and late cross-payment/session results, plus safe DOM rendering.

JavaScript ran as the same browser modules with mocked fetch in the available JavaScript runtime and minimal DOM/event doubles. No Node build system, dependency or package was introduced. The integrated app also initialized and exercised mocked lookup → detail summary → refund review → locked lookup → cancel/unlock → sign-out/clear. This is wiring/state verification, not visual browser certification.

Browser skill connection returned unavailable. Phase 6.4 actual browser/mobile/clipboard/focus/screen-reader QA remains manual. Earlier user-confirmed Phase 6.3 browser/live checks are historical, not claimed fresh Phase 6.4 tests. No live protected business request or refund was issued by the agent.

Read-only checks passed: existing frontend serves updated HTML and refund-tests.html, proxied payment health RUNNING, Java readiness UP, Python UP/configured RAG_LLM (health reports modelConnectivity NOT_VERIFIED), llama.cpp status ok. No service was restarted. Backend suites were not rerun because backend implementation is unchanged.

## Startup and exact test URLs

Reuse the running http://127.0.0.1:5500 server. Reload the main page to receive static files; do not start another listener or restart existing services. Only if no frontend is running in a later session, from repository root run `python3 frontend/dev_server.py`.

```bash
python3 -m unittest discover -s frontend/tests -v
curl --fail http://127.0.0.1:5500/ -o /dev/null
curl --fail http://127.0.0.1:5500/api/v1/payments/health
```

Open test pages in separate tabs; all use mocked fetch, synthetic credentials and no live financial calls:

- http://127.0.0.1:5500/assets/js/tests.html — PASS: 10 assertions.
- http://127.0.0.1:5500/assets/js/auth-tests.html — PASS: 34 assertions.
- http://127.0.0.1:5500/assets/js/payment-tests.html — PASS: 94 assertions.
- http://127.0.0.1:5500/assets/js/refund-tests.html — PASS: 125 assertions.

## Planned user-operated browser verification

These are **manual steps for the user**, not actions performed by the agent. Enter provisioned Merchant A credentials privately; no credentials/tokens belong in screenshots, reports or console logs. Do not deliberately stop services or use the original application/database. The USD payment must remain unchanged for later AI investigation.

1. Reload http://127.0.0.1:5500/ and sign in as Merchant A. Look up INR UUID **96829409-bb1a-4f82-b113-4bc9694bd2c0**. The details workspace loads automatically; Open payment details explicitly refreshes it. Verify actual payment merchant DEMO_MERCHANT_A, amount 500.00 INR, method UPI and current status. In Gateway transactions verify actual gatewayName MOCK_RAZORPAY, internal/provider UUIDs, status and both timestamps. Do not infer missing records from currency. Nullable values must say Unavailable; empty history must say no records.
2. Look up USD UUID **842b460e-2451-4294-abc7-62c5525bc180**. Verify actual merchant DEMO_MERCHANT_A, amount 25.00 USD, method CARD, current status and actual MOCK_STRIPE gateway record. **Do not click any refund or process confirmation for USD.** Gateway/detail GETs leave it unchanged.
3. Return to the INR UUID and select Refresh payment & refunds. Before mutation verify current SUCCESS, complete refund history, original 500.00, successful refunds 0.00 and remaining 500.00 INR. If state/history differs, stop this exact 200+300 sequence and inspect what already happened; never repeat it assuming the original balance. A missing/unavailable history must leave refund controls disabled. If the 30-second snapshot expires, refresh before reviewing.
4. Enter **200.00** and select Review refund. Review re-fetches Java state/history without mutating. Confirm UUID 96829409-bb1a-4f82-b113-4bc9694bd2c0, merchant DEMO_MERCHANT_A, refund 200.00 INR, successful total 0.00 and expected remaining 300.00. Select **Confirm simulated refund** once, deliberately. While pending, buttons/other financial operations must be blocked. Do not refresh the browser or issue another intent on uncertainty; use only the provided exact-intent recovery action.
5. Verify a confirmed actual refund record with UUID, payment UUID, 200.00, SUCCESS and timestamp (HTTP 201 for new record; 200 only for an exact replay). After automatic authoritative refresh, verify history includes the record, total successful 200.00, remaining **300.00 INR**, and Java payment status **SUCCESS**. Partial refund does not imply REFUNDED. If refresh fails, distinguish the confirmed record from unavailable totals and use Refresh payment & refunds; do not create another refund yet.
6. With fresh valid state, choose Use remaining amount (or enter **300.00**) and Review refund. Verify a distinct new intent: same INR payment/merchant, refund 300.00, prior successful 200.00 and expected remaining 0.00. Select **Confirm simulated refund** once. This is a separate refund, not a retry of the first intent.
7. After authoritative refresh, verify both actual refund records, total successful **500.00 INR**, remaining **0.00**, and actual backend payment status **REFUNDED** in overview. Verify further new refunds and Use remaining amount are disabled; no further intent should be possible for this payment.
8. Read-only look up the USD UUID again, if desired. Verify it remains 25.00 USD/SUCCESS with no refund records and remaining 25.00 if its starting history was empty. Do not mutate it. It is reserved for Phase 6.5.
9. Sign out and confirm private forms/history/review disappear. Repeat keyboard-only navigation, section anchors, focus visibility and status announcements at desktop and approximately 375px width. Tables must scroll within their region rather than clipping the page. Test mocks cover unavailable services and uncertain responses; do not induce live financial failures to reproduce them.

## Remaining limitations and Phase 6.5 plan

Live refund mutations and full browser visual/accessibility QA remain user verification tasks. Snapshots are bounded by separate HTTP reads rather than a backend atomic summary/version API; Java protects concurrent cumulative limits. Unknown refund statuses deliberately block new actions. Raw gateway exceptions are withheld, so detailed diagnosis requires separate authorized operational tooling. Browser refresh/session loss discards recovery keys; no persistent storage or lookup-by-key API is introduced.

Phase 6.5, when instructed: add Java-authorized POST `/api/v1/payments/{UUID}/investigate` UI only through the existing allowlist; customer/technical views; explicit loading/duplicate prevention for 10–45 second investigations; response timeout handling; provenance, collectedAt/scope/unavailableEvidence, actual analysisMode/generationStatus, evidence and knowledge references and limitations; safe text rendering and session/selection staleness guards. Keep Python/LLM off browser access and distinguish simulated outcomes from unverified bank behavior. No Phase 6.5 UI was implemented.

## Final security and preservation audit

All agent writes were confined to frontend/. The non-frontend unstaged binary diff matches the initial snapshot. No Java/Python implementation, protected configuration, migration/schema, credentials, backups or archives were modified. No direct database connection or original paymesh_db/port 8080 access occurred. No live payment creation, processing, refund or investigation was executed. Financial test requests were mocked; live requests were static files and public health GETs only.

All initial/final listener PIDs match: frontend 85275 on 5500, Java 83515 on 18080, Python 80995 on 8000, llama.cpp 79855 on 8082. Existing frontend static serving was reused. No services were stopped or restarted.

Git observations:

- Initial index SHA-256: `6c309d46191880304d7e1c5b77c0f83c9ffd326b36093eff3d42029fa6e20136`.
- Initial staged binary diff SHA-256: `cc9d3e727b474058f88d1fc7d775af4ebd4f56efc63f7ce68aed2c20d29cc0d1`.
- An intermediate preservation check matched both initial hashes.
- Final observed index SHA-256: `c7cbbae42c5fb48feef96a4b7aa7e8320d865b9c236211d95a167ebc7ddbfbbb`.
- Final observed staged binary diff SHA-256: `956c213749be687af219bae2fda32b5132499cb1842ebd127af1415534207d7e`.

Concurrent external staging occurred between checks: new Phase 6.4 files/report that were initially untracked now appear staged. The agent issued no git add/commit/push/reset/clean, restored no index snapshot and made no index mutation. The concurrent staging was left untouched. Consequently byte-for-byte index equality across the entire phase cannot be claimed; agent work preserved staging without attempting to undo the external update.

Final JavaScript results after all functional refinements: gateway/refund 125, API 10, authentication 34, payment workflow 94 assertions passed. Python proxy suite remains 12 passed; no proxy implementation changes were made. Stop after Phase 6.4; no Phase 6.5 implementation begun.
