# Phase 6.9.4 — Admin AI Chat UI

**Implementation complete; mocked verification recorded below. Live activation and native browser verification pending.** No Phase695 payment-detail Ask AI, persistence, backend/schema change or live operation is included. Live remains operator-reported V11; V12/V13 and earlier phase verification gaps remain pending. Chat and OTP settings were not changed.

## Inspected contracts and design

Reviewed Phase692/693 reports and actual ChatDtos, ChatEvidenceBuilder, DashboardAnalytics, AdminQueries, Admin routes/models/profile, Merchant chat, central API client, session/cross-tab handling, portal operation guards, proxy/static catalog and test fixtures. Phase692 already supplies `POST /api/v1/admin/ai/chat`; no backend extension is needed.

`/admin/ai` is a dedicated same-document Admin portal route, labeled **AI Assistant**. The existing router requires the Admin role. A separate Admin chat model checks current ACTIVE Admin presentation state, then calls the existing `/admin/profile` API and requires matching authenticated user UUID, enabled ACTIVE account and ADMIN role. Java remains authoritative; the UI does not authenticate a user from a selector or profile label. Opening the page never sends an AI request.

The shared `chat/presentation.js` shell and `chat/render.js` renderer were extracted from Phase693. They provide conversation bubbles, composer/keyboard behavior, elapsed/loading state, confirmation, retry, clipboard, evidence and safe text rendering. Merchant view becomes a role-specific context adapter and keeps its original model and public exports, including the renderAnswer compatibility export. Admin and Merchant **never share a conversation instance, selected context, history or eligibility state**. The response validator has a shared scoped implementation; the original Merchant entry point still fixes MERCHANT_OWNED, while Admin fixes ADMIN_AUTHORIZED in code.

Admin-specific `admin-ai/model.js` owns authorization, bounded selector projections, aggregate filters and lifecycle. `admin-ai/view.js` owns the platform/Merchant/payment controls and supported suggestions. No global conversation cache or browser storage was introduced. Existing local Bootstrap/styles are reused without new dependencies.

## Exact public integration

`POST /api/v1/admin/ai/chat`, JSON, bearer access token, credentials omitted, no Idempotency-Key, no query parameters, no automatic retries. Only question, bounded history and allowlisted resource context are sent. The authenticated actor/role/ownership/evidence are never supplied by the UI. `context.merchantId` is an explicitly requested authorized resource selector, not a claim about the caller's identity or ownership.

Platform example:

```json
{"question":"Summarize platform payment statistics","history":[],"context":{"statistics":{}}}
```

Selected Merchant and supported statistics filters (synthetic ID):

```json
{"question":"Summarize this Merchant's payment statistics","history":[],"context":{"merchantId":"SYNTHETIC_A","statistics":{"currency":"USD","from":"2026-11-01T00:00:00.000Z","to":"2026-11-03T00:00:00.000Z"}}}
```

Selected payment, with optional explicitly selected Merchant consistency constraint:

```json
{"question":"How much was refunded?","history":[],"context":{"merchantId":"SYNTHETIC_A","paymentId":"00000000-0000-4000-8000-000000000001"}}
```

When a payment is selected from platform-wide choices without selecting a Merchant, only `paymentId` is sent; Java derives/rechecks ownership. The UI never silently selects a Merchant. A selected Merchant constrains every payment choice and submitted payment context. Unknown/inconsistent choices are rejected, not silently filtered or replaced.

Question limit1–1,000 Unicode code points; completed history<=8 messages/6,000 total code points/1,000 per message. Shared history includes only complete valid pairs and never truncates a financial answer. Failed/cancelled/stale/sending results are excluded. Long/privacy-incompatible pairs stop older history inclusion. Maximum20 turns in memory; a failed final turn can still be retried, otherwise New Chat is required. The full serialized UTF-8 request is bounded to32,768 bytes by the client, and Java independently bounds its internal evidence snapshot. Common accidental credentials/contact/identifier patterns are rejected; this is not a universal secret detector.

Both chat routes share the existing45-second browser timeout; Java defaults25 seconds, proxy40 seconds, Python inference cap15 seconds. No runtime timing measurement is claimed. Client cancellation/timeout does not establish that server/model work stopped. No Python/llama.cpp endpoint, internal credential or browser refresh cookie is used by chat.

The public response remains the exact Phase692 DTO: correlationId, answer, intent, evidenceProvenance, evidenceReferences, knowledgeReferences, limitations, suggestedFollowUps, moneyFacts, analysisMode and generationStatus. Shared validation enforces Admin provenance/scope, timestamp/UUID/bounds, selected-payment association, reference kinds, exact decimal strings, currencies and mode/status combinations before displaying an answer. Java retains the independent approved-answer/citation/money verification; frontend validation does not replace it.

## Context selection and date semantics

All selectors use existing authorized Admin reads, with `page`, `size=5`, `sort=newest` and bounded search. Only one page is kept per selector, never the complete dataset:

- `GET /api/v1/admin/merchants?page=0&size=5&sort=newest[&search=...]`: existing case-insensitive Merchant ID/business name/email search. Chat state projects only Merchant ID, nullable business name and lifecycle status; returned contact/audit fields are not retained or sent to AI.
- `GET /api/v1/admin/payments?page=0&size=5&sort=newest[&search=...][&merchantId=...]`: existing exact payment UUID/customer ID search. A selected Merchant always adds its ID. The whole page is rejected if a returned payment does not belong to it. Choices retain only IDs, exact amount/currency and recorded status.
- `GET /api/v1/admin/profile`: current Admin verification only, not evidence construction in the browser.

Platform/Merchant overview sends `statistics`. The default is the actual backend's last30 UTC days. Optional INR or USD narrows the scope; omitted currency preserves separate INR/USD aggregates. Custom date inputs are inclusive UTC days and convert to UTC instants with an **exclusive next-day end**. Maximum93 days through today UTC; both dates or neither are required. These are full Java SUM/COUNT aggregates, never calculated from selector pages or recent records.

Aggregate date/currency filters are explicitly independent from payment search. Selected-payment facts are not date/currency filtered; applying aggregate filters clears the selected payment/history and returns to the current Merchant/platform aggregate context. Context replacement clears previous turns/evidence, failed question, both selector pages/searches and pending generations. No context replacement invokes AI. New Chat additionally returns to platform defaults and clears all selections/filters.

Only actual Phase692 fields are offered. No arbitrary filters, raw evidence, payment-link selectors, checkout tokens, Merchant rankings, forecasting, fraud detection, settlement verification or financial actions are implemented. A backend identifier incompatible with the existing chat syntax fails validation; it is not rewritten or guessed.

## Suggestions, rendering and errors

Platform and Merchant suggestions explicitly use supported payment-statistics wording; comparisons are offered only with the two-currency aggregate scope. Payment context offers recorded status, successful-refund summary and this payment's refundable amount. General timeout/uncertainty questions are approved domain guidance. This wording follows the actual finite Python intent router rather than advertising unrestricted analysis. If context/evidence is insufficient, the successful structured clarification is displayed honestly.

The shared renderer displays actual answer, generation status, dated provenance, exact money facts, expandable evidence/knowledge, relevance scores, limitations and explicit follow-up buttons. It keeps INR/USD separate, uses no floating-point financial arithmetic, never infers settlement/bank arrival and renders all API/AI text through DOM textContent/createElement. Source strings are text, never model-provided external links. Relevance is not confidence or probability of correctness.

Only validated PAYMENT references for the selected authorized payment offer **Open authorized payment**, using the existing Admin known-payment lookup callback/workspace. No unsupported UUID-detail SPA route, arbitrary redirect, automatic investigation/refund or payment-detail Ask AI entry is introduced. Copy Answer is explicit clipboard text with a safe manual fallback.

RAG_LLM/SUCCEEDED is labeled successful local LLM assistance. RAG_ASSISTED and DETERMINISTIC explicitly state that no successful LLM generation occurred; actual generationStatus is shown. A small-model approved wording selection is not autonomous financial decision-making.

Disabled and unavailable share Phase692's AI_UNAVAILABLE code, so the UI reports **disabled or unavailable**, not a fabricated capability or answer. Fixed messages also distinguish capacity, timeouts/network, invalid upstream response, input/evidence bounds, missing context and authentication loss. No raw exception/backend message is rendered. Failed questions remain for explicit retry. Duplicate sends are blocked.

Admin offers **Cancel pending analysis** with confirmation: it stops browser waiting, ignores the old reply and retains the failed question for deliberate retry. New Chat can separately cancel/invalidate and clear the whole conversation, with confirmation while nonempty/pending. Declining either confirmation preserves the current operation. Neither claims server inference stopped; no retry occurs automatically.

## Session, role isolation and operation guards

Requests bind session version, current Admin role/eligibility, selected context and conversation generation. The existing Java authorization-before/after-inference boundary remains unchanged. Logout, expiry, revocation, cross-tab logout/replacement and account switching clear/abort all private Admin conversation/context/selector state. An Admin-to-Merchant change cannot render a prior Admin result; Merchant-to-Admin cannot import Merchant history. Late401 protection in the central client continues to preserve replacement sessions.

Context replacement, New Chat, cancellation and real route leave invalidate stale success/error/list responses. Same-route router refresh hides/shows presentation without clearing an active conversation. The shared shell restricts answer actions to current visible authorized DOM nodes. New Chat/context edits never carry a previous Merchant's financial history into another context.

Admin chat busy participates in existing router/account-switch guards and the shared readBusy/financial lock path. Pending Admin management, payment/refund and investigation operations block chat. While chat is pending, guarded financial/administrative mutations remain blocked. Existing uncertain administrative state is not reset merely by hiding its workspace. Chat itself sends no approval/rejection/suspension/reactivation/password/payment/refund mutation.

## Accessibility and responsive review

Reuses the existing navy/white Bootstrap shell, focus-visible styling, responsive field grids and wrapping controls. The Admin AI heading receives route focus. Labels, Enter/Shift+Enter with IME exclusion, native buttons/details, status announcements outside busy content, aria-busy composer, disabled controls and elapsed timer are shared. UUIDs/long citations wrap; the transcript scrolls within its bounded height and the composer stays in normal flow at375px. Static design review is not measured native-browser, screen-reader or contrast certification.

## Files created

- `frontend/assets/js/admin-ai/model.js`
- `frontend/assets/js/admin-ai/view.js`
- `frontend/assets/js/chat/presentation.js`
- `frontend/assets/js/chat/render.js`
- `frontend/assets/js/admin-ai-test-fixtures.js` — synthetic Phase692 Python oracle mapped to the Java Admin DTO
- `frontend/assets/js/admin-ai-tests.js`
- `frontend/assets/js/admin-ai-tests.html`
- `frontend/tests/test_admin_ai_ui.py`
- This report.

## Files modified

- `frontend/assets/js/merchant-ai/view.js` — role-specific adapter and compatibility exports for extracted presentation.
- `frontend/assets/js/merchant-ai/schema.js` — shared scoped validator, preserving fixed Merchant entry point.
- `frontend/assets/js/merchant-ai/model.js` — optional role label for fixed safe error feedback; Merchant state semantics preserved.
- `frontend/assets/js/admin/routes.js`, `api/client.js` — exact Admin route and existing chat timeout/bounds/error behavior.
- `frontend/assets/js/portals/view.js`, `frontend/index.html` — dedicated host/navigation, route focus, cleanup and operation locks.
- `frontend/admin_proxy.py` — exact static `/admin/ai`; upstream Java chat route was already allowlisted.
- `frontend/assets/js/portal-tests.js`, `frontend/tests/test_portal_routes.py` —24 explicit static routes.
- `frontend/tests/test_merchant_ai_ui.py` — follows the extracted shared accessibility implementation and continues storage/unsafe-HTML checks across both modules.
- Root README/PROGRESS and frontend README — status, actual results and pending verification.

No Java/Python AI-service source, dependency, migration, protected configuration or historical evidence was changed.

## Automated verification

Final executed results and staging observations follow below. All JavaScript requests are mocked; the existing dependency-free offline DOM helper rejects unmocked fetch. Proxy tests use temporary mocked loopback listeners. No native-browser, live model, actual cookie or live database verification is claimed.

Java388, Python AI-service237 and operational119 are prior baseline results, **not rerun here**. Unchanged backend/service contracts required no new isolated backend run or packaging. Earlier phase live gaps remain open.

## Pending native browser checklist and handler reload

A separately approved frontend-only handler reload is required for the new explicit `/admin/ai` route on direct navigation/refresh because Python imports the static route set at startup. JS/CSS assets serve from disk and require browser hard refresh. No handler/backend/Python/LLM restart, chat activation, secret generation or deployment was executed in this phase.

After separately authorized combined activation:

1. Open **http://127.0.0.1:5500/admin/ai** as an authorized Admin; verify direct refresh, Back/Forward, title focus and navigation. Merchant/unauthenticated sessions must not enter the Admin workspace.
2. Verify page opening performs profile verification only, never an AI POST. While chat is disabled, explicit send must report disabled/unavailable without fabricated output.
3. Inspect platform aggregates and separate INR/USD facts. Apply supported UTC/currency filters; verify the displayed range matches the request/provenance and is not derived from the five choice rows.
4. Search/page Merchants, choose explicitly, then search/page payments constrained to it. Switch Merchant/platform/payment/filter context and confirm that old history/pages/drafts are cleared, with no automatic send.
5. Ask supported status/refund/timeout/statistics questions. Inspect actual intent, mode, generation status, evidence, knowledge/score labels and limitations; do not assume live LLM success.
6. Verify Enter/Shift+Enter/IME, duplicate prevention, real elapsed state, explicit retry, Cancel pending analysis and New Chat confirmation/cancellation. Late replies must not repopulate cancelled or replaced contexts.
7. Switch Admin↔Merchant accounts through the existing safe account switch flow, and verify logout/cross-tab/expiry clearing and role isolation. Do not create accounts, reset passwords or mutate financial records to perform this checklist.
8. Confirm pending AI/financial/administrative guards using the mocked suites; do not induce live failures or submit administrative/financial mutations. Verify approved payment-detail navigation remains an explicit read and does not start investigation.
9. Verify Copy Answer/manual fallback, expandable evidence, keyboard/screen-reader feedback and375px wrapping. Sources remain text; malicious markup cannot execute.
10. Run mocked-only **http://127.0.0.1:5500/assets/js/admin-ai-tests.html** and the full existing **merchant-ai-tests.html** page. These use synthetic fetch responses, not live business/chat requests.

## Known limitations and Phase695 handoff

Chat remains disabled pending protected Java/Python configuration/activation. Live V11, V12/V13 activation, Phase681 dashboard/native/password/final audit, Phase682/683 activation/checkout browser, Phase691 live LLM, Phase692 live integration and Phase693 native browser/handler reload remain pending. Phase673/674 historical evidence limitations are preserved. No previous phase is closed and this is not production security certification.

History is bounded and memory-only; long answers may be omitted from follow-up context. The Python schema has no arbitrary daily/method comparison, fraud/ranking/forecasting or settlement evidence. Cancellation/timeout cannot prove remote work stopped. Future secure conversation persistence belongs to Phase696.

Phase695 may add a separately reviewed payment-detail Ask AI entry using explicit authorized context, existing shared rendering, exact Java request fields and role-specific models. It must reauthorize every selector, retain operation/session-generation guards and avoid automatic send or financial execution. **Phase695 has not started.**

## Final executed verification — 2026-11-16

- **1,300 JavaScript assertions passed** across all17 suites: API10; auth34; payments94; refunds125; investigation149; QA18; portals73; registration39; persistent sessions/recovery67; Admin management116; Merchant100; analytics/account-switch46; dashboard pagination51; Payment Links70; checkout57; Merchant AI108; **Admin AI143**. All API calls were mocked. The existing Admin suite gained3 route checks; the complete Phase693 Merchant AI suite remained green.
- **50 frontend Python proxy/security tests passed**, including2 new Admin AI tests. Actual final command: `python3 -m unittest discover -s frontend/tests -p 'test_*.py'`. Temporary mock loopback listeners only; zero failures/errors.
- **Total frontend:1,350 checks**, compared with the prior1,202 baseline. This is mocked runtime verification, not native-browser/live inference proof.
- All68 JS/ES-module files (including the existing offline DOM helper) passed Node VM syntax parsing. `python3 -m compileall -q frontend` and `git diff --check` passed.
- Java388, Python AI-service237 and operational119 are **unchanged prior baselines, not newly rerun**. No backend/AI-service source change, Maven build, database access or live model call occurred.

JavaScript suites were executed through the existing Node-backed ES-module runtime with `frontend/tests/mock-dom.mjs` and mocked fetch. This helper is a limited DOM approximation, including automatic fixture-ID provisioning; it does not certify native layout, focus behavior, clipboard permissions, screen readers or actual browsers. Native checklist execution remains pending. The first proxy regression attempt found an accessibility source-location assertion still pointing at the pre-extraction Merchant view; it was updated to inspect the actual shared component and retain the same safety assertions. The final full suites passed.

Initial staged-content SHA256: `550b128fa2d3db4a9afe93a1aadffad769cb8795ed1583a25efb426395eff2de`; final observed SHA256: `30bfcc4adbfe6b5a4c490a98a5b9478ab032b0ca45fc3fb7f41d618c3529d3a8`. Eight new externally staged patch blocks were observed. **Zero initial staged blocks changed or disappeared**.490 status entries were observed. No Git staging/index mutation command was issued; external staging was left untouched. Byte-identical whole-index preservation is not claimed because of those external additions.

Protected configuration, backups, historical evidence, original database/application and running services were untouched. No deployment, restart, chat/OTP activation, financial/account mutation, password change, paid dependency or Phase695 implementation occurred.

**Handoff: Phase694 implementation and mocked verification complete; separate live activation/native browser verification pending. Previous phases remain open wherever previously documented.**
