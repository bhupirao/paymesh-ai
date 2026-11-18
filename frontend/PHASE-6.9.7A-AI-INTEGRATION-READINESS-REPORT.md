# Phase 6.9.7A — AI integration readiness

**Preparation complete; no live verification, migration, service restart, inference or activation performed.** Phase697B/Phase6.10 are not started. Live remains operator-reported V11, counts users/Merchants/memberships/registrations/payments/refunds6/4/4/2/6/4. V12/V13/V14, chat activation, frontend handler reload and previous native browser checks remain pending. OTP remains disabled.

This report distinguishes source inspection, newly executed offline operational tests, previous isolated/mock application results, and unperformed operator verification. Example outputs below are expected criteria, not observed live evidence.

## Inspected implementation

Reviewed README/PROGRESS/frontend README, Phase691–696 reports, migration inventory, checked-in configuration examples, Phase682/683 deployment preparation and reusable Phase673 operational helpers. Protected live configuration, keys, database, model endpoint and historical private evidence were **not read**.

Actual chain:

```text
Merchant/Admin browser
  -> fixed frontend proxy5500 (bearer to Java; no refresh cookie/internal service key)
  -> Java18080: current JWT/session/account/lifecycle/ownership authorization
     -> detached authorized evidence + server-owned bounded saved history
     -> private POST Python8000/api/v1/chat + chat-only service token
        -> deterministic intents/money/status, local retrieval
        -> bounded approved-wording selection via llama.cpp8082
     -> strict correlation/citations/money/answer/mode validation
     -> authorization recheck + atomic saved turn, or safe failure
```

Python never reads PostgreSQL or conversation tables. No AI financial/account tool exists. Legacy investigation remains a separate authorized Java integration; its Python route retains the existing loopback trust model (the new chat token is chat-specific, not a claim that every Python route has service authentication).

## Exact configuration, without secrets

| Component | Actual property/environment | Reviewed local value |
|---|---|---|
| Java chat feature | `paymesh.ai.chat.enabled` | false during schema activation; true only after separate approval |
| Java private upstream | `paymesh.ai.base-url` | http://127.0.0.1:8000 |
| Java connect/read/body | `paymesh.ai.connect-timeout-ms`, `paymesh.ai.chat.response-timeout-ms`, `paymesh.ai.chat.max-response-bytes` |2000 /25000 /65536 |
| Java service credential | `paymesh.ai.chat.service-token` | protected external properties only;64–128 URL-safe high-entropy characters |
| Python HTTP chat gate | `PAYMESH_AI_CHAT_API_ENABLED` | false initially; separately approved true |
| Python matching credential | `PAYMESH_AI_CHAT_SERVICE_TOKEN` | same protected value; never JWT/cookie |
| Python connector | uvicorn `--host 127.0.0.1 --port 8000 --no-access-log` | CLI binding must agree with reviewed local profile |
| Python mode/generation | `PAYMESH_AI_ANALYSIS_MODE`, `PAYMESH_AI_GENERATION_ENABLED` | RAG_LLM /true only for approved inference; deterministic modes remain valid fallbacks |
| Python inference origin | `PAYMESH_AI_INFERENCE_URL` | http://127.0.0.1:8082/v1/chat/completions |
| Python alias | `PAYMESH_AI_MODEL_NAME` | paymesh-qwen, matching the existing local server alias |
| Generation settings | `PAYMESH_AI_GENERATION_TIMEOUT`, `PAYMESH_AI_MAX_OUTPUT_TOKENS`, `PAYMESH_AI_CONTEXT_CHARS` | retain reviewed investigation settings (template30/128/12000); chat independently caps15s/128/8000 |
| Retrieval | `PAYMESH_AI_RETRIEVAL_TOP_K`, `PAYMESH_AI_RETRIEVAL_CONTEXT_CHARS`, `PAYMESH_AI_RETRIEVAL_THRESHOLD` | reviewed defaults3/3000/0.12 |
| Python general body limit | `PAYMESH_AI_REQUEST_BODY_BYTES` |131072; chat independently32768 |
| Java investigation | `paymesh.ai.enabled`, investigation timeout/response settings | preserve existing enabled investigation integration unchanged |
| Local sessions | `paymesh.sessions.origin`, `paymesh.sessions.local-http` | http://127.0.0.1:5500 /true; same existing demo-only checks |
| Database/connector | datasource URL/user, demo profile, address/port, forward strategy | exact demo target, demo,127.0.0.1:18080,none |
| OTP/settlement | `paymesh.demo.password-recovery.enabled`, `paymesh.settlement.scheduling-enabled` |false /false |

New checked-in **inactive** examples: `backend/phase697-ai.properties.example`, `ai-service/phase697-chat.env.example`. They contain no credential and disable chat. The generic older AI .env example defaults inference to8080; **do not use that default for this demo**. No request/probe here targets8080 or the original database.

Java uses exactly `X-PayMesh-AI-Chat-Token`; Python requires one header and constant-time comparison. No redirect, environment HTTP proxy, browser JWT or refresh cookie goes to Python. Local shared-secret HTTP plus verified loopback is not production TLS/mTLS or public-service certification.

The configured alias alone is not proof that Qwen is loaded. At execution the operator must privately corroborate the existing llama-server command/model artifact (Qwen2.5-0.5B-Instruct Q4_K_M) and known file checksum, without printing model prompts or changing/downloading models. This preparation did not inspect the live process or model.

Timeout hierarchy: Python chat inference<=15s, Java chat25s, proxy40s, browser45s. Investigation retains its distinct reviewed budget. Java and Python each share one nonqueued inference slot across chat/investigation. A timeout/abort does not prove server inference stopped; no automatic retries.

## Actual API and persistence contracts

Stateless, unchanged:

- POST `/api/v1/merchant/ai/chat`
- POST `/api/v1/admin/ai/chat`
- POST `/api/v1/payments/{paymentId}/ai/chat`

Overview body: `{"question":"Summarize payment statistics","history":[],"context":{"statistics":{}}}`.
Admin context may select `merchantId`; either role may select an authorized `paymentId`. Selected-payment context must not carry aggregate statistics. Payment-path body is only question/history. Existing stateless link selector `paymentLinkId` is supported by Java but is not offered by saved-conversation/UI contexts. No token is sent as evidence.

Internal Python body: `correlationId,callerRole,question,history,evidence,paymentContext`; resources are aliases, not raw financial IDs. Python response has `evidenceCollectedAt`; Java supplies public `evidenceProvenance` and authorized references. Public answer/money/citations are not unfiltered upstream JSON. Java accepts only its independently reconstructed approved answer variants and exact facts.

Persistent base `/api/v1/{merchant|admin}/ai/conversations`:

| Method/path | Actual use |
|---|---|
| POST base | requestId/context/optional title;201 create,200 exact replay |
| GET base | page,size,search,optional exact paymentId; owned currently authorized contexts only |
| GET /creations/{requestId} | reconcile uncertain creation;410 journal of deleted content |
| GET /{conversationId} | safe authorized metadata |
| GET /{conversationId}/messages | page0 newest completed turns; size5 default/max10; within-page chronological |
| GET /{conversationId}/requests/{requestId} | completed/in-progress/failed/effective-uncertain reconciliation |
| POST /{conversationId}/messages | requestId/expectedVersion/question only, never client assistant history |
| POST /{conversationId}/rename | expectedVersion/title |
| POST /{conversationId}/delete | expectedVersion; deletes content atomically |

Question<=1000 code points; inference history<=8 messages/6000 code points; internal/stateless requests<=32768 UTF-8 bytes; persistent bodies<=8192 bytes. Java selects up to four complete eligible server-owned turns.50 conversations/owner-role,50 turns/conversation,100 request identities/conversation,1MiB content;30-day access retention,31-day creation journal, bounded hourly cleanup. Historical answers remain dated snapshots.

Owner/portal/context are immutable. Admin platform rights do not grant other users' saved history. Every operation rechecks lifecycle/membership and selected resources. Database locks/transactions are released before inference. Completion rechecks authorization/version/worker nonce and commits both messages together.120s lease; same-ID completion replay; conflicting IDs/versions409; bounded explicit same-ID retry fences old workers. No exactly-once inference claim. Deleted content cannot be resurrected by a late completion; backup copies may retain content.

See Phase692/696 reports for complete DTOs, errors and constraints. Relevant safe errors:400 input/spoofing,401 credentials,403 role/lifecycle,404 inaccessible context/history,409 version/request conflict,410 deleted creation,413 body size,422 evidence/storage,429 quota,502 invalid upstream,503 disabled/unavailable/capacity,504 timeout. Insufficient evidence can be a successful explanatory response.

## Integration verification matrix

All future rows remain **pending**, not passed. “Prior” refers to existing source-backed isolated/mocked suites, not suites rerun in697A.

| Check | Prior automated evidence /697A preparation | Future operator verification and pass criterion |
|---|---|---|
|1 Merchant own scope/platform denial | Java ownership/role/spoofing tests; proxy restrictions | Merchant overview equals own full aggregates; Admin route403; client Merchant/role/evidence override400; foreign payment404 |
|2 Admin platform/Merchant/payment | Java snapshots and Admin UI fixtures | Authorized aggregate contexts, explicit Merchant/payment consistency, UTC/currency filters; unsupported selectors rejected |
|3 Payment Ask AI both roles | Merchant/Admin/payment UI regression and BusinessAccess | Explicit detail Ask AI; fixed UUID from authorized detail; no auto request, no investigation replacement |
|4 Java→Python service authentication | Java mock HTTP/Python private-auth tests; new prepared internal probe | Wrong service key401, matching key200; then Java authenticated chat200 confirms end-to-end configuration. No user credential forwarded |
|5 Python→Qwen inference | Mocked constrained-selection tests | Correct model artifact/alias + live chat RAG_LLM/SUCCEEDED, valid retrieval references; health alone insufficient |
|6 Server-owned multi-turn history | Java persistence/history tests; prepared two-turn probe | POST question/requestId/version only; restore two completed turns; independently inspect contract, not raw logs |
|7 Saved create/restore/rename/delete | Java/JS tests; prepared temporary-conversation probe | Create once, fresh authorized GET restores, rename increments version, confirmed delete removes live content |
|8 Merchant A/B conversation isolation | Prior isolated cross-owner/financial tests | Two separately authorized Merchant sessions: B gets404 for A conversation/messages/rename/delete. No resource enumeration |
|9 Admin private ownership | Prior Admin A/B isolated test | Another Admin's private history404 despite platform data permission |
|10 Exact money/refunds | Java oracle/BigDecimal and Python exact arithmetic tests | Compare fresh authorized full aggregate/detail evidence; INR/USD separate; incomplete refund history declares unavailable refundable total |
|11 Evidence/knowledge | Alias/contract/oracle and frontend validators; new offline policy-manifest comparison | Only authorized resource references and actual stable KB references; no raw customer/contact/token/internal data |
|12 Honest generation/fallback | Mode/status/approved-answer tests; probe refuses fallback as inference proof | RAG_LLM/SUCCEEDED distinct from RAG_ASSISTED/TIMEOUT etc.; fallback remains useful but model criterion not passed |
|13 Unavailable/timeout/malformed | Existing mocked Java HTTP/Python inference tests | Keep mocked/isolated fault injection; do not stop live services or return forged SUCCESS. Any optional live fault test requires separate approval |
|14 Request replay/uncertainty | Prior durable request/fencing tests; exact replay in prepared probe | Same question/ID/version returns original pair;202/UNCERTAIN resolved by GET, no automatic retry/new ID |
|15 Delete/revoke during inference | Prior isolated Java and JS race tests | Native browser controlled disposable conversation: Cancel/Close then delete/logout, late answer never disclosed/recreated; no account suspension/password change without separate approval |
|16 Session switch/stale response | Existing cross-tab/session/role/view tests | Existing account-switch confirmation/logout across tabs; no old history after Merchant↔Admin change, including late list/detail results |
|17 Investigation regression | Prior Java/Python/JS investigation tests | Explicit known authorized payment investigation; correct finite report/mode, no financial mutation; no chat-triggered investigation |
|18 No unauthorized mutation | Prior snapshots/read-only boundary tests; schema fingerprints | Compare eight financial tables and account/role/membership/lifecycle fingerprints around approved run; session/conversation rows may legitimately change |

INR/USD real-data coverage depends on the authorized existing dataset. If a currency/refund/link scenario is absent, mark that live scenario **not available**, retaining isolated fixture evidence; do not manufacture financial records. Pending/rejected/suspended checks need existing eligible test fixtures or separate approval, not new account/status mutation during AI verification.

## Guarded V11→V14 schema procedure — prepared, not executed

New paths:
- `backend/scripts/activate-phase697a-schema.sh`
- `backend/scripts/phase697a_schema.py`

Historical Phase682/683 deployment and Phase673/674 verification scripts are unchanged. The older combined deployment correctly rejects a V14 JAR; do not bypass or edit it.

Future separately approved operator command:

```bash
/bin/bash "$HOME/Developer/paymesh-ai/backend/scripts/activate-phase697a-schema.sh"
```

Prompts:
1. Hidden existing paymesh_demo_user database password from /dev/tty.
2. `NO_PUBLIC_PROXY_OR_TUNNEL`
3. `ACTIVATE_PHASE697_SCHEMA_V11_TO_V14_CHAT_OTP_DISABLED`

Safeguards implemented: private700 config root/600 env files; reject unsafe startup overrides or secret/unknown argv; verify current Java/frontend/Python/LLM executable, working directory, PID/start identity and exactly one loopback listener; verify PostgreSQL16 tools/server, exact paymesh_demo/user/127.0.0.1:5432, successful ordered V1–V11 and matching Flyway CRC32 checksums; JAR source/migration equality V1–V14 and required classes; baseline6/4/4/2/6/4; OTP=false and zero eligibility; new tables absent; preserve account/role/membership/registration/lifecycle and eight financial table contents via exact serialized-row digest comparisons.

A fresh timestamped mode600 custom archive is verified with pg_restore list/extraction and SHA-256 under the existing external backup policy. No test restore is claimed. Data changing during backup stops execution. Backup/evidence never overwrite old files.

Only verified Java and frontend are restarted; explicit Java chat=false, OTP=false and checkout controls=false override external settings. Flyway target14/validate and Hibernate validate are pinned. New link/attempt/conversation tables must initially be empty; all migration checksums, new triggers, original counts and fingerprints must match. AI/LLM PIDs remain unchanged. No login, chat/inference, checkout execution or financial mutation is part of schema activation.

Expected success marker only after all checks:
`SCHEMA_VERIFIED_CHAT_OTP_DISABLED; protected evidence: <new evidence.json path>`.
Failure:
`STOPPED_NO_AUTOMATIC_RESTORE`; inspect private evidence before any next operation.

Chat=false is supported by the reviewed authoritative launch flag; there is no invented public chat-capability API. OTP capabilities are a separate feature and do not prove chat state. Python is not restarted or enabled by schema deployment.

Rollback: stop on migration/startup/integrity failure; never clean/repair/baseline/downgrade blindly. Do not run an old JAR against changed schema. Review actual Flyway state and protected logs, retain archive/failed evidence and repair-forward only after separate approval. An isolated test restore and availability of a matching older artifact are **not verified**; any real restoration needs its own operator review and approval, never restoration over the original database.

## Future AI configuration and service activation

Prepared helper:
`backend/scripts/verify-phase697a-ai.sh` → `phase697a_ai_verify.py`.

It is inert until run interactively. No password/key argument is accepted. It first verifies all four service identities/bindings. Every mode requires its exact confirmation phrase. It uses fixed origins, redirect/proxy refusal, bounded HTTP responses, private mode700/600 sanitized evidence, no raw questions/answers/prompts/tokens. Protected records use a new directory, never historical evidence.

### Stage matching configuration, not activation

After schema success and **separate approval**, run:

```bash
/bin/bash "$HOME/Developer/paymesh-ai/backend/scripts/verify-phase697a-ai.sh" stage-enable
```

Confirm `STAGE_PHASE697_AI_ENABLE_CONFIG_ONLY`, then `NO_PUBLIC_PROXY_OR_TUNNEL`; supply a privately operator-generated high-entropy64–128-character URL-safe shared key through the hidden prompt. No key was generated here. Format validation cannot certify entropy.

Expected `CONFIG_STAGED_ONLY; services unchanged`.
The protected evidence names two new files:
- `java-chat.properties`: enable chat + service-token, force OTP=false.
- `python-chat.env`: enable Python HTTP chat + same service token.

These are **fragments**, not replacements for complete existing demo/investigation configuration. They never restart services or modify tracked files.

### Explicit activation/startup forms — operator launch review required

The protected current Python environment and actual launcher were deliberately not read. Consequently **unattended AI service replacement is not certified by this preparation**. Before any stop/restart the operator must separately approve it, verify fresh identities again, privately establish the complete current launch flags/environment and retain all existing investigation configuration. Do not guess a protected configuration filename, old PID, Qwen path, Java flags or environment. Stop if that review is unavailable.

Exact supported startup forms below are for a reviewed operator-run shell, after only the verified service has stopped and its port is free. Required variables are review outputs, not values fabricated in this report:

```bash
# Set BUNDLE to the protected stage-enable evidence directory.
# AI_CURRENT_ENV is the complete, reviewed current private Python env file.
# JAVA21, REVIEWED_JAVA_FLAGS and REVIEWED_LOCATIONS come from the verified current demo launch.
# Do not echo these values or enable shell tracing.
set +x
umask 077
: "${BUNDLE:?review protected staging evidence}"
: "${AI_CURRENT_ENV:?review complete existing private Python environment}"
# Validate both external files are regular, current-owner, mode600, non-symlinks
# under ~/.config/paymesh-demo before sourcing. Keep old files unchanged.
set -a
source "$AI_CURRENT_ENV" >/dev/null 2>&1
source "$BUNDLE/python-chat.env" >/dev/null 2>&1
set +a
set +x
# Preserve the reviewed existing inference settings; explicit required local overrides:
export PAYMESH_AI_INFERENCE_URL=http://127.0.0.1:8082/v1/chat/completions
export PAYMESH_AI_MODEL_NAME=paymesh-qwen
export PAYMESH_AI_ANALYSIS_MODE=RAG_LLM
export PAYMESH_AI_GENERATION_ENABLED=true
cd "$HOME/Developer/paymesh-ai/ai-service"
.venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --no-access-log
```

Run the Python service using the reviewed existing terminal/supervision/logging policy; this foreground command is intentional. Recheck readiness/listener before approved Java replacement. Java must inherit its own existing protected database/JWT/gateway/session/investigation environment, **not the Python environment above**:

```bash
: "${JAVA21:?review Java21 executable}"
: "${REVIEWED_LOCATIONS:?review complete existing additional locations}"
: "${BUNDLE:?review protected staging evidence}"
(( ${#REVIEWED_JAVA_FLAGS[@]} > 0 )) || { echo 'Reviewed launch flags required'; return 1; }
cd "$HOME/Developer/paymesh-ai/backend"
"$JAVA21" -jar target/paymesh-backend-0.0.1-SNAPSHOT.jar "${REVIEWED_JAVA_FLAGS[@]}" \
  --spring.config.additional-location="$REVIEWED_LOCATIONS,file:$BUNDLE/java-chat.properties" \
  --paymesh.ai.chat.enabled=true --paymesh.demo.password-recovery.enabled=false
```

The reviewed array must exclude the replaced additional-location/chat-enabled flags (no duplicate/secret argv), retain the exact demo datasource, loopback, sessions, Flyway target14, OTP/settlement settings and every unrelated reviewed flag. The token stays in a mode600 file, never argv. Because current launch inputs are intentionally uninspected, these startup forms are **not a substitute for an approved PID-specific service-management procedure**. Do not run them against occupied ports, and do not restart frontend or LLM unnecessarily.

After a successful schema handler reload, later chat flag changes need Java/Python restart only; no schema change or second frontend restart is required. No actual service restart is authorized by this report.

## Exact future verification commands and expected evidence

All helper commands require explicit approval at execution, verify process identities first and perform no database query. Login modes create/revoke a temporary authentication session and create/delete only their own new test conversation. They never reset passwords, create accounts, alter roles, mutate financial data, expose Python through the frontend proxy or retry failed inference automatically.

```bash
/bin/bash "$HOME/Developer/paymesh-ai/backend/scripts/verify-phase697a-ai.sh" health
/bin/bash "$HOME/Developer/paymesh-ai/backend/scripts/verify-phase697a-ai.sh" internal
/bin/bash "$HOME/Developer/paymesh-ai/backend/scripts/verify-phase697a-ai.sh" merchant
/bin/bash "$HOME/Developer/paymesh-ai/backend/scripts/verify-phase697a-ai.sh" admin
```

| Mode | Exact confirmation | Behavior / expected safe marker |
|---|---|---|
|health|VERIFY_PHASE697_HEALTH_ONLY|Java readiness, Python/LLM health, frontend AI routes, payment health, OTP=false → HEALTH_PASS; MODEL_INFERENCE_NOT_VERIFIED|
|internal|VERIFY_PHASE697_PRIVATE_MODEL_INFERENCE|Hidden shared key; wrong-key401, matching-key200, matching correlation, known generation combination/citations → PRIVATE_AUTH_AND_RAG_LLM_SUCCEEDED only for actual SUCCEEDED|
|merchant/admin|VERIFY_PHASE697_AUTHORIZED_CHAT_AND_TEMP_CONVERSATION|Hidden login/password; current ACTIVE single role; opposite role API403; optional authorized Merchant/payment selectors; stateless and payment chat, two saved turns, replay, GET restoration, rename/delete; logout attempt in finally|

The internal probe sends a synthetic knowledge question without real financial evidence. It proves Python private authentication/inference, not Java ownership. Java probes independently exercise real Java authorization and current evidence. Any deterministic/RAG fallback is recorded honestly and does not satisfy the model criterion. Credentials/JWT/refresh cookie remain only in helper memory; cookie goes only to current-session logout. Logout failure is reported, never claimed successful.

Standalone optional health commands (only after approval, no credentials, no inference):

```bash
curl --noproxy '*' --max-time 10 -fsS http://127.0.0.1:18080/actuator/health/readiness
curl --noproxy '*' --max-time 10 -fsS http://127.0.0.1:8000/health
curl --noproxy '*' --max-time 10 -fsS http://127.0.0.1:8082/health
curl --noproxy '*' --max-time 10 -fsS -o /dev/null -w '%{http_code}\n' http://127.0.0.1:5500/merchant/ai
curl --noproxy '*' --max-time 10 -fsS -o /dev/null -w '%{http_code}\n' http://127.0.0.1:5500/admin/ai
```

Java/Python expected status UP; Python explicitly returns modelConnectivity NOT_VERIFIED even when healthy. llama.cpp expected healthy200 (body may vary by reviewed build). Frontend expected200. None is evidence of an actual inference. Do not use curl with passwords/tokens in arguments.

The helper stores only sanitized generation metadata, status checks, conversation/request IDs needed to reconcile and timestamps/services. It does not store answers, money values, credentials, raw prompts or upstream bodies. An uncertain operation stops; do not rerun the entire script to guess success. Inspect the protected conversation/request IDs through the already authorized history UI/GET APIs. Browser cancellation may leave a completed turn; original request ID must be retained. A temporary conversation creation journal legitimately remains after confirmed content deletion.

After Java probes, use the native browser checklist below for A/B ownership, current-session switching and races. The scripted two-turn result plus existing isolated history tests is not an independent capture of live Python history bytes; those are deliberately not logged.

### Deactivation after failed verification

Future exact staging command:

```bash
/bin/bash "$HOME/Developer/paymesh-ai/backend/scripts/verify-phase697a-ai.sh" stage-disable
```

Confirm `STAGE_PHASE697_AI_DISABLE_CONFIG_ONLY`, then `NO_PUBLIC_PROXY_OR_TUNNEL`. No key prompt/read/generation. It creates new disable fragments; existing key files remain protected but unused.

With separate approved current PID/launch review, repeat the supported Python startup form using the disable fragment and Java form with `--paymesh.ai.chat.enabled=false`. Keep existing inference/investigation settings (the investigation can stay RAG_LLM), sessions, OTP=false, schema14 and protected credentials. Do not stop LLM/frontend. Confirm Java chat503 AI_UNAVAILABLE through an authorized existing account and Python internal503 even with no token; do not claim OTP capability is chat capability. If a service is absent or launch inputs are not verified, stop for operator review rather than force-kill/guess/restart repeatedly. No automatic DB restoration, old-schema downgrade, key deletion or account mutation.

## Native browser and retained evidence checklist — pending

- Direct /merchant/ai and /admin/ai navigation/refresh/Back; no AI or empty conversation creation on entry.
- Merchant own overview/payment and Admin platform/Merchant/payment filters; complete datasets, exact separate currencies, no balance/settlement/arrival claims.
- Merchant A/B and two Admin owners: conversations unavailable across owners, including list/message/rename/delete; do not expose another history's existence.
- Fixed-payment Ask AI opens only by explicit action in details/investigation area; payment A→B never mixes history. Existing Investigate Payment remains separate and read-only.
- Multi-turn fresh evidence, reload/search/pagination/restore, historical labels, explicit rename/delete, exact request replay and unknown outcome reconciliation.
- Cancel/New Chat/context replacement/delete/logout during inference ignores stale replies; no assertion that abort cancels inference. No account status mutation merely to test revocation.
- Cross-tab/account/role switch clears all private content; current session invalidation is visible; old no-sid limitations remain documented.
- Keyboard, screen reader/focus, expandable evidence, Copy Answer, safe strings, mobile375px and exact-money rendering.
- Disabled/fallback/capacity/timeout/invalid upstream states: use prior mocked fault evidence or a separately approved isolated fault harness, not unapproved live outage injection.
- Compare all eight financial tables/account-role-membership/lifecycle fingerprints around approved verification. Counts alone are insufficient. Session/conversation changes are expected; preserve actual before/after evidence, never fabricate missing history.
- No checkout payment, refund, link creation, password/security change or Merchant lifecycle transition occurs in AI verification.
- Keep Phase681 dashboard/browser/password/final audit, Phase682/683 activation/native verification, Phase691 actual model compatibility and all Phase673/674 evidence limitations open until actual evidence resolves each item.

## Automated preparation results

Newly executed: **143 mocked operational tests passed**, including24 new readiness/probe/guard/contract-literal tests; complete119 existing operational regression tests included. No Ops live constructors, actual database/service requests, shared credentials or inference were used by these tests. Test stdout containing success-marker strings belongs to mocks, not live evidence.

Bash syntax checks passed for both new wrappers; Python syntax checks passed for both new helpers and their test module. Final git diff --check passed.

Java412, Python AI237 and frontend1558 are previous verified baselines, **not rerun**. Application source, actual chat contracts and frontend code are unchanged; only inactive example fragments, operational preparation/tests and documentation were added. No full application packaging or migration execution was necessary. The literal contract test checks checked-in Java policy/limitations/follow-up data against Python AST constants without importing Python settings or reading .env.

## Changed files

New:
- backend/scripts/activate-phase697a-schema.sh
- backend/scripts/phase697a_schema.py
- backend/scripts/verify-phase697a-ai.sh
- backend/scripts/phase697a_ai_verify.py
- backend/scripts/test_phase697a_readiness.py
- backend/phase697-ai.properties.example
- ai-service/phase697-chat.env.example
- this report

Modified: README.md, PROGRESS.md. Historical scripts/migrations, private evidence/backups/configuration and all application source remain unchanged by this phase.

## Remaining blockers and handoff

- No operator approval or execution evidence for schema/handler deployment, protected service key/configuration, Java/Python activation or native browser/model verification.
- Complete actual private Python launch environment and Java flags were intentionally not inspected; they must be reviewed before their separately approved restarts. Configuration staging/probe helpers do not pretend to solve this missing runtime review.
- Actual loaded Qwen artifact, llama.cpp structured-output compatibility and successful live RAG_LLM timing remain unverified.
- Data-dependent currency/refund/link scenarios may be unavailable in existing records; do not generate records to make a check pass.
- No production security certification: local HTTP shared-key trust, single-process capacity, heuristic accidental-secret screening, legacy no-sid tokens, saved historical evidence, bounded eventual cleanup and backup retention limitations remain.
- Phase697B may execute only separately approved integration procedures and collect authentic evidence. Phase6.10 requires a separate scope decision after integration evidence; no production/deployment/portfolio claim is preapproved here.

## Final preservation check

The503 staged diff blocks captured at Phase697A start remain byte-for-byte unchanged;
no new external staging occurred during this preparation. This preserves the earlier
external additions as part of that baseline; no index mutation command was used.
Final inspected shared working tree:517 entries (223 AM,280 A,14 untracked), not all
attributable to this phase. Historical migrations, activation/verification scripts,
backups and evidence were not modified. No live configuration or secret was read.

The new schema procedure is intentionally one-way from the exact reviewed V11 baseline;
it must stop if V14 is already active. It is not an AI feature-toggle/redeployment script.
The AI staging helper does not restart services. Actual activation remains contingent on
separate approval and the operator's verified protected launch inputs. No successful live
result, unrestricted security certification or closure of a previous gap is asserted.
