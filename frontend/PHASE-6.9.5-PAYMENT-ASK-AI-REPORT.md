# Phase 6.9.5 — Payment-Specific Ask AI

**Implementation complete; mocked verification recorded below. Live deployment, chat activation and native browser verification pending.** No Phase696 persistence, migration, backend change, live database/inference/financial operation or service restart is included. Previous phase verification gaps and Phase673/674 historical evidence limitations remain open. Live remains operator-reported V11; V12/V13 activation is pending. Chat/OTP configuration is unchanged.

## Actual integration points

Merchant and Admin both reach the existing authorized payment-details workspace from known-payment lookup, created/processed results or their existing monitoring lists. The application does not have separate UUID-based payment-detail SPA routes. This phase therefore adds an inline panel inside `#details-workspace`, not an invented detail route:

- `#payment-ask-open`: explicit Ask AI action in the payment detail header.
- `#investigation-ask-open`: explicit same-payment Ask AI action beside the existing investigation button.
- `#payment-ask-panel` / `#payment-ask-chat`: inline shared conversation layout with fixed read-only payment context.
- `#payment-ask-feedback`: safe status announcements outside a cleared/hidden panel.
- `#payment-ask-close`: clears/invalidate chat only and returns focus to the entry action (or detail heading while it is unavailable).

Opening details, displaying an investigation or opening Ask AI never sends a chat request. The panel only prepares context. Existing investigate/payment/refund APIs and workflows remain separate. No investigation answer, rendered report or DOM content is used as chat evidence/history.

Reviewed actual Phase692/693/694 reports, Java payment chat DTO/controller/authorization path, shared presentation/schema/history, details/refund lifecycle, investigation model, operation guards, router, central client and test fixtures. The existing Java contract supplies all needed functionality; no backend extension is required.

## Shared components and fixed context

`payment-ai/model.js` provides a payment-bound lifecycle adapter. `payment-ai/view.js` mounts the existing `chat/presentation.js` shell and `chat/render.js` output, using the same validators, completed-history builder, error feedback, exact-decimal validation and copy/evidence components as Merchant/Admin AI. Standalone Merchant/Admin conversations are never imported into this panel.

The read-only context displays the currently authorized UUID, Merchant, exact amount/currency, method, recorded status and authenticated portal role. It has no payment/ownership selector. Payment identity comes only from the validated detail state's selected UUID and matching authorized payment response. Amount must remain an exact decimal string; numeric/invalid/mismatched details cannot prepare chat. Customer identifiers/contact information are not retained in the chat context or posted as evidence.

Only ACTIVE presentation state proceeds: exact MERCHANT or authorized ADMIN role semantics match the existing application. The UI relies on the already authorized detail read for preparation, not a claim of independently verified membership. Java reauthorizes account/session, role, ownership and current Merchant lifecycle before and after every inference; opening a cached UI is not authorization.

Suggested questions use actual finite intent support: recorded status, processing when PROCESSING, failure when FAILED, gateway observations, successful refund history and this payment's recorded refundable amount. Buttons require a deliberate click; nothing sends on open/render/result arrival. Payment-only chat does **not** supply link/checkout association in the actual Phase692 projection, so no fabricated checkout suggestion or link selector is offered. Unknown failure/refund cause, timeout history or bank arrival stays unknown.

## Exact API integration

```text
POST /api/v1/payments/{authorizedPaymentId}/ai/chat
Authorization: Bearer <current access token>
Content-Type: application/json
```

Body example:

```json
{"question":"How much was refunded?","history":[{"role":"user","content":"What is this payment's recorded status?"},{"role":"assistant","content":"A prior approved explanation."}]}
```

The path fixes the payment. There is **no body context, paymentId, Merchant ID, caller role, evidence, SQL, internal Python field or Idempotency-Key**. The central client adds only this exact POST path, uses the existing same-origin proxy, no-store/redirect refusal, bearer auth and credentials omitted. No direct Python/llama.cpp access is introduced. Java's strict payment-path contract rejects redundant payment/link selectors and constructs fresh server-authorized evidence itself.

Question: nonblank1–1,000 Unicode code points, valid Unicode/no NUL/control characters, shared accidental secret/contact/raw-ID checks. History: completed pairs only, at most8 messages/6,000 total code points,1,000 per message. Failed/cancelled/stale turns are excluded; oversized/privacy-incompatible pairs stop older history inclusion rather than truncating financial facts. Maximum20 turns in memory, with retry permitted for a failed final turn. Both the payload helper and central client enforce32,768 serialized UTF-8 bytes.

Browser timeout45 seconds; existing proxy40 seconds, Java default25 seconds and Python inference cap15 seconds. These are configured budgets, not measured inference timing. Timeout, Close, cancellation, context replacement and abort do not establish that server-side analysis stopped. No automatic retry or authentication-based request replay is added.

The full Phase692 public response is validated against the fixed selected UUID and code-selected MERCHANT_OWNED/ADMIN_AUTHORIZED provenance. Output uses the shared safe renderer: answer, actual intent/mode/generation status, expandable evidence, known-reference metadata, exact string money facts, limitations and explicit follow-ups. INR/USD remain separate; no JavaScript floating-point financial calculation or authoritative status assignment is performed. Sources are text, not arbitrary links. Copy Answer is explicit clipboard text with safe manual fallback.

RAG_LLM/SUCCEEDED is labeled successful local LLM assistance; deterministic and RAG-assisted fallbacks explicitly state no successful LLM generation. Insufficient evidence is a successful explanatory state. Disabled/unavailable share the existing AI_UNAVAILABLE code and are labeled honestly. Invalid/mismatched responses show no partial answer or raw backend exception.

A validated payment evidence reference can focus the already-open payment detail heading. It cannot select another resource, construct an external URL, process/refund or automatically investigate a payment.

## Context, session and view isolation

Each request captures current session version, role, canonical authorized payment UUID and conversation generation. The coordinator additionally tracks whether the payment-detail view is present. Real route/subpanel leave clears/invalidate chat without clearing the parent financial state. Hidden detail updates cannot rearm a departed chat; explicit re-entry permits observation of the real selected detail again.

Opening payment B closes/clears payment A's conversation immediately. Late A success/error cannot appear against B or reopen the panel. Account/role replacement, logout, expiry, session revocation and existing cross-tab lifecycle notifications abort/invalidate and clear all private chat state. Admin history cannot enter a Merchant session. Neither standalone chat's state is reused.

New Chat clears turns/failed question and invalidates pending replies while retaining the fixed current authorized payment. Close clears the panel's turns/payment display/draft and invalidates pending work. Cancel pending analysis retains a failed question for deliberate retry. All are memory-only; no localStorage, sessionStorage, IndexedDB, database persistence or conversation cache is introduced.

The detail read model now exposes UI-only `accessDenied` and a monotonic `authorizationRead` marker. These are not JWT/account versions or database authorization. They identify successful validated payment reads and read-denial state. A403/404 chat response latches that binding as unavailable until a newer authorized detail read (or a genuinely replaced context/session), preventing ordinary rerenders from reusing a denied cached payment.401 continues to use the central session-clearing/version guard. A denied parent payment/gateway read disables preparation and clears chat. No financial intent or money/status arithmetic is changed by these metadata fields.

Same-payment refresh pauses sending and invalidates pending replies when appropriate. If recorded data changes, earlier completed answers remain explicitly dated historical snapshots and the read-only context updates. Every subsequent deliberate question requests fresh Java evidence; neither old assistant text nor investigation results override it. This is not live continuous state synchronization.

## Financial and investigation safeguards

The existing payment processing/creation, refund and uncertainty locks are preserved. Opening Ask AI is denied during financial review/pending/uncertain intent, unavailable details, another chat or investigation. A pending chat participates in the existing `readBusy` financial-mutation guard. Closing, cancelling or leaving chat releases only its own read busy flag; it never calls parent clear, cancels a financial review, replaces an idempotency key or releases unresolved financial intent.

The original `POST /payments/{id}/investigate` contract and structured report remain unchanged. Investigation gains an optional external busy guard (default false) so chat prevents concurrent investigation **without changing its evidence fingerprint or deleting a displayed report**. Conversely investigation busy blocks chat. Parent authorization loss correctly invalidates private investigation/chat data. No conversation starts automatically after investigation.

The panel posts only chat. It cannot approve/reject/suspend/reactivate Merchants, change passwords, create/process/refund payments or trigger automatic financial retries. AI output never becomes authoritative payment/refund state. Tests verify both unchanged review intent and a preserved investigation report across the guard.

## UX and accessibility

Welcome/empty, real loading/elapsed, successful/insufficient/fallback, disabled/unavailable/capacity, timeout/network/invalid response and authentication/inaccessible-payment states are supported with fixed safe messages. Failed questions remain retryable where authorization/context is still safe. Duplicate sends are blocked.

Reuses Bootstrap, wrapping styles, native buttons/details, composer Enter/Shift+Enter/IME behavior, busy/disabled controls, status announcements and elapsed timer without fabricated progress. Header/investigation entry points focus the chat heading; Close returns focus safely. Fixed UUIDs/long citations wrap and transcript height is bounded for375px layouts. Responsive/accessibility review is static/mocked, not native screen-reader/contrast/layout certification.

## Files created

- `frontend/assets/js/payment-ai/model.js`
- `frontend/assets/js/payment-ai/view.js`
- `frontend/assets/js/payment-ai-tests.js`
- `frontend/assets/js/payment-ai-tests.html`
- `frontend/tests/test_payment_ai_ui.py`
- This report.

## Files modified

- `frontend/index.html`: detail/investigation entry actions and inline panel.
- `frontend/assets/js/app.js`: detail observation, shared locks, view enter/leave coordination.
- `frontend/assets/js/portals/view.js`: explicit payment-context enter/leave hooks; no new routes.
- `frontend/assets/js/api/config.js`, `api/client.js`: exact payment chat path, existing45-second chat budget, safe errors/abort/UTF-8 bounds.
- `frontend/assets/js/features/refunds.js`: read-only authorization-result metadata; existing financial intent/amount logic retained.
- `frontend/assets/js/investigation/model.js`, `investigation/view.js`: optional busy guard preserving reports and authority-loss handling; endpoint unchanged.
- `frontend/assets/js/chat/presentation.js`: configurable fixed-context welcome text, preserving default standalone behavior.
- Root README/PROGRESS and frontend README: implementation status, verification and handoff.

No Java/Python AI-service source, historical migration, dependency, protected configuration, activation script, backup or historical evidence was changed. Existing upstream proxy route/method/security allowlists were already sufficient and remain unchanged.

## Automated verification

Final results follow below. All18 JavaScript suites run with mocked API responses and the existing limited offline DOM helper; it automatically provisions fixture IDs and is not a native browser emulator. New fixtures reuse actual Phase692 oracle/public-DTO samples from Phase693/694. Proxy/security tests use temporary mocked loopback HTTP listeners, not live business services.

Java388, Python AI-service237 and operational119 remain prior baseline results, **not newly rerun**. Backend/service contracts are unchanged; no backend test run, packaging or database connection was needed. Native browser and actual local LLM verification remain pending.

## Pending native browser checklist

After separately approved combined deployment/activation:

1. As Merchant and Admin, explicitly open an existing authorized payment through the current lookup/monitoring/detail flows. Verify no automatic chat or investigation request.
2. Open Ask AI from the detail header and from an existing investigation section. Verify the exact UUID/amount/currency/method/status and no editable scope selector; opening performs no AI request.
3. Send status/refund/gateway questions explicitly; inspect path/body, exact facts, actual generation/fallback, evidence and limitations. Prior investigation output must not appear in posted history/evidence.
4. Test Enter/Shift+Enter/IME, duplicate prevention, loading/elapsed, explicit retry, Cancel, New Chat and Close. The cancelled server work may finish; no late result may reopen or replace the current panel.
5. Replace payment A with B, navigate away/back and switch Merchant/Admin accounts using existing safe account controls. Check logout/cross-tab/expiry clearing and stale-response rejection. No A answer may appear within B.
6. Verify financial/investigation lock behavior with mocked suites; do not create/refund/process/approve/reset records or stop services to induce errors. Closing Ask AI must never release unresolved financial intent. Existing investigation remains a distinct explicit operation/report.
7. Refresh authoritative details and observe changed-status/history labeling. Old answers must stay dated; the next request collects fresh evidence, without changing financial state from AI output.
8. Verify keyboard/focus, safe clipboard/manual fallback, expandable evidence, long UUID/source wrapping and375px layout. Confirm no model-provided external URLs or HTML execution.
9. Run **http://127.0.0.1:5500/assets/js/payment-ai-tests.html**, plus Merchant/Admin AI mocked pages. These use synthetic APIs only.

This phase adds no new handler routes or proxy configuration. The implemented static server reads HTML/JS/CSS from disk with no-store, so these asset changes need a later release/browser hard refresh rather than a new Phase695-specific server configuration. Previously pending Phase693/694 direct-route/frontend handler reload and chat activation requirements remain pending; no restart or activation was performed here.

## Limitations and Phase696 handoff

Live remains V11, chat disabled and V12/V13 pending. Phase681 dashboard/native/password/final audit, Phase682/683 activation/checkout browser, Phase691 live LLM, Phase692 live integration and Phase693/694 native browser/handler reload gaps remain open. Phase673/674 documented historical evidence limitations are untouched. No earlier phase is closed and no production security certification is claimed.

The payment-only endpoint has no supplied checkout/link association; richer context needs a separately reviewed backend contract, not fabricated frontend fields. History can omit long answers, so users may need to restate questions. Timed-out/cancelled inference may continue. The model selects approved wording and cannot execute financial tools.

Phase696 may design authenticated conversation ownership/lifecycle/persistence separately. It must not persist raw transient UI state, trust previous assistant statements as financial evidence, weaken current per-request authorization or replay mutations. **No Phase696 implementation was started.**

## Final executed verification — 2026-11-16

- **1,406 mocked JavaScript assertions passed**, all18 suites: API10; auth34; payments94; refunds125; investigation149; QA18; portals73; registration39; sessions/recovery67; Admin management116; Merchant100; analytics/account-switch46; pagination51; Payment Links70; checkout57; Merchant AI108; Admin AI143; **payment Ask AI106**.
- **52 frontend Python proxy/security tests passed**, including2 new payment Ask AI cases. Actual command: `python3 -m unittest discover -s frontend/tests -p 'test_*.py'`. Temporary mocked loopback listeners only, zero failures/errors.
- **Total frontend:1,458 checks**, compared with the prior1,350 baseline. All financial/chat fetches were synthetic. The real frontend refund review/investigation models were exercised against mocked reads/responses; no live business request was made.
- All71 JS/ES-module files (including the existing offline DOM helper) passed Node VM syntax checks. `python3 -m compileall -q frontend` and `git diff --check` passed.
- Java388, Python AI-service237 and operational119 remain previous baselines, **not newly executed**. No backend/AI-service source changes or isolated database run were required.

The JavaScript tests used the existing limited mocked DOM runtime, not a native browser. Its fixture-ID provisioning cannot certify a full browser application's DOM/layout; new static checks verify each actual HTML entrypoint occurs exactly once. Native browser, screen-reader, live cookie/model and combined activation verification remain pending. No false browser-success claim is made.

Initial staged-content SHA256: `b9320a130799516919c7749888e03c8994812a832852d2f9ac2403d52834a472`; final observed SHA256: `ef14972e5a867386e4dff8fcae542641fc98f8c791f90176a5168ab141f72727`. Five new externally staged patch blocks were observed. **Zero initial staged blocks changed or disappeared**;496 status entries were observed. No Git staging/index mutation command was issued. External staging was left untouched; byte-identical whole-index preservation is not asserted because of those additions.

Protected credentials/configuration, backups/evidence, original database/application and running services were untouched. No deployment, service restart, live database access, chat/OTP activation, password change, account creation, financial mutation or paid dependency occurred.

**Handoff: Phase695 implementation and mocked verification complete. Live activation/native verification remains pending, previous verification gaps remain open, and Phase696 has not started.**
