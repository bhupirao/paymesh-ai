# Phase 6.8.3 — Customer checkout and simulated payment execution

**Implementation / automated verification. NOT live deployment or native browser certification.**
Live baseline remains operator-supplied V1–V11, counts6/4/4/2/6/4, OTP disabled.
V12 and V13 are pending combined activation. Phase681 native browser/password-change/
final audit and Phase682 live verification remain pending; neither phase is closed.
All Phase673/674 historical limitations remain unchanged. No Phase6.9 code is implemented.

## Actual architecture

Inspected the Phase682 report, actual V12/PaymentLinks, MerchantPortal and BusinessAccess,
account-administration lock/lifecycle, internal financial core, BusinessProcessingClaims,
original orchestration/routing/timeout simulator, reconciliation, session bootstrap,
frontend router/proxy, operational helpers and test harness.

Checkout is a **link-capability boundary**, not an impersonated Merchant/Admin account.
A public request never invokes the secured PaymentService/processing facade with a fake
principal. `CheckoutTransactions.accept` validates the exact token and authoritative
link/Merchant context, then creates and claims only the stored link's fixed payment via
`InternalPaymentService`. Account-enabled/ACTIVE, exact MERCHANT role, single ownership
membership (both Merchant→account and account→Merchant), active membership, verified/
active registry and ACTIVE V11 business state are rechecked under the existing exclusive
account-administration lock and a link row lock. Ambiguity fails closed.

The original Merchant/Admin facade still uses BusinessProcessingClaims and its JWT/
authorization checks. Both trusted paths continue through `AcceptedPaymentExecution`:
a package-private post-claim method containing the original gateway/initiation/ledger/
completion/status transition logic. Original constructors remain compatible for direct
unit tests; Spring uses the shared executor. No public arbitrary-payment processing API
was added. The exact new internal consumers are explicitly reviewed in the existing
architecture allowlist, with a regression asserting the continuation is not public and
HTTP controllers cannot supply a PaymentResponse/internal service/repository.

## Schema — additive V13 only

V1–V12 are unmodified. V13 adds:

- Composite owner uniqueness on existing payments/payment_links and a composite FK for
  the successful link association; no existing row values are updated.
- `checkout_attempts`: UUID PK; link/Merchant/payment association; unique payment UUID;
  SHA-256 idempotency key digest; canonical consent/simulation request digest; status;
  optional gate-validated simulation choice; creation/update timestamps.
- Composite FKs enforce link and payment ownership. Insert trigger requires the payment
  already PROCESSING and exact stored link amount/currency/method/Merchant match.
- Unique(link,key_digest) provides durable replay identity across retries/restarts.
- Partial unique(link_id) WHERE status IN(PROCESSING,UNCERTAIN,SUCCESS): at most one
  unresolved or successful attempt. FAILED rows retain full attempt/payment history.
- Payment outcome trigger synchronizes link PAID/successful association and attempt
  SUCCESS in the **same transaction** as payment SUCCESS (including webhook/reconciliation).
  FAILED releases the blocking slot. REFUNDED preserves the historical paid link and
  receipt timestamp; it does not reopen checkout.

V12's `PAID iff payment_id IS NOT NULL` constraint remains intact: processing association
is in checkout_attempts, while payment_links.payment_id is **successful payment only**.
A link is never attached to another Merchant's payment. One successful slot and existing
terminal payment lifecycle prevent a second successful checkout; this is local database
idempotency, **not an external exactly-once charge guarantee**.

## State machine and safe boundaries

1. GET reads a repeatable-read, read-only snapshot. No initiation/reconciliation/mutation.
2. Explicit consent POST + key enters a short REQUIRES_NEW acceptance transaction:
   account lock → link lock → same-key replay check → eligibility/expiry/blocking-attempt
   checks → exact internal payment creation → atomic CREATED→PROCESSING claim → durable
   attempt + honest CHECKOUT_ACCEPTED audit. All acceptance writes roll back together.
3. Commit releases database/account locks **before** gateway execution. The coordinator
   has no surrounding transaction. Existing gateway attempt/ledger operations remain.
4. Financial SUCCESS/FAILED completion runs through the shared original financial core.
   V13 triggers commit link/attempt state atomically. Exceptions/timeouts never imply
   FAILED; only still-PROCESSING accepted attempts are marked UNCERTAIN.
5. Same-key replay returns current link state without executing the gateway again.
   A different key is rejected while any attempt is PROCESSING/UNCERTAIN/SUCCESS. Status and cancellation prioritize this unique non-failed attempt over timestamp-sorted failed history, including clock-order anomalies.
6. A new explicit key/confirmation is allowed only after **definitive FAILED**, still
   eligible/unexpired ACTIVE link. History is retained; maximum5 attempts per link.

| Effective customer state | Pay behavior |
| --- | --- |
| ACTIVE | Explicit review/confirm may initiate |
| FAILED | New confirmation/key only if eligible, unexpired and <5 attempts |
| PROCESSING / UNCERTAIN | Status checks only; no replacement attempt |
| PAID | Receipt, no further payment; full refund never reopens link |
| EXPIRED / CANCELLED / UNAVAILABLE | No new attempt |

Accepted processing takes precedence over later expiry or Merchant suspension. Cancel
uses the same link/account serialization boundary and refuses an unresolved attempt.
A prior cancellation/suspension/expiry prevents initiation; a later one cannot erase an
accepted financial obligation. Tests race cancellation/acceptance and suspend while a
latch-controlled gateway is running, proving no long account lock spans that call.

### Crashes, reconciliation and remaining uncertainty

- Failure before acceptance commit: no durable payment/attempt; exact-key retry is safe.
- Commit then crash before gateway: durable PROCESSING, no gateway replay. Existing
  reconciliation has no provider evidence; it may retain UNKNOWN/RETRY. Manual authorized
  investigation is necessary; do not declare failed or create another payment by guess.
- Provider/ledger success but observation lost: PROCESSING/UNCERTAIN blocks new attempts.
  Existing authorized reconciliation/webhook may settle the payment; V13 synchronizes
  the link. Public GET/status **never calls reconciliation** or gateway execution.
- Financial success committed but HTTP response lost: status/replay returns PAID.
- Database unavailable/uncertain commit:503; client preserves key. No automatic mutation
  retry. Disabling demo outcome controls does not prevent reading/replaying an already
  accepted exact intent; replay does not invoke the simulator.

The existing local demo settlement scheduler remains disabled unless separately reviewed.
A timeout may still be completing server-side. Client cancellation does not stop it.
Real provider idempotency/chargebacks/provider availability are not simulated guarantees.

## Public API contracts

Exact public routes (no JWT/session needed):

| Method | Path | Request/result |
| --- | --- | --- |
| GET | /api/v1/checkout/{token} | Customer-safe snapshot, no query/body |
| GET | /api/v1/checkout/{token}/status | Same safe current status/receipt snapshot, no query/body |
| POST | /api/v1/checkout/{token}/pay | Required Idempotency-Key; JSON below; no query |

Token: exactly43 base64url characters from existing256-bit random V12 token. No list,
arbitrary payment lookup, refund, AI, gateway history or other public business API.
POST requires one exact configured `paymesh.sessions.origin` Origin, `X-PayMesh-Checkout:1`,
non-cross-site fetch, and body<=4096 bytes. Key is1–128 letters/digits/`.`/`_`/`:`/`-`.
JSON: `{ "confirmed":true }`; optional `"simulationOutcome":"SUCCESS|FAILED|TIMEOUT"`
only through the explicit private demo gate. Unknown fields, duplicate JSON keys,
trailing JSON, missing/non-boolean/false consent are rejected. Client amount, currency,
Merchant/user, method, gateway, status, paymentId or return URL are not accepted.
Server-generated `customerId=checkout-<attemptUUID>` cannot select the existing reserved
customer timeout scenario via untrusted order text.

Successful/resolved POST returns200; still PROCESSING/UNCERTAIN returns202. Same-key
replay returns current authorized link snapshot (not a second execution). Current global
link/receipt state may advance since the original attempt. Changed same-key intent409.
GET200 includes expired/cancelled/unavailable/paid states; unknown token404; malformed400.
Other safe statuses:403 Origin/header,409 ineligible/conflict/attempt limit,413 size,
415 media type,429 rate (Retry-After60),503 unknown/unavailable outcome. No raw errors.

Snapshot fields:

- merchantName (business name or honest “business name not recorded” fallback)
- orderReference, description (Merchant-designated public link text)
- amount (**exact two-decimal string**), currency, fixed paymentMethod, expiresAt
- checkoutStatus, canPay, simulationChoices, simulationNotice
- attemptReference/attemptStatus/paymentStatus (nullable)
- receiptReference/paidAt (nullable; present for PAID)

Receipt reference is the opaque attempt UUID, **not internal payment/user identity**;
there is no endpoint resolving receipts independently of the token. Public output has
no Merchant ID/email/mobile, account/user UUID, authorization data, internal gateway
errors, token/key digests, audit details or another link. Current REFUNDED status can be
shown with the historical paid receipt; it does not claim bank refund arrival.
Business/order/description fields must not be used to publish private customer data.

## Simulation gate — separate from OTP

Normal application behavior still uses the existing simulated gateway; no real money or
real credentials. There is **no unrestricted force-success parameter** in normal profiles.
Outcome chooser is disabled by default, choices absent and new explicit choices rejected.
`paymesh.demo.checkout-controls.enabled=true` additionally requires:

- exactly demo profile; literal verified paymesh_demo/paymesh_demo_user JDBC target
- 127.0.0.1:5432 database identity through existing metadata + actual SQL identity checks
- actual Tomcat connector bound127.0.0.1:18080; configured127.0.0.1:5500 origin/local HTTP
- forwarding strategy none; no TLS/public connector; NO_PUBLIC_PROXY_OR_TUNNEL attestation
  in `paymesh.demo.checkout-controls.operator-confirmation`.

Unsafe configuration rejects startup. Attestation is an operator trust requirement, not
technical proof that no external tunnel exists. The guarded deployment verifies actual
frontend listener binding. These choices must never be publicly exposed. OTP remains
false and no recovery key/eligibility/password is generated or modified.

SUCCESS uses normal gateway response. FAILED creates a simulated provider decline and
records it in the same existing simulated ledger. TIMEOUT calls the normal simulated
gateway (ledger SUCCESS) and reuses DemoGatewayTimeoutSimulator's observation transformation;
payment stays PROCESSING until authorized reconciliation. Mode cannot alter amount/method.

## Token / proxy / privacy

V12 retrievable256-bit tokens are preserved; hash-only storage cannot redisplay a URL.
The database/backups must protect them. No token in application/audit logs; public routes
never log request paths (`Handler.log_message` remains disabled). Existing Hibernate SQL
and bind logging are OFF; Spring Boot defaults Tomcat access logging to disabled; no access-log enablement was added. Runtime external logging remains an operator review obligation. Do not enable URL/body/
SQL bind logging or third-party telemetry for checkout; a future reverse proxy must redact
capability paths. Token URLs remain in browser history/share clipboard by design.

Proxy adds only exact GET token[/status],POST token/pay and exact static `/checkout/token`.
Fixed Java upstream, framing/body/query/path checks, response limits/timeouts, CSP and
no-store remain. It strips Authorization and does not forward cookies; Set-Cookie still
only passes reviewed auth endpoints. POST requires exact same-origin + checkout header.
No internal Python/LLM/actuator/signing/database endpoint is added.

Public controller uses bounded single-process IP/token-digest buckets:120 GET/20 POST per
actual peer IP/minute,60 GET/6 POST per token/minute; bounded4096-map capacity fails closed.
No forwarded-IP trust. Behind the local proxy peers share an IP; this is intentionally
conservative, not a distributed production rate limiter. There are no token/JWT/password
secrets in localStorage/sessionStorage, request logs or audit metadata.

## Customer page / Merchant integration

`/checkout/{token}` serves **checkout.html**, separate from the portal's index/app entry.
It imports no authentication/session restoration module and sends credentials:omit, no JWT,
no-referrer, no-store, redirect:error. It never clears or restores a Merchant refresh cookie.
No card/CVV/bank/UPI PIN/OTP is collected. Review and explicit Confirm Pay, pending/receipt/
failure/expired/unavailable states and deliberate status refresh are implemented with safe
createElement/textContent and live/aria-busy labels. Retry retains exact body/key; refresh
loses memory-only intent but reads durable status, never starts another payment. Pagehide
clears memory; bfcache pageshow reinitializes a **read**, never pay. Scoped wrapping/Bootstrap
layout supports375px, keyboard-visible focus and receipt/review focus management. Definitive HTTP rejection requires a fresh status read before another review; malformed/contradictory financial status envelopes are withheld.

Merchant link records now include `checkoutAttemptStatus` and `failedAttemptCount`.
Unresolved attempts project link status PROCESSING; paid status/association remains durable.
Merchant filters/proxy/frontend allow PROCESSING. Successful detail provides explicit
“Open authorized payment” using existing JWT-scoped lookup; refunds/AI remain explicit and
private. New actual payments naturally enter existing financial statistics and charts;
links are never counted as payments. Five-row dashboard tables and full list paging remain.

## Verification and changed files

Final actual counts are appended after final execution; no browser/live verification is claimed.

New backend: V13 migration; CheckoutTransactions/CheckoutDemoGate; CheckoutController/
CheckoutRateLimit; AcceptedPaymentExecution/CheckoutExecution/CheckoutSimulation; checkout
integration/safety tests; combined activation wrapper/Python helper/mock tests.
Modified backend: AccountAudit (honest capability audit); PaymentLinks (projection/cancel
eligibility); PaymentOrchestrationServiceImpl (shared continuation, original auth claim);
LegacyEndpointCatalog/BoundedRequestBodyFilter/CheckoutHttpPolicyFilter (exact public paths, body caps and safe framing/media errors without capability-path echo);
InternalFinancialBoundaryArchitectureTest (explicit narrow review and non-public assertion).

New frontend: checkout.html; checkout_proxy.py; checkout/client.js,model.js,view.js,page.js;
checkout-tests.html/js; test_checkout_proxy.py. Modified: dev_server.py; app.css; Merchant
link models/views/routes and merchant_proxy; Merchant view passes authorized payment callback;
prior link test notice expectations. Docs: this report, README, PROGRESS, frontend README,
API reference and Phase682 report addendum. Historical migrations/evidence/verifiers unchanged.

## Exact combined deployment procedure — PREPARED, NOT EXECUTED

After explicit separate approval, in a private Mac Terminal:

```bash
/bin/bash "$HOME/Developer/paymesh-ai/backend/scripts/activate-phase682-683-demo.sh"
```

No arguments, real TTY required. Wrapper validates existing protected configuration ownership/
modes and uses existing hidden `/dev/tty` DB password prompt. No credentials in CLI/chat.
Requires actual current process identities/loopback bindings, exact demo DB identity,
successful V1–V11 only, no checkout/link tables, OTP=false/no eligibility, baseline6/4/4/2/6/4.
Requires reviewed package V1–V13, exact V12/V13 packaged/source bytes, configured Flyway,
schema validation, immutable existing startup settings. New evidence prefix is distinct;
old Phase681 records/backups remain. Backup verified before restart: PostgreSQL16 custom
archive,600 permissions, list/extraction/checksum/disk reserve; no test restore is claimed.
Fingerprints include all eight financial tables, full account/password row fingerprints,
roles, lifecycle, registry, memberships and registrations (hashes only in private evidence).

Confirmation: `ACTIVATE_PHASE682_683_V12_V13_OTP_DISABLED`.
Controls prompt: blank keeps disabled; to deliberately enable private outcome controls type
`ENABLE_PRIVATE_CHECKOUT_CONTROLS`, then `NO_PUBLIC_PROXY_OR_TUNNEL`.
Only the verified Java and frontend processes restart. Python/LLM identities are preserved.
Normal Flyway applies V12/V13; success history, initially empty new tables, unchanged rows/
counts/fingerprints, readiness/health/frontend routes and OTP=false are verified. No link,
customer payment, refund, login, password change or investigation is issued by deployment.

The helper reuses existing protected Ops conventions (including legacy otp-step17 evidence
prefix); this does **not** enable OTP. Private gate key remains unused. Do not run old V11-only
Phase681 scripts for this artifact. Abort on mismatch; preserve evidence. No automatic SQL
repair/clean/restore/downgrade/repeated restart. If startup/migration fails, stop and review
actual Flyway/schema/private logs with the operator before any recovery. A verified archive
is a recovery prerequisite, not proof a live restore was tested or approval to restore.

## Later operator browser checklist (separate mutation approval)

1. Finish pending Phase681 verification independently; do not infer it from checkout tests.
2. Merchant A creates an explicitly approved simulated link; copy URL. No payment until Pay.
3. Open checkout in a fresh browser profile/Incognito, no sign-in. Verify safe name/fallback,
   order/description, exact INR/UPI or CARD, expiry, simulation notice, no credential fields.
4. Network review: no auth refresh/login, Cookie/JWT, third-party resources or query token echo.
5. Review then cancel review: no POST. Confirm normal success; loading blocks duplicates.
6. Receipt PAID/reference/time; revisit/status and same intent do not create another payment.
7. With private controls explicitly enabled, FAILED creates one definitive failure; new explicit
   confirmation/key creates a retained new attempt. No auto retry. Verify Merchant failed count.
8. TIMEOUT: PROCESSING/UNCERTAIN, no replacement pay/cancel. Status GET does not execute or
   reconcile. Only separately authorized existing reconciliation may resolve ledger success;
   then receipt/link become PAID. A closed/timed-out tab did not stop server execution.
9. Expired/cancelled/unavailable links prevent new Pay. Test cancellation/suspension before
   versus after acceptance only with approved disposable link scenarios; preserve accepted status.
10. Merchant detail opens successful payment through existing authorization; Merchant B cannot
    use private A records; customer cannot access financial/refund/AI/history/admin endpoints.
11. Refund/AI are separate explicitly authorized tests, never automatic checkout behavior.
12.375px/desktop/keyboard: wrapping UUID/order text, method read-only, labelled chooser only when
    gated, review/receipt focus, screen-reader status and no hidden infinite status polling.
13. Check counts/financial changes against **approved new test payments**, not old6/4 baselines.
    Do not reuse historical closeout verifiers as approvals for changed state.
14. Disable private checkout controls after testing through a separately reviewed guarded restart;
    no OTP flag/key change. Do not claim production certification from local browser checks.

## Remaining limitations / Phase6.9 handoff

No real gateways/money/checkout credentials, distributed limiter, external exactly-once guarantee,
public production deployment certification or live test restore. A pre-gateway crash can remain
unresolved and needs manual evidence review; no unsafe auto-resume was added. Fixed amount links
have no edit API. Maximum5 attempts prevents unbounded public failed-attempt creation. Public
business/order text must be deliberately safe for sharing. No shipping/tax/return URL/customer
identity collection is invented. Private controls require honest operator isolation attestation.

Phase6.9 may build an **authenticated** conversational investigation experience over existing
Java-authorized evidence. It must not inherit public link capability as authority for refunds,
AI/private records or autonomous financial mutation. No Phase6.9 implementation in this batch.

## Final automated results — 2026-11-15

**IMPLEMENTED AND AUTOMATED-VERIFIED; combined live activation/native browser verification pending.**
Phase681/682 remain OPEN; this is not production security certification.

| Executed verification | Actual final result |
| --- | --- |
| Full isolated PostgreSQL Java suite |361 tests,0 failures/errors/skips |
| New checkout integration tests |20 (included in361) |
| New gate/rate safety tests |4 (included in361) |
| New non-public continuation architecture regression |1 (included in361) |
| Complete mocked JS batch |1043 assertions across15 suites |
| Full frontend proxy suite |43 tests |
| Combined frontend checks |1086 (1043 JS +43 proxy) |
| Full mocked operational suite |119 tests (8 new) |
| Maven package -DskipTests |BUILD SUCCESS |
| JavaScript syntax |56 source files passed node --input-type=module --check |
| Modified Python / new Bash wrapper syntax |passed |
| git diff --check |passed |

JS breakdown: API10,auth34,payment94,refund125,investigation149,QA18,portal73,
registration39,session/recovery67,Admin113,Merchant97,analytics/switch46,pagination51,
payment-links70,checkout57. Mocked DOM/Node execution is **not native browser verification**.
No Python AI implementation changed; its independent suite was not rerun.

Commands actually executed: `cd backend && bash scripts/test-isolated.sh` (only fresh
verified disposable PostgreSQL cluster, stopped on completion); `mvn package -DskipTests`;
`python3 -m unittest discover -s frontend/tests -v`;
`python3 -m unittest discover -s backend/scripts -p 'test_*.py'`; syntax and whitespace checks.
All15 browser-compatible JS modules were imported in the existing mocked DOM runtime.
New mocked browser page: http://127.0.0.1:5500/assets/js/checkout-tests.html.
Existing payment-link/pagination test pages remain available after normal static serving.

Initial regression failures exposed an unreviewed internal consumer and a concrete
orchestration-class dependency incompatible with an existing interface mock. Corrected
by the explicit narrow architecture review and shared package-private executor; the old
mocked gateway-exception test remains unchanged and passes. New proxy fixture tuple/
listener-Origin and operational test case-text issues were corrected. Subsequent full
Java runs passed360; final clock-order regression brought the final fully rerun total361.
The final suite includes exact-intent replay after controls are disabled and safe public
media/framing errors. No failure was ignored or assertion broadly exempted.

Final JAR contains exact source bytes for V12/V13, CheckoutController and the shared
AcceptedPaymentExecution. Live schema was not queried or migrated. No public checkout,
financial operation, credential operation, OTP activation or service restart was performed.
The activation script is prepared only and still requires separate operator approval.

Final staging observation: cached binary diff equals the initial capture;0 changed
cached patch blocks,438 Git status entries including existing unrelated work. No staging/
commit/reset/clean/restore was performed. Prior external-staging observations remain in
historical reports; none detected relative to this batch's captured staged content.
Protected activation/backup/evidence/configuration files were not modified.
