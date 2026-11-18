# PayMesh AI — simulated payment backend

PayMesh AI is a Java portfolio backend for payment orchestration, financial
state handling, and application security. All gateways are simulated: it does
not contact Razorpay, Stripe, or move money.

## Project status

**Phase 6.9.7A — AI integration readiness prepared; no live activation or verification.**
A new guarded V11→V14 schema procedure preserves financial/account contents and keeps
chat/OTP disabled. Separate interactive configuration-staging and AI probes are prepared;
actual Java/Python launch settings require private operator review before approved restarts.
See the [Phase697A report](frontend/PHASE-6.9.7A-AI-INTEGRATION-READINESS-REPORT.md)
for the integration matrix, exact confirmations, future commands and remaining blockers.
Newly executed:143 mocked operational tests. Java412/Python237/frontend1558 remain prior
baselines, not rerun. All previous native/browser/model/evidence gaps remain open.
Phase697B and Phase6.10 have not started.


**Phase 6.9.6 — Persistent conversation management implemented; activation/native verification pending.**
Java/PostgreSQL owner- and portal-scoped conversations now support saved history,
server-owned inference context, bounded storage, explicit reconciliation and atomic deletion.
Merchant/Admin AI and fixed-payment Ask AI share the history drawer.
See [Phase696 report](frontend/PHASE-6.9.6-CONVERSATION-MANAGEMENT-REPORT.md).
Live remains V11; V12–V14 and protected chat activation are pending. Previous
Phase681–695 verification gaps and Phase673/674 evidence limitations remain open.


**Phase 6.9.4 — Admin AI Assistant UI implemented; live activation/native verification pending.**
`/admin/ai` supports explicit platform/Merchant/payment context, bounded searches, UTC/currency
aggregate filters and role-isolated memory-only conversations. Shared chat rendering preserves
Merchant behavior, exact money/evidence and honest fallback labels. No payment-detail Ask AI,
conversation persistence or backend/schema change. Chat remains disabled and live remains V11.
See [Phase694 report](frontend/PHASE-6.9.4-ADMIN-AI-CHAT-REPORT.md) for actual verification,
contracts, inventory and pending browser checklist. Prior phase summaries are historical;
all pending live verification and evidence limitations remain open.


**Phase 6.9.3 — Merchant AI Assistant UI implemented; live activation/native verification pending.**
`/merchant/ai` provides explicit questions, bounded memory-only conversation, authorized
payment selection, exact money/evidence rendering, honest fallback labels and session/stale
response guards. No Admin chat UI, payment-detail Ask AI, persistence or live activation.
See [Phase693 report](frontend/PHASE-6.9.3-MERCHANT-AI-CHAT-REPORT.md) for actual test results,
contracts, file inventory and pending browser checklist. Backend/AI services and live V11
remain unchanged; all prior live verification gaps and evidence limitations remain open.


**Phase 6.9.2 — Secure Java AI Chat APIs implemented; live activation pending.**
Authenticated Merchant/Admin/payment chat constructs minimized aliased snapshots, checks
current authorization before/after inference, validates exact approved answers/money/citations,
and uses private chat-only service authentication. Phase692 delivered APIs only; Phase693 adds Merchant UI without conversation storage.
See [Phase692 report](frontend/PHASE-6.9.2-SECURE-AI-CHAT-API-REPORT.md) for contracts,
actual automated results, configuration and Phase693 handoff. No live database/service/LLM
operation occurred. Live remains V11; V12/V13 and prior live verification remain pending.
The Phase691 summary below describes its earlier Python-only delivery.


**Phase6.9.1 — Python conversational engine implemented and automated-verified.**
229 Python tests passed (102 existing investigation/RAG +127 new chat tests).
Internal token-free minimized evidence analysis, exact money, bounded follow-ups/RAG and
local approved wording selection; no Java/frontend chat integration or financial tools.
No live inference/activation/restart/database access performed. Phase681/682/683 verification
remains pending. Phase692 now supplies the Java boundary described above; earlier summaries are historical.
See the [conversational AI report](ai-service/PHASE-6.9.1-CONVERSATIONAL-AI-REPORT.md).


**Phase 6.8.3 — Customer checkout implemented; V12/V13 combined activation and live verification pending.**
Public token-scoped checkout uses durable accepted attempts, server-derived payment values,
safe receipts and definitive-failure retries. Existing Merchant/Admin authorization is preserved.
Private simulation controls are disabled by default; OTP remains disabled. No live schema change,
financial operation or service restart was performed. Phase681 and Phase682 remain OPEN.
See the [Phase683 report](frontend/PHASE-6.8.3-CUSTOMER-CHECKOUT-REPORT.md) for exact APIs,
crash/reconciliation limits, actual tests and the guarded combined activation procedure.


**Phase 6.8.2 — Payment Link management implemented; V12/live activation and native browser verification pending.**
Merchant-owned create/list/detail/cancel, validated simulated gateway selection, exact
amounts and idempotent recovery are documented in the [Phase682 report](frontend/PHASE-6.8.2-PAYMENT-LINKS-REPORT.md).
No public checkout or link-based payment execution (Phase683). The deployed live schema
remains V1–V11 until separate approval. Phase681 analytics deployment is operator-confirmed;
its browser/password-change/final audit checks remain pending. The earlier status entries
below are implementation history, not a Phase681 closeout.

**Phase 6.8.1 — base deployment operator-confirmed; browser verification in progress.
Analytics/account-switching enhancement implemented and tested; redeployment pending approval.**

Merchant dashboard, owned payment/refund monitoring, read-only business profile and
ACTIVE verified Merchant password change reuse existing V11/security/workflow logic.
No new migration. Latest enhancement results:322 isolated Java tests (zero failures/errors/skips),
895 frontend checks (859 mocked JS assertions +36 proxy tests),111 mocked operational
tests. Local Chart.js4.4.8/MIT charts use authorized UTC analytics; explicit account
switching preserves shared-cookie/cross-tab session behavior. Packaging/syntax passed. No live DB access, deployment, password/financial mutation
or service restart was performed. See the [Phase 6.8.1 report](frontend/PHASE-6.8.1-MERCHANT-DASHBOARD-PROFILE-REPORT.md)
for exact contracts, restrictions, deployment command and manual browser checklist.
No Payment Links, checkout or conversational AI implementation begins here.

### Prior verified Phase 6.7.4 closeout

**PHASE 6.7.4 — COMPLETE WITH DOCUMENTED EVIDENCE LIMITATIONS.**
**GO for continued private local portfolio development. Not production security certification.**

V11 controlled activation, Admin dashboard and Merchant management are complete.
Previously executed results: **300 isolated Java tests** (zero failures/errors/skips),
**752 frontend automated checks**, **105 mocked operational tests**; packaging and
syntax checks passed. No tests were rerun for this documentation closeout.

Final operator-run read-only evidence confirms counts users/merchants/memberships/
registrations/payments/refunds **6/4/4/2/6/4**, exact row matches across all eight financial
tables against the pre-V11 archive, and retained-session-row verification for Merchant
offline recovery, approval, suspension, reactivation and Admin password change. The
Merchant's Phase674 version2→6 has all four increments explained. The actual Admin
password test was the explicitly authorized **demo-admin** self change, version3→4;
**otp-admin-demo remains unchanged**. OTP is disabled; runtime health and persistent-session
configuration passed. See the [official Phase 6.7.4 closeout](frontend/PHASE-6.7.4-ADMIN-DASHBOARD-MERCHANT-MANAGEMENT-REPORT.md).

The operator initially reported36 browser checklist items passed; no revised exact
browser-pass count is claimed. Successful live rejection remains unverified: no rejection
registration or successful MERCHANT_REJECT event exists. No direct live JWT acceptance/
replay test or backup test restore occurred; legacy no-sid tokens are not inventoried.
[Phase 6.7.3 historical evidence limitations](frontend/PHASE-6.7.3-SESSIONS-PASSWORD-RECOVERY-REPORT.md)
remain unchanged, including its earlier unexplained Merchant increment and missing
historical/fingerprint evidence. The new Phase674 evidence does not reconstruct them.
On-screen OTP must never be enabled publicly; production-grade public recovery remains
unimplemented.

Phase6.8.1 implementation is recorded above; live activation/browser verification
remain pending separate approval.
Docker remains separate future work.

Historical Phase 6.6 QA: 424 baseline frontend/proxy checks and 18 new QA regressions
passed; four live investigations were operator-reported. Its earlier pending/manual
notes remain historical; no investigations or tests were repeated for this closeout.
See the [Phase 6.6 QA report](frontend/PHASE-6.6-FINAL-QA-REPORT.md).

Historical Phase 5.4 backend verification:
Java automated tests: **226 passed**; Python: **102 previously passed**.
The combined reported total is **328**, not a fresh combined run.

Live Java-to-Python investigations passed for webhook recovery, full refund and
reconciliation recovery, all with RAG_LLM/SUCCEEDED and authorized database snapshot
provenance. Refund history and cross-merchant/unauthenticated rejection checks passed.
Java readiness was UP (18080), Python UP (8000, RAG_LLM), and llama.cpp OK (8082).
Mean observed investigation latency was approximately 10.81 seconds across three
requests, not a load-test benchmark. No financial records changed during verification.
See the [Phase 5.4 report](backend/PHASE-5.4-JAVA-PYTHON-INTEGRATION-REPORT.md)
for results, resolved issues and limitations. Docker runtime, remote CI and production
deployment remain future verification tasks. This project is not production certified.

## Architecture

```text
Merchant / administrator
        |
        | RS256 JWT (business APIs)
        v
Spring Boot 3.5.7 / Java 21
  |       |                |
  |       | HMAC-SHA256    +-- Separate settlement bearer authentication
  |       +-- Mock Razorpay / Mock Stripe routing
  +-- PostgreSQL + Flyway V1–V8
          |-- Payments, idempotency, gateway attempts, refunds
          +-- Webhook inbox and reconciliation audit
```

The backend has payment and refund orchestration, currency routing, database
idempotency and concurrency protection, account/merchant authorization,
merchant-scoped data access, request-body limits, signed webhook processing,
reconciliation against a simulated gateway ledger, and a guarded demo-only
timeout scenario. It includes offline account provisioners and explicit
health/readiness endpoints. No public account-registration API exists.

## Technology

- Java 21, Spring Boot 3.5.7, Spring Security, OAuth2 Resource Server
- PostgreSQL 16 for the new Compose examples; Flyway migrations V1–V8
- Maven and isolated PostgreSQL integration testing
- Docker Compose for separate local demo database and normal-mode local
  container examples

## Local development and verification

See [`backend/README-DEPLOY.md`](backend/README-DEPLOY.md) for requirements,
configuration, health behavior, test and CI commands. Run the complete test
suite only through the isolated runner:

```bash
cd backend
bash scripts/test-isolated.sh
```

The runner creates its own marked temporary PostgreSQL cluster and stops it at
exit. Do not run bare Maven tests against an application database.

## API and demo

- [`backend/API-REFERENCE.md`](backend/API-REFERENCE.md) is the canonical
  source-backed API contract.
- [`backend/README-DEMO.md`](backend/README-DEMO.md) explains the guarded local
  demonstration. Its PostgreSQL-only Compose project is fresh and isolated; it
  does not reuse or copy existing databases. Review the runbook before issuing
  any state-changing request.
- [`backend/README-BUSINESS-SECURITY.md`](backend/README-BUSINESS-SECURITY.md)
  documents roles and merchant ownership boundaries.

JWT access tokens use RS256 and expire after 15 minutes. Webhooks authenticate
with provider-specific HMAC-SHA256 secrets, independently of JWT. Settlement
administration uses a separate bearer token. SQL statement and bind logging are
off by default. Never commit actual environment secrets or private keys.

## Deployment limits

The Compose files are for isolated local development only. The normal
containerized database starts with no provisioned ADMIN or merchant account;
there is no non-demo account bootstrap path. The offline provisioners are
guarded to loopback `paymesh_demo`, so the full-stack Compose topology is not a
complete authenticated workflow. Do not use this project as a public service.

Deferred work includes separate production migration/runtime database
identities, distributed login rate limiting, managed secret rotation, TLS and
production ingress, database-enforced aggregate refund constraints beyond
application locking, real payment-provider integrations, and non-demo ADMIN
provisioning.

## AI investigation service

The Python FastAPI investigation service now integrates with Java-authorized,
read-only payment evidence and local RAG/LLM generation. Financial decisions remain
deterministic; the model performs constrained wording selection. Python remains a
loopback demo trust boundary without independent network authentication. Bank debit,
settlement and refund arrival are not verified. Outage and malformed upstream responses
were covered by automated tests rather than deliberate live service shutdown.

## Historical implementation update — Phase 6.7.3

Phase 6.7.3 is implemented and locally verified with documented evidence limitations.
V10/session settings and the authenticated additional Admin API were activated through
guarded operator procedures; both disposable accounts completed one reset each. OTP is
now disabled and must remain disabled in any public deployment. Current-state/archive
verification succeeded, but missing historical session/fingerprint evidence and the
unexplained additional Merchant authorization increment prevent unrestricted audit
certification. See the [Phase 6.7.3 report](frontend/PHASE-6.7.3-SESSIONS-PASSWORD-RECOVERY-REPORT.md).
Phase 6.7.4 is now officially complete with documented evidence limitations; see
the current project status and final report above. Phase6.8.1 implementation is now recorded above; activation is pending.
No Docker implementation is part of this closeout.

Phase682 final automated results:336 isolated Java tests;1022 frontend checks
(983 mocked JavaScript assertions +39 proxy tests);111 operational mocked tests.
Packaging, syntax and diff checks passed. Native browser/live V12 activation pending.
See the Phase682 report for complete contracts, limitations and operator checklist.

Phase683 final automated verification: **361 isolated Java tests** (zero failures/errors/
skips), **1086 frontend checks** (1043 mocked JS +43 proxy), **119 operational mocked tests**.
Maven packaging, syntax and git diff --check passed. Native browser verification and
combined V12/V13 activation are pending separate approval; live remains operator-supplied
V11. Phase681/682 are not closed. No live DB access/mutation/restart/OTP activation performed.

Phase692 automated verification: **388 isolated Java tests**, **237 Python tests**,
**1,089 frontend checks** (1,043 mocked JS assertions +46 proxy tests), and
**119 operational mocked tests** passed. No native browser/live LLM verification is claimed.
Detailed execution, packaging and preservation evidence is in the Phase692 report.

Phase693 actual automated result: **1,202 frontend checks passed** (1,154 mocked JS
assertions across16 suites +48 proxy/static-security tests). Module/Python syntax and
`git diff --check` passed. Browser unavailable; no native browser/live AI verification.
Java388/Python237/operational119 are unchanged baseline evidence, not rerun in this phase.

Phase694 actual automated verification: **1,350 frontend checks passed** (1,300 mocked JS
assertions across17 suites +50 proxy/security tests), including all108 Merchant AI and143
new Admin AI assertions. Module/Python syntax and `git diff --check` passed. Native browser
and live chat activation remain pending. Java388/Python237/operational119 are prior baselines,
not rerun in this frontend-only phase. Full evidence: Phase694 Admin AI Chat report.

Phase695 actual automated verification: **1,458 frontend checks passed** (1,406 mocked JS
assertions across18 suites +52 proxy/security tests), including106 payment Ask AI,108
Merchant AI and143 Admin AI assertions. Syntax and `git diff --check` passed. Java388,
Python237 and operational119 remain prior baselines, not rerun. Native browser/live chat
activation and earlier verification gaps remain pending; see the Phase695 report.

Phase696 final verification: **412 isolated Java tests** (zero failures/errors/skips),
**1,558 frontend checks** (1,503 mocked JS assertions +55 proxy/security tests), Maven
packaging, relevant syntax and `git diff --check` passed. Python237 and operational119
remain prior baselines, not rerun; their source/operational scripts are unchanged.
No native browser/live verification is claimed. See the Phase696 report for limits and
the future separately approved V11→V14 migration plan.

## Container and publication preparation

The isolated five-service amd64 setup and manual remote-build workflow are documented
in [deploy/README.md](deploy/README.md). Container builds/runtime E2E and registry
publication remain pending; no existing local services or PostgreSQL data are used.
GitHub/Docker Hub destinations and publication approval are still required.
