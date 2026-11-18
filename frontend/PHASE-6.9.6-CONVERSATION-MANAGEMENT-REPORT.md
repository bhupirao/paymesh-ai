# Phase 6.9.6 — Persistent conversation management

Implementation and isolated/mock verification are recorded below. **Live activation and native browser verification are pending.** Live remains operator-reported V11; V12/V13/V14 have not been applied by this work. Chat and OTP remain disabled. No previous phase is closed by this implementation and Phase697 has not started.

## Architecture and schema

Java owns conversation authorization, PostgreSQL persistence, history selection and validated public responses. Python remains the existing private, stateless inference service; its contracts/source and database privileges are unchanged. Existing Phase692 stateless endpoints remain compatible.

Additive **V14__private_ai_conversations.sql** follows the inspected V1–V13 inventory; historical migrations are unchanged. Four tables:

- `ai_conversations`: UUID, owner FK, exact portal role, immutable context type/context JSON and Merchant/payment scope, title, optimistic version, turn/content counters, creation/update/expiry timestamps.
- `ai_conversation_creations`: owner/role/client-request UUID journal, canonical context/title fingerprint and nullable conversation FK. Deletion keeps only metadata to prevent uncertain create retries from recreating deleted content.
- `ai_conversation_requests`: per-conversation request UUID, question digest, expected version, status, worker nonce, attempt counter, lease and safe failure code. No failed question or upstream payload is stored.
- `ai_conversation_messages`: ordered user/assistant pairs with request FK, text question or validated public structured response, and timestamps. Unique ordinals and request/role constraints, cascading deletion and a partial unique in-progress-request index protect ordering. Composite payment/Merchant FK uses the existing V13 ownership constraint. A trigger prohibits changing conversation ownership, role or context.

No financial/account table is changed. Message deletion cascades atomically; the creation journal retains no title, question, answer, evidence or deleted message content. No deleted content is placed in audit metadata.

## Public Java API

Use bearer authentication, JSON and no-store responses. Replace `{role}` with exactly `merchant` or `admin`; UUIDs are canonical. All body properties are strict: unknown/duplicate fields, trailing JSON, numeric strings for versions, invalid context combinations and bodies over **8,192 UTF-8 bytes** are rejected. No caller-supplied owner, role, evidence or assistant history.

Base: `/api/v1/{role}/ai/conversations`.

| Method/path relative to base | Request / result |
|---|---|
| POST base | `{"requestId":"<uuid>","context":{"statistics":{}},"title":"Optional title"}` →201 `{conversation,replay:false}`; identical create replay200; changed same-ID intent409 |
| GET base | `page=0&size=5&search=title`; optional exact `paymentId` filters pure payment contexts; `{items,page,size,total}` |
| GET `/creations/{requestId}` | Reconcile original creation;200 metadata,404 unavailable,410 deleted journal |
| GET `/{conversationId}` | `{conversation}`, after fresh authorization |
| GET `/{conversationId}/messages?page=0&size=5` | `{conversation,turns,page,size,total}`; page0 newest completed pairs, each page internally chronological |
| GET `/{conversationId}/requests/{requestId}` | `{requestId,expectedVersion,status,conversation,errorCode,turn}` for explicit reconciliation |
| POST `/{conversationId}/messages` | `{"requestId":"<uuid>","expectedVersion":0,"question":"Explain this payment's recorded status."}` |
| POST `/{conversationId}/rename` | `{"expectedVersion":1,"title":"Payment follow-up"}` → `{conversation}`; increments version |
| POST `/{conversationId}/delete` | `{"expectedVersion":2}` → `{"deleted":true}`; physical cascade |

Lists default5, maximum10; page0–10000; title search at most120 characters, parameterized literal matching (wildcards escaped). Titles are1–120 Unicode code points, no controls/malformed Unicode/recognized credentials. The default title is context-derived; no extra LLM call.

A conversation projection includes `conversationId,portalRole,contextType,context,title,version,turnCount,createdAt,updatedAt,expiresAt,merchantId,payment,merchant,activeRequest`. Nullable payment is a safe current authorized projection (ID, Merchant ID, exact amount string, currency, method, status); Merchant projection contains only ID, nullable business name and lifecycle status. Owner IDs, token digests and worker nonces are not returned.

Completed send200 example shape:

```json
{
  "requestId": "<original-request-uuid>",
  "expectedVersion": 0,
  "status": "COMPLETED",
  "conversation": {"conversationId": "<uuid>", "version": 1, "turnCount": 1},
  "errorCode": null,
  "turn": {
    "requestId": "<original-request-uuid>",
    "turnIndex": 1,
    "question": "Explain this payment's recorded status.",
    "response": {
      "correlationId": "<server-generated-uuid>",
      "answer": "<validated grounded answer>",
      "intent": "PAYMENT_STATUS",
      "evidenceReferences": [],
      "knowledgeReferences": [],
      "moneyFacts": [],
      "limitations": [],
      "suggestedFollowUps": [],
      "analysisMode": "DETERMINISTIC",
      "generationStatus": "DISABLED",
      "evidenceProvenance": {"source": "JAVA_AUTHORIZED_DATABASE_SNAPSHOT"}
    },
    "createdAt": "<UTC timestamp>"
  }
}
```

Nested conversation/response projections above are abbreviated for readability, not alternative schemas: response is the complete existing Phase692 public DTO, including authorized provenance scope, timestamp/range/limitations and its validated references. Exact money fields remain decimal strings; generation labels remain honest.

In-progress replay202 returns the same envelope with `turn:null`. Effective expired lease is `UNCERTAIN`, not proof of failure. Errors preserve existing conventions:400 invalid input,401 invalid current credentials,403 role/eligibility denied,404 inaccessible conversation/context (including foreign histories),409 conflict/stale version,410 deleted creation journal,413 body limit,422 storage/evidence limit,429 owner quota,502 invalid AI response,503 disabled/unavailable/capacity and504 timeout. Error bodies are safe code/message/correlation IDs; no raw exception or sensitive payload.

## Authorization and immutable contexts

Every operation re-decodes current credentials and acquires the existing account administration lock in a short transaction. Merchant access requires current eligible ACTIVE exact-MERCHANT authorization, verified/active registry, active membership and business lifecycle. Admin requires current ACTIVE authorized Admin identity. Namespace fixes portal role; authenticated user fixes owner. Admin platform authority does not grant another user's private chat history.

Supported persisted contexts:

- Merchant overview `{"statistics":{}}` or existing supported currency/UTC range; Merchant scope is pinned to the server-derived membership.
- Merchant payment `{"paymentId":"<authorized uuid>"}`.
- Admin platform statistics, selected Merchant with statistics, or selected authorized payment (optionally explicit matching Merchant).
- Existing statistics keys are only `currency,from,to`, with existing analytics bounds and UTC/end-exclusive semantics. No payment+statistics combination.
- Payment Ask AI restores only the exact current payment and role, with no additional Merchant selector/aggregate filters. A conversation created under a different scope is never silently adapted.
- Payment-link selectors are not supported for saved conversations in this phase; the stateless Phase692 API is unchanged.

List/detail/rename/delete/send revalidate stored financial contexts before returning content. Inaccessible list contexts are omitted rather than leaking titles. Owner/role mismatches use the same unavailable response. Context cannot be edited or migrated across users, roles, memberships or payments.

## Submission, idempotency and concurrency

1. Short transaction authorizes/locks owner and conversation; validates version/question/request identity and reserves an IN_PROGRESS request.
2. Java loads up to four completed server-owned turns, at most8 messages/6,000 code points and1,000 characters per history message. Long/unsafe pairs are omitted whole. Failed/cancelled requests are excluded.
3. Existing Phase692 builder collects fresh, bounded, authorized evidence and preserves exact money/refund completeness and32KiB internal request limits.
4. Database transaction/account locks are released before shared-budget Python HTTP inference. Existing private authentication, timeouts, alias mapping, correlation/citation/money validation and fallback rules are reused.
5. Authorization and original scope/version are rechecked. A short final transaction reauthorizes and verifies conversation/version/nonce, then atomically inserts both messages, completes the request and increments version/counters.

Same request ID/question/expected version replays the completed turn without another inference. Changed intent409. Another request while unresolved409; live same-ID replay202. Leases are120 seconds, independently of existing40-second transport/45-second browser budgets. A deliberately retried expired/failed request uses the same identity, receives a new worker nonce and is bounded to3 attempts. An older worker cannot commit after being fenced. No claim of exactly-once inference: crash/timeout can leave uncertain inference and an explicit retry may perform inference again.

Deletion during inference cannot recreate rows; late completion fails authorization/existence/fence checks. Rename during inference changes version and prevents stale persistence. Revocation/membership change suppresses late answers. If a failure cannot be durably recorded because authorization was lost, the request remains uncertain until safely reconciled or expired/deleted.

No DB row lock or account administration lock spans remote inference. The existing shared AI capacity semaphore remains authoritative. Conversation operations do not execute payments, refunds, approvals or any other financial/account mutation.

## Storage and retention

- 50 conversations per owner/portal;50 completed turns per conversation;100 durable request identities per conversation.
- 1MiB aggregate stored question/response UTF-8 content per conversation; validated compact response at most60,000 bytes, DB response JSON text at most65,536 bytes.
- Conversation access expires30 days after creation (not sliding); creation journal expires31 days.
- `ConversationRetention` removes at most5 expired conversations and50 expired journal records per hourly run under the administration lock. Properties: `paymesh.conversations.cleanup-enabled` (defaulttrue), `paymesh.conversations.cleanup-delay-ms` (default3600000). Delayed cleanup can leave expired inaccessible rows temporarily and consume quotas; no unbounded sweeping.
- Deletion removes live conversation content atomically, not protected backup copies. Backup retention/encryption/access policies and any future legal erasure obligations require separate operator handling. Content is not encrypted by this application at rest; protect PostgreSQL and archives.
- Request digests/IDs and creation metadata survive only as documented; no message content is retained in deletion audit metadata.

## Frontend integration

Shared `chat/presentation.js` mounts the reusable saved-history store/drawer in Merchant AI, Admin AI and Payment Ask AI. Production mounts use persistent endpoints; stateless APIs remain available to existing callers. Test injection explicitly selects managed persistence in new integration fixtures.

No initialization AI call or empty conversation creation. First explicit send lazily creates once using a stable UUID; uncertain creation reads its original creation journal before deliberate same-ID retry. New Chat clears local content and waits until a new question to create. Server-derived default titles can be explicitly renamed.

The history drawer provides owned title search,5-row pagination, dates, current selection, bounded completed-turn pages, rename, confirmed deletion and explicit reconciliation. Restored answers are labelled historical snapshots. Sending is blocked on older history pages until latest turns are loaded. Merchant restored filters and Admin contexts are preserved exactly; fixed-payment panels reject incompatible histories.

Only question/request ID/expected version are sent for saved messages. Browser history is never submitted as trusted assistant content. Uncertain sends retain original identity; explicit retry first reads status. Completed late turns can be restored without inference. In-progress requests are not blindly retried. If an unconfirmed creation identity is lost on reload, explicitly inspect owned history before starting a distinct new conversation; memory-only client intent cannot provide cross-reload exactly-once creation. If the original question is lost after reload and the server reports UNCERTAIN, the UI requires reconciliation or deliberate deletion rather than inventing an intent.

Unknown deletion outcomes are not optimistic success. An authorized read can establish that a conversation remains accessible;404 only means no accessible conversation, not independent proof of physical deletion.

Session/account/role/context/view generation changes invalidate private lists, selectors, turns and pending responses. Existing cross-tab events are reused. Abort cancels browser waiting, not server inference. No localStorage/sessionStorage content, tokens or selectors. Safe text rendering, exact-money strings, honest generation labels, existing clipboard/evidence controls and financial/investigation operation guards remain.

## File inventory

New:
- `backend/src/main/resources/db/migration/V14__private_ai_conversations.sql`
- `backend/src/main/java/com/paymesh/backend/chat/conversations/ConversationDtos.java`
- `backend/src/main/java/com/paymesh/backend/chat/conversations/ConversationTransactions.java`
- `backend/src/main/java/com/paymesh/backend/chat/conversations/ConversationService.java`
- `backend/src/main/java/com/paymesh/backend/chat/conversations/ConversationController.java`
- `backend/src/main/java/com/paymesh/backend/security/accounts/ConversationRetention.java`
- `backend/src/test/java/com/paymesh/backend/security/auth/ConversationIntegrationTest.java`
- `frontend/assets/js/conversations/{routes,schema,store,view}.js`
- `frontend/assets/js/conversation-tests.{js,html}`
- `frontend/conversation_proxy.py`
- `frontend/tests/test_conversation_proxy.py`
- This report.

Modified:
- `backend/src/main/java/com/paymesh/backend/security/accounts/ChatEvidenceBuilder.java` (transaction-bound authorization reuse).
- `backend/src/main/java/com/paymesh/backend/security/auth/BusinessEndpointCatalog.java`.
- `backend/src/main/java/com/paymesh/backend/security/BoundedRequestBodyFilter.java`.
- `frontend/assets/js/chat/presentation.js`.
- `frontend/assets/js/{merchant-ai,admin-ai,payment-ai}/{model,view}.js`.
- `frontend/assets/js/api/{client,config}.js`.
- `frontend/assets/css/app.css`, `frontend/dev_server.py`.
- `README.md`, `PROGRESS.md`, `frontend/README.md`.

## Automated verification

Final newly executed verification:
- **412 Java tests passed**, zero failures/errors/skips, via the complete isolated PostgreSQL runner. Includes24 new conversation integration tests and existing stateless/security/financial regressions. Disposable PostgreSQL14.20 was selected by the existing harness; live PostgreSQL16 was not accessed. V1–V14 migration/constraints were exercised in isolation.
- **1,558 frontend checks passed**:1,503 mocked JavaScript assertions across19 suites, including97 conversation assertions, plus55 Python proxy/security tests (3 new tests). Full Phase693/694/695 regression is included (108 Merchant,143 Admin,106 Payment assertions).
- Maven `package -DskipTests`: BUILD SUCCESS after the isolated suite.
- JavaScript syntax:77 source/harness files parsed; frontend Python compileall and Bash syntax for the isolated runner passed.
- `git diff --check`: passed.

Intermediate verification found nested-MockMvc security-context fixture interference and an incorrect singular/plural evidence assertion; fixtures were corrected. An intermediate run was also invalidated by iteration of the new V14 test resources during verification. The final complete run used a fresh isolated database and finalized migration; no Flyway repair or historical migration change was used. Initial sandbox failures concerned disposable PostgreSQL shared memory and temporary proxy test sockets; approved test-only execution resolved these. No live services were contacted.

 Python AI source/contracts and operational activation scripts are unchanged; Python237 and operational119 are prior baselines, not newly rerun results. Mocked DOM assertions are not browser/layout verification.

## Future guarded activation plan — NOT executed

No existing activation script has been extended automatically. Existing Phase682/683 scripts expect their reviewed schema boundary; do not reuse them blindly for V14. A separately reviewed/approved operator procedure must:

1. Inspect current listener identities, working directories and loopback bindings for demo Java18080/frontend5500/Python8000/LLM8082. Preserve original DB/application; never target paymesh_db or8080.
2. With private hidden terminal credentials and PostgreSQL16 tools `/Library/PostgreSQL/16/bin`, verify literal demo target127.0.0.1:5432/paymesh_demo and paymesh_demo_user, actual server identity, V1–V11 history and pending V12–V14 compatibility. Stop on unexpected state.
3. Verify authentic baseline6/4/4/2/6/4, roles/memberships/ownership, OTP=false and chat disabled; record all eight financial-table contents/fingerprints and safe account/ownership comparisons without exposing hashes or secrets.
4. Create a new timestamped custom-format archive outside Git under the existing protected backup policy, mode600; verify nonempty archive, pg_restore list and extraction, checksum/disk space. This is archive verification, not a test restore. Preserve all old backups/evidence.
5. Require a separate explicit operator approval for **V11→V12→V13→V14**, reviewed JAR/frontend handler deployment and cleanup configuration. Preserve private keys, issuer/audience, session settings, gateways, AI limits, disabled settlement scheduling and loopback-only configuration.
6. Stop only verified demo Java, launch approved JAR with normal Flyway and Hibernate validation. Never clean/repair/baseline/downgrade automatically. On startup/migration failure stop and report; PostgreSQL backup restoration is a separate operator-reviewed procedure, never an automatic rollback.
7. Verify V12/V13/V14 history, constraints/indexes/immutable-scope trigger and initially empty new link/checkout/conversation tables. Compare original accounts/ownership and exact eight financial tables; counts unchanged. Check readiness/payment health, frontend routes and exact proxy boundaries. Reload only the approved frontend handler if required for new proxy routes; preserve Python/LLM identities.
8. Keep chat and OTP disabled. No AI call, account mutation, password change or customer payment as deployment verification. Protected chat activation and native browser testing require separate approval.

There is deliberately no executable live activation command in this phase: the documented plan requires its own reviewed operator approval and protected credentials. Existing migration/activation evidence remains untouched.

## Native browser checklist — pending

After approved migration, handler reload and separately approved chat activation:

- Merchant/Admin AI and fixed-payment panels: open without AI/empty record creation; explicit first send saves one turn.
- Reload, explicitly load/search/page history and restore correct role/owner/context; historical label and exact INR/USD strings visible.
- Merchant A/B and Admin A/B isolation; revoked membership/payment access refuses history; no selector substitution.
- Create-response timeout: reconcile same creation ID; completed-send timeout/cancel: reconcile saved turn, no duplicate message; explicit retry keeps original request ID.
- New Chat/context replacement during inference ignores late reply; server completion may still appear in history.
- Rename/version conflict, confirmed delete, uncertain deletion, delete during inference, expiry and storage limits.
- Payment A→B panel navigation never restores A under B; compatible pure-payment history can reopen under same authorized role.
- Cross-tab logout/account switch/revocation clear all private content; Admin history never enters Merchant session.
- Existing payment/refund intent and investigation report remain intact; chat never performs a mutation.
- Desktop/375px, keyboard focus, drawer controls, announcements, exact-money/citation/fallback rendering.
- Keep Phase681/682/683, Merchant password/browser/audit gaps, Phase691 live LLM checks and Phase673/674 evidence limitations explicitly open.

## Phase697 handoff and limitations

Phase697 may verify integrated behavior only under separate instructions; it is not implemented here. Local LLM/native browser behavior, deployment, V12–V14 activation and protected chat configuration remain unverified. Retention cleanup is bounded/eventual and backups may contain deleted content. Lease recovery does not provide exactly-once inference. Historical saved answers do not establish current financial state, ownership, settlement or bank arrival; each new question uses fresh authorized evidence.

## Workspace preservation and final status

All492 originally captured staged diff blocks remained byte-for-byte unchanged. The
index gained10 externally staged additions during this work; they were left untouched.
No staging/reset/restore/clean/commit command was used. Final inspected working tree had
509 entries (223 AM,279 A,7 untracked); these describe the shared repository, not a claim
that all changes belong to Phase696. New code/tests were modified only in the worktree.

The packaged JAR was inspected and contains V14, ConversationController and
ConversationRetention. Complete isolated Java verification passed412/0/0/0; full frontend
verification passed1,558 checks. Syntax and final whitespace checks passed. Operational119
and Python237 remain prior baselines, not fresh runs. No live database/service/LLM or
financial operation, protected secret access, deployment, migration, password change or
OTP/chat activation occurred. Implementation is complete; native browser verification,
the separately approved handler reload/migration/activation and Phase697 remain pending.


## Merchant manual E2E failure review — 2026-11-18

The exact question “what payment have done last?” is not a supported latest-record
selector. Python recognizes no applicable intent and returns INSUFFICIENT_EVIDENCE /
NOT_ATTEMPTED without inference. Merchant overview evidence contains authorized
aggregates, not the latest transaction. Payment-specific evidence requires explicit
selection from the authorized payment list. This is an unsupported query capability,
not evidence of a Qwen generation failure. No new selector or financial inference was
introduced. Use payment search/selection and “Explain this payment's recorded status.”

Creation, restoration, rename and deletion already exist. Restoration is explicit:
expand Saved conversations, Load saved conversations, then select a record. Browser
refresh does not persist or automatically reopen a private conversation selector.
Rename/delete require a selected saved record and use POST rename/delete with the
current expectedVersion and bearer authorization. A read-only repeatable-read database
inspection, rolled back without writes or reading titles/questions/answers, found one
Merchant conversation and two messages, but none owned by the dedicated disposable
Merchant. This proves some persistence, not the reported browser user's identity or
successful restoration. No live record was renamed or deleted.

A reproducible presentation defect left the old title/version in an already-loaded
history list after a confirmed rename. The store now replaces that list entry with the
validated server projection. Search matches/order still require explicit reload; the UI
states this. The selected projection already updated correctly. Deletion already clears
local history/selection after confirmed success; no deletion defect was demonstrated.
The specific manual restoration/deletion failures and actual live rename outcome remain
UNKNOWN without sanitized browser method/path-shape/status/error-code evidence. Do not
capture bearer headers, UUIDs, conversation text or raw responses for diagnosis.

Files changed in this review:
- frontend/assets/js/conversations/store.js
- frontend/assets/js/conversation-tests.js
- ai-service/tests/test_chat.py (test only)
- this report

Fresh offline results: 1,512 JavaScript assertions across 19 suites (106 conversation
assertions), 55 proxy/security tests: 1,567 frontend checks; complete Python suite
379 passed (one pre-existing Starlette deprecation warning); eight Java ChatContractTest /
AiChatClientTest tests passed with mocked HTTP and no database. The full isolated Java
412-test result and operational 236-test result remain prior baselines, not reruns here.
Nine frontend assertions cover confirmed rename labels/version, a fresh memory-only
store's explicit list/restore, persisted title/turn, no inference during restore, and
confirmed deletion method/version/cleanup. The Python regression proves the exact
unsupported question performs no generation or fabricated citation. Syntax and
whitespace checks are recorded in the handoff.

Only static frontend JavaScript changed at runtime. A browser hard refresh is sufficient
for that patch; no Java/Python restart or proxy reload is required by these changes.
One next operator action, after separate live-test approval: use the same authenticated
Merchant that created the synthetic conversation, hard refresh, expand Saved
conversations, load/select that record, and verify the restored historical turn. Then
rename/delete only that operator-designated synthetic record, explicitly refreshing the
list after each operation. If a step fails, retain only sanitized HTTP status and safe
error code. No live E2E, inference, service restart, account/financial mutation or
conversation write was performed during this review. Previous evidence gaps remain open.


## API-first conversation reliability correction — 2026-11-18

Offline handler tests established a concrete transport defect: dev_server accepted
conversation routes in allowed(), but its subsequent path-character validation applied
to the entire query-bearing URL. Thus the normal list and history URLs containing
?page=0&size=5 were rejected with 400 before reaching Java. Validation now strips the
query only after allowed_conversation has validated the exact method/path/query
allowlist. Invalid or arbitrary queries remain rejected. This explains a demonstrable
restoration/list failure; no claim is made about the operator's individual live requests.

Java contracts are unchanged: role base /api/v1/{merchant|admin}/ai/conversations;
POST create {requestId,context,title?}; GET list ?page&size&search&paymentId?;
GET /{id}/messages?page&size returns {conversation,turns,page,size,total};
POST /{id}/rename {expectedVersion,title} returns {conversation};
POST /{id}/delete {expectedVersion} returns {deleted:true}. Java independently checks
owner, exact role and current context eligibility on every request. No backend source,
ownership checks, schema, inference architecture or existing record changed.

Automatic refresh restoration now keeps only a minimal pointer in the current tab's
history.state: account subject, refresh-session ID, role, entry point and conversation
UUID. No content, title, token, amount or evidence is stored there, and localStorage /
sessionStorage remain unused. This is a deliberate change from the earlier explicit-only
restore behavior. Java reauthorizes GET messages before any history is displayed.
The pointer requires an exact current user/session/role match; fixed-payment entry
points must also match. Portal restoration adopts only validated authorized saved
context. Sessions without sid, unavailable history APIs or overwritten history entries
fall back to explicit Saved conversations → Load → Select. This does not synchronize
selection between tabs or guarantee retention after browser history deletion.

New Chat, logout/account replacement, context replacement, deletion and failed restore
clear the pointer as appropriate. Late responses remain fenced by session version and
conversation generation. Restoration is attempted once per mounted instance and sends
no AI request or database mutation. Confirmed rename uses the returned version and
updates loaded history labels. Confirmed deletion clears list and selection; unconfirmed
deletion retains state for explicit reconciliation. Errors distinguish 401/403/404/409
and service failures without exposing upstream data. Conflict recovery requires an
explicit authorized reload; no mutation is automatically retried.

Fresh verification: 1,544 JS assertions across all 19 suites, including 138 conversation
assertions; 57 proxy/security tests, totaling 1,601 frontend checks. Eight Java mocked
contract/transport tests passed. Java/Python application code is unchanged; full Java
412, Python 379 and operational 236 remain prior results, not new suite executions.
Proxy tests exercise real temporary offline handlers against mocked Java transport for
both role list/search and messages query URLs, fixed upstream, no-store and static asset
cache headers. JS tests cover refresh pointers, session/account/role/context isolation,
automatic GET restoration, 401/403/404/409/503 failures, rename conflicts and version
handling, confirmed/failed deletion and all existing Merchant/Admin/payment AI tests.

Changed files in this API-first correction:
- frontend/dev_server.py
- frontend/tests/test_conversation_proxy.py
- frontend/assets/js/conversations/bookmark.js (new)
- frontend/assets/js/conversations/store.js
- frontend/assets/js/chat/presentation.js
- frontend/assets/js/conversation-tests.js
- this report

Static JS and API requests use no-store. Offline cache-header tests prove the reviewed
handler behavior, not which code an existing browser has loaded. A later explicitly
approved frontend-handler reload is required for the Python proxy fix, followed by a
browser hard refresh. No Java/Python AI service restart is needed. Live restoration,
rename/delete persistence and browser cache behavior remain unverified. Next safe
operator action is to review/approve a frontend-only handler reload before retesting
with an explicitly designated synthetic conversation. No live API requests, database
access/writes, inference, browser mutations or service restarts occurred in this pass.
All previous verification gaps and evidence limitations remain open.
