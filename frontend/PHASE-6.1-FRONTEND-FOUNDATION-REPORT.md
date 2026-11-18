# Phase 6.1 — Frontend architecture and foundation

Date: November 14, 2026. Scope ends at foundation; no business screens implemented.

## Inspection and existing work

`frontend/` existed and was empty (including hidden files). No reusable frontend assets existed. No AGENTS.md was found in the project/parent search. Inspected root README.md, PROGRESS.md, backend/API-REFERENCE.md, Phase 5.4 report, payment/refund/gateway controllers and DTOs, AuthController, JwtTokenService, JwtSecurityConfiguration, BusinessEndpointCatalog, LegacyEndpointCatalog, BusinessAccess, BusinessSecurityErrors, body limiter, global exception handler, investigation controller/collector/client/response validator, and Python investigation schema.

Existing backend contracts, security, DTO naming and Phase 5.4 provenance are reusable. Root progress notes remain unchanged. The historical 226 Java and 102 Python results were not rerun; this phase does not change backend code. Git already contained extensive staged and unstaged work; no staging operations were performed.

## Exact browser-relevant API inventory

All paths below are actual Java routes, without proxy rewrites. `id` is a UUID path parameter. No query schema or pagination exists. Request/response field names below are case-sensitive. Dates are ISO-8601 instants; money is Java BigDecimal serialized as JSON numbers. UI must avoid floating-point arithmetic for financial calculations; later forms should validate decimal strings and rely on backend authoritative totals. Gateway/refund nullable fields must remain unknown rather than invented values.

Authentication shorthand: B = Bearer RS256 access JWT with ADMIN or MERCHANT, checked against current enabled account, authorization version and roles. M = active membership in an active verified merchant for merchant operations; ADMIN can access payment resources across merchants with auditing. Creation by ADMIN still requires an existing active verified merchant. No browser settlement credential exists.

| Method / path | Authentication | Request schema / headers | Success schema / codes | Endpoint-specific errors |
|---|---|---|---|---|
| POST `/api/v1/auth/login` | Public; remote-address rate limit | JSON `{login:string,password:string}`; login nonblank ≤255; password nonnull char array ≤72 in DTO (no DTO minimum); JSON content type | 200 Token | 400 validation, 401 credentials/disabled/invalid state, 413 >4096 bytes, 429 with Retry-After, 503 auth unavailable |
| GET `/api/v1/payments/health` | Public | No body | 200 `{service:"PayMesh AI Payment Service",status:"RUNNING"}` | Static service indicator, not readiness |
| POST `/api/v1/payments` | B + creation authorization | JSON PaymentInput; required `Idempotency-Key` nonblank 1–255 | 201 Payment; exact replay 200 Payment | 400 invalid/missing key, 403 creation scope, 404 unknown merchant, 409 conflicting key |
| GET `/api/v1/payments/{id}` | B + M or ADMIN | No body | 200 Payment | 404 missing or inaccessible |
| POST `/api/v1/payments/{id}/process` | B + M or ADMIN | No body; no idempotency header required | 200 Payment | 404 missing/inaccessible, 409 lifecycle/claim conflict, 503 uncertain gateway failure |
| GET `/api/v1/payments/{id}/gateway-transactions` | B + M or ADMIN | No body | 200 Gateway[] (empty allowed) | 404 missing/inaccessible |
| POST `/api/v1/payments/{id}/refund` | B + M or ADMIN | JSON `{amount:number}` ≥0.01, ≤17 integer and 2 fraction digits; required Idempotency-Key | 201 Refund; exact replay 200 Refund | 400 invalid/key missing, 404 missing/inaccessible, 409 changed replay amount/non-SUCCESS/amount exceeds remaining |
| GET `/api/v1/payments/{id}/refund` | B + M or ADMIN | No body | 200 latest Refund | 404 missing/inaccessible payment or no refund |
| GET `/api/v1/payments/{id}/refunds` | B + M or ADMIN | No body | 200 Refund[] in creation order; [] if none | 404 missing/inaccessible payment |
| POST `/api/v1/payments/{id}/investigate` | B + M or ADMIN | No body; Java collects authorized evidence | 200 InvestigationEnvelope | 404 missing/inaccessible, 422 unsupported/excessive evidence, 502 timeout/non-2xx/invalid upstream, 503 disabled/busy/evidence unavailable |

Every protected route can return 401 for invalid/missing/stale JWT, 403 for denied role, and 503 for unavailable security state. Malformed UUID/JSON and framework parameter conversion errors can return 400 with framework-dependent shape. Application validation/argument failures use 400; absent resources 404; idempotency/state conflicts 409; gateway exceptions 503. Do not assume every error has fieldErrors. Proxy additionally returns sanitized 400/403/404/405/413/415/502/504 boundary errors. Unhandled HTTP methods are rejected by the standard server (501); no HEAD/OPTIONS forwarding is implemented even though Java catalogs include these for enumerated routes.

Schemas:

- Token: `{accessToken:string,tokenType:"Bearer",expiresIn:900,expiresAt:instant}`. No separate role, user or merchant fields.
- PaymentInput: `{merchantId:string,amount:number,currency:string,customerId:string,paymentMethod:string}`. Strings nonblank; amount ≥0.01, ≤12 integer and 2 fraction digits. INR routes MOCK_RAZORPAY, USD MOCK_STRIPE; unsupported currency fails processing without provider fallback.
- Payment: `{paymentId:UUID,merchantId:string,amount:number,currency:string,customerId:string,paymentMethod:string,status:string,createdAt:instant}`. Payment statuses CREATED, PROCESSING, SUCCESS, FAILED, CANCELLED, REFUNDED.
- Gateway: `{id:UUID,paymentId:UUID,gatewayName:string,gatewayTransactionId:UUID|null,status:string,errorCode:string|null,errorMessage:string|null,createdAt:instant,updatedAt:instant}`. The name is **gatewayName**, not gateway. Gateway status SUCCESS/FAILED/TIMEOUT in investigation evidence.
- Refund: `{refundId:UUID,paymentId:UUID,amount:number,status:string,createdAt:instant}`; current simulated success flow records SUCCESS. Partial refunds leave payment SUCCESS; consuming remaining balance changes it to REFUNDED. No remaining-balance field or currency field in Refund; derive context from authorized payment and complete refund history, with exact decimal handling.
- InvestigationEnvelope: `{evidenceProvenance:{source:"JAVA_AUTHORIZED_DATABASE_SNAPSHOT",collectedAt:string,unavailableEvidence:Record<string,string>,scope:string},investigation:Investigation}`.
- Investigation: `{investigationId:UUID,paymentId:UUID,investigationStatus:"COMPLETED"|"INCONCLUSIVE",scenario:string,generatedAt:instant,customerView:CustomerView,technicalView:TechnicalView,evidenceReferences:string[],limitations:string[],analysisMode:"DETERMINISTIC"|"RAG_ASSISTED"|"RAG_LLM",knowledgeReferences:KnowledgeReference[],generationStatus:string}`.
- CustomerView: `{title:string,summary:string,whatHappened:string,nextAction:string,requiresUserAction:boolean}`.
- TechnicalView: `{observedPaymentStatus:string,rootCause:string,rootCauseCertainty:"CONFIRMED"|"LIKELY"|"INCONCLUSIVE",supportingEvidence:string[],technicalExplanation:string,recommendedActions:string[],certainty:"CONFIRMED"|"LIKELY"|"INCONCLUSIVE"}`.
- KnowledgeReference: `{documentId:string,chunkId:string,title:string,sources:string[],score:number}`.
- Scenario: CREATED, PROCESSING, GATEWAY_TIMEOUT, SUCCESS, WEBHOOK_RECOVERY, RECONCILIATION_RECOVERY, FAILED, PARTIAL_REFUND, FULL_REFUND, UNRESOLVED_REFUND, INCONCLUSIVE.
- GenerationStatus: DISABLED, NOT_ATTEMPTED, SUCCEEDED, NO_RELEVANT_CONTEXT, RETRIEVAL_UNAVAILABLE, TIMEOUT, UNAVAILABLE, INVALID_RESPONSE, VALIDATION_FAILED, CONTEXT_LIMIT. RAG_LLM requires SUCCEEDED; fallback results must not be presented as LLM success.

Security errors commonly use `{status:number,message:string}`; 401 may include WWW-Authenticate (controller-level failures need not). Login responses disable caching. Application and investigation errors use `{timestamp:instant,status:number,error:string,message:string,fieldErrors:Record<string,string>,path:string}`. Missing/framework errors may differ. Never display raw upstream bodies, stacks or secrets. API client retains status, safe message, fieldErrors and Retry-After; render messages as text.

### Unsupported and excluded APIs

There is **no payment listing, dashboard aggregates, pagination, current-user profile, merchant listing, refresh token, registration or server-side logout endpoint**. Backend repository methods are not browser APIs. Lookup must use an operator-supplied UUID; merchant creation scope requires an operator-supplied known merchant ID, verified by Java. No invented financial KPI cards, merchant dropdown data or transaction feed.

ADMIN has the same business operations across merchants; ADMIN JWT also permits GET `/actuator` and `/actuator/info` in Java, intentionally omitted from this frontend proxy. Public actuator health/readiness/liveness also stay outside the proxy. Settlement reconcile/history/webhook retry routes use a separate opaque bearer token; webhook provider routes use HMAC. Neither is an ADMIN JWT operation and neither is proxied. Python `/investigations` is an internal Java dependency, never a browser route. No browser calls to Python/llama.cpp, signing utilities, database or port 8080.

## Selected integration architecture

Browser → `http://127.0.0.1:5500` static assets and same-origin `/api/v1/...` → fixed Java `127.0.0.1:18080`. Python standard library only, no new runtime dependency. Compared with file:// or separate-origin static hosting, this avoids module origin problems and backend CORS edits. Compared with using Java static resources, it avoids rebuilding the frozen backend. Tradeoff: a small development server must be maintained; it is not an internet-facing production server.

Proxy route and method allowlist matches the business table and static payment health only. Literal UUID shape; no query, fragment, percent encoding, traversal, backslash, absolute URL or double-slash target. Static files restricted to index and assets with recognized suffixes and resolved-root containment; no directory listing, backend files, reports or Python source served. Host must equal literal loopback and listener port. Origin, when present, must equal same origin; cross-site fetch rejected. No Access-Control-Allow-Origin header. This limits DNS rebinding and browser cross-origin abuse; it does not authenticate local processes.

Login limit 4096 bytes; other request bodies 16384. Reject ambiguous Content-Length, transfer encoding and Expect. Downstream socket idle timeout 10 seconds; Java socket timeout 15 seconds or 55 for investigation. Upstream response cap 512 KiB; no redirects followed; oversized/redirect responses become 502. Timeout becomes 504, network failure 502, with no automatic retries. Socket timeouts are idle limits, not hard total deadlines. Client timeout 20 seconds, investigation 65 seconds. Cancellation does not undo backend work.

Only Authorization, Content-Type and Idempotency-Key are forwarded from browser; Accept is fixed JSON. No Cookies, Origin, forwarded-host/IP, arbitrary headers, or user-selected upstream target. Response status/body preserved except boundary failures; only Retry-After and WWW-Authenticate extra headers forwarded. No upstream cookies/location/CORS forwarded. All responses no-store with CSP, nosniff and no-referrer. Request logs disabled. Java sees loopback IP, so login rate limiting is shared across frontend users; appropriate only for the single-operator demo. Thread-per-request development server lacks production concurrency admission/global rate limiting and TLS. Production should use maintained HTTPS ingress and the same explicit allowlist rather than exposing this script.

## Authentication strategy

Short-lived 900-second access JWT, stored only in a module variable. Refresh/tab close loses session; sign in again. No localStorage, sessionStorage, cookies, URL tokens, console logging or refresh token. Logout clears memory and sensitive UI; it cannot revoke an already issued stateless token, which remains subject to backend expiry/revocation checks. Clear session on 401, show sign-in-required state, never automatically resubmit mutations. 403 retains session and shows access denied; 404 does not disclose merchant existence. Session module checks expiresAt on token access; future UI adds expiry timer and focus checks and clears private views/in-flight UI results on logout.

JWT claims from JwtTokenService are iss, aud, sub (user UUID), jti, iat, nbf, exp, authorization_version, roles. No merchant membership identity is embedded. Later UI may decode roles for presentation only; this is unverified client data and is **not a security boundary**. Java validates signature and current account/role/membership state for every authorized operation. Never infer merchant from login name or user UUID. No profile endpoint exists. No signing keys, database credentials, HMAC secrets or settlement tokens enter frontend configuration.

## Structure and created files

Everything changed in this phase is new under frontend/:

```text
frontend/
  .gitignore
  index.html
  README.md
  PHASE-6.1-FRONTEND-FOUNDATION-REPORT.md
  dev_server.py
  assets/
    css/app.css
    vendor/bootstrap/{bootstrap.min.css,LICENSE}
    js/
      app.js
      api/{config.js,client.js}
      auth/session.js
      components/dom.js
      features/README.md
      tests.html
      tests.js
  tests/test_dev_server.py
```

Base shell includes semantic landmarks, skip link, focus indicators, local system typography, navy/white/blue tokens, responsive sidebar/grid and an explicit simulation notice. It makes no API calls. Bootstrap 5.3.3 CSS and MIT license were downloaded from the official twbs/bootstrap v5.3.3 GitHub source (exact URLs in README); no Bootstrap JavaScript or external fonts/CDN needed. Initial sandbox DNS restrictions required approved download access. No packages installed.

## Subsequent implementation plan (not implemented)

Keep a single HTML entry for memory-session continuity; implement views in features/login.js, workspace.js, payments.js, payment-details.js, refunds.js, investigation.js and admin.js. Reusable components will include forms, status badges, loading/error/empty states and evidence/timeline renderers. Keep endpoint wrappers under api/ and auth presentation under auth/. Add tests alongside behavior as each phase arrives; no dummy data adapter.

1. Login: labeled login/password fields, correct autocomplete, required constraints, pending button, generic credential errors and Retry-After feedback. Consume actual token metadata; role claims only for navigation. Clear password after submission and never log it.
2. Merchant workspace: UUID lookup and known merchant-ID entry for creation. Empty state explains no listing endpoint; no fabricated balance/revenue/settlement totals. Read authorized payment merchantId only after lookup.
3. Creation/processing: decimal validation, supported-currency guidance, operation confirmation with simulation context, stable idempotency key per exact creation intent. Disable repeat submission; after uncertain response look up state before a deliberate retry. Never silently change key or automatically process a newly created payment.
4. Details/gateway history: authorized payment fields, timestamps and real gateway attempts. Timeline combines only supported observed events; label timestamp source and avoid fabricated process/settlement events. Empty gateway history differs from unavailable history. Responsive table/card treatment preserves labels and keyboard access.
5. Refunds: exact remaining amount from complete successful refund history and payment amount; backend remains authoritative. New refund intent gets a stable key, replay uses exact same key/amount. Separate latest-refund 404 from an empty history; distinguish failed loads from no refunds. Amount/merchant/status review before submission.
6. Investigation: customer and technical views, persistent visible loading text (typically 10–45 seconds), aria-live status, disabled trigger and duplicate prevention. Client 65-second timeout accommodates Java evidence collection and 45-second upstream timeout. No automatic retry; busy 503 allows explicit retry after waiting. Ignore stale results after navigation/logout. Display provenance source, collectedAt, scope, unavailableEvidence, investigationStatus, scenario, analysisMode, generationStatus, evidenceReferences, knowledgeReferences and limitations. Render bank debit/settlement/refund arrival as unverified. Cancel UI does not imply server cancellation.
7. ADMIN workspace: same authorized operations with explicit known merchant/UUID inputs and cross-merchant context. No merchant management, settlement/reconcile controls or global stats; these APIs are absent or use excluded credentials.

All forms use visible labels, inline error association, field focus on failure, keyboard-operable controls and no color-only status. Use textContent/createElement, never innerHTML for API/model strings; knowledge references remain text unless a later explicit safe URL policy is added. Tables scroll on small screens; no hover-only actions; honor reduced motion. Planned screens must preserve unsent inputs on service errors while clearing sensitive data on logout. Loading, empty, unavailable, forbidden, missing, conflict, timeout and validation states are distinct.

## Startup and verification

From repository root (Python 3.10+, verified 3.13.10):

```bash
python3 frontend/dev_server.py
# Open http://127.0.0.1:5500/
# Another terminal:
curl --fail http://127.0.0.1:5500/ -o /dev/null
curl --fail http://127.0.0.1:5500/api/v1/payments/health
python3 -m unittest discover -s frontend/tests -v
# Open http://127.0.0.1:5500/assets/js/tests.html for mocked client tests
```

Ctrl-C stops only the new foreground frontend server. Do not restart any existing service. Existing Java on 18080 is required only for real API use, not the shell or tests. No credentials needed for the listed checks.

## Tests and limitations

- Python proxy suite: **12 tests passed**, 0.574 seconds. Exercises static exposure, MIME/module serving, security headers, path normalization/encoding/traversal, forbidden routes/methods, Host/Origin, framing, request limits, allowlist, header forwarding, redirects, oversized upstream response, upstream failure and status/Retry-After preservation. Upstream is mocked; temporary listener uses an ephemeral loopback port. First run exposed leading-double-slash normalization; raw request-line validation fixed it, suite rerun green.
- API ES modules: **10 assertions passed**, using the same tests.js module in available JavaScript runtime with mocked fetch and minimal DOM. Checks JSON, same-origin URL, redirect policy, invalid route rejection before fetch, 401/session expiry clearing, duplicate suppression and malformed JSON. No Node build system or project Node dependency introduced.
- In-app browser bootstrap reported browser unavailable. Browser execution, screenshot review, mobile visual QA and full accessibility review remain unverified. Browser test page is provided for reproduction; this report does not claim visual verification.
- Backend suites not rerun: no backend changes, no need to create database clusters or load the 8 GB machine. No login, payment creation/processing/refunds or investigation performed. Runtime secrets and database content were not read.
- This is a development foundation; complete business screens, expiry-driven UI, API typed decoders, exact decimal display helpers and view-specific tests belong to later phases. No production certification or real bank settlement claim.

## Preservation and live verification results

Read-only HTTP checks passed: frontend shell 200, proxied payment health RUNNING, Java readiness UP, Python health UP (configured RAG_LLM; modelConnectivity NOT_VERIFIED in that health response), llama.cpp health ok. Health calls required approved loopback network access because the restricted shell could not connect. No original port 8080 or database connection was attempted.

Original listeners remain Java PID 83515 on 18080, Python PID 80995 on 8000 and llama.cpp PID 79855 on 8082. No existing process was stopped or restarted. The new frontend server was started for checks on port 5500.

Initial and final `.git/index` SHA-256: `1548bce336428293592c8b241c807d82a23fe99091b38d01599897a41ab119ad`.
Initial and final staged binary diff SHA-256: `cdc3e4d2f638e09fdc9549ccd638d8e47c48981b962d9f10e470247f5bbe5966`.
Git index and staged content preserved. All phase writes are confined to the previously empty frontend directory. No backend, migrations, protected configuration, backups, archives or pre-existing staged files changed. No git add/commit/push/reset/clean issued.

## Phase 6.2 next steps

Await explicit instruction before beginning. Start with login and authenticated workspace state, role-aware presentation, session expiry/logout clearing and UUID lookup against the documented contracts. Then add payments, details, refunds and investigation in separately authorized phases. Perform browser/mobile/accessibility QA when the browser is available. Keep the same-origin boundary and simulation disclosures intact.
