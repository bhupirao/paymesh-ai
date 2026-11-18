# Payment-domain chat reliability audit and offline correction

Date: 2026-11-18. This is a correction to the existing chat architecture, not a new
project phase. No live database access, inference, authentication, conversation
mutation, activation or service restart occurred. Existing records are unchanged.

## Audited architecture and contracts

Merchant/Admin/payment UIs use shared safe-text presentation, role-specific models and
the memory-only conversation store. Stateless POST /api/v1/merchant/ai/chat,
/api/v1/admin/ai/chat and /api/v1/payments/{paymentId}/ai/chat accept only question,
bounded history and supported selectors. Saved conversation POST messages accepts only
requestId, expectedVersion and question; Java loads completed history itself. Existing
create/list/detail/messages/rename/delete routes and DTOs are unchanged.

Java ChatEvidenceBuilder revalidates the authenticated account/session and exact role,
Merchant membership/lifecycle and BusinessAccess payment ownership. ChatProjectionQueries
builds detached authorized snapshots under existing short transaction boundaries. No
new SQL, selection capability, schema, ownership exception or financial mutation was
introduced. Java rechecks authorization after private inference. Internal aliases are
request-scoped and raw identifiers/tokens never establish authorization.

Java sends a fixed private authenticated POST /api/v1/chat; no browser JWT/cookie is
forwarded. Limits remain 1,000 question code points, eight history messages / 6,000
characters, 32 KiB serialized internal request and bounded response. Existing defaults:
2-second connection / 25-second Java response budget, 40-second proxy / 45-second browser
chat budget; local inference is capped at 15 seconds, 128 output tokens and 8,000 prompt
characters. Existing shared single inference slot and no automatic retries remain.

Python never queries financial tables. It routes the validated question, builds exact
facts and retrieves allowlisted topic chunks. Qwen selects BASE or EXPLAIN approved
wording, not arbitrary generated financial prose. Selection JSON/schema/alias checks
remain strict; required empty outgoing arrays still use const: [] for llama.cpp b4514.
Java independently reconstructs the allowed answer, exact money facts and citations.
Thus SUCCEEDED proves successful constrained model selection, not semantic relevance or
independent factual correctness. A bad router can still choose an irrelevant approved
answer; that was a systemic defect addressed here.

## Capability / evidence matrix

| Capability | Existing authorized evidence | Result after correction / limitation |
|---|---|---|
| General payment lifecycle, orchestration | Relevant local guidance only | KNOWLEDGE; no transaction claims |
| Gateway routing concepts | Relevant routing guidance | KNOWLEDGE; legacy routing rules not redefined |
| API/security concepts | New general API/security guidance | KNOWLEDGE; no credential disclosure or authorization actions |
| Current selected payment | Explicit authorized payment selector | PAYMENT_STATUS; absent snapshot explained without model invocation |
| Failure explanation | Current payment status | PAYMENT_FAILURE; cause unknown without supporting evidence; not full investigation |
| Gateway / timeout | Selected payment and bounded gateway rows | GATEWAY / PROCESSING; mutable current rows do not prove historical timeout/recovery |
| Refund summary / remaining amount | Selected payment, successful refunds, completeness marker | REFUND_SUMMARY; exact integer-unit/BigDecimal arithmetic; incomplete/absent history cannot establish remaining amount |
| Pending/failed refund diagnosis | Not represented in refund projection | Unsupported; no invented refund reason/arrival |
| Payment/refund aggregate activity | Complete grouped query by currency/status in bounded UTC window | STATISTICS; never totals from five recent previews; INR/USD separate |
| Daily trends / method breakdown | Not represented by chat schema | Clarification / INSUFFICIENT_EVIDENCE; dashboard functionality does not imply chat support |
| Latest/recent/oldest payment selection | Not implemented by chat selector/projection | Explicit unsupported retrieval / INSUFFICIENT_EVIDENCE; no automatic query expansion |
| Checkout/link lifecycle | Explicit link selector where existing stateless contract permits | CHECKOUT; no public token, new payment or checkout action; saved conversations do not support link selectors |
| Ambiguous or unrelated question | None sufficient | Clarification / INSUFFICIENT_EVIDENCE, no generation |
| Financial actions / injections / secrets | Never tool authority | UNSUPPORTED; existing authorization boundaries preserved |
| Follow-up | Nearest user turn plus current authorized snapshot | Only explicit short follow-up grammar; assistant claims never become evidence |
| Saved history / rename / delete | Current role/owner/context-authorized Java APIs | Implemented, offline regressions pass; final live persistence verification pending |

## Confirmed defects and corrections

1. Broad keyword precedence confused concepts with observations. In particular, a generic
status keyword and the old broad why/history heuristic could select PAYMENT_STATUS for
an unrelated conceptual question. The new frame/topic router is declarative and shared
with Java through the exported manifest. Conceptual frames, transaction references,
specific domain topics and explicit capability exclusions are evaluated separately.
Multiple conflicting topics return clarification. Categorical HIGH / BOUNDED /
CONTEXTUAL / NONE specificity is internal and is not a calibrated probability or a new
public field. This is a bounded English rule grammar, not unrestricted natural-language
understanding; unknown paraphrases remain honest clarification rather than guessed data.

2. Prior history was scanned for a keyword match even when a new question had a new
subject. Only an exact short follow-up frame can now borrow the nearest user topic;
unknown recent user topics stop inheritance. Current explicit conceptual questions do
not inherit a prior financial intent. No global conversation state is added.

3. Missing required financial evidence could still invoke Qwen and receive SUCCEEDED
for an unanswerable financial request. Such requests now produce a grounded missing-data
explanation with NOT_ATTEMPTED in non-deterministic modes. Deterministic mode retains its
existing DISABLED metadata. Complete empty aggregates remain distinct from unavailable
aggregates. Missing detailed refunds remain distinct from a confirmed zero total.

4. Frontend text validation allowed whitespace-only reference text, and the shared list
renderer could produce empty bullets for blank arrays/values. Text validation rejects
blank fields; presentation filters blank list entries with explicit empty-state text.
Reference groups already had explicit no-citation states. Safe textContent rendering is
preserved. There is no model-Markdown renderer; the exact reported live empty-heading
state cannot be independently reconstructed from this audit. No raw completion was
read or retained. The successful-model label now explicitly disclaims factual proof.

5. The previous query-string proxy correction, rename-list update, automatic refresh
pointer, error/version handling and delete reconciliation are preserved. Conversation
management was inspected and exercised through the full frontend and isolated Java
regressions; no new live persistence failure was demonstrated. A same-tab history
pointer carries only the conversation ID and user/session/role/entry-point fence. Java
reauthorizes restored content. No chat content, credentials or evidence is persisted in
localStorage/sessionStorage. Legacy sessions lacking sid retain manual restoration.

## RAG and response quality boundaries

Three small general guidance documents cover API boundaries, security and orchestration.
Investigation's original eight-document corpus is unchanged; the chat corpus grows from
13 to 16 documents. Retrieval still filters by approved document, chunk, topic anchor
and metadata; only actually retrieved approved citations may be returned. General
knowledge is separate from transaction observations. Prompt shape, model alias,
credentials, endpoint and timeout settings are unchanged. Financial facts, history
completeness, currencies and recorded-versus-bank-settlement limitations remain enforced.
No claim is made that these finite policy explanations answer every possible question.

## Smallest proposed financial extension — NOT implemented

A separately approved latest/recent capability would require an explicit bounded Java
selector/intent, Merchant ownership in every query, deterministic created_at plus
payment_id ordering, a small bounded projection and an evidence timestamp/range. Admin
scope would require explicit authorized selection. Python and Java response schemas,
finite fact construction, aliases, privacy validation and UI would then need synchronized
changes. Daily trends similarly require a new bounded evidence contract, not reuse of
recent previews. This audit adds neither capability nor any financial query.

## Files changed in this correction

- ai-service/app/services/chat_routing.py (new)
- ai-service/app/services/chat_routing.json (new shared routing definition)
- ai-service/app/services/chat_service.py
- ai-service/app/services/retrieval.py
- ai-service/knowledge_base/api.md (new)
- ai-service/knowledge_base/security.md (new)
- ai-service/knowledge_base/orchestration.md (new)
- ai-service/scripts/export_chat_contract.py
- ai-service/tests/test_chat.py (chat corpus count)
- ai-service/tests/test_chat_routing_matrix.py (new)
- backend/src/main/java/com/paymesh/backend/chat/ChatRules.java
- backend/src/main/resources/ai-chat/contract.json (offline regenerated)
- backend/src/test/resources/ai-chat/python-fixtures.json (offline regenerated)
- frontend/assets/js/chat/render.js
- frontend/assets/js/merchant-ai/schema.js
- frontend/assets/js/merchant-ai-tests.js
- this report

## Offline verification

Final counts and checks are recorded below after completion. The reusable Python matrix
covers intent/topic, categorical confidence, evidence absence, model invocation policy,
context contamination, unsupported retrieval and injection. Existing Python tests cover
exact amounts/refund completeness, malformed JSON/aliases/schema, empty-array grammar,
private authentication, bounded inputs, model unavailability/timeouts and fallback.
75 exported synthetic request/response fixtures compare Java answers, intents, amounts,
citations and limitations against actual Python construction. Existing isolated Java
security/persistence tests cover role/owner denial, authorization loss, concurrent sends,
delete races, transactions outside inference and financial preservation. Frontend suites
cover all three chat entry points, restoration, rename conflict/version, deletion and
uncertain outcomes, session replacement, stale responses and malicious content. Proxy
checks use temporary loopback servers and mocked upstreams, never live services.

An initial targeted run exposed a generic-lifecycle candidate collision; it was fixed
before final tests. A corpus-count assertion was updated for the three new chat-only
documents. An initial full Python invocation from the repository root produced two
working-directory fixture failures; rerunning from ai-service was required. No application
behavior was changed to mask those harness-path failures.

## Controlled activation proposal — separate approval required

No current live services were queried or restarted. The existing source-pinned Python
reload launcher correctly fails closed on the changed source manifest; it was NOT
re-pinned or executed. Its old evidence/source hashes must not be reused to activate
this release. The new routing JSON must also be included in a fresh reviewed hash manifest.

The minimum next activation step is a separately reviewed, coordinated Java/Python chat
release: pin the new packaged Java artifact, matching exported manifest, Python routing
code/JSON and knowledge files; verify current native process identities and protected
configuration without exposing credentials; preserve backup/evidence and all other
services; then reload only the approved Java and Python services after explicit approval.
Mixed old/new versions can fail closed at Java response verification; do not activate
Python alone or relax validation to accommodate mismatches. No migration or database
write is required. Static UI changes need a browser hard refresh; no new frontend-handler
change/reload is required by this correction. The previously approved proxy reload is
not repeated.

Later operator-approved browser checks must verify conceptual topic relevance, explicit
payment context and missing-evidence handling, honest fallback/model labels, Merchant A/B
and Admin isolation, same-account refresh restoration, rename with current version and
delete only designated synthetic conversations. No automatic inference retries. Preserve
all previous evidence gaps and financial/account baselines. Unit success and historical
Qwen success do not establish complete live E2E correctness.


### Final executed results

- Full isolated Java runner: 412 passed, zero failures/errors/skips. Fresh temporary
  PostgreSQL 14.20 cluster on port55441; live5432 was not used. Existing runner selected
  the locally available14.20 tools, so this run is not a fresh PostgreSQL16 certification.
- Complete Python suite: 442 passed; one existing Starlette/httpx deprecation warning.
  Includes63 new routing/manifest tests (29 questions evaluated both for routing/history
  and generation-without-evidence, three new topic retrieval checks, nearest-user history
  and shared-manifest integrity). Mocked inference only.
- All19 frontend JS suites: 1,548 assertions passed, including112 Merchant AI and all
  existing Admin/payment AI plus138 conversation assertions.
- All frontend proxy/security tests: 57 passed. Combined frontend: 1,605 checks.
- Maven offline packaging after successful isolated tests: BUILD SUCCESS.
- JavaScript/Python/JSON syntax and git diff --check passed.
- Operational scripts were not modified or rerun; their prior236 count is not a new
  result. A source-only fail-closed check confirmed the old reload manifest is stale.

Concurrent external staging changed the index from the previously observed
ed95b756c19d5145a44dae0e24a43e30c253ee8d422fa3d6c47196ae8b2883da to
3b9c20d6a3b2a1649e5168e3fe3c5564451f3673dd30ef79d895a6c93566beb6. No index-writing Git
command was executed. Existing staged/unstaged changes were preserved; an external
index change is not reported as index integrity failure caused by this work.

Live Merchant/Admin/payment conversations, actual new-question relevance, refresh
restoration, rename/delete persistence, browser/mobile behavior and mixed-service
version rollout remain pending. No unit-test total or SUCCEEDED status closes those
checks. Keep earlier phase verification/evidence limitations open.


### Future controlled browser checklist — not executed

After a separately approved coordinated activation and browser hard refresh:
1. Ask conceptual lifecycle/orchestration/routing/API questions after a prior financial
   question; verify KNOWLEDGE and relevant general citations rather than selected status.
2. With explicit authorized payment context, ask recorded status, gateway and refund
   questions; compare authorized current evidence and exact INR/USD strings. Do not
   invoke payment/refund actions. Unsupported recent/trend questions must clarify.
3. Test unsupported/injection text with synthetic questions only; verify no scope growth.
4. Confirm model success/fallback labels match actual metadata and no blank reference
   headings/bullets appear. A successful generation label is not correctness proof.
5. With approval to create only designated synthetic test conversations, reload/restore,
   rename with current version, and delete only those records. Verify Merchant/Admin
   isolation, account switching and stale responses; preserve all existing conversations.
6. Test unavailable/timeout behavior through a separately approved safe procedure, not
   by stopping live services or automatically retrying inference.

Remaining limitations: finite English phrase grammar, categorical—not statistical—
confidence, bounded policy explanations rather than unrestricted generated prose,
unsupported financial retrieval/trends, unchanged historical evidence gaps and pending
live browser/persistence verification. The existing source-hash-pinned launcher requires
new review; no activation command is approved by this report.
