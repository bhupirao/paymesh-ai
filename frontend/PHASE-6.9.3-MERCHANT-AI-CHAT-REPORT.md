# Phase 6.9.3 — Merchant AI Chat UI

**Implementation complete; mocked verification recorded below. Live activation and native browser verification pending.** No Phase694 Admin UI, payment-detail Ask AI entry, persistence, migration, backend contract change or live operation is included.

## Route and architecture

`/merchant/ai` is an explicit same-document Merchant portal route, labeled **AI Assistant**. It uses the existing navy/white layout, local Bootstrap and ES modules. Direct refresh is explicitly served by the existing narrow static router after the separately approved frontend handler reload. It does not introduce arbitrary SPA paths, upstreams or CORS. Same-document navigation preserves the existing memory-only access token and persistent-session lifecycle.

`merchant-ai/schema.js` validates question/history and the public Java response. `model.js` owns per-instance, memory-only eligibility, selected context, generation, history, pending AbortController and bounded payment choices. `view.js` renders safe DOM elements, conversation bubbles, controls, evidence and exact money. The Merchant workspace mounts it lazily; the Admin chatbot remains the existing placeholder.

Opening the page makes only an explicit authorized-profile read to establish current workspace eligibility; it **never automatically calls AI**. Only exact MERCHANT + ACTIVE presentation state proceeds to the existing `/merchant/profile` read. The profile must corroborate ACTIVE business/account, active membership and verified active registry. Java remains authoritative and reauthorizes every chat request. Pending, rejected, suspended, wrong-role and unverifiable profiles cannot use the composer. Client presentation checks do not substitute for Java ownership checks.

## Exact API integration

Only `POST /api/v1/merchant/ai/chat` is added to the central browser API catalog for this phase. The existing same-origin proxy already allows this endpoint. The browser sends its existing bearer access token, `credentials: omit`, JSON, no-store and redirect refusal. It never sends the refresh cookie, internal service key, caller role, Merchant identity, evidence, SQL or Python fields. No financial mutation/retry or automatic authentication replay is introduced.

Overview example:

```json
{"question":"Summarize payment statistics","history":[],"context":{"statistics":{}}}
```

Java uses the actual current Merchant's default last-30-UTC-day statistics, with INR/USD separated. A selected-payment example is:

```json
{"question":"How much was refunded?","history":[{"role":"user","content":"What is the current payment status?"},{"role":"assistant","content":"A prior approved explanation."}],"context":{"paymentId":"00000000-0000-4000-8000-000000000001"}}
```

That UUID is illustrative, not a live selection. Selected payment context supplies payment/gateway/refund evidence; overview aggregates are a separate conversation context. A payment is selected only from a bounded authorized `GET /api/v1/merchant/payments?page=0&size=5&sort=newest[&search=...]` response. Search uses the existing exact Payment UUID/customer ID contract. Previous/Next fetch separate pages; no full Merchant dataset is accumulated. Java reauthorizes the UUID on every question. No checkout token or link selector is added to this UI.

Question validation mirrors the actual Java constraints: nonblank, 1–1,000 Unicode code points, no NUL/malformed Unicode/control characters; common raw credential/contact/identifier patterns are rejected. This is not a universal secret detector: the notice tells users not to enter sensitive information. The exact serialized public request is checked with TextEncoder against32,768 UTF-8 bytes before fetch. Java separately enforces the complete internal evidence request's32KiB limit.

History includes only completed user/assistant pairs, newest contiguous eligible turns, no more than8 messages or6,000 code points total, with1,000 code points maximum per message. Failed/sending/stale/cancelled replies are excluded. **Long answers are never truncated into financial history**: an over-limit or privacy-incompatible pair stops inclusion of older history. The full answer stays visible; the user may need to restate the follow-up. At most20 turns are kept in the current conversation. New questions then require New Chat; the failed last turn can still be explicitly retried without adding another turn.

The central client applies a dedicated45-second timeout (Java default25 seconds, proxy40 seconds, Python inference cap15 seconds). These are configured budgets, not measured inference duration. There are no automatic retries. New Chat aborts the browser request and invalidates its generation; server/model work can still finish.

## Conversation and UX

Initial welcome, suggested questions, composer, Enter-to-send/Shift+Enter newline (IME composition excluded), accessible Send, New Chat, elapsed timer, failed-question retry and explicit context selection are implemented. Questions/answers use separate bubbles. The page provides real sending feedback, never fabricated typing/model stages or percentages. A successful INSUFFICIENT_EVIDENCE answer is an explanatory result, not a transport failure.

Changing payment/overview context after turns exist requires confirmation and clears the previous conversation. New Chat also confirms when turns/pending work exist; cancelling confirmation preserves the current conversation. New Chat clears turns, selected payment, failed question, search page and draft. All new AI calls require a deliberate button/key action. Suggested follow-up buttons are labeled “Ask: …”; a click explicitly submits that question, subject to the same locks and bounds.

The failed question stays visible and memory-only for **Retry failed question explicitly**. Fixed messages distinguish input/evidence failures, disabled-or-unavailable service, capacity, timeout, network and invalid responses. Phase692 intentionally uses AI_UNAVAILABLE for both disabled and unavailable; the UI says exactly that instead of inventing a capability probe or successful answer. It does not use the unrelated OTP capability to infer chat availability.

The composer and selection controls are disabled during sending. New Chat remains available for safe invalidation. Shared busy state participates in Merchant navigation/account-switch guards and existing payment/refund/investigation locks. Existing unresolved financial intents block chat sends. Logout can still clear/abort the private chat through the existing session mechanism.

## Structured response rendering

The public Phase692 DTO is validated before displaying any assistant result: exact root fields, correlation UUID, Merchant Java provenance and aware timestamp, recognized intent, valid mode/status combination, bounded arrays/strings, selected-payment association, allowed evidence types, knowledge shape/scores, canonical24-integer-digit/two-decimal money strings and integer counts. Malformed/mismatched responses show no partial assistant answer. Java remains responsible for independent finite-answer, citation and monetary correctness validation; the frontend does not claim to repeat its financial reasoning.

Rendered fields: answer, intent, analysisMode, generationStatus, evidenceProvenance, evidenceReferences, knowledgeReferences, moneyFacts, limitations and suggestedFollowUps. Evidence appears under native expandable details/summary. Human-readable evidence labels replace aliases. Source strings/document/chunk identifiers remain safe text, not arbitrary external links. Relevance is labeled retrieval relevance, never correctness probability or root-cause certainty.

Exact money facts remain decimal strings and separate INR/USD labels. No floating-point financial arithmetic, balance/revenue/settlement inference or bank-arrival claim is added. Copy Answer uses the user-initiated clipboard API, with safe manual-copy feedback when unavailable.

There is no UUID payment-detail SPA route in the existing application. An authorized PAYMENT reference therefore offers an explicit **Open authorized payment** button using the existing validated lookup callback/workspace. It never constructs a model-provided URL, automatically loads a detail page, performs a financial mutation or adds an Ask AI button to payment details.

Labels are honest: RAG_LLM/SUCCEEDED → successful local LLM-assisted analysis; RAG_ASSISTED → RAG-assisted deterministic explanation with no successful LLM generation; DETERMINISTIC → deterministic explanation with no successful LLM generation. Actual generationStatus is also shown, including fallback statuses.

## Session and stale-response boundaries

Each request captures the session version, current selected payment and a conversation generation. Session notifications (logout, expiry, refresh failure, cross-tab replacement/logout, account replacement) abort/invalidate pending work and clear private turns/context/payment choices. The existing persistence layer remains responsible for Web Locks, BroadcastChannel, cookie refresh and cross-tab events. Same-family token renewal remains compatible with existing session-version behavior.

New Chat, context replacement and actual route leave invalidate prior results. Router refresh of the same AI route does not discard a pending conversation. Late successes/errors cannot populate a cleared/new context or replacement session. The central client's existing version/token comparison preserves late401 protection. Current401 clears the session;403/inaccessible context clears private chat and requires eligibility confirmation again. Backend rechecks during inference remain unchanged.

Answer actions are bound to current visible DOM and session eligibility; removed answer nodes cannot submit follow-ups/open details or announce late clipboard completion. No localStorage, sessionStorage, IndexedDB, conversation database, global conversation cache or token persistence was added.

## Accessibility and responsive design

Explicit labels, native buttons/forms/details, visible inherited focus styling, focused route heading, conversation region, status announcements outside busy content, disabled controls, aria-busy composer and elapsed timer (not live-announced each second) are implemented. UUIDs, long questions/citations and source strings wrap; controls flex/wrap; transcript has bounded scroll height and composer remains in normal mobile flow. Desktop/375px layout review is static, **not native-browser or contrast-measurement certification**.

## Changed files

Created:

- `frontend/assets/js/merchant-ai/schema.js`
- `frontend/assets/js/merchant-ai/model.js`
- `frontend/assets/js/merchant-ai/view.js`
- `frontend/assets/js/merchant-ai-test-fixtures.js` — synthetic Phase692 oracle/public-DTO fixture
- `frontend/assets/js/merchant-ai-tests.js`
- `frontend/assets/js/merchant-ai-tests.html`
- `frontend/tests/test_merchant_ai_ui.py`
- `frontend/tests/mock-dom.mjs` — dependency-free offline test helper, not a browser emulator
- This report.

Modified:

- `frontend/assets/js/api/config.js`, `api/client.js` — exact Merchant chat route usage,45-second budget, bounded UTF-8 body, optional AbortSignal, allowlisted safe error code.
- `frontend/assets/js/merchant/routes.js`, `merchant/view.js` — route/navigation/lazy view and shared locks.
- `frontend/assets/js/portals/view.js`, `app.js` — route leave cleanup, focused AI title, shared operation/account-switch safeguards.
- `frontend/index.html`, `assets/css/app.css` — private workspace host and responsive styles.
- `frontend/merchant_proxy.py` — only explicit static `/merchant/ai`; upstream chat routes were already implemented.
- `frontend/assets/js/portal-tests.js`, `tests/test_portal_routes.py` —23 explicit routes instead of22.
- `frontend/assets/js/merchant-tests.html` — missing Payment Links fixture host for its existing workspace mount; no production behavior change.
- Root `README.md`, `PROGRESS.md`, `frontend/README.md` — status and handoff.

No Java/Python ai-service source, migrations, protected configuration, historical evidence, business logic or dependency files were changed.

## Automated verification

Final counts/commands and preservation observations are appended below. All JavaScript API requests were mocked; default test-helper fetch rejects unmocked network. Proxy tests bind temporary mock loopback servers. The in-app browser connection reported unavailable, so no actual browser, live cookie, native layout or live model verification is claimed. The helper provisions missing fixture IDs and is a limited DOM approximation; the native test pages/checklist remain important.

Previous **388 Java**, **237 Python** and **119 operational mocked tests** are retained baseline evidence, **not rerun in Phase693**. Backend/ai-service code is unchanged, so no live/isolated database tests, packaging or operational activation was necessary.

## Native browser checklist — pending separate activation approval

No deployment/restart or activation was performed. Updated JS/CSS are served directly by the static server, but the new explicit `/merchant/ai` handler route requires a later approved frontend-only handler restart. Do not launch a duplicate listener. Backend/Python chat activation still needs protected matching service configuration and separate approval; this report supplies no activation or key-generation action.

After approved combined activation, verify:

1. Sign in as an eligible Merchant, open **http://127.0.0.1:5500/merchant/ai** directly, refresh and use Back/Forward. Admin/unauthenticated users must not enter Merchant AI; limited Merchants must retain onboarding/financial denial.
2. Verify opening makes no chat POST. Overview shows no fabricated answer; separately disabled chat shows disabled/unavailable feedback. No OTP change is involved.
3. Send a suggested/general question, test Enter, Shift+Enter and IME composition. Verify loading/elapsed and duplicate prevention; inspect actual mode/status and limitations rather than assuming LLM success.
4. Search authorized payments with five-record pages, select a payment and ask status/refund/gateway questions. Check exact INR/USD values, sources, provenance and explicit detail navigation. Merchant A cannot select/access Merchant B data.
5. Ask a follow-up, inspect bounded completed history. Change context/New Chat and verify confirmation/cancel, history clearing and no automatic send.
6. Verify explicit failure retry, insufficient evidence and honest fallback labels. Do not induce live service failures by restarting/stopping services.
7. While pending, verify financial/navigation/account-switch guards. New Chat may abort locally; server completion must not repopulate the conversation. Logout/replacement/expiry/cross-tab logout clears all private messages and context.
8. Verify Copy Answer/manual fallback, keyboard focus, native details, screen-reader feedback and375px layout/long UUID/source wrapping. No unsafe HTML or model-provided external links.
9. Run mocked-only page **http://127.0.0.1:5500/assets/js/merchant-ai-tests.html** after static asset refresh. It performs no real business/chat requests. Existing test pages remain available.

## Remaining limitations and Phase694 handoff

Chat remains disabled pending protected Java/Python activation; live schema remains operator-reported V11 with V12/V13 pending. Phase681 dashboard/native/password/final-audit, Phase682/683 activation/native checkout, Phase691 live LLM and Phase692 live integration remain open. Phase673/674 evidence limitations remain intact. No prior phase is closed here.

Only Merchant chat is implemented. Admin chat UI is Phase694; payment-detail Ask AI and Phase696 persistence remain separate. Reuse the safe response renderer/contract patterns in a future role-specific Admin model; do not reuse Merchant identity assumptions or expose arbitrary evidence. Preserve explicit context authorization, request bounds, honest fallback labels, no tools/mutations and session-generation guards.

The small model selects approved explanation variants; this is not unrestricted autonomous financial reasoning. Long answers may not fit history, unknown evidence remains unknown, and timeout/abort does not prove server inference stopped. No production security certification is made.

## Final executed verification and preservation — 2026-11-16

- **1,154 mocked JavaScript assertions passed**, all16 suites: API10, auth34, payments94, refunds125, investigation149, QA18, portals73, registration39, persistent sessions/recovery67, Admin113, Merchant100, analytics/account-switch46, pagination51, Payment Links70, checkout57, Merchant AI108. The existing Merchant suite gained3 route assertions from the newly enumerated route; the new Merchant AI suite contributes108.
- **48 frontend Python proxy/static-security tests passed**, including2 new Merchant AI route/privacy/accessibility tests. Actual final command: `python3 -m unittest discover -s frontend/tests -p 'test_*.py'`. Temporary mock listeners were shut down; no live backend requests were used.
- **Total frontend:1,202 checks**, compared with the prior1,089 baseline.
- All62 JS/ES-module files (including the offline DOM helper) parsed successfully with Node VM syntax checks. `python3 -m compileall -q frontend` passed. `git diff --check` passed.
- Java388, Python ai-service237 and operational119 remain previous baseline totals, not newly executed suites. No backend source changed and no Maven/database/live inference test ran.

The interrupted partial run exposed limitations in the lightweight DOM environment; the recovered offline helper supplies the existing browser-compatible APIs and rejects unmocked fetch. Native browser bootstrap reported `Browser is not available: iab`. Therefore these results are explicitly mocked runtime verification. The first full regression attempt exposed obsolete22-route assertions and a syntax error from a default-argument edit; these were corrected before the final successful complete batch. No failing final suite is omitted.

Initial staged-content SHA256: `fc092b2d7ed0253d3ae9eace670ba15c8525466d5caa06f54dcf42f633a490c9`. Final observed SHA256: `550b128fa2d3db4a9afe93a1aadffad769cb8795ed1583a25efb426395eff2de`. There were9 externally changed staged patch blocks involving the new Merchant AI/report/test files;481 status entries were observed. No Git staging/index mutation command was issued. External staging was left untouched, so byte-identical index preservation is not asserted. Existing unrelated changes and protected evidence/configuration remain untouched.

**Handoff:** Phase693 implementation and mocked verification complete; separate live activation/native browser verification pending. No previous phase is closed, and Phase694 has not started.
