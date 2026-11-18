# Phase 6.6 — Final frontend QA and release readiness

Date: November 14, 2026. Scope: audit, existing mocked regressions, read-only runtime checks, three evidence-backed frontend corrections and documentation. No Docker implementation, backend change, financial mutation, service restart or final Git operation.

## 1. Executive summary

The frontend's implemented demo workflows pass the existing **424 checks** (12 proxy tests plus 412 JavaScript assertions). Three focused frontend fixes pass **18 additional QA assertions**. Four actual frontend investigations — SUCCESS, FULL_REFUND, WEBHOOK_RECOVERY and RECONCILIATION_RECOVERY — are **user-reported previous verification**, all COMPLETED/RAG_LLM/SUCCEEDED with matching Java-authorized provenance. They were not rerun by the agent.

`generatedAt` is confirmed to be assigned **before retrieval and model generation**, explaining why it can be close to Java's `collectedAt`. Their difference is not inference time. The frontend now labels this accurately, without changing backend behavior or adding a metric.

**Decision:** the audit is complete and the code is suitable for continued local portfolio/demo development, with manual sign-off pending. This is **not an unconditional production release**. Phase 7 design/feasibility can begin when requested; five-service Docker execution is gated on a compatible free runtime, reviewed container trust boundaries/bootstrap and the manual checks below. Nothing starts automatically.

## 2. Actual tests executed and results

| Suite | Fresh execution | Result |
|---|---|---|
| Proxy | `python3 -m unittest discover -s frontend/tests -v` | 12 passed, 0.581 seconds |
| API client | assets/js/tests.js | 10 assertions passed |
| Authentication/session | assets/js/auth-tests.js | 34 assertions passed |
| Payment creation/processing | assets/js/payment-tests.js | 94 assertions passed |
| Gateway/refunds | assets/js/refund-tests.js | 125 assertions passed |
| Investigation | assets/js/investigation-tests.js | 149 assertions passed |
| New Phase 6.6 regressions | assets/js/qa-tests.js | 18 assertions passed |

The five existing JavaScript suites total 412 assertions; adding the existing 12 proxy tests gives the stated baseline 424. The new 18 are reported separately (430 JavaScript assertions plus 12 proxy tests overall).

JavaScript suites executed as their existing ES modules in the available JavaScript runtime with mocked fetch and minimal DOM/event doubles. The new suite mounts the real details view against native-element fixtures in a browser, or DOM doubles in this runtime. These results establish module/state behavior, not browser layout or screen-reader output. No Node build system, package, dependency or external asset was introduced.

The new HTTP-null regression first **failed before the fix**, with `FAIL: null JSON error preserves HTTP 403`; after correction, all 18 passed. They cover 403/503/401 status preservation for JSON null errors, fixed safe messages, session retention/clearing, actual timestamp preservation and clarified timing label, busy-region placement, fresh refund eligibility and mounted private-details clearing on logout. All existing suites reran green after the fixes.

The in-app browser skill was read and connection attempted; it reported browser unavailable. No new actual desktop/mobile/browser run is claimed. Previous actual-browser results and live scenario results are supplied by the user. No new financial mutation or live investigation was performed. No Java/Python suites or bare Maven commands ran; backend implementation is unchanged. Any later backend changes must use the documented isolated test runner.

Safe reproduction from repository root:

```bash
python3 -m unittest discover -s frontend/tests -v
curl --fail http://127.0.0.1:5500/ -o /dev/null
curl --fail http://127.0.0.1:5500/api/v1/payments/health
```

Reuse the existing server and reload static assets; do not launch a duplicate listener. Browser pages, each in a separate tab, use mocked requests only:

- http://127.0.0.1:5500/assets/js/tests.html — 10 assertions.
- http://127.0.0.1:5500/assets/js/auth-tests.html — 34 assertions.
- http://127.0.0.1:5500/assets/js/payment-tests.html — 94 assertions.
- http://127.0.0.1:5500/assets/js/refund-tests.html — 125 assertions.
- http://127.0.0.1:5500/assets/js/investigation-tests.html — 149 assertions.
- http://127.0.0.1:5500/assets/js/qa-tests.html — 18 assertions.

## 3. Desktop and mobile findings

Static review of current HTML/CSS finds responsive grid breakpoints, a stacked sidebar on small screens, min-width:0 content columns, wrapping UUIDs/technical text, stacked lookup controls below 575px, and one-column definition lists on mobile. Gateway/refund tables have local horizontal scrolling rather than requiring the whole page to scroll. Investigation cards use minmax columns and overflow wrapping, with one column on smaller screens. Password inputs use a compact toggle in the input group. No confirmed layout defect was fixed without a rendered browser reproduction.

**Not verified afresh:** actual 375px/desktop geometry, browser zoom, long-content clipping, touch targets, native validation display and focus visibility under actual rendering. Static CSS inspection is not a substitute for those checks. Precise manual steps are in section 9.

## 4. Accessibility findings

Reviewed semantic main/navigation/section landmarks, skip link, visible labels, native required/pattern constraints, visible button names, password toggle aria-pressed, explicit confirmation controls, keyboard section links, programmatic review focus and 3px focus outlines. Tables have captions, column headers and labeled focusable scroll regions. Loading/empty/error feedback uses role=status and polite live announcements. Investigation elapsed seconds deliberately have aria-live=off; no fake progress percentages are announced. Status text remains meaningful without color.

**Confirmed semantic issue fixed:** details-workspace previously carried aria-busy while containing live loading/error messages. That can defer announcements within the busy ancestor. Busy flags now apply only to overview/history/summary content, leaving live feedback outside those regions. This is a markup/state correction; actual assistive-technology speech behavior still requires manual verification. The new tests assert busy flags during and after a mounted read-only load.

Static sRGB contrast calculations for explicit foreground/background pairs:

| Pair | Ratio |
|---|---:|
| Body #172c48 on #f3f6fb | 13.01:1 |
| Sidebar #cfdaeb on #10233f | 11.15:1 |
| Secondary #6c757d on white | 4.69:1 |
| White button text on #215dcc | 6.00:1 |
| Success #20543f on #e7f3ee | 7.68:1 |
| Inconclusive #765410 on #fff4da | 6.31:1 |
| Failure #893a23 on #fff0eb | 7.02:1 |

These sampled pairs exceed 4.5:1 for normal text. This is not a complete WCAG audit of computed styles, opacity, focus states, screenshots or all combinations. Keyboard/screen-reader/native browser behavior remains pending.

## 5. Security and privacy findings

- Tokens remain in module memory only, with 15-minute expiry, focus/visibility checks and versioned sessions. Refresh loses authentication. Client logout clears local UI/token state, not server JWT revocation; Java still validates current account/roles/membership.
- Source review found no localStorage, sessionStorage, IndexedDB, unsafe HTML insertion, console logging or extra direct-network channel in frontend modules. All API/AI text uses safe DOM nodes; knowledge source strings are not links. A high-confidence scan of frontend files and root documentation found no embedded private-key blocks or literal JWT credentials. No frontend symlinks were present. This scoped scan is not a full repository/history secret audit or proof that every historical terminal log is secret-free.
- Same-origin proxy remains literal-loopback-only, with Host/Origin/path checks, exact route/method allowlist, 4096-byte login and 16384-byte other request limits, no GET bodies, framing checks, 512 KiB response cap, fixed Java target, no redirects and no arbitrary URL forwarding. Only the existing approved request/response headers cross it.
- Runtime HTML headers were read: Cache-Control no-store, CSP self-only script/style/connect with frame-ancestors none, base-uri none and form-action self, nosniff and no-referrer remain in place. No broad CORS was added. Python/LLM, settlement-token/signing and sensitive actuator paths remain absent from the browser allowlist.
- Java source/API catalog remains the authorization boundary. 401 clears current private state, 403 retains session but denies action, 404 conceals resource existence. Late 401 cannot clear a replacement session. Prior user-reported Merchant A → Merchant B lookup denial and Merchant B positive access were not rerun with live credentials.
- Financial mutations require explicit reviews, stable in-memory idempotency intent/key and duplicate guards. Uncertain results do not mean failure; exact retries are deliberate only. BigInt refund totals and complete-history eligibility remain unchanged. The agent issued no live create/process/refund/reconcile/webhook/settlement request.
- Investigation is explicit and bodyless, using Java only. All supported statuses/scenarios, actual generation modes, separate certainty labels, provenance, unavailable evidence and limitations remain rendered from validated responses. Refresh/selection/session changes clear historical results. Timeout does not imply server cancellation; no automatic investigation or mutation retry was introduced.

**Confirmed HTTP error bug fixed:** JSON null on a non-2xx response caused `data.fieldErrors` access to throw, losing the real status as a generic network error. Optional field access preserves 401/403/503 while keeping fixed messages and 401 clearing. No security policy or endpoint changed.

The development server is thread-per-request and HTTP-only with shared proxy-IP login rate limiting; it is not internet-facing production infrastructure. Those remain deployment limits, not reasons to weaken current controls.

## 6. AI timestamps and inference timing

Actual source order:

1. Java EvidenceCollector reads authorized evidence in its read-only snapshot transaction, then assigns `collectedAt` near the **end** of collection, validates evidence and returns the detached snapshot.
2. Java invokes Python after releasing the database transaction.
3. Python `rag_service.enrich()` first calls deterministic `investigation_service.investigate()`.
4. That function constructs InvestigationResponse and assigns `generated_at=datetime.now(timezone.utc)` **before returning to enrich**.
5. Enrich performs TF-IDF retrieval, builds the constrained prompt, calls LocalHTTPProvider, validates the wording selection and updates approved text/mode/status on the same result. It does **not** replace generated_at afterward.

Therefore generatedAt means **deterministic analysis prepared time**, not LLM completion, HTTP completion, retrieval duration or evidence-collection start. `generatedAt − collectedAt` does not measure inference and cannot be used to conclude that generation was skipped or cached. Both timestamps being close is consistent with the actual implementation. No backend timestamp semantics or AI behavior were changed for QA.

The frontend now labels the field `Analysis prepared at (generatedAt)` and explicitly says it precedes retrieval/LLM generation. The exact returned timestamp is preserved. Browser elapsed time is request-wait time, not model-only inference. The local LLM selects approved wording variants and echoes the deterministic scenario; financial classification, amounts, refund limits, authorization, certainty and recommended actions remain constrained by deterministic logic. The custom local retriever is TF-IDF cosine retrieval over the curated corpus, not a paid embedding service.

Existing instrumentation and available logs:

- Production LocalHTTPProvider requests a bounded local chat completion, parses content/finish_reason and discards upstream usage/timings. Neither Java nor Python's normal response supplies a dedicated inference-duration metric.
- `ai-service/scripts/diagnose_llm.py` is an opt-in synthetic diagnostic with perf_counter and HTTP response hooks capturing usage/timings. It can also write full prompts/responses and make direct Python/LLM calls. **It was inspected, not run**; it is unsuitable for casually logging real financial evidence and is outside this QA's live-call scope.
- Phase 5.3B documents historical prompt-evaluation/generation/direct-wall/HTTP-wall samples and caching caveats. Phase 5.4 records historical end-to-end investigations. Those are different runs and not new measurements of the four recent user investigations.
- Current Java/Python/llama stdout and stderr resolve to existing terminal devices (ttys006/ttys005/ttys003), not identified persistent log files. Terminal contents, environment variables, prompts and raw evidence were not read. There is no fresh recoverable per-request inference duration from these checks. Public health does not measure inference.

Safe future manual procedure, without sharing credentials:

1. Use the existing frontend login privately. If an investigation result remains on-screen, record only its nonsensitive scenario/mode/status and timestamps before refresh; do not rerun simply to fabricate a metric.
2. If a new timing observation is desired, run one explicitly authorized, read-only investigation through the frontend, serially. In browser DevTools Network, inspect only the request's Timing pane/total duration. Do not copy Authorization headers, Copy as cURL, export a HAR, or paste credentials/tokens into chat.
3. That number is **total browser HTTP time**. It includes transport and server waiting for Java authorization/evidence collection, deterministic analysis, retrieval, model work and server-side validation. Network timing ends with response receipt; it excludes subsequent frontend rendering. The UI elapsed indicator has application-side boundaries and one-second granularity. Neither is model-only inference duration.
4. If existing llama.cpp terminal output exposes performance summaries for that same isolated request, the operator may record numeric prompt-evaluation and token-generation timings/counts only, omitting prompts/request bodies and unrelated records. Prompt evaluation and output generation are distinct; warm prefix cache can reduce evaluated prompt work. If no unambiguous existing summary is available, report model-only duration unavailable.
5. Do not stop/restart services, enable verbose prompt logging, change generation settings, access Python/LLM directly, or add a new backend metric for this phase. Exact per-request correlation is not guaranteed by the current response contract.

## 7. Issues found and fixes applied

| Issue | Evidence | Resolution |
|---|---|---|
| Ambiguous generatedAt completion interpretation | Timestamp construction precedes enrich/retrieval/provider call | Accurate frontend label and timing note; exact value unchanged |
| Busy ancestor covers live details messages | details-workspace aria-busy enclosed status regions | Move busy state onto content regions; keep live status outside |
| Null JSON error loses HTTP status | New regression failed before fix with HTTP 403 becoming status 0 | Null-safe fieldErrors access; 401/403/503 regressions pass |
| Root status documentation still says frontend not begun | Current README/PROGRESS text contradicted implemented phases | Minimal current-status updates, retaining historical backend results and planning notes |

No speculative layout rewrite, backend change, new runtime metric or Docker implementation was made. No financial defect requiring a new live mutation was found in this QA.

## 8. Changed files and reasons

- frontend/assets/js/api/client.js — preserve status on JSON-null errors.
- frontend/assets/js/investigation/render.js — clarify generatedAt without changing the API.
- frontend/assets/js/features/refunds-view.js — correct busy-region placement.
- frontend/assets/js/qa-tests.html and qa-tests.js — 18 separate mocked QA regressions.
- frontend/PHASE-6.6-FINAL-QA-REPORT.md — this report.
- frontend/README.md — QA/test URLs, timing semantics, remaining sign-off and Phase 7 gate.
- Root README.md and PROGRESS.md — current frontend QA status correction only; earlier backend verification remains historical.

No existing test count was inflated or silently replaced. Historical phase reports were not rewritten. Existing frontend/backend staged and unstaged edits were retained.

## 9. Manual checks still pending

The user reports the four real investigations passed, but **post-investigation refresh and logout still require explicit actual-browser confirmation**. An asynchronous question requested that confirmation; none had been received when this report was prepared. Mocked clearing tests passing do not substitute for that confirmation.

Use the existing server; no new financial mutations are needed:

1. If a live investigation result is still displayed, note selected UUID/scenario/mode/status and actual observed payment status. Select Refresh payment & refunds. Confirm the historical AI result clears, no new investigation starts, and the payment/refund data are unchanged. If the session/result was already lost, verify with the mocked investigation page or schedule one separately authorized read-only investigation; do not create a payment to obtain a result.
2. Expected unchanged records: USD `842b460e-2451-4294-abc7-62c5525bc180` SUCCESS/25.00/no refunds; INR `96829409-bb1a-4f82-b113-4bc9694bd2c0` REFUNDED/500.00 with 200.00 + 300.00 refunds and remaining 0.00; webhook payment `c072351f-4646-4288-b8ca-6758d4e521f3` SUCCESS; Merchant B `c6f797c0-c810-4730-bac2-19cb8504a87d` SUCCESS. Only inspect records authorized to the current account. Do not click financial confirmation controls.
3. Sign out. Confirm login appears, password/identity/private details/history/AI text clear, Back/hash navigation cannot redisplay them and reload requires sign-in. Sign in under another account only through the normal form, never by sharing tokens. Merchant A must still receive generic inaccessible/not-found for Merchant B.
4. At desktop width (~1440px) and DevTools responsive width **375px**, inspect sidebar/navigation, login toggle, all form labels, exact amount fields, long UUIDs, overview definition lists, history regions and long AI text/references. Horizontal scrolling must stay inside tables; page text/cards must wrap. Also inspect at 200% zoom. A visual pass cannot be inferred from CSS alone.
5. Use Tab/Shift-Tab/Enter/Space without a mouse: skip link, login/toggle, nav, lookup, details links, focusable table regions and read-only investigation entry. Confirm visible focus and sensible order. Unsubmitted financial forms can be inspected without confirming, but canceled intents must be cleared before investigation. Do not perform new payment/refund/processing actions.
6. With VoiceOver or another already available screen reader, verify username/password names, required/native errors, disabled states, review focus, loading/error/result status messages and separate certainty labels. Loading messages should now announce outside busy content. Check no color-only meaning or invented progress.
7. Use the mocked pages for invalid credentials, 429, 401/403/404, unavailable histories, all AI lifecycles, failed/fallback analysis, duplicate protection and late responses. Do not stop live services or flood live login to reproduce errors. Verify session expiry by waiting until the shown expiry and returning focus; no clock/security configuration change is required.
8. Open the six test URLs from section 2 in the actual browser after reloading and confirm each fresh PASS count. Record actual browser results separately from runtime test results. Do not rerun earlier mutation runbooks against already refunded payments.

## 10. Current service status

| Service | Listener before/after QA | Public read-only result |
|---|---|---|
| Frontend | 127.0.0.1:5500, PID 85275 | HTML/new QA page 200; security headers retained |
| Java | 127.0.0.1:18080, PID 83515 | proxied payment health RUNNING; direct readiness UP |
| Python | 127.0.0.1:8000, PID 80995 | UP, configured RAG_LLM; modelConnectivity NOT_VERIFIED |
| llama.cpp | 127.0.0.1:8082, PID 79855 | status ok |

No existing service was stopped or restarted; no original port 8080 request or direct database connection occurred. Health checks establish availability at observation time, not a new live inference benchmark or production readiness.

## 11. Git and preservation observations

Initial status and staged/unstaged binary diffs were captured read-only under /tmp before edits. The repository already contained extensive staged and unstaged work. Initial index SHA-256: `d5ca729e656e3380db23a425ab1d97d94bc7bbb03137749f9f2eca099be90620`. Initial staged binary diff SHA-256: `a064ce9b342c4f1f37431f7e69124e629c1303e650c631c01907e8f3f82685bb`.

No git add/commit/push/reset/clean, index restoration or service-control command was issued. Root documentation was edited only in its current-status blocks, after saving original bytes for audit; historical results/checklists were preserved. Final hash/diff observations are recorded at the end of this report. A concurrent external staging update, if observed, must be left untouched rather than overwritten to force matching hashes.

## 12. Known production limitations

This remains a local simulated portfolio platform, not real provider/bank integration or production certification. Open limitations include: development-only HTTP proxy, no production ingress/TLS/rate-limit infrastructure, memory-only JWT/recovery intents, shared proxy-IP login limits, no refresh/profile/list/aggregate APIs, uncertain-intent loss on browser reload, separate HTTP refund snapshots rather than an atomic summary/version API, unsupported evidence/size limits, one AI request per Java process, unverified bank outcomes, no distributed orchestration/observability guarantees and no new exact inference metric. Existing backend docs also identify non-demo account bootstrap, migration/runtime database privileges and deployment hardening as future work. No vulnerabilities/CVE audit of existing image tags or full historical secret scan was performed.

## 13. Release readiness decision

**Local demo/frontend development:** conditional GO. Implemented flows and all fresh mocked regressions pass; user-supplied live investigations support integration behavior. The three confirmed QA issues are corrected.

**Final public/production release:** NO-GO. Actual responsive/accessibility sign-off and explicit live refresh/logout confirmation remain open, and production deployment/security limits above remain. Documentation distinguishes supplied live checks, fresh runtime checks and pending checks.

**Phase 7:** GO for requested architecture/feasibility planning, not automatic launch. Five-service execution must wait for a compatible free runtime, isolated new database/account bootstrap, reviewed container-specific origin/trust configuration and a resource/cutover plan. No final Git action, paid product or Docker implementation was started in Phase 6.6.

## 14. Exact prerequisites for Phase 7 Dockerization — planning only

### Existing configuration inventory

Only backend/Dockerfile and backend/compose.yaml plus compose.demo.yaml exist for container work. Dockerfile uses a Maven/Temurin 21 multi-stage build with tests skipped during image packaging and UID 10001 runtime. The normal Compose file supplies PostgreSQL 16.16 plus Java, a dedicated named volume, external environment/key mounts, loopback host Java port 18081 and disabled scheduler/demo fault settings. The demo Compose file is database-only, with a separate named volume and loopback port 15432. Neither is a working authenticated five-service stack. No frontend/Python/LLM container definition was found. No build, pull, Docker command, Compose startup or volume operation ran.

No docker, colima, limactl, podman or qemu-system-x86_64 executable was found on the current PATH. This does not prove there is no unrelated application outside PATH; it does establish that no usable CLI was verified.

### Free host/runtime gate

Use only open-source components or a verified genuinely free eligible tier, with no paid cloud dependency. Current Docker Desktop docs support the current and two previous major macOS releases; current Colima documentation explicitly requires macOS 13+, with source builds on older macOS only a possibility. **Do not assume either current binary supports Monterey 12.7.6.** See [official Docker Mac requirements](https://docs.docker.com/desktop/setup/install/mac-install/) and [official Colima installation requirements](https://github.com/abiosoft/colima/blob/main/skills/references/install.md).

A free Linux Engine/Compose environment or a verified compatible open-source Linux VM toolchain is a prerequisite. Investigate Intel/QEMU compatibility for this host; do not promise that a legacy or source-built Colima/Lima/QEMU combination is supported or secure without testing it. [Lima's QEMU documentation](https://lima-vm.io/docs/config/vmtype/qemu/) describes the driver and QEMU requirements; it is not a guarantee of a supported current Monterey binary. An already available compatible Linux host is another option, not an assumption that new hardware or a paid VM is free. Do not install obsolete Docker Desktop as an unreviewed workaround. No runtime was installed in this phase.

### Proposed five-service topology

| Service | Planned responsibility | Exposure/data |
|---|---|---|
| frontend | Local static assets and narrow Java business gateway | Only loopback host entry by default; preserve Host/Origin/path/method/header/body/response limits and CSP |
| backend | Java 21 authorization and payment/evidence API | Internal app/db/evidence networks; optional separate loopback debug port only if reviewed |
| ai-service | Python FastAPI, local TF-IDF corpus and constrained generation | Internal only, Java access; no browser/host public port |
| db | Dedicated PostgreSQL/Flyway database | New project-scoped persistent volume; no reuse of original paymesh_db or current demo volume |
| llm | CPU llama.cpp plus approved quantized Qwen model | Internal only, Python access; model mounted read-only outside image |

Plan separate app (frontend/Java), db (Java/Postgres), evidence (Java/Python) and inference (Python/LLM) networks as appropriate. Only the intended neighbors should communicate; do not publish AI/LLM/Postgres ports by default. Choose new host ports/project names avoiding all current services and original port 8080; e.g. future frontend 5501 and optional Java 18081, subject to availability. Do not reuse host 5432. Internal container port 8080 is not the original host application, but must not be published on original host port 8080.

### Security/configuration gate — explicit design required

Current frontend server binds 127.0.0.1, validates literal Host/Origin against its listening port and targets Java 127.0.0.1:18080. Java's AI client accepts literal IPv4 loopback only. Python validates a loopback-IP inference URL, and defaults to loopback binding. Separate containers cannot reach each other through their own 127.0.0.1. Account provisioners also enforce a guarded loopback demo database. The existing normal Compose database has no provisioned ADMIN/merchant workflow.

Therefore Phase 7 needs an **explicitly reviewed, opt-in container-specific configuration and tests**, not CORS wildcards, arbitrary proxy targets or disabled guards. Scope service-name/port/origin allowlists to the isolated deployment; keep existing host defaults and negative validation tests intact. Internal Python/LLM trust must be reviewed with network isolation or explicit authentication as needed. Do not use host networking, broad URLs or edited host secrets to pretend existing loopback validation is container-ready. Any necessary Java/Python container support is separate approved Phase 7 work; none is implemented here.

### Secrets, initialization and persistence gate

Generate new deployment secrets outside the repository/image/build context; use read-only key/secret mounts or reviewed file-based consumption. Compose environment substitution alone is not equivalent to an orchestrator secret store. Do not copy existing passwords, JWT keys, HMAC material, settlement tokens or databases into a new stack. Keep settlement/signing endpoints off the frontend gateway. Plan least-privilege migration/runtime identities.

Use a fresh dedicated PostgreSQL database/user/volume and reviewed Flyway V1–V8 initialization. Define an explicit guarded offline container account bootstrap (ADMIN, merchant registry and memberships) with synthetic accounts; current loopback-only provisioners cannot simply be assumed to work against `db`. Do not bypass authorization or hand-edit current financial records. Validate persistence/restart/recovery on the new volume only; never use down -v on existing volumes. Model files need a separate read-only mount, recorded source/license/checksum and no download on every startup. Confirm the exact Qwen artifact's license before redistribution.

### Intel/8 GB resource and build gate

Use native linux/amd64 images/builds and CPU inference, not ARM emulation, CUDA or a Metal-in-Linux assumption. Pin an actually tested llama.cpp revision compatible with the current structured response_format contract (existing code notes b4514 behavior) and model alias/artifact. Keep one inference slot and a small CPU thread budget; retain or explicitly validate the tested context/output limits instead of silently truncating prompts.

Initial profiling budget proposal, **not measured or guaranteed**: frontend 64–128 MiB, Java ~640–1024 MiB RSS with bounded heap, Python 256–384 MiB, PostgreSQL 256–384 MiB, llama.cpp ~768–1536 MiB depending on model/KV context. A ~4 GiB Linux VM may leave host room only with a carefully agreed cutover; running duplicate host and container Java/Python/LLM stacks simultaneously on 8 GB risks pressure/swap. Measure disk availability/build cache and image/model footprint before pulls. Build sequentially and avoid heavy extra services, Kubernetes, vector databases or paid infrastructure. Agree any later cutover/service stop separately; current services stay running now.

### Health, reproducibility and acceptance gate

Define cheap health checks: PostgreSQL readiness; Java minimal actuator readiness (without leaking details); Python health reporting its actual model-connectivity limitations; llama.cpp health; frontend static/proxy availability. Do not run inference repeatedly as a health probe. Health dependencies help startup order but do not replace runtime error handling, busy admission or retries policy.

Before Phase 7 execution, record exact free runtime/versions, base-image architecture/digests/licenses, model revision/checksum, network/origin and timeout design, secret ownership, account bootstrap, new volumes/ports, memory/disk budget and rollback plan. Later container changes need isolated backend/security tests, current frontend regressions and explicitly authorized smoke checks on synthetic container data. Final manual frontend QA and refresh/logout confirmation remain release gates. No Docker implementation begins automatically from this report.

### Final preservation result

Final observed index SHA-256: `d5ca729e656e3380db23a425ab1d97d94bc7bbb03137749f9f2eca099be90620`.
Final observed staged binary diff SHA-256: `a064ce9b342c4f1f37431f7e69124e629c1303e650c631c01907e8f3f82685bb`.
Both match the initial observations; no concurrent staging change was detected. Non-frontend/non-status-document tracked working changes matched the initial binary diff. The original README/PROGRESS historical verification tails were compared byte-for-text and remained unchanged. Service PIDs matched all four initial listeners. No index restoration, financial write, backend change, Docker operation or restart occurred.

Phase 6.6 audit is complete with the explicitly listed manual sign-off and Phase 7 feasibility/security gates remaining. No next phase was started.
