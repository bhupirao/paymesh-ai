# Phase 6.7.3 — Persistent sessions and explicitly insecure local-demo recovery

## Scope and operational boundary

One coordinated backend/frontend batch: server-managed rotating refresh credentials, Remember Me, restoration, logout/current/all, and the requested on-screen OTP UX. No V10/live eligibility/live password operation or service restart is authorized or performed. No original paymesh_db/8080 access, financial business-logic change, Python AI change, email/SMS/SMTP/Mailpit, paid tool or Docker implementation.

Phase 6.7.2 closeout was appended to both reports using the operator's supplied evidence: 244 Java / 562 frontend checks; six browser checks; V9 active; signup/pending/active login working; counts 4 users, 3 merchants, 3 memberships, 1 registration, 6 payments, 4 refunds; admin authorization version 0→1 and recovery audit. None was independently rerun live.

## Implementation design and contracts

Existing credential verification, BCrypt configuration, 15-minute JWT issuance, database authorization-version/role/status checks, account-administration advisory lock, transactional audit and narrow proxy are reused. JDBC authentication tables use the validated server-side Hibernate schema prefix (public by default, isolated test schema in tests), never a request-provided table/schema. JDBC/JPA writes share the Spring transaction.

### Persistent sessions

`POST /api/v1/auth/login` retains login/password and its exact accessToken/tokenType/expiresIn/expiresAt envelope; optional rememberMe defaults false. Browser login with the approved Origin and `X-PayMesh-CSRF: 1` creates a session, revokes the replaced browser cookie family and sets `pm_refresh`. Legacy non-browser requests without Origin retain JWT-only behavior and receive no cookie, preserving compatibility without enabling login CSRF.

Access JWTs carry sid (session UUID), existing roles/account_status and authorization_version. The validator checks the live family on each JWT authentication. Tokens without sid retain existing role/status/version checks and their 15-minute expiry; they cannot be associated with a particular newly created cookie family. Logout All/password change invalidates such legacy tokens through authorization_version.

`POST /api/v1/auth/refresh`: no body or bearer required; uses only HttpOnly cookie and strict browser policy. Success rotates a fresh 256-bit opaque credential, marks its predecessor used and retains the family absolute expiry. Only SHA-256 digests are stored; rotated digests remain for replay detection. Any used token replay revokes the entire family, including access JWT authorization. The failure return is committed, rather than thrown through a rollback that would undo revocation. Concurrent direct replay fails closed; frontend single flight and browser Web Locks serialize legitimate refresh/login/logout across tabs.

`POST /api/v1/auth/logout`: idempotently revokes the presented cookie family and expires its cookie. `POST /api/v1/auth/logout-all`: requires a valid current refresh credential, increments account authorization_version and revokes all families. Both reject absent/mismatched Origin/CSRF. Logout clears private frontend state immediately; if network confirmation fails, UI explicitly says server logout could not be confirmed, without claiming remote revocation.

Remember Me: persistent cookie, default 30-day absolute / 7-day refresh-idle lifetime. Without Remember Me: browser-session cookie, 8-hour absolute/idle lifetime. Configuration permits bounded shorter values via paymesh.sessions.remember-seconds, short-seconds, idle-seconds, remember-idle-seconds. Idle means time since successful authentication refresh; background refresh counts as activity, not proof of human presence. Absolute expiry never slides. Cleanup is bounded (100 old expired families per new login); no background financial scheduler is introduced.

Cookie: pm_refresh, HttpOnly, SameSite=Strict, Path=/api/v1/auth, no Domain. Secure is mandatory by default. `paymesh.sessions.origin` must be a literal HTTPS origin. Local HTTP requires explicit `paymesh.sessions.local-http=true`, demo/development profile, server.address=127.0.0.1, server.port=18080 and exact origin http://127.0.0.1:5500. Defaults do not silently allow HTTP. Authentication controller browser policy requires one exact Origin and the non-simple CSRF header; no wildcard CORS or forwarded-origin trust is introduced. Origin-less login remains JWT-only; origin-less refresh/logout/recovery is denied.

V10 triggers revoke sessions/challenges/reset grants atomically on account authorization-version/enabled/status changes and role changes. This preserves the unchanged offline admin recovery command: it already updates authorization_version, so its transaction also revokes all new credentials after V10. Pending sessions restore but retain no financial authorities. Disabled users, status/role/version changes and expiry reject refresh.

### On-screen recovery is NOT identity verification

Displaying an OTP to its requester does not establish ownership. This is explicitly insecure, local-only UX demonstration for disposable operator-designated accounts, not public account recovery.

`GET /api/v1/auth/password/capabilities`: no-store `{localDemoEnabled:false}` by default. The frontend displays no OTP controls when disabled.

`POST /api/v1/auth/password/forgot`: `{identity,portal}`; portal ADMIN or MERCHANT. When eligible, returns `{challengeId,otp,expiresAt,resendAfterSeconds:60}`. Unknown/ineligible requests return the same envelope with otp=null and an unpersisted random challenge; frontend gives generic unavailable feedback. Within this explicitly insecure enabled flow, an actual displayed code necessarily reveals eligibility; no enumeration-resistance claim is made. No response body/OTP is logged.

`POST /api/v1/auth/password/verify-otp`: `{challengeId,portal,otp}`. Five-minute, six-digit SecureRandom code; keyed HMAC-SHA256 with challenge/purpose/portal binding, stored only as digest; five failed guesses maximum. Verification is single-use and returns `{resetAuthorization,expiresIn:300}`. Resend requires 60 seconds and invalidates all prior challenges/grants. Account limit: five generations per ten minutes. Bounded requester budget: twenty recovery operations per ten minutes, max 1024 requester entries, based on the direct remote address, never X-Forwarded-For. All loopback proxy users share the conservative budget.

`POST /api/v1/auth/password/reset`: `{challengeId,portal,resetAuthorization,password,confirmPassword}`. 256-bit opaque authorization, digest-only, five-minute lifetime, single-use and bound to challenge/account/portal/purpose. Existing password validation is unchanged: minimum 12 Unicode code points, maximum 72 UTF-8 bytes, matching confirmation, no NUL/malformed Unicode. The account lock, current eligibility/roles/enabled/version checks, grant consumption, hash update, authorization invalidation, session/challenge revocation and success audit share one transaction. Any failure rolls back all changes. Pending remains pending, active remains active, identity/roles/memberships/financial data remain unchanged.

Audit LOCAL_DEMO_PASSWORD_RESET has null authenticated actor fields and source insecure_local_demo_on_screen_otp. It does not fabricate an administrator actor. Role isolation requires exactly one corresponding role: mixed ADMIN+MERCHANT accounts are denied this recovery flow. No automatic sign-in or OTP verification occurs.

### Gate requirements (ALL required; no live configuration performed)

- Flag paymesh.demo.password-recovery.enabled=true (default false).
- Exactly demo profile; no production/cloud/development/mixed profiles.
- Literal database jdbc:postgresql://127.0.0.1:5432/paymesh_demo and paymesh_demo_user; actual JDBC metadata/database/user/host/port verified. Uses corrected host(inet_server_addr()).
- Configured server.address=127.0.0.1 and port18080; actual Tomcat connectors must all have that address/port. Unknown servers/connectors fail closed. Enabled state remains false until actual server binding is verified.
- Exact local browser origin and explicit local HTTP cookie setting; forwarding strategy none; no TLS/public origin configuration for this demonstration.
- Explicit operator confirmation property NO_PUBLIC_PROXY_OR_TUNNEL; operator must not expose localhost through a public proxy/tunnel. Host headers alone cannot enable the feature. HTTP operations also check actual local/remote loopback addresses/port and reject Forwarded/X-Forwarded-For.
- Private high-entropy recovery digest key, at least 64 characters, supplied privately via paymesh.demo.password-recovery.key; no default key and no generated/printed live key here.
- Explicit enabled row in demo_recovery_eligibility for that account and exact portal, with designated_by and review_reference. The empty table is the operator-controlled opt-in mechanism; there is no public enrollment or approval API and no role-wide seed. Public registrations never become eligible automatically.

Unsafe configured enablement fails during startup configuration checking; actual database/connector validation is independent. Loopback binding and header checks cannot detect every possible OS-level port-forwarding arrangement: the operator attestation/private deployment is a required custody condition, not a claim to detect arbitrary tunnels.

## Frontend/proxy

Eight explicit SPA routes preserve the original six plus /merchant/forgot-password and /admin/forgot-password. Both portal login contexts share the existing form, Remember Me and Forgot Password controls. Recovery shows identify → displayed runtime OTP/manual entry/countdown/resend → new password/confirmation/toggle → success/correct login link. Local Demo Only warning remains visible. Native labels, busy controls, status announcements, focus on transitions and responsive Bootstrap layout are retained.

Recovery state is memory-only, reset on route leave/restart/session replacement/expiry/terminal errors/success. No automatic generation/verification/sign-in/retry. Password fields clear on submission. API/AI text uses safe text rendering. Existing payment/refund/investigation workflows are unchanged.

Session startup restoration and automatic pre-expiry refresh use a single-flight manager. Same-family token renewal does not increment the frontend private-operation version or notify financial-state resets, preserving uncertain creation/refund intent recovery. Replaced sessions/logout still invalidate versions. Cookie operations serialize with browser Web Locks; BroadcastChannel clears other tabs on logout/session replacement. Browsers without Web Locks do not perform automatic restoration/refresh (manual sign-in still works) rather than risking parallel-cookie replay. Access tokens never enter localStorage/sessionStorage/IndexedDB. No financial mutation is retried after authentication refresh or 401.

The proxy keeps a fixed Java upstream, strict Host/Origin/path/method/body/response limits and existing CSP/no-store. Only exact new auth routes are added. Only pm_refresh is forwarded, only on login/refresh/logout/logout-all; other cookies, duplicates/malformed cookie values and forwarded identity headers are denied or stripped. Set-Cookie forwarding is limited to that name, exact path, HttpOnly, SameSite Strict and no Domain. Browser credentials stay omitted on business/recovery requests. Cookie-authenticated mutations require Origin and X-PayMesh-CSRF at both proxy and Java boundaries. No Python/LLM/settlement/webhook path is added.

## Tests and results

Implementation and test-writing precede full suite execution. Compilation during implementation is explicitly not counted as testing. Actual results will be recorded after final runs. Java tests use only `cd backend && bash scripts/test-isolated.sh`, never a live demo database or bare Maven tests. Frontend proxy tests use ephemeral loopback servers/mocked upstream; JS pages use mocked fetch. No live OTP/session/reset experiment is permitted in this phase.

## Activation prerequisites — planning only

V10 must be reviewed/applied through a separately approved startup and protected backup procedure. Cookie origin/local exception must be explicitly configured before browser login/restoration; otherwise refresh and browser-origin login fail closed while legacy non-browser JWT login remains backward compatible. Restarting the frontend is necessary to load its new auth proxy routes/cookie handling; static changes alone do not activate them. Python/LLM need no changes/restart.

OTP enablement is a separate, explicitly insecure opt-in after migration. The operator must approve a private loopback-only deployment, privately supply a fresh high-entropy key and designate disposable account UUIDs with exact portal and administrator/review metadata in the empty eligibility table through an independently authorized administrative database procedure. No such rows, keys or approvals are created here. Do not enable this feature in public cloud/Docker/production or reset a non-disposable account. Real public recovery requires a separately designed ownership-proof channel; the on-screen code is not that channel.

Manual URLs after approved activation: http://127.0.0.1:5500/merchant/login, /admin/login, /merchant/forgot-password, /admin/forgot-password, and /assets/js/session-recovery-tests.html. Use disposable designated accounts only, verify cookie flags/rotation/restoration/current/all logout/old-token denial, then manually type the displayed OTP and reset a disposable password only with explicit approval. Verify pending restrictions and unchanged financial counts. No actual browser/live activation is claimed by this implementation report.

## Files created and modified

Created backend:

- `src/main/resources/db/migration/V10__persistent_sessions_and_local_demo_recovery.sql`.
- Accounts: `AuthStore.java`, `AuthenticationClock.java`, `PersistentSessions.java`, `LocalDemoRecoveryGate.java`, `LocalPasswordRecovery.java`.
- Auth: `AuthBrowserPolicy.java`, `SessionController.java`, `PasswordRecoveryController.java`.
- Isolated tests: `SessionRecoveryIntegrationTest.java` (20 methods), `SessionRecoverySafetyTest.java` (5 methods).

Modified backend auth/security integration: `AuthController.java`, `JwtTokenService.java`, `JwtAccountValidator.java`, `JwtConfiguration.java`, `JwtSecurityConfiguration.java`, `LoginRateLimitFilter.java`, `BoundedRequestBodyFilter.java`, `AccountAudit.java`. Existing password policy, offline recovery command/guard/transaction, historical migrations, financial services and dependencies were not modified. `API-REFERENCE.md` documents the new contracts.

Created frontend: `assets/js/auth/persistence.js`, `recovery.js`, `recovery-view.js`; `assets/js/session-recovery-tests.html` and `.js`; `tests/test_auth_session_proxy.py`; this report.

Modified frontend: `index.html`, `assets/js/app.js`, `auth/session.js`, `api/client.js`, `api/config.js`, `features/workspace.js`, `portals/router.js`, `portals/view.js`, `portal-tests.js`, `tests/test_portal_routes.py`, `dev_server.py`, `README.md`. Portal test counts changed from six to eight routes while retaining every original assertion. Logout network feedback remains visible on the login screen with an explicit finish-signing-out action.

Documentation: appended operator closeout to Phase 6.7.2 merchant/admin-recovery reports; appended current status to root README/PROGRESS without removing earlier historical content.

## Executed verification — final results

| Suite | Actual result |
| --- | --- |
| Complete isolated Java runner | **269 tests passed**, 0 failures/errors/skips |
| Existing Java baseline | 244 tests retained |
| New Java session/recovery coverage | 25 tests (20 integration + 5 safety) |
| Python proxy/static routes | **25 tests passed**, 1.707 seconds on final run |
| API client JS | 10 assertions passed |
| Authentication JS | 34 assertions passed |
| Payment JS | 94 assertions passed |
| Gateway/refund JS | 125 assertions passed |
| Investigation JS | 149 assertions passed |
| Phase 6.6 QA JS | 18 assertions passed |
| Portal JS | 73 assertions passed |
| Registration JS | 39 assertions passed |
| New session/recovery JS | **67 assertions passed** |
| JavaScript total | **609 assertions passed** |
| Frontend total | **634 checks passed** (25 Python + 609 JS) |
| Maven packaging | BUILD SUCCESS, 6.899 seconds |
| git diff --check | Passed |

The previous 562 frontend checks remain covered, plus 5 new proxy tests and 67 new JS assertions. No tests were removed/skipped to obtain these totals. Java's final full run took approximately 3 minutes 22 seconds and stopped only its temporary PostgreSQL cluster. PostgreSQL integration tests exercise real isolated tables/locks/triggers/transactions; clock advancement uses an injected AuthenticationClock, not OTP-expiry sleeps.

All nine JS suites actually executed in the available JavaScript runtime using DOM/event/history doubles and mocked fetch. They are **not actual browser visual/native-cookie certification**. An initial runtime fixture lacked removeEventListener; completing that event double allowed the new suite to execute. Synthetic assembled-app observations separately confirmed Merchant/Admin login context, corresponding forgot links, shared Remember Me control and disabled recovery panel. Actual desktop/mobile/browser-cookie/Web-Locks multi-tab verification remains manual after approved activation.

An initial Java run exposed null sid claim rejection for legacy JWT login. Issuance now omits sid entirely when there is no server session. The full corrected run passed 267 tests; adding seeded financial-preservation and verified-grant/eligibility-revocation checks produced the final passing 269-test run. No live account operation was used to debug failures.

The packaging command was `mvn package -DskipTests`, not bare Maven testing. JAR inspection confirmed V10 and both new auth controllers are included. No new artifact was launched as a live service. Local logs: `/tmp/paymesh-673-java-verified.log`, `/tmp/paymesh-673-proxy-final.log`, `/tmp/paymesh-673-package.log`.

Exact executed commands:

```bash
cd ~/Developer/paymesh-ai/backend
bash scripts/test-isolated.sh
mvn package -DskipTests
cd ..
python3 -m unittest discover -s frontend/tests -v
git diff --check
```

The environment approved temporary test-server/database permissions; no production/demo target was used. Compile/test-compile checks during implementation did not execute tests and are not added to these counts.

### Test coverage details

Java covers legacy/no-Origin login, Remember Me/session-cookie attributes, secure/local cookie configuration, strict Origin/CSRF, rotation/digest storage, replay family/access revocation, concurrent refresh, idle/absolute expiry, current/all logout and signed access denial, enabled/status/roles/version changes, pending access denial, disabled-by-default recovery, production/public/non-demo safety rejection, eligible single-role Merchant/Admin/pending flows, mixed-role denial, unknown accounts, guesses/max attempts/expiry/cooldown/resend, verified-grant invalidation on resend, reset-grant expiry/replay/cross-challenge rejection, concurrent reset, password policy/BCrypt old/new credential checks, session revocation, audit rollback, and seeded financial/ownership/registration preservation. Existing offline admin recovery and all old financial/AI suites remain green under V10 in isolated schemas.

Frontend covers both portal Remember Me request values, startup restoration, single flight, failed refresh, silent same-family renewal preserving operation version, late old-token 401 not clearing a renewed session, replaced-claim rejection, logout/all, stale restoration, same-family tab messages preserving private state, other-family replacement clearing state, both forgot routes, disabled capability, backend-issued OTP display without auto verification, manual entry, cooldown/resend, countdown expiry, invalid server OTP clearing state, password mismatch/policy, reset success/no automatic login, route/replacement/stale cleanup, and all original payment/refund/investigation regressions. New proxy tests check exact methods/routes, direct forgot URLs, required Origin/CSRF, exclusive cookie forwarding, cookie exclusion from business/recovery and malformed/duplicate/upstream-cookie denial.

Browser test URLs (all mocked requests):

- http://127.0.0.1:5500/assets/js/tests.html
- http://127.0.0.1:5500/assets/js/auth-tests.html
- http://127.0.0.1:5500/assets/js/payment-tests.html
- http://127.0.0.1:5500/assets/js/refund-tests.html
- http://127.0.0.1:5500/assets/js/investigation-tests.html
- http://127.0.0.1:5500/assets/js/qa-tests.html
- http://127.0.0.1:5500/assets/js/portal-tests.html
- http://127.0.0.1:5500/assets/js/registration-tests.html
- http://127.0.0.1:5500/assets/js/session-recovery-tests.html

## Security review and limits

- Same-family token renewal remains silent to financial state subscribers; an old request's 401 cannot clear a newer same-family access token. Replaced-account/logout versions still reject late responses. Same-family restoration in another tab does not discard an existing uncertain intent merely because it broadcasts a restoration event.
- Browser refresh restores authentication, **not memory-only financial intent keys or uncertain request bytes**. After losing such state, inspect authorized payment/refund history before a new financial action. No persistent financial cache or automatic replay was added.
- A confirmed session logout revokes subsequent JWT validation. It does not promise cancellation or rollback of work already in flight. A network-failed logout is explicitly unconfirmed; the browser must not be left shared until server logout is resolved. All-device uncertainty cannot be proven resolved merely by clearing this browser cookie.
- Web Locks are required for automatic restoration/refresh in real browsers. Unsupported browsers retain manual login rather than unsafe parallel-cookie rotation. BroadcastChannel is an additional memory cleanup aid, not the authorization boundary. Verify native browser behavior and multiple tabs before release.
- Server account-administration locking serializes low-volume authentication/security changes. This is safe/simple for the local portfolio, not a high-throughput identity-provider claim. Request budgets are bounded single-process controls, not distributed anti-abuse infrastructure.
- Disabled/public production recovery remains unavailable. An operator-designated disposable account can be reset by anyone with access to the deliberately insecure enabled local flow; that is the explicit demonstration risk, not an ownership proof. Eligibility must never be granted to real privileged/user accounts merely for convenience.
- No secure public recovery channel, admin approval API/UI, account listing/profile API, deployment, Docker, email verification or password delivery service is implemented. Admin approval remains Phase 6.7.4. Real production break-glass/recovery and identity proof need separate review.
- The local demo guard requires operator assurance that no public reverse proxy/tunnel exposes loopback. It does not claim software can prove the absence of all externally established port forwarding.
- All new sensitive responses use no-store; no new unsafe HTML insertion, console-secret logging or browser persistent credential storage was found in the new modules. Static review found no duplicate HTML IDs or missing literal app/view element IDs. Existing CSP and AI/gateway route limits remain intact.

## Preservation audit

Initial Git index SHA-256: `f0c8610b9428c6fc7c5efbf2df3c66fbfa7d1f459e7f4824be08b5d17ac5d3f7`. Initial staged binary diff SHA-256: `bfa72c70a1a3ea8577c057adeb9b5bb87001e8fd9800113d0d35e64a4f37e4d9`. Final observed hashes matched exactly, and binary staged snapshots compared equal. No git add/commit/push/reset/clean/restore or index modification was issued. Existing unrelated staged/unstaged work was retained; only the enumerated implementation/documentation files were edited and Maven generated target output.

Existing listeners remained Java96717/18080, frontend96829/5500, Python80995/8000 and llama.cpp79855/8082. No service restart/stop, original paymesh_db/8080 access, live database connection, live V10 migration, eligibility insert, live password reset, financial mutation, webhook/settlement operation or live investigation request was performed. The supplied demo counts are operator evidence, not newly queried counts. Protected environment, keys/secrets, backups/archives and Python AI files were not edited.

## Completion decision

Phase 6.7.3 implementation, isolated tests, frontend mocked tests, packaging and documentation are complete. The code is ready for a separately approved controlled activation review, **not a claim that the new live configuration or insecure OTP flow is enabled or production-ready**. Before approval, review V10/backup plan, exact origin/cookie settings, supported browser gates and optional disposable eligibility/private demo custody. Keep OTP disabled unless that separate security review explicitly authorizes it. Stop after this batch; do not start Phase 6.7.4 or Docker automatically.

### Precise manual browser checks after separately approved activation

1. Keep local recovery disabled initially. Open each login route on desktop and at approximately 375px. Check the shared Remember Me label, keyboard focus, Forgot Password link and existing Merchant signup navigation. Both forgot routes must show unavailable state with no OTP entry/display controls. Do not paste credentials/cookies/JWTs into console, screenshots or reports.
2. Privately sign in as an existing ACTIVE Merchant with Remember Me unchecked. Inspect **cookie attributes only**: HttpOnly, SameSite Strict, exact auth path, no Domain, no Max-Age. Local Secure exception is permitted only under the approved loopback config. Refresh the page and verify authorized workspace restoration. The access token must remain absent from browser persistent storage.
3. Explicitly sign out, then repeat with Remember Me checked. Inspect a persistent Max-Age within the configured absolute lifetime. Refresh/new same-browser tab must restore while the server family remains valid. Closing a browser is subject to that browser's session-restore cookie policy; the server's absolute/idle limits remain authoritative. Repeat Admin sign-in separately and verify cross-role routes remain guarded; repeat pending Merchant sign-in and confirm financial panels stay disabled.
4. In a supported Web-Locks browser, use two same-family tabs and refresh them concurrently. Restoration must not clear an uncertain financial intent in the original same-family tab and must not trigger replay logout. Do not create a real uncertain mutation to test this—use mocked workflows. Explicit logout must clear both tabs and block Back restoration. Explicit replacement with another account must clear the old account's private results. Logout All must also reject another existing session's next authorized read. Do not export token values for these checks.
5. Confirm a failed/unavailable logout is labeled unconfirmed and the finish-signing-out action is visible on the login screen. Use mocked network failures rather than stopping live services. Native-cookie/Web-Locks behavior is the remaining manual sign-off gate; automated runtime doubles do not certify it.
6. Only after **additional explicit approval** for the insecure local flow, review the actual loopback connectors/database/origin/private key/operator attestation and designate chosen disposable account UUIDs. Do not grant blanket eligibility or automatically designate newly registered users. Reload the approved configuration without public exposure. The capabilities response may now enable the two recovery forms for this verified deployment.
7. Merchant flow: enter the designated email → Generate OTP → observe a new six-digit runtime code → manually type it → Verify OTP → enter matching valid new password/confirmation → Reset Password. Check code/countdown/resend/keyboard labels; do not auto-fill the displayed code programmatically. Success must clear OTP/grant/password state, stay signed out and provide the Merchant login link. Sign in privately with the new password; pending must remain pending.
8. Admin flow: repeat with a separately designated disposable ADMIN-only username and the Admin route/link. A non-designated, wrong-portal or mixed-role account must never get a usable code. Do not use the operational demo-admin account unless the operator has expressly designated it disposable for this test.
9. Test invalid/expired code, 60-second resend and route leave/restart using the mocked test page first. In any separately authorized live demo test, a newly generated challenge must invalidate previous codes/grants, a consumed grant must not reset again, and no automatic sign-in may occur. Inspect only safe audit metadata/account status and counts through approved read-only procedures; financial state must remain unchanged.
10. Return the insecure recovery feature to disabled after demonstration. No public production recovery, admin approval, Docker or next-phase work is included in this checklist or automatically authorized by this report.

## Controlled sessions-only activation attempt — credential blocker

The operator authorized V10 and persistent-session activation only, with on-screen OTP recovery remaining disabled. The agent read this report completely, inspected the actual AuthBrowserPolicy/LocalDemoRecoveryGate property names and the Phase 5.4 startup runbook, and performed independent safe preflight/build preparation.

### Actual observations

- Discovered current listeners: Java PID96717/18080, frontend Python PID96829/5500, Python AI PID80995/8000 and llama.cpp PID79855/8082, all reported on 127.0.0.1. Executable identities were inspected without printing full command lines or process environments.
- Verified working directories: backend, repository root, ai-service and `~/Developer/paymesh-tools/llama.cpp` respectively. No historical PID was used as permission to stop a service.
- Protected demo directory was mode0700; demo.env, secrets.env and private JWT key were mode0600. Source configuration was loaded privately with output/tracing suppressed; credential values and private keys were not printed.
- Database credential presence check returned **DB_CREDENTIAL_UNAVAILABLE**. No password was guessed, requested in chat, persisted or extracted from another process. No Codex heredoc/TTY password-input attempt was made.
- Available disk was approximately 6.4 GiB. PostgreSQL psql/pg_dump/pg_restore at `/Library/PostgreSQL/16/bin` reported version16.3. No database-size measurement was possible without the credential.
- Independent `mvn package -DskipTests` passed in 4.859 seconds. No full test suite was unnecessarily repeated. JAR inspection found V10, SessionController and PasswordRecoveryController, and confirmed packaged V10 bytes match the reviewed source. Local build log: `/tmp/paymesh-673-activation-package.log`.

### Activation status — not performed

Database identity, actual Flyway history, live V10 absence/success, live admin state and current six-table counts were **not independently queried** in this attempt because the required credential was unavailable. The supplied counts `4|3|3|1|6|4` remain the operator's approved expected baseline, not a new measurement. No backup was created, listed, extracted or restored. No private configuration file was changed and no Java/frontend process was stopped or started. There are no new service PIDs. Python/LLM were left untouched. Live readiness, new schema/triggers, recovery-eligibility emptiness and capabilities=false are therefore not claimed as newly verified activation results. No login, recovery POST, password reset, financial mutation, original paymesh_db connection or port8080 request was issued.

### One exact operator-run Mac Terminal script

Created `backend/scripts/activate-phase673-demo.sh`. Run this file directly in a **real interactive Mac Terminal**, without piping/redirecting stdin/stdout, after privately reviewing it:

```bash
cd "$HOME/Developer/paymesh-ai"
/bin/bash backend/scripts/activate-phase673-demo.sh
```

It prompts silently for the existing database user's password via `/dev/tty`. Enter it only there; do not put it in command arguments, shell history, files or chat. The script is **not executed by the agent** and is not claimed to have completed a live activation.

The script includes:

- Fresh listener/executable/cwd/binding/start-identity checks, including rechecks immediately before stopping only the verified Java/frontend processes. It refuses unexpected additional listeners on either process and preserves Python/LLM identities.
- Private demo configuration loading without content output; rejection of unreviewed JVM/datasource/migration overrides and conflicts with reviewed existing launch settings. JWT issuer/audience/keys, gateway settings, webhook/settlement credentials and reviewed AI limits are retained; nothing is generated/rotated.
- Exact read-only database/user/host/port verification, successful V1–V9/no-V10 checks, absence of a partial V10 schema, expected six counts and an enabled ACTIVE ADMIN-only `demo-admin` at authorization_version1. It prints aggregates/booleans only, not personal records or hashes.
- PostgreSQL16 custom-format backup under `~/.config/paymesh-demo/backups/`, unique timestamped filename, mode0600/nonempty checks, pg_restore listing, full archive extraction to `/dev/null` and SHA-256 sidecar. No database restore or existing backup overwrite. It checks space against actual database size before backup and refuses changed baseline state.
- Packaging with tests skipped and JAR/migration identity checks. It creates a fresh mode0600 non-secret sessions.properties in a unique mode0700 private activation directory, leaving existing demo.env/secrets/key files unchanged. Exact origin/local-HTTP/OTP-disabled settings are also pinned at Java startup.
- One guarded Java restart with normal Flyway validation/migration, public-schema JPA validate-only, demo/loopback18080, settlement scheduling disabled and existing AI URL/timeouts/response bound. No clean/repair/baseline/restore/downgrade or blind retry. Startup failures are retained in protected logs, not printed as raw exceptions.
- Actual V10 history/table/trigger/eligibility verification, unchanged before/after counts and admin state, readiness/health and OTP-disabled capabilities, followed by the guarded loopback5500 frontend restart.
- All eight SPA routes and test-page GET checks, direct/proxy health/capabilities, exact proxy auth-route assertions and cookie-empty refresh probes only (401 with correct Origin/CSRF, 403 without). The deletion-cookie attributes are checked without creating a session or logging in. No password-recovery POST or financial action is issued.
- Final staged/index comparison with no index mutation; concurrent external staging is reported and left untouched. It appends actual success or stage-specific failure evidence to this report when the operator runs it. A failure after Java startup may leave V10 applied; the script explicitly stops and requires private review instead of retrying or rolling back automatically.

Validation actually executed for the script: `bash -n` passed; seven embedded Python snippets compiled syntactically **without executing them**; `git diff --check` passed. This is syntax/review evidence, not an end-to-end test of the live activation script or a test restore.

### Preservation and remaining work

Activation-attempt initial index SHA-256: `f0c8610b9428c6fc7c5efbf2df3c66fbfa7d1f459e7f4824be08b5d17ac5d3f7`; initial staged binary diff SHA-256: `bfa72c70a1a3ea8577c057adeb9b5bb87001e8fd9800113d0d35e64a4f37e4d9`. Final observations are recorded below. Agent changes in this attempt are the operator script, this report append and generated Maven output only. No staged/unrelated work was restored or overwritten.

After an operator-run successful activation, native browser verification remains pending at http://127.0.0.1:5500/merchant/login and http://127.0.0.1:5500/admin/login: privately test Remember Me off/on, refresh restoration, current/all logout, role isolation and pending restrictions using the earlier manual checklist. Both forgot-password routes must remain disabled. Do not perform OTP/reset tests or designate accounts; separate explicit approval is still required for any insecure recovery demonstration. Phase6.7.4 is not started.

Final activation-attempt index and staged-diff hashes matched the initial values exactly; binary staged snapshots compared equal. Final listeners retained the same four PIDs. `git diff --check` passed. Activation remains blocked solely at credential-dependent operations; the reviewed operator script and independent build preparation are complete, with no live state claimed as activated.

## Successful operator-run sessions-only activation

Backup: `/Users/bhupirao/.config/paymesh-demo/backups/paymesh_demo-pre-v10-20261114T165650Z.tKKcMJ`, custom format, mode600, nonempty; PostgreSQL16 pg_restore list and full archive extraction to /dev/null passed. SHA-256 `bb8303a0e3fe4b57d9b63eeb58ade2dbc484e13d71130d756cddad5591b2d8e7`. No actual test restore performed.

Maven package succeeded; packaged V10 matched source and both controllers were present. Protected non-secret session configuration: `/Users/bhupirao/.config/paymesh-demo/activation-673-20261114T165645Z.BOzvsG/sessions.properties`. OTP explicitly disabled; no recovery key or eligibility was created.

V1-V10 history successful; five auth/recovery tables and both enabled security triggers verified. Before/after counts users|merchants|memberships|registrations|payments|refunds: `4|3|3|1|6|4` / `4|3|3|1|6|4`. Existing admin remains enabled ACTIVE ADMIN-only at authorization_version1.

Java old/new PID: 96717/4045. Frontend old/new PID: 96829/4255. Python PID 80995 and llama.cpp PID 79855 plus start identities remain unchanged. Readiness UP, direct/proxy health, all eight SPA routes, test page and disabled recovery capabilities verified. Empty-cookie refresh returned401; missing Origin/CSRF returned403. No login, recovery POST, password reset, financial mutation or original paymesh_db/8080 operation was performed.

Git index initial/final: `bd1a30cbf9d13ea457b4e9c722f7cea62715772567eae8a208a7e90129700c32` / `bd1a30cbf9d13ea457b4e9c722f7cea62715772567eae8a208a7e90129700c32`; staged diff initial/final: `4290d3bce9ee9a8b07dc0bfd2babfa7882ad80a6023d849eff0eac06bd8e69a7` / `4290d3bce9ee9a8b07dc0bfd2babfa7882ad80a6023d849eff0eac06bd8e69a7`. Initial/final staged snapshots and index match. git diff --check passed. Private evidence: `/Users/bhupirao/.config/paymesh-demo/activation-673-20261114T165645Z.BOzvsG`. Native browser/cookie/Web-Locks verification remains pending. OTP activation and Phase6.7.4 are not authorized by this run.

## Step 17 — operator session closeout and local OTP preparation

### Supplied live verification (operator confirmation)

The operator confirms **all eight Phase6.7.3 live session browser checks passed**, and confirms Secure Context, Web Locks and BroadcastChannel support. This is operator-performed evidence, not automated browser testing or an independently repeated agent observation. No additional native cookie-attribute inspection or unspecified manual security check is claimed here. The successful operator-run V10 activation evidence above remains the activation record; its counts stayed 4 users, 3 merchants, 3 memberships, 1 registration, 6 payments and 4 refunds. The supplied current Java/frontend PIDs are 4045/4255. Baselines remain 269 isolated Java tests and 634 frontend mocked checks; those suites were not rerun for this operations-only preparation.

Preparation independently observed those four loopback listeners (Java4045, frontend4255, Python80995, llama.cpp79855) and read only the non-secret whitelisted session properties from the previously activated private configuration: exact local origin, local HTTP true, loopback18080 and recovery enabled=false. Protected directory mode0700 and demo.env/secrets.env/private JWT file modes0600 were observed. No credentials or private keys were displayed. These observations are not a new live database query, recovery request or browser verification.

### Important unresolved provisioning blocker

The source contains a supported **internal** administrative operation:

`AccountCredentials.authenticate(existingAdminLogin, char[])` → genuine password-verified `AuthenticatedAccount` → `AccountAdministration.createAdminAccount(actor, newLogin, char[])`.

It enforces current administrator authorization, AccountAdministrationLock, BCrypt, duplicate protection, transactional role assignment and ACCOUNT_CREATED audit. **No additional-ADMIN interactive command or REST endpoint exposes it in this repository.** `InitialAdminProvisioner` is initial bootstrap only and deliberately refuses once any ADMIN assignment/bootstrap history exists. `MerchantAccountProvisioner` creates a verified Merchant, not an Admin and not the requested pending registration. `AdminPasswordRecovery` resets an existing password; it is not provisioning and must not be used here.

Therefore there is no honest operator command to supply for creating `otp-admin-demo` today. Do not run bootstrap, deserialize/fabricate a principal, call an invented endpoint, use JShell/reflection as a backdoor, or insert password hashes/role assignments with SQL. A separately authorized guarded interactive adapter invoking the existing authenticated createAdminAccount facade, with isolated tests, is the unresolved prerequisite if this disposable admin does not already exist. No such application adapter was implemented silently in Step17.

The activation script **stops before backup/provisioning/key/eligibility/restart mutations if the dedicated admin is missing**, while recording the name-availability result and blocker. Names were not queried by the agent because live database access is reserved for the operator-run credential procedure. No absence/presence is assumed from names alone. If an existing dedicated admin is found, it must be enabled ACTIVE ADMIN-only, have a matching successful ACCOUNT_CREATED audit from an authorized administrator and be explicitly affirmed disposable by the operator. It is verified/reused, never duplicated or reset. A coincidentally named or wrong-role account fails closed.

### Files added/modified

Added:

- `backend/scripts/activate-phase673-otp-demo.sh` — guarded interactive wrapper.
- `backend/scripts/disable-phase673-otp-demo.sh` — guarded deactivation wrapper.
- `backend/scripts/phase673_otp_ops.py` — shared standard-library operational helper, **not** application/AI business code or a new provisioning authority.

Modified: this report only. Existing successful sessions-only activation script, Java gate/recovery/provisioning implementation, migrations, dependencies, frontend and Python AI implementation were left unchanged. No live accounts, eligibility, keys, password changes, backups or service restarts were performed during preparation.

### Supported Merchant provisioning and expected counts

The existing real `POST /api/v1/auth/register` API is the supported pending-Merchant path. The script uses it only **after** the Admin prerequisite is satisfied and a fresh protected backup is verified. It supplies the already implemented fields: synthetic first/last/business name, fixed proposed email `otp-merchant-demo@example.test`, synthetic mobile, businessType OTHER, country IN, operator-entered password/confirmation and explicit demo terms acknowledgment. The server generates merchant identity and MERCHANT role and persists an inactive membership/unverified registry in PENDING_APPROVAL. The script never approves it. Existing same-name Merchant reuse requires enabled PENDING_APPROVAL, exactly MERCHANT and the expected registration row; no password is changed by reuse.

A newly created additional Admin through the supported facade adds one user/role/audit, no merchant rows. A normal new pending Merchant registration adds one user, merchant, membership and registration. Thus the expected final counts with both new disposable accounts are **6 users, 4 merchants, 4 memberships, 2 registrations, 6 payments, 4 refunds**. Because this script cannot create the absent Admin itself, a future authorized Admin prerequisite may make its actual initial counts 5/3/3/1/6/4, followed by the supported Merchant addition. If both dedicated accounts already exist legitimately, it verifies/reuses them at 6/4/4/2/6/4. Unexplained changes fail closed. It does not claim the original account counts remain unchanged after provisioning; actual before/after counts and whether the script created the Merchant are recorded in private evidence.

Do not create the Merchant preemptively merely to work around the missing Admin command. The current approved four-user baseline normally reaches the deliberate missing-admin blocker before any account write. A separately reviewed Admin command is a prerequisite, not permission to start Phase6.7.4 UI/API work.

### Exact operator commands and prompts

**Preparation is not an instruction to bypass the unresolved Admin prerequisite.** Review the scripts and resolve that supported-command gap separately before expecting a complete activation. The scripts themselves have not been executed during preparation.

Activation in a real private Mac Terminal (no arguments, pipes, terminal recording or shell tracing):

```bash
cd "$HOME/Developer/paymesh-ai"
/bin/bash backend/scripts/activate-phase673-otp-demo.sh
```

Expected prompts/flow:

1. Existing paymesh_demo_user **database password**, silently through `/dev/tty`.
2. Exact private-deployment attestation `NO_PUBLIC_PROXY_OR_TUNNEL` (echoed, non-secret).
3. Read-only name/count/schema/gate checks. If `otp-admin-demo` is absent, an explicit **BLOCKER** is printed and activation stops before any provisioning/key/eligibility/restart. No additional-Admin password prompt is invented.
4. If a correctly provisioned disposable Admin is present: explicit `DISPOSABLE_OTP_ACCOUNTS_ONLY` affirmation, then fresh backup verification.
5. Existing operational `demo-admin` password entered silently, solely to authenticate the actual reviewer through existing login; it is not changed. The JWT stays in process memory and is not printed/stored. Designation uses the matching current reviewer UUID, version and unexpired authorization, never a fabricated actor.
6. If the pending Merchant is absent: explicit `REGISTER_OTP_MERCHANT` terms/creation consent, then hidden new Merchant password and hidden confirmation. The server's existing password policy/registration transaction apply. No registration automatically retries on uncertainty; inspect the account before trying again.
7. Private target manifest, key/config preparation, exact two-row eligibility transaction, one guarded Java restart and readiness/capability/count verification. No OTP generation/verification/reset is performed automatically.

Deactivation after separately successful activation/browser demonstration:

```bash
cd "$HOME/Developer/paymesh-ai"
/bin/bash backend/scripts/disable-phase673-otp-demo.sh
```

Deactivation requests only the hidden database password. It uses the protected target manifest `~/.config/paymesh-demo/otp-step17-disposable-accounts.json`, makes a fresh verified backup, disables the global gate first when a restart is required, then disables only the two target eligibility rows and consumes their outstanding challenges/reset authorizations. It uses the same V10 consumed_at semantics and existing account-administration advisory lock as LocalPasswordRecovery.invalidate(), via an explicitly scoped operator SQL transaction; it adds no REST maintenance endpoint. If later scoped invalidation fails, the global gate has already been contained where restart succeeded, and the evidence records partial failure rather than claiming full completion.

It does not delete accounts, modify passwords/roles/status, bump account authorization versions or revoke unrelated persistent sessions. Frontend, Python and LLM remain untouched. If everything is already disabled with no eligibility and no manifest, it verifies a no-op. If a manifest is missing while recovery/eligibility is active, it stops instead of guessing UUIDs or issuing broad SQL; use a separately reviewed private containment procedure. If Java is unavailable after a partial startup failure, inspect private evidence before any separately authorized restart—do not run blind repair/restore/downgrade commands.

### Script safeguards and metadata

- PostgreSQL16 tools pinned at `/Library/PostgreSQL/16/bin`; exact database/user/host/port via host(inet_server_addr()); successful V1–V10 history and actual eligibility column names checked. No migrations are run intentionally; the current reviewed JAR must contain exactly V1–V10, matching source V10, and its checksum must remain unchanged through preparation.
- Current PIDs, executable names, working directories, start identities and literal loopback-only listeners are discovered anew. Java alone is restarted. Frontend/Python/LLM PIDs and start identities are compared before/after. Original paymesh_db and port8080 are not targets.
- Current reviewed Java flags are copied only after a strict allowlist and exact gate/session checks; unexpected flags/settings stop rather than being dropped. Additional configuration paths remain protected. JWT/session/gateway/AI/scheduling settings remain in place. The only intended changes are recovery enabled/attestation and an added protected recovery-key file.
- No Host or forwarded-IP assertion substitutes for the actual connector/database checks. LocalDemoRecoveryGate remains unchanged and must still accept exactly demo, literal JDBC target, database user, actual loopback Tomcat connectors, exact local HTTP session origin, forwarding none, attestation and private key. Software does not prove absence of all tunnels; the explicit operator attestation remains required.
- Backup uses a new timestamped custom-format file in the protected backups directory, mode0600/nonempty, archive listing/extraction verification and SHA-256 sidecar. No old backup is overwritten and no test restore is claimed/performed by preparation.
- A fresh 256-bit `secrets.token_hex(32)` key (64 hex characters) is generated only after prerequisites/backup/account checks pass and is written only to a new mode0600 external OTP properties file in a mode0700 private run directory. It is never a CLI value or log entry; stale environment key aliases are removed so they cannot override that fresh file. No key was generated by Codex preparation.
- Eligibility is limited to the two canonical UUIDs and their exact portals. Operational demo-admin UUID is explicitly excluded. designated_by is the real separately authenticated reviewer, review_reference is a generated phase673-step17 timestamp, and that reviewer's current version/role/status/token expiry are rechecked under the database lock. No broad user/merchant enrollment or password-hash SQL occurs.
- Old challenges/grants for those two UUIDs are invalidated using consumed_at in the same eligibility transaction. Deactivation uses the same scope, tolerating account disablement/role changes for containment while still requiring exact UUID/name identity. No unrelated credentials or financial tables are updated.
- Passwords use hidden terminal input; GetPassWarning is treated as failure rather than falling back to echo. No plaintext credentials enter argv, files or evidence. JDBC/HTTP clients necessarily hold transient immutable strings; process memory cannot be perfectly erased by this operational helper. No console/debug/environment dumps are used.
- Missing Admin support, uncertain registration, changed artifact/process/counts, unexpected eligibility or failed startup stop execution. There is no automatic OTP/reset, repeated provisioning, forced kill, rollback restore, downgrade, Flyway clean/repair/baseline or account deletion.
- Each operator run writes a private evidence JSON with actual counts, backup checks, stages/PIDs/target identifiers and outcome, and appends a safe outcome/reference to this report. Failed/partial runs are not labeled successful. Git index/staged snapshots are compared without mutation; external staging is left untouched.

### Browser test instructions — only after prerequisites and verified activation

1. Confirm direct/proxy capabilities show localDemoEnabled=true and only the two disposable UUIDs are enabled. Keep all operational users ineligible. Do not test recovery on `demo-admin` or existing operational merchants.
2. Merchant: open http://127.0.0.1:5500/merchant/forgot-password (or Merchant Login → Forgot Password), enter `otp-merchant-demo@example.test`, select Generate OTP, observe the runtime six-digit code and manually type it. Verify OTP, enter/confirm a new private policy-compliant password, Reset Password, then use the Merchant login link and sign in with the new credentials. The account must still be PENDING_APPROVAL, with no financial access. No automatic sign-in occurs.
3. Admin: repeat at http://127.0.0.1:5500/admin/forgot-password using `otp-admin-demo`. Return to Admin Login and authenticate privately with its new password; ADMIN-only ACTIVE state must remain unchanged. Do not approve merchants or perform financial actions.
4. Check invalid code, five-minute expiry, 60-second resend, single-use code/grant and route-leave clearing using the existing mocked page first. Any live demonstration is confined to these two disposable accounts. Neither screenshots nor reports should include OTPs, passwords, JWTs, reset grants or recovery key values.
5. Password changes invalidate the disposable account's prior sessions; operational account passwords/memberships and payment/refund counts must remain unchanged at 6/4. Actual account counts should reflect legitimate newly provisioned disposable rows, not the original four-user count.
6. Run the deactivation command immediately after the demonstration. Verify direct/proxy capabilities=false, zero enabled eligibility, no usable outstanding grants for those targets, unchanged account/financial counts and original frontend/Python/LLM identities. Both forgot pages should become unavailable again; persistent sessions remain configured. Keep the secure offline admin recovery utility unchanged.

### Preparation verification and status

Executed: bash syntax checks for both new wrappers, Python source compilation without running its entry point, and two focused mocked operational checks: missing-admin path stops before mutations; deactivation SQL uses the exact two-target lock/consumed_at scope without password/account/financial updates or deletes. No database or service operation was executed by those checks. `git diff --check` passed. Full Java/frontend suites were not rerun because application code was not changed; the supplied 269/634 baselines remain historical verified evidence.

Step17 is **prepared with the explicit additional-Admin provisioning blocker**, not live activated or browser-tested. No live account existence query, backup, key, eligibility, OTP, reset or service restart was performed by the agent. The scripts must not be portrayed as successful activation from the current four-user baseline when no dedicated additional Admin can yet be created through a supported interactive command. Do not start Phase6.7.4.

Final preparation preservation check: the Git index SHA-256 remained `bd1a30cbf9d13ea457b4e9c722f7cea62715772567eae8a208a7e90129700c32`; initial/final staged binary diffs were byte-identical (SHA-256 `4290d3bce9ee9a8b07dc0bfd2babfa7882ad80a6023d849eff0eac06bd8e69a7`). Both bash syntax checks, Python compilation and final `git diff --check` passed. No staging operation was issued.

## Operator Step17 activate evidence

Outcome: stopped; no automatic retry/restore. Stage: dedicated-account-prerequisites. Private evidence: `/Users/bhupirao/.config/paymesh-demo/otp-step17-activate-20261114T174352Z-5jfh25md/evidence.json`.
No OTP generation or password reset was performed by the activation/deactivation script. Check private evidence for actual counts/PIDs/backup verification; do not assume unchanged account counts.

## Step 17 additional-Administrator provisioning blocker resolution

### Root cause and scope

The operator ran the original activation helper and confirmed its safe missing-Admin stop before Merchant creation, key/eligibility changes or restart. The earlier Step17 blocker description above is historical and is superseded by this section: the existing AccountAdministration facade supported authenticated Admin creation internally, but no supported HTTP/interactive adapter exposed it. Bootstrap intentionally remains first-Admin-only. This batch adds the narrow authenticated API explicitly requested by the operator, not the Phase6.7.4 Admin Dashboard.

No live database connection, account creation, login, OTP/recovery request, password change or service restart was performed during this implementation. The supplied live baseline remains operator evidence: V10 active; 4 users / 3 merchants / 3 memberships / 1 registration / 6 payments / 4 refunds; eight browser session checks passed; OTP disabled. It was not independently re-queried during coding.

### API and authorization design

`POST /api/v1/admin/accounts`, Content-Type application/json, Authorization Bearer access JWT. Request contains exactly `{login,password,confirmPassword}`. No role/status/authority input is accepted. Jackson rejects unknown fields, duplicate keys, trailing JSON and malformed input; the existing bounded-body filter now covers this exact path at 4096 bytes, including streamed bodies. All handled responses are no-store. There is no public signup page, wildcard route/CORS change or frontend proxy addition.

The existing business SecurityFilterChain now explicitly recognizes this POST as ADMIN-only. The unchanged signed-JWT validator checks enabled state, current roles/account status/authorization version, expiry and sid revocation when present. Cookie-only requests do not authenticate this endpoint. Pending accounts have no financial/admin authorities. AccountCredentials.currentJwtAccount adapts the actual already verified JwtAuthenticationToken from Spring SecurityContext into the existing constructor-restricted internal identity; it accepts no client-selected UUID/role and does not fabricate an authenticated administrator. The existing AccountAdministration.createAdminAccount facade then rechecks current enabled/ACTIVE/version/ADMIN under AccountAdministrationLock and runs the unchanged transactional account creation/audit.

Login normalization uses the existing strip/lowercase ASCII policy; BCrypt configuration and password policy are reused. AccountPasswords.validate is now public for policy-only reuse at the adapter boundary; its logic is unchanged. Matching confirmation is required. Password byte/character buffers owned by the adapter are cleared where accessible in finally; parsing/HTTP runtimes may retain transient copies until garbage collection. No credential or hash is logged or returned.

Success HTTP201 returns only `{userId,login,enabled:true,accountStatus:"ACTIVE",roles:["ADMIN"]}`. Existing service invariants create precisely that state. ACCOUNT_CREATED records the actual authenticated actor, role metadata and new account UUID. User, role assignment and required success audit commit/roll back atomically. No merchant, membership, registration or OTP eligibility is created by this endpoint. InitialAdminProvisioner and offline recovery are unchanged.

Errors: 400 malformed/missing/mismatched/password-policy input; 401 unauthenticated/invalid/expired/revoked token; 403 insufficient/current changed authorization; 409 duplicate/invalid normalized login (existing facade deliberately uses a combined safe rejection); 413 oversized body; 415 unsupported content type; 503 safe unconfirmed creation failure. Raw bodies/exceptions/hashes are never echoed. A 503 or lost response is not automatic permission to retry: check the exact account name and audit first.

### Operator workflow and safeguards

A new `deploy-phase673-admin-api.sh` wrapper reuses the protected standard-library operational helper. It must be run **before activation**, only after separate deployment approval. It requires a real terminal, protected configuration owner/modes, PostgreSQL16 tooling, newly discovered exact loopback service executable/cwd/PID/start identity, exact literal demo JDBC/user and actual PostgreSQL identity, V1–V10 successful history, disabled capabilities (direct and proxy), zero enabled eligibility and the approved four-user baseline. The packaged JAR must include AdminAccountController and exactly V1–V10 with unchanged reviewed V10 content.

Deployment requires the hidden database password and explicit `DEPLOY_ADMIN_API_OTP_DISABLED`. It verifies a fresh protected custom-format backup (nonempty600, list/extraction, SHA256; no test restore), rechecks artifact/process identity, restarts only the exact demo Java process and verifies readiness, payment health, capabilities=false and unchanged counts. Existing session/JWT/gateway/AI/scheduling flags are preserved; only a private disabled recovery config is appended. No migration is added or intentionally activated, no account is created, and frontend/Python/LLM identities must stay unchanged. Flyway remains in the established launch configuration with the same already-applied V1–V10; mismatched history/artifacts fail closed.

Updated activation retains its independent fresh backup/private-deployment attestation/identity/count checks. It authenticates the actual operational demo-admin via the supported login API with hidden `/dev/tty` input (legacy no-Origin JWT-only login, no browser cookie). That JWT remains in Python process memory only. If the dedicated Admin name is absent, explicit `CREATE_OTP_ADMIN` plus hidden new password/confirmation triggers the new authenticated POST. No SQL user/role/hash creation or bootstrap bypass occurs. If the name already exists, it is never overwritten/reset: it must be enabled ACTIVE ADMIN-only with a matching successful authorized ACCOUNT_CREATED audit and explicit disposable-account affirmation. Uncertain/conflicting API responses stop without automatic retry; inspect actual authorized state before rerunning.

The Merchant is created, if absent, via the existing registration API with explicit `REGISTER_OTP_MERCHANT` terms consent and hidden new password/confirmation. It must remain enabled PENDING_APPROVAL MERCHANT-only with the expected registration row. Operational demo-admin and existing merchants are never designated. The exact two canonical UUIDs/portals are checked; the real reviewer/version/expiry is rechecked under the existing administration advisory lock before designation. Only after valid accounts/counts/backup does the helper generate a private 64-hex-character recovery key, write external mode600 configuration, scope eligibility/invalidation to those UUIDs and restart Java with all original LocalDemoRecoveryGate safeguards intact.

Expected actual counts after both new accounts: 6 users / 4 merchants / 4 memberships / 2 registrations / 6 payments / 4 refunds. Partial prior provisioning is detected and reused only after exact identity/state/audit checks, never silently overwritten. Private evidence records whether each account was newly created and actual before/after counts. Passwords/JWTs are never argv, shell-history values or evidence. Python necessarily holds transient immutable secret strings; perfect in-process erasure is not claimed. Fixed safe messages replace raw HTTP failures. No automatic OTP generation/reset occurs.

The existing deactivation wrapper remains unchanged. Its shared helper keeps scoped eligibility/challenge/grant invalidation and globally disables recovery before scoped SQL cleanup. It does not delete accounts, change passwords or alter persistent-session configuration. Missing manifest, changed identity, failed backup, unavailable Java or uncertain outcome requires private review; no forced kill/restore/repair/downgrade or blind restart is attempted.

### Exact operator commands — AFTER separate approval

Do not run these automatically or provide passwords in chat/command arguments. Use a private Mac Terminal, without recording/tracing, and pause browser financial activity throughout. Packaging has been performed by implementation; if rebuilding later, use only the package command below, not bare Maven tests.

```bash
cd "$HOME/Developer/paymesh-ai/backend"
mvn package -DskipTests
cd ..
/bin/bash backend/scripts/deploy-phase673-admin-api.sh
```

Deployment prompts: hidden existing paymesh_demo_user password; non-secret `DEPLOY_ADMIN_API_OTP_DISABLED`. It creates no disposable account/key/eligibility and must report OTP disabled. Inspect its protected evidence before continuing. A failed deployment is not permission to repeatedly restart or restore.

Then, after verified disabled deployment and operator approval to enable the local demo:

```bash
cd "$HOME/Developer/paymesh-ai"
/bin/bash backend/scripts/activate-phase673-otp-demo.sh
```

Activation prompts, in order: hidden DB password; `NO_PUBLIC_PROXY_OR_TUNNEL`; `DISPOSABLE_OTP_ACCOUNTS_ONLY`; verified backup; hidden existing operational demo-admin password; if absent `CREATE_OTP_ADMIN` and hidden new Admin password/confirmation; if absent `REGISTER_OTP_MERCHANT` and hidden new Merchant password/confirmation. Existing dedicated names are verified/reused without password prompts/reset. The new API must already be running; an old backend rejection stops before Merchant/key/eligibility changes. No password reset or live OTP is performed by activation itself.

After successful activation only, use the manual two-portal browser instructions in the preceding Step17 section: runtime OTP must be manually entered, reset is explicit, no automatic sign-in; pending Merchant remains pending, dedicated Admin remains ACTIVE ADMIN-only, all operational accounts/financial records remain unchanged. These are pending operator checks, not tests performed by the agent.

Immediately after the demonstration:

```bash
cd "$HOME/Developer/paymesh-ai"
/bin/bash backend/scripts/disable-phase673-otp-demo.sh
```

Supply only the hidden DB password. Verify capabilities=false, zero enabled eligibility, consumed target challenges/grants, same account/financial counts and unchanged frontend/Python/LLM identities using private evidence. Keep the protected target manifest/configuration for audited containment; do not delete accounts or change operational passwords. Secure offline Admin recovery remains available.

### Files in this resolution

Created:

- `backend/src/main/java/com/paymesh/backend/security/auth/AdminAccountController.java` — narrow HTTP adapter and safe contract.
- `backend/src/test/java/com/paymesh/backend/security/auth/AdminAccountApiIntegrationTest.java` — real isolated PostgreSQL/JWT endpoint tests.
- `backend/scripts/deploy-phase673-admin-api.sh` — guarded disabled-OTP deployment wrapper.
- `backend/scripts/test_phase673_otp_ops.py` — mocked operations/security/failure tests.

Modified:

- `backend/src/main/java/com/paymesh/backend/security/accounts/AccountCredentials.java` — verified SecurityContext identity adapter and accurate identity documentation.
- `backend/src/main/java/com/paymesh/backend/security/accounts/AccountPasswords.java` — public reuse of unchanged policy validator.
- `backend/src/main/java/com/paymesh/backend/security/auth/BusinessEndpointCatalog.java` — exact ADMIN POST match.
- `backend/src/main/java/com/paymesh/backend/security/BoundedRequestBodyFilter.java` — exact body bound/no-store handling.
- `backend/scripts/activate-phase673-otp-demo.sh` — deployment prerequisite comment; implementation remains in shared helper.
- `backend/scripts/phase673_otp_ops.py` — authenticated provisioning, transient JWT forwarding, safe HTTP errors and disabled deployment mode.
- `backend/API-REFERENCE.md`, `backend/README-ACCOUNTS.md`, this report — contract/operator/evidence documentation.

No migration, dependency, frontend runtime/proxy, Java financial/AI logic, Python AI implementation, original database/application, protected configuration or existing staged file content was changed by this task. Existing unrelated unstaged work is retained. Shared operational-helper changes also apply to deactivation; its wrapper needed no change.

### Executed final verification and preservation

| Check | Actual result |
| --- | --- |
| Complete `bash scripts/test-isolated.sh` | **283 tests passed; 0 failures, 0 errors, 0 skips**, 3m40s |
| New Admin API isolated integration suite | **14 tests passed** |
| Retained Java baseline | **269 tests passed**, including offline recovery, sessions, registration and financial/AI regressions |
| `python3 -m unittest discover -s backend/scripts -p 'test_phase673_otp_ops.py' -v` | **9 mocked operational tests passed**, no live HTTP/DB/process operation |
| Bash syntax | All three activate/disable/deploy wrappers passed `bash -n` |
| Maven `package -DskipTests` | **BUILD SUCCESS**, 6.690s |
| Packaged artifact | New controller present; exactly V1–V10; every packaged migration byte-matches source |
| `git diff --check` | Passed |
| Frontend runtime/proxy | Unchanged; frontend suites not rerun; supplied 634 checks remain prior evidence |

Java totals were independently summed from Surefire XML: tests283/failures0/errors0/skipped0. Tests ran only in the script-created temporary PostgreSQL cluster at 127.0.0.1:55441, database with the guarded paymesh_isolated_ prefix; the runner stopped only that test cluster. It did not connect to either live financial database. No bare Maven test was used. The initial sandbox attempt could not allocate PostgreSQL shared memory; the documented runner was then allowed outside the sandbox. Early iterations caught a checked JSON-reader IOException declaration, a package-private test fixture reference and an out-of-range test-only login limiter setting; those were corrected without weakening production controls. The final full suite above is passing, not a claim that unsuccessful earlier iterations passed.

Operational mocks cover real-bearer API request construction, safe header/body-only secrets, confirmation rejection before HTTP, fixed errors for 400/401/403/404/409/413/503, network uncertainty without automatic resubmission, malformed/mismatched state rejection, safe duplicate-account reuse without password changes, backup→actual-reviewer→API sequencing, no JWT in target metadata, disabled deployment without provisioning, and exact scoped deactivation/invalidation SQL. They are not a live end-to-end deployment/backup/OTP test.

Verification logs: `/tmp/paymesh-admin-api-isolated-final.log`, `/tmp/paymesh-admin-api-package.log`. Packaged JAR SHA256: `443ac4a333966fdb92dac81478beaaa50357d9532ec955ded5381b7af62aa0b4`. The JAR has not been launched by the agent.

Initial/final Git index SHA256 matched: `bd1a30cbf9d13ea457b4e9c722f7cea62715772567eae8a208a7e90129700c32`. Initial/final staged binary diff SHA256 matched: `4290d3bce9ee9a8b07dc0bfd2babfa7882ad80a6023d849eff0eac06bd8e69a7`; staged snapshots compared byte-for-byte equal. No index-changing Git command was issued; unrelated working-tree work was retained.

Final read-only listener observation still reports Java4045 on127.0.0.1:18080, frontend4255 on127.0.0.1:5500, Python80995 on127.0.0.1:8000 and llama79855 on127.0.0.1:8082, matching the supplied baseline identities. No running service was stopped/restarted by this task. No request was made to port8080 or any live business/authentication endpoint; no live database connection/count query was performed. Protected demo settings/secrets/backups were not changed. The original successful V10 migration remains historical operator evidence; no new migration was added/applied.

### Resolution and remaining limits

The additional-Admin provisioning implementation blocker is resolved and the new JAR is packaged for review. **Deployment and OTP activation remain unperformed and await operator approval.** Neither disposable-account existence nor post-provisioning counts are newly claimed. Run the guarded disabled deployment first; only then can updated activation call the new API. The deployment helper intentionally expects the current approved four-user baseline and no eligibility; unexplained external changes require review rather than relaxing checks. Production public password recovery, full Admin management/approval, Docker and Phase6.7.4 remain out of scope.

The deliberately insecure displayed-OTP flow is still subject to the original gate, exact two disposable accounts and explicit local/private custody; this task does not enable it. After separately approved deployment/activation, the operator must perform the two manual OTP/reset/sign-in checks and deactivation described above. No runtime credential is requested in chat and no automatic live action follows this report.

## Operator Step17 deploy evidence

Outcome: verified. Stage: java-restart. Private evidence: `/Users/bhupirao/.config/paymesh-demo/otp-step17-deploy-20261114T181004Z-5kbrnbq_/evidence.json`.
No OTP generation or password reset was performed by the activation/deactivation script. Check private evidence for actual counts/PIDs/backup verification; do not assume unchanged account counts.

## Operator Step17 activate evidence

Outcome: verified. Stage: java-restart. Private evidence: `/Users/bhupirao/.config/paymesh-demo/otp-step17-activate-20261114T181150Z-exy1_tap/evidence.json`.
No OTP generation or password reset was performed by the activation/deactivation script. Check private evidence for actual counts/PIDs/backup verification; do not assume unchanged account counts.

## Final Phase 6.7.3 closeout preparation — 2026-11-15

### Evidence classification and current decision

The operator confirms **all 30 live browser checks passed: 8 persistent-session checks plus 22 Merchant/Admin/OTP security checks**. These are operator-performed results, not automated or independently repeated browser observations. The supplied outcomes are: both dedicated accounts reset successfully; old passwords rejected/new passwords accepted; prior sessions invalidated; pending Merchant remained pending; Admin retained authorized dashboard access; incorrect and superseded OTPs rejected; operational non-designated Admin and wrong-portal requests displayed no OTP; reset did not automatically sign in. The entire two check groups are confirmed passed; no additional per-check details, native cookie-attribute inspection or unreported browser actions are invented here.

The implementation baseline remains 283 isolated Java tests (zero failures/errors/skips), 634 frontend mocked checks, 9 existing mocked operational tests, three prior Bash syntax checks, successful packaging and diff check. These application suites were not rerun for operations/documentation-only preparation. **Live audit verification, OTP deactivation and post-deactivation verification are still pending operator execution. Phase6.7.3 is not marked fully closed or OTP disabled by this preparation.** No Phase6.7.4/Docker work starts.

### Successful deployment and activation evidence inspected

The agent read the two specified protected evidence JSON files, returning only whitelisted non-secret results. No evidence content was dumped wholesale, no protected key/password/token was displayed, and no live database connection was used to inspect this evidence.

- Deployment evidence `otp-step17-deploy-20261114T181004Z-5kbrnbq_/evidence.json`: success=true, Verified deployment, recovery disabled, Java4045→7735; entity counts before/after 4/3/3/1/6/4. Backup listing/extraction verified, mode600, no test restore. Backup SHA256 `2d3f7f6c5ace35dd73d25897e299c8ba3f8e6705bedab60c58c97ee82c30c8ac`.
- Activation evidence `otp-step17-activate-20261114T181150Z-exy1_tap/evidence.json`: success=true, Verified activate, recovery enabled, Java7735→8001. Both adminCreatedByScript and merchantCreatedByScript are true. Actual recorded counts increased from 4/3/3/1/6/4 to **6 users / 4 merchants / 4 memberships / 2 registrations / 6 payments / 4 refunds**. These are recorded activation-time measurements, not a new current database observation.
- Activation pre-OTP backup: `~/.config/paymesh-demo/backups/paymesh_demo-pre-otp-activate-20261114T181218Z-wc1ie9hy`, SHA256 `f945faf9a50e42cafb709ee7e6b4f6e1cd642274fa24f813a6b96707a654b342`; successful mode600/list/extraction evidence; no test restore. It predates both disposable accounts and is the verifier's fixed row-comparison reference.
- Recorded preserved services during deployment/activation: frontend4255, Python80995, LLM79855, with matching start identities in those evidence records. Preparation has not freshly polled the services or assumed those PIDs are permission to stop them; operational commands rediscover identities/bindings.

This supersedes historical statements that additional Admin provisioning or live activation was still blocked. `otp-admin-demo` was created through authenticated AccountAdministration API and `otp-merchant-demo@example.test` through pending registration, as recorded by successful activation. Exact account UUIDs stay in protected evidence/manifest rather than this public report. Audit-level actor/target/state confirmation remains the next read-only step.

### New guarded read-only verification

Created:

- `backend/scripts/verify-phase673-closeout.sh` — private Mac Terminal wrapper, modes `pre` and `post`, hidden database password from `/dev/tty` only.
- `backend/scripts/phase673_closeout.py` — standard-library read-only audit using existing Ops identity, protected-file, strict launch, GET, no-redirect and sanitized evidence helpers.
- `backend/scripts/test_phase673_closeout.py` — mocked operational regression tests.

Modified: this report only. Existing activation/deployment/deactivation scripts, shared Ops helper, application sources, migrations, dependencies, frontend/proxy, private configuration and backups are unchanged during preparation. No packaging is needed for this operations-only addition.

The verifier pins paymesh_demo/paymesh_demo_user/127.0.0.1:5432; independently verifies current_database(), current_user, host(inet_server_addr()), inet_server_port() and successful V1–V10 history. Every SQL call uses an explicit **REPEATABLE READ READ ONLY** transaction plus the existing default-read-only connection setting, UTC and a bounded statement timeout. Its full audit snapshot is collected in one read-only transaction. `write=True` is rejected. It never calls the imported activation/restart/provisioning functions, authenticates a user, sends a recovery POST or performs financial mutations.

Fresh Java/frontend/Python/LLM executable/cwd/PID/start/binding checks and reviewed JAR/launch checks are reused; only literal loopback18080/5500/8000/8082 qualify. Expected counts are 6/4/4/2/6/4. Persistent-session origin/local HTTP, demo profile, forwarding and disabled financial scheduling flags remain checked. Direct and frontend-proxied capabilities, Java readiness/payment health, proxy payment health and frontend landing availability are GET-only checks. Pre expects capabilities=true and the activated Java PID; post expects false and allows the Java restart required by deactivation while requiring preserved frontend/AI/LLM identities.

Account checks use actual V8/V9/V10 schema:

- Operational Admin enabled ACTIVE ADMIN-only and original authorization version; both dedicated accounts present, enabled, exact single roles/status; dedicated Merchant remains PENDING_APPROVAL with its sole inactive membership and unverified/inactive registry, no grant/verification actor.
- Activation UUID manifest associations, exact intended portals and actual designated_by/review_reference are verified. Pre permits enabled eligibility for precisely those two accounts; post requires zero enabled eligibility and retains both disabled target rows.
- Each dedicated account must have exactly one successful LOCAL_DEMO_PASSWORD_RESET, source insecure_local_demo_on_screen_otp, null authenticated actor fields, correct ACCOUNT target and consistent occurred_at. Expected authorization version is1 from original new-account version0 plus one reset. Unexpected additional reset counts or version changes fail closed with actual counts/versions in sanitized protected evidence rather than inventing a pass.
- ACCOUNT_CREATED for the new Admin must record the operational authenticated Admin UUID/login as actor, ADMIN role metadata and a consistent timestamp. No successful local-demo reset of operational/non-designated accounts is allowed.
- Retained prior-version session families must be present and revoked by reset time. **Later current-version sign-ins may remain valid/unrevoked**; the verifier reports those separately. Missing retained history cannot be silently certified as successful revocation.
- Old-version reset grants must be consumed and cannot pass current-version validation. This is read-only state/source verification, not a new mutating replay attempt. The audit schema does not record a challenge UUID in each success event, so the verifier does not pretend to establish an exact per-event grant link: it checks successful target/source/version, retained consumed pre-reset grants and revocation invariants. Operator browser evidence separately confirms old-session denial. Post requires no unconsumed challenges or grants anywhere, a stronger condition than merely waiting for expiry. Unexpected records cause a stop, not broad cleanup SQL.

### Financial/account row integrity comparison and privacy

Matching payment/refund counts alone is insufficient. On operator execution, pg_restore is used **without a database target**, only to extract selected COPY table data to the helper's private process memory. No extracted SQL is executed and no backup is restored. The protected archive's SHA256 is rechecked against the successful activation evidence, and its listing must parse. The parser handles inspected public table/column syntax, COPY NULL/control escaping, exact decimal values and timezone-normalized timestamps; missing/changed schema or malformed data fails closed.

Full row multisets are compared for eight tables: payments, refunds, payment_gateway_transactions, idempotency_keys, simulated_gateway_outcomes, webhook_events, reconciliation_jobs and reconciliation_attempts. Existing pre-OTP app_users/user_roles/merchants/merchant_memberships/merchant_registrations rows must also remain present byte/value-equivalent under type-aware comparison, while the two authorized disposable-account additions are allowed. All-column comparison detects changed financial values even if counts stay6/4. It does not claim an actual database restore test, database-wide physical integrity or comparison of every PostgreSQL object/sequence/audit row.

For pre→post preservation, the first passing pre-audit saves `~/.config/paymesh-demo/phase673-closeout-pre.json` mode600. It contains a private random **integrity-comparison key** and keyed fingerprints, never raw account password hashes or financial rows. This is not the OTP recovery key and is not installed in application configuration. Post compares all six account rows (including new password hashes in memory), roles/registry/memberships/registrations and all eight financial tables, plus non-recovery launch settings and preserved service identities. This confirms the new hashes were not changed by deactivation without asking for the new passwords or issuing logins. Actual BCrypt matching remains operator browser evidence. A repeated pre-audit reuses the original baseline only if unchanged; it does not silently replace evidence after drift. A missing post baseline stops verification.

Raw archive/live password hashes and row contents are necessarily read into process memory for these comparisons but are never printed, placed in arguments, persisted in audit evidence or written to the report. OTP, refresh-token and reset-authorization digests are not selected. Only safe counts, audit timestamps, versions, revocation totals, comparison results and service identities enter protected evidence. Python/process memory cannot be perfectly erased; operator custody remains required. Do not display the private baseline JSON, keys, raw archives, logs or session credentials in chat/screenshots.

### Existing deactivation review — actual behavior

`disable-phase673-otp-demo.sh` is unchanged and remains the supported operator procedure. It discovers and validates actual service/DB identity, requires the protected two-target manifest and V10 history, and makes a fresh verified backup before changes. It appends a protected `enabled=false` properties file and pins the disabled flag at startup. It preserves original session/JWT/database/gateway/AI/scheduling flags and additional configuration locations; only the verified demo Java is restarted when required, with readiness/direct/proxy capability checks. Frontend/Python/LLM must retain their identities.

After global disablement, the exact two target eligibility rows are set enabled=false and their challenges/grants consumed under AccountAdministrationLock's advisory-lock identity in one explicit transaction, using the same consumed_at semantics as LocalPasswordRecovery.invalidate(). No users/passwords/roles/status/authorization versions, original accounts, memberships, financial rows or offline Admin recovery implementation are modified. No account is deleted. A partial failure stops and retains protected evidence; it never performs broad invalidation, automatic restore, forced kill or blind restart. The post verifier adds explicit grant/account/financial-content checks beyond the disable script's existing counts/capability checks.

**Key retention:** the disable helper does not remove the old key-containing file or its earlier additional-location entry. The key remains in mode600 private configuration under a mode700 directory; LocalDemoRecoveryGate's constructor can still read it into memory even with configured=false. `enabled()` is false and `key()` throws while disabled, and recovery operations reject before using it. Thus it is securely retained but unused by the disabled flow, **not erased or removed from the configuration chain**. No key deletion/rotation/configuration pruning is silently performed. Never copy these private demo files/keys into a public deployment.

### Exact remaining operator commands

Pause recovery/account/financial activity and close unnecessary tabs during the audit/deactivation window. In a private, unrecorded Mac Terminal with no shell tracing, from the repository root:

```bash
cd "$HOME/Developer/paymesh-ai"
/bin/bash backend/scripts/verify-phase673-closeout.sh pre
```

Enter only the existing paymesh_demo_user password at the hidden terminal prompt. This command must pass first. It compares existing data with the verified pre-OTP archive and creates the protected pre→post integrity baseline. If counts, audit counts, versions, identities or rows differ, stop and review the private evidence; do not edit the script's expectations, reset another password or execute repair SQL to force a pass. An extra reset is reported as an actual deviation to investigate.

After a successful pre-audit:

```bash
/bin/bash backend/scripts/disable-phase673-otp-demo.sh
```

Enter the hidden database password. This is the **only** command in this sequence that changes eligibility/challenge state or restarts Java. It must report Verified; inspect its private evidence if it stops. It preserves the two accounts/new passwords and persistent sessions. Do not blindly repeat on a partial failure or remove the target manifest.

Then:

```bash
/bin/bash backend/scripts/verify-phase673-closeout.sh post
```

Enter the hidden database password again. This checks disabled capabilities/eligibility/consumed records, accounts/new hashes unchanged from pre, original rows unchanged from pre-OTP, readiness/health/frontend and preserved services/settings. It performs no reset, login or financial mutation. Missing baseline/retained evidence or changed records fails closed. Each successful/failed run appends a clearly named verify-pre/verify-post outcome and a protected evidence reference using the existing helper; it does not invent success when the operator has not run it.

Expected sanitized successful output (actual values are generated/checked at runtime):

```text
Successful reset counts admin|merchant: 1|1
Counts users|merchants|memberships|registrations|payments|refunds: 6|4|4|2|6|4
Account integrity, reset audit, prior revocation and consumed grants: PASS
Financial row contents: MATCH (8 pre-OTP archive tables; no restore)
Capabilities localDemoEnabled=true; readiness/health/frontend: PASS
Verified. Evidence: <protected verify-pre evidence path>
```

The disable command's successful summary is `Verified. Evidence: <protected disable evidence path>`. Post output changes localDemoEnabled to false and adds `Pre/post account/password/financial fingerprints and preserved services: MATCH`. Failed checks emit only fixed safe messages (and actual reset counts where already collected), nonzero exit and a protected failure reference. No raw row/credential/OTP/digest/key output is expected. Terminal messages are templates here, **not executed live results**.

### Security limitations and final pending gate

Displaying an OTP to its requester is explicitly insecure and provides no ownership proof. **On-screen OTP must never be enabled in any public deployment**, regardless of free hosting/Docker/HTTPS. The unchanged local gate, database identity, actual loopback connectors, private attestation/key and per-account opt-in remain mandatory during this temporary demonstration. Public production-grade password recovery requires a separately designed and reviewed ownership-verification/delivery mechanism; it is not completed by this phase. Persistent sessions remain server-managed with the existing production HTTPS cookie requirements; local HTTP exceptions remain restricted to the private demo.

Only after the operator supplies successful pre-audit, disable and post-audit evidence may the report mark database audit and deactivation complete. The 30 confirmed browser checks and prior automated baseline do not substitute for those pending read-only/current-runtime checks. No live database access, audit run, deactivation, service restart, account/password change or financial mutation occurred during Codex preparation.

### Preparation checks actually executed

- `python3 -m unittest discover -s backend/scripts -p 'test_phase673*.py' -v`: **24 tests passed** — 15 new closeout tests plus all 9 existing operational tests, zero failures/errors, final run0.047s. No live DB/HTTP/service action was used. Coverage includes read-only transaction wrapping/write refusal, exclusion of OTP/refresh/reset digests, valid current-version sign-ins after reset, disabled/consumed postconditions, missing/extra/operational resets, actor/source/timestamp/version failures, pending registry/membership/role safeguards, COPY escaping/NULL/empty/malformed data, exact large decimals/timezone normalization, count-preserving financial changes, bad archive checksum, pre/post secret-safe keyed comparison, missing baseline and absence of mutating/recovery HTTP calls.
- Bash `-n`: new verify wrapper and all three existing activate/disable/deploy wrappers passed. Both new Python modules compiled syntactically without executing the operator entry point.
- `git diff --check`: passed. No full Java/frontend test or packaging rerun; no application/runtime/proxy code changed.
- A mocked archive-comparison test initially exposed macOS temporary-path aliasing (`/var` versus `/private/var`). The verifier now validates mode/ownership of the backup directory and compares canonical paths on both sides; the corrected full mocked run above passes. No live archive/table was accessed to fix it.

**Concurrent staging observation:** initial index SHA256 `dd256a2b13c4eea5fe243bd3039028d6405be0792f0b77542baf90cc2fdcdcf4`; final observed index SHA256 `743146a9a019262058c55a11efa6a91c2a9ca4ce38930a14747c409304da9273`. Initial/final staged binary diff SHA256s `1ccc5220b518016376f4d450ff08de69364a603fc2c2dd904cfadc55aa18605b` / `cc7a7b968fd9817592a9df6880d22235869c037ffc3da630811c7df551a1ca7e` differ. Comparing patch-block hashes identifies concurrent staging changes for the three new verifier files only (verify-phase673-closeout.sh, phase673_closeout.py, test_phase673_closeout.py). The agent issued no add/commit/push/reset/clean/restore/index-write command and left the external staging untouched; it does **not** claim an unchanged index. Existing unrelated working-tree work was not restored or overwritten. Later external staging may change these observations again.

Preparation is complete; current database audit and OTP deactivation are **not executed/certified**. The next actions are the three exact operator commands above, with successful live evidence required before final closeout. No known implementation blocker remains for those commands; missing/changed protected evidence, additional resets, drift, expired/cleaned audit history or failed runtime checks deliberately stop verification for review rather than producing a fabricated pass.

## Operator Step17 verify-pre evidence

Outcome: stopped; no automatic retry/restore. Stage: read-only-snapshot. Private evidence: `/Users/bhupirao/.config/paymesh-demo/otp-step17-verify-pre-20261114T192333Z-78oeqnfd/evidence.json`.
No OTP generation or password reset was performed by the activation/deactivation script. Check private evidence for actual counts/PIDs/backup verification; do not assume unchanged account counts.

## Operator Step17 disable evidence

Outcome: verified. Stage: eligibility-and-invalidation. Private evidence: `/Users/bhupirao/.config/paymesh-demo/otp-step17-disable-20261114T192418Z-f2y4hrzi/evidence.json`.
No OTP generation or password reset was performed by the activation/deactivation script. Check private evidence for actual counts/PIDs/backup verification; do not assume unchanged account counts.

## Operator Step17 verify-post evidence

Outcome: stopped; no automatic retry/restore. Stage: read-only-snapshot. Private evidence: `/Users/bhupirao/.config/paymesh-demo/otp-step17-verify-post-20261114T192457Z-_z3n8mrc/evidence.json`.
No OTP generation or password reset was performed by the activation/deactivation script. Check private evidence for actual counts/PIDs/backup verification; do not assume unchanged account counts.

## Session-revocation audit blocker investigation — preparation only

### Observed evidence and exact failed condition

Read protected `otp-step17-verify-pre-20261114T192333Z-78oeqnfd/evidence.json` using a non-secret whitelist. It records failed verify-pre at read-only-snapshot, actual counts6/4/4/2/6/4, successful reset counts Admin1/Merchant1, and authorization versions operationalAdmin3/dedicatedAdmin1/dedicatedMerchant2. It does **not** retain session rows, reset timestamps or a partial recoveryAudit result. Therefore it cannot identify whether the error was caused by zero matching families, an unrevoked family or a revocation later than the reset audit. No password/token/digest/key was read from this evidence.

Exact current verifier SQL for the relevant snapshot components:

```sql
SELECT user_id, authorization_version, created_at, revoked_at
FROM public.auth_sessions;

SELECT actor_user_id, actor_identifier, event_type, resource_id,
       resource_type, outcome, metadata, occurred_at
FROM public.security_audit_events
WHERE event_type IN ('LOCAL_DEMO_PASSWORD_RESET', 'ACCOUNT_CREATED');
```

The complete snapshot is collected by json aggregation inside an explicit REPEATABLE READ READ ONLY transaction in UTC. For each dedicated account, `when` is its sole successful LOCAL_DEMO_PASSWORD_RESET's occurred_at. The condition is precisely:

```python
prior = [s for s in snapshot['sessions']
         if s['user_id'] == user['user_id']
         and s['authorization_version'] < user['authorization_version']]
require(prior and all(s['revoked_at'] is not None
                      and instant(s['revoked_at']) <= when for s in prior),
        'Prior session-family revocation is missing/inconsistent; cannot certify from retained rows.')
```

It never uses created_at to select `prior`; lower-than-**current** version is its sole session cohort criterion. The loop processes Admin first. The observed failure therefore occurs for the dedicated Admin's version<1 families before the Merchant is examined. It does not, by itself, establish any application security defect. The subsequent hardcoded dedicated-version==1 assertion would also require review for the Merchant's recorded version2; one reset does not generally imply current version1 if Logout All/security changes have also incremented it. This task does not replace that assertion or assume why the version increased.

### State discrepancy discovered in existing records

The prompt says deactivation has not occurred. The repository report, however, contains later operator-run evidence references. Read-only inspection of those protected summaries shows:

- `otp-step17-disable-20261114T192418Z-f2y4hrzi/evidence.json`: success=true, Verified disable, recoveryEnabled=false, newJavaPid9556, counts before/after6/4/4/2/6/4.
- `otp-step17-verify-post-20261114T192457Z-_z3n8mrc/evidence.json`: success=false at read-only-snapshot, same counts, versions3/1/2 and successful resets1/1.

These are recorded operator outcomes, not actions executed by the agent or a new current-runtime check. They contradict the supplied “not executed” statement and must be reconciled during operator review. Do **not** reactivate OTP or repeat deactivation solely to match the prompt. The new diagnostic works with either flag state and reports the currently inspected launch flag; it sends no recovery/authentication HTTP request. Final post-audit/closeout remains blocked, regardless of recorded disable success.

### Source-supported conclusions and remaining unknowns

Inspected actual PersistentSessions, LocalPasswordRecovery, AuthenticationClock, AuthStore, JwtAccountValidator, V10 and SessionRecoveryIntegrationTest (including reset revocation, old credential rejection, JWT revocation, Logout All, expiry and rollback cases).

- Password reset changes the existing password and increments authorization_version in the same transaction as LOCAL_DEMO_PASSWORD_RESET. V10's AFTER UPDATE trigger sets all account session revoked_at values to COALESCE(revoked_at,CURRENT_TIMESTAMP). Success audit construction uses Java Instant.now(). No separate authenticated actor is fabricated for recovery.
- PostgreSQL CURRENT_TIMESTAMP is the **transaction start** time, potentially before lock waits/hash calculation. Java AuthenticationClock.now() and audit Instant.now() are wall-clock observations later in the flow. Thus different timestamps are expected; revoked_at need not be greater than created_at when a transaction waited for the common lock. Audit time is neither commit time nor a timestamped identifier of the exact family/grant that was used.
- Declared TIMESTAMPTZ columns default to PostgreSQL microsecond precision, while Java Instant can hold nanoseconds. The diagnostic reads actual datetime_precision and reports exact signed microsecond differences, including equality boundaries. No arbitrary clock-skew allowance or timestamp inequality relaxation is introduced. Clock drift/rounding cannot be declared the actual cause without rows.
- `PersistentSessions.cleanup()` runs only while creating a new session, deleting at most100 families with absolute_expires_at strictly less than AuthenticationClock.now()−24h. Refresh credentials cascade on deletion. There is no deletion audit/tombstone here. Expiry alone does not delete rows; null/absent rows do not prove successful revocation. The minimum configured lifetime permitted by this implementation is900seconds, so account creation plus24h15min provides an earliest possible cleanup bound under normal clock ordering; crossing that bound permits, but does not prove, cleanup.
- Logout All increments authorization_version and revokes families. Consequently, a valid **post-reset** family can later have version<current and a revocation time after the reset. A new mocked fixture reproduces that semantic false-positive of the original predicate. It is a proven limitation of cohort selection, **not proof that it caused this Admin failure**. No current-version post-reset family is required to be revoked by the diagnostic.
- Current family authorization additionally requires enabled user, nonempty current roles, no revoked_at, unexpired absolute/idle timestamps, and equal version/status/sorted roles snapshots. JWT validation checks signed claims/current roles/status/version and, when sid exists, that family. A pre-reset unrevoked row can still be blocked by version mismatch, but that is not proof that the required revocation write happened. Legacy no-sid tokens are not inventoried as families and still undergo version/role/status/expiry validation.

**Actual cause remains unknown** among missing history/never-created families/cleanup, late or missing revocation, timestamp ordering/precision, or an application/trigger defect. The saved evidence lacks the rows needed to distinguish them. No application or existing closeout verifier change is justified as a fix for this exact runtime failure yet. The existing verifier stays fail-closed; it has not been weakened to pass. Do not rerun it expecting this preparation alone to fix the blocker.

### New narrowly scoped read-only diagnostic

Created:

- `backend/scripts/diagnose-phase673-session-revocation.sh`.
- `backend/scripts/phase673_session_diagnosis.py`.
- `backend/scripts/test_phase673_session_diagnosis.py`.

Modified: this report only. Existing verifier/tests/activation/deactivation, application sources, migrations, configuration and financial logic remain unchanged.

The wrapper accepts no arguments; loads only the established protected environment; reads the database password silently through `/dev/tty`, never chat/argv/history; and invokes the standard-library helper. Existing Ops protected-file, service binding/cwd/PID/start, reviewed JAR/launch, pinned psql target and sanitized failure helpers are reused. It does **not** call Ops.preflight's broader business/account-count queries, imported restart/provisioning/eligibility operations or any HTTP endpoint.

It independently verifies paymesh_demo/paymesh_demo_user/127.0.0.1:5432, transaction_read_only=on and successful V10. All SQL is wrapped in explicit REPEATABLE READ READ ONLY transactions, UTC and bounded statement timeout. The diagnostic snapshot uses one transaction and an explicit target CTE binding **only the two fixed dedicated UUID/name pairs** from the protected manifest. No operational Admin/account financial rows are inspected. Database catalogs for the V10 trigger/function body and timestamp precision are read; function body is compared in memory with reviewed V10 and is not printed or persisted. A missing/disabled/different trigger is reported explicitly, not silently accepted.

For each dedicated account, sanitized output/private evidence includes current version/status/roles/account creation time; successful reset count/timestamps; families created before, equal to and after the audit boundary; revoked-by-reset counts; unrevoked pre-reset counts; exact revocation/creation/expiry timestamps; signed microsecond differences; source-based current cleanup eligibility; original predicate components; current family/account eligibility; and retained recovery challenge version/time metadata without OTPs/digests or challenge identifiers. Session identifiers are replaced with sorted ordinals. The schema contains **no session revocation reason column**; the diagnostic reports “Not recorded in auth_sessions,” never invents PASSWORD_RESET/LOGOUT reasons.

Missing pre-reset rows are labeled evidence-insufficient, not success or proof of cleanup. Multiple/missing reset events do not receive a fabricated single boundary. Unrevoked pre-reset rows remain an anomaly even if expiry/version blocks access. A family passing necessary current row/account checks is flagged, but full JWT/refresh possession, signature, token expiry and acceptance are not experimentally tested. Zero candidates concerns only retained rows at the captured observation time; it does not certify historical revocation or inventory all previously issued legacy tokens. Database/operator clock brackets and actual timestamp precision are captured for review, not marketed as Java clock synchronization measurements.

The script prints/saves only this sanitized diagnosis, its stage and a protected evidence reference. Capture completion is explicitly **not closeout certification**. No password hashes, OTPs, JWTs, refresh/reset digests, reset grants or recovery key values are selected or displayed. SQL queries contain only canonical target UUIDs and fixed names, not credentials. No session is created, refreshed, revoked or deleted; no trigger/audit/account/financial row is modified; no service is restarted and no baseline is overwritten. Existing protected evidence stays untouched.

### Exact next operator command and decision gate

Run only this diagnostic in a private unrecorded Mac Terminal, without tracing/pipes/arguments:

```bash
/bin/bash "$HOME/Developer/paymesh-ai/backend/scripts/diagnose-phase673-session-revocation.sh"
```

Enter the existing paymesh_demo_user database password only at its hidden terminal prompt. No confirmation phrase or evidence-file argument is required. This command has **not** been run during Codex preparation. Return the sanitized diagnostic result/evidence reference for review; do not expose private raw logs or credentials. Do not reset another password, edit session timestamps, fabricate rows, delete families, restart or run deactivation automatically as a workaround.

After diagnosis:

1. If rows demonstrate a verifier cohort/timestamp assumption error, correct precisely that assumption with row-reproducing regression tests while preserving revocation, version and current-usability assertions. Investigate Merchant version2 separately rather than replacing1 with2 without evidence.
2. If retained history is insufficient, record that limitation. The smallest additional experiment, **only after separate approval if needed**, is to privately sign in a dedicated disposable account, record its version/family presence through this read-only diagnostic, perform one deliberate authorized demo reset, and read-only verify the same retained family is revoked and the old browser session denied. Use only the disposable accounts; never manufacture uncertain history or reset operational accounts. This changes audit/reset counts and would require explicitly reviewed closeout expectations, not an automatic retry. It is proposed, not executed or presently required.
3. If an actual trigger/session revocation defect is shown, fix the application transaction/trigger behavior with isolated reproduction tests, run the documented full isolated Java suite/package, and prepare separately approved guarded deployment. Never repair live rows to hide the defect.
4. Once the precise blocker and state discrepancy are resolved, complete the corrected pre-audit/deactivation-if-still-needed/post-audit sequence. Because protected records already report a disable success, verify current state before contemplating any further disable operation. Do not run the existing three-command sequence blindly while the failed audit is unresolved.

No further browser reset test is currently justified: first obtain read-only evidence. Application changes/full Java/frontend reruns/deployment are not presently necessary or performed. Phase6.7.3 remains **incomplete pending diagnosis and successful final audit**.

### Executed blocker-preparation verification and Git observation

`python3 -m unittest discover -s backend/scripts -p 'test_phase673*.py' -v`: **35 tests passed**, zero failures/errors, final run0.069s — 11 new session-diagnosis tests plus all24 existing operational tests. These use sanitized fixtures/mocks only, not a live database/server. New cases cover revoked pre-reset and valid post-reset families, missing history without a false success claim, the later-Logout-All cohort false-positive, genuinely unrevoked families both with/without current-version eligibility, exact timestamp equality/±1microsecond boundaries, absolute/idle expiry and strict cleanup boundaries, account-status/roles/enabled rejection, absent/multiple reset audits, explicit two-account SQL scope/read-only wrapping, exclusion of secret columns and absence of mutating/HTTP calls. The existing failing closeout assertions remain unchanged; these are diagnostic regressions, not a fabricated reproduction of unknown live row values.

Bash syntax checks passed for diagnose, verify, activate and disable wrappers; both new Python modules compiled syntactically. `git diff --check` passed. No full Java/frontend suite or package rerun: application code is unchanged. No live diagnostic/SQL/login/refresh/reset/deactivation, service restart, database repair or financial request was performed by the agent. Protected evidence/configuration/backups were not altered; only the specified evidence summaries were read.

Initial Git index SHA256 `743146a9a019262058c55a11efa6a91c2a9ca4ce38930a14747c409304da9273`; final observed `456cdc2935ee64f8ab088b4fee1d9b4dd0cb92d7dcd10d225ded840a3809d591`. Staged binary diff hashes changed from `cc7a7b968fd9817592a9df6880d22235869c037ffc3da630811c7df551a1ca7e` to `fc02d79965afd7447a9f6db37a29f3412fa1e047d1c2312d070f3c273912f474`. Patch-block comparison identifies concurrent external staging changes for the new diagnose shell wrapper and phase673_session_diagnosis.py. No staging/index-write command was issued by the agent; external staging was left untouched, never restored/reset. This is not an unchanged-index claim; further external staging may change the observations again.

**Stop state:** diagnostic preparation complete, exact live root cause not established, original verification still blocked, recorded disable success/current-state discrepancy awaiting operator review. Run only the diagnostic command above next and provide its sanitized evidence. No further browser reset test or application deployment is authorized or necessary at this point. Phase6.7.3 is not complete.

## Operator session-revocation diagnostic evidence

Diagnostic capture completed; **not closeout certification**. Stage diagnosis-captured-not-certified. Protected evidence: `/Users/bhupirao/.config/paymesh-demo/otp-step17-diagnose-session-revocation-20261114T193805Z-36o57blm/evidence.json`. No password/session/OTP/service mutation performed.

## Corrected final session audit — already-disabled closeout preparation

### Actual diagnosis and root cause

Read the protected diagnostic `otp-step17-diagnose-session-revocation-20261114T193805Z-36o57blm/evidence.json` and the authentic activation, failed pre-audit, successful disable and failed post-audit evidence. The diagnostic capture succeeded but deliberately did not certify closeout. The operator separately reports the frontend-proxied capabilities response `{localDemoEnabled:false}`. **Deactivation has occurred; no reactivation or repeat deactivation is required or performed.** Current database verification by the corrected final mode remains pending operator execution.

Actual captured timelines:

| Dedicated account | Reset audit UTC | Retained family creation UTC | Version at capture / family | Revocation UTC | Retained pre-reset rows |
| --- | --- | --- | --- | --- | --- |
| Merchant | 2026-11-14T18:17:03.513322Z | 2026-11-14T18:17:25.621579Z | 2 / 1 | 2026-11-14T18:17:43.246398Z | 0 |
| Admin | 2026-11-14T19:02:03.361913Z | 2026-11-14T19:02:21.491717Z | 1 / 1 | 2026-11-14T19:03:52.116685Z | 0 |

Both have exactly one successful reset and one retained family, each family created **after** its reset. Both retained families fail the current family/account authentication checks. Admin remains enabled ACTIVE ADMIN-only; Merchant remains enabled PENDING_APPROVAL MERCHANT-only. The actual V10 trigger was enabled and its function body matched reviewed source. Normal documented cleanup could not yet have become eligible at diagnostic capture. This excludes normal eligible cleanup as an explanation at that time, but does not establish whether earlier families were never created or removed by an unrecorded path. Deleted-family history is unavailable. No JWT acceptance/replay was tested and legacy no-sid tokens are not inventoried as families.

The original Admin failure was the verifier's requirement that lower-version families must exist: that set was empty. The Merchant's lower-version predicate additionally misclassified its **post-reset** version1 family as historical because the account was currently version2, then rejected its legitimate later revocation timestamp. The hardcoded current-version==1 assertion was also not a valid general derivation from one reset. These are demonstrated verifier assumptions, not evidence of an application revocation defect. The supplied rows cannot prove historical pre-reset-family revocation; changing them to a historical PASS would be false.

### Merchant version2 — what can and cannot be established

The retained pre-reset challenge metadata has version0; the retained later family was issued at version1; current version is2. This is consistent with the reset invalidating version0 and a further increment occurring subsequently, but the available evidence does not identify the exact operation causing the additional increment. The family table has no revocation-reason column, and PersistentSessions.logoutAll does not produce a security audit event naming that operation. Therefore **ADDITIONAL_INCREMENT_UNEXPLAINED** is retained; the verifier does not label the increment Logout All merely because that operation can increment versions.

The snapshot now includes safe relevant successful account-security audit events (enabled/disabled, membership assigned/revoked and offline recovery) for review. Their type/time are possible contributors, not a fabricated complete version-change ledger or exact causal attribution. No extra version-changing operation was performed to investigate this gap. Operational Admin's version/identity/password/roles are compared with the existing activation manifest and protected archive, rather than reset to an earlier documentation value.

### Corrected classification and strictness

`session_history()` now selects before/equal/after cohorts using actual family created_at relative to the specific reset audit occurred_at. Authorization version is used for actual current account/session validation and ambiguity detection, **never as the sole historical cohort selector**. Post-reset rows are excluded from historical revocation assertions even when their version is lower than the current account version. A legitimate current-version post-reset sign-in need not be revoked.

The outcomes are distinct:

- VERIFIED_FROM_RETAINED_ROWS: retained pre-reset rows exist and all satisfy the revocation boundary, with no ambiguous row ordering/version condition. This covers retained rows only, not deleted history.
- HISTORICAL_EVIDENCE_UNAVAILABLE: no retained pre-reset rows and no exact-boundary rows; missing rows are not proof of successful revocation or deletion.
- AMBIGUOUS_BOUNDARY: created_at equals the audit timestamp, or version/order metadata prevents strict ordering certification. No arbitrary skew allowance is added.
- REVOCATION_INCONSISTENT: a retained pre-reset family lacks revoked_at or has revoked_at later than the reset audit boundary. Expiry/version mismatch does not excuse that inconsistency.
- CURRENT_SECURITY_FAILURE: a retained pre-reset family passes necessary current family/account checks. This blocks verification; it is not represented as an experimentally accepted signed JWT.

Current checks preserve enabled/nonempty role state, no revoked_at, strict absolute/idle expiry, equal authorization version, equal account status and exact sorted role snapshot. Historical and current security statuses/counts are reported separately. Timestamp equality and ±microsecond ordering remain visible; PostgreSQL transaction-start CURRENT_TIMESTAMP is not treated as Java audit Instant.now() or commit time. Existing source locks/transaction semantics remain unchanged.

Both supplied actual timelines now yield **HISTORICAL_EVIDENCE_UNAVAILABLE**, zero retained pre-reset candidates and no historical PASS. Retained unrevoked/late-revoked pre-reset families and currently eligible pre-reset families remain blocking conditions, including in final mode. Strict `pre`/`post` modes continue to require retained historical/grant proof, explained single-reset versions and the original pre/post baseline behavior. They are not the appropriate mode to reconstruct a failed pre-audit after deactivation.

### Authentic usable baseline inventory

Observed during preparation without database access:

- Activation evidence is successful and references the verified **pre-OTP** custom-format archive, before both disposable accounts were created. It supports existing operational account/ownership/financial row comparisons, not the new passwords.
- The pre-audit and post-audit both failed. Neither contains successful fingerprint comparisons, and `~/.config/paymesh-demo/phase673-closeout-pre.json` **does not exist**. No successful pre-audit baseline is invented or created retroactively.
- Successful disable evidence references a protected custom archive created **after both resets, before deactivation**: `~/.config/paymesh-demo/backups/paymesh_demo-pre-otp-disable-20261114T192424Z-ekellz2y`. Recorded SHA256 `c19507795035153ba2b425a0e522fea4c11ce1e0ad30cd8bc88a514715db3909`; recorded mode600, list/extraction verified, no test restore. Preparation confirmed the file exists but did not inspect its contents or newly reverify its checksum. The operator-run final mode will reverify it and compare its rows.
- Activation/deactivation JSON evidence contains **no account/password/financial fingerprint fields**. The real archives are usable row baselines, not pre-audit HMAC evidence. Exact row comparisons against an authenticated archive are stronger than count-only checks, but cannot be mislabeled as a fingerprint comparison that never happened.

### Guarded final read-only mode

The existing wrapper accepts `final` in addition to `pre`/`post`. Final mode requires authentic successful disable evidence, matching target UUIDs/counts, its Java PID/artifact, the exact disabled launch flag and fresh direct/proxy capabilities=false. Existing database identity, V10 history, literal loopback service identities/bindings, private configuration, no-store GET health and read-only transaction safeguards remain intact. It cannot enable recovery, create sessions/accounts, reset passwords or restart/deactivate anything.

It verifies actual6/4/4/2/6/4 counts; operational Admin and both dedicated account states/roles; pending registry/membership restrictions; actual successful reset targets/source/null actor/timestamps; authenticated additional Admin creation actor; zero enabled eligibility and consumed recovery challenges/grants. It records retained consumed grant evidence without claiming an exact audit-to-grant link absent from the schema. All application/financial authorization logic remains unchanged.

It performs the existing type-aware, exact-decimal COPY row comparison for **all eight financial tables** against the pre-OTP archive, plus preservation of all original account/role/registry/membership/registration rows. It separately compares **all rows of those eight tables and all five account/ownership tables exactly** against the pre-deactivation archive, including account password hashes in memory. This can establish preservation of both new password hashes and all six account rows across deactivation, without another login/password request or exposing hashes. It is an archive comparison, not a claim of fresh BCrypt matching or a restored database. All archives are mode/owner/path/SHA checked and extracted to memory; no SQL from them is executed or restored.

If authentic source fingerprints exist, comparison is allowed only with a successful pre-audit evidence reference and a timestamp before the recorded deactivation. A file alone is insufficient provenance. Missing pre-audit fingerprints are explicitly reported as UNAVAILABLE_NO_SUCCESSFUL_PRE_AUDIT and never created by final mode. Missing archive comparison sources are reported as unavailable; present but invalid/mismatching sources fail closed. Current financial pre-OTP archive verification remains mandatory. In this environment the pre-deactivation archive is available and expected to provide the exact account/password/financial comparison; its actual match is still pending execution.

Final mode checks Java readiness, direct/proxy payment health, frontend availability, persistent-session local origin/configuration and preserved frontend/Python/LLM identities against activation evidence. If authentic pre-audit fingerprints are available they also cover unchanged non-recovery launch settings; without them, source/settings checks and recorded activation/deactivation provenance are distinguished from an unavailable complete pre-audit settings fingerprint. No unsupported native-cookie or fresh browser-session test is claimed.

A successful final command reports **VERIFIED_WITH_DOCUMENTED_EVIDENCE_LIMITATIONS**, with strictFullCertification=false. Its success means the actual mandatory current checks passed and limitations were recorded, not full reconstruction of historical session proof. Bad current state, retained revocation inconsistency, unauthorized roles/eligibility, audit mismatch, financial/archive drift or untrusted evidence still causes nonzero failure. The 30 browser checks/password matching/session rejection remain separately operator-confirmed behavior. Historical row absence, missing pre-audit HMAC and the unexplained additional Merchant increment remain explicit limitations.

### Exact next operator command — no reactivation/deactivation

```bash
/bin/bash "$HOME/Developer/paymesh-ai/backend/scripts/verify-phase673-closeout.sh" final
```

Enter only the existing paymesh_demo_user password at the hidden `/dev/tty` prompt. No confirmation phrase, pre-audit evidence argument, password reset, login or deactivation command is required. Pause account/recovery/financial activity during the snapshot/comparison window. The agent has not executed this command or any live database query.

Expected sanitized successful result, conditional on all actual current checks passing:

```text
Successful reset counts admin|merchant: 1|1
Counts users|merchants|memberships|registrations|payments|refunds: 6|4|4|2|6|4
Current account/eligibility/reset-audit/grant checks: VERIFIED
admin: HISTORICAL_EVIDENCE_UNAVAILABLE; SINGLE_RESET_VERSION
merchant: HISTORICAL_EVIDENCE_UNAVAILABLE; ADDITIONAL_INCREMENT_UNEXPLAINED
Financial row contents: MATCH (8 pre-OTP archive tables; no restore)
Capabilities localDemoEnabled=false; readiness/health/frontend: PASS
preDeactivationArchive: VERIFIED_EXACT_ACCOUNT_PASSWORD_AND_FINANCIAL_ROWS
activationDeactivationFingerprints: UNAVAILABLE_NOT_RECORDED
preAuditFingerprints: UNAVAILABLE_NO_SUCCESSFUL_PRE_AUDIT
VERIFIED_WITH_DOCUMENTED_EVIDENCE_LIMITATIONS. Evidence: <protected final evidence path>
```

These are expected templates, not completed live results. The final mode writes a new protected outcome and report reference; failed historical evidence is left unchanged. It never fabricates a baseline or hides limited certification behind a generic full-PASS message.

### Files and remaining review

Modified `backend/scripts/phase673_closeout.py` (cohorts/outcomes/final evidence/archive comparisons), `backend/scripts/verify-phase673-closeout.sh` (explicit final mode), `backend/scripts/test_phase673_closeout.py` (complete session metadata in existing mocked fixtures), and this report. Created `backend/scripts/test_phase673_final_audit.py` (actual timelines, current/historical failures, boundary/missing history, disabled state and authentic available/unavailable baseline coverage). No application, migration, dependency, frontend runtime, private configuration or financial data changes.

No application defect has been demonstrated; no Java/frontend suite rerun, package or deployment is needed for these operational changes. No additional browser reset test is required for the limited result. If the operator later requires strict retained-row historical proof, a separately approved, targeted disposable-account sign-in/reset/read-only before/after comparison could establish a **new** controlled event, not recreate the missing original history. Do not perform it automatically or mutate old audit/session rows. Public deployment must continue to keep this insecure on-screen OTP disabled; production-grade recovery remains a separate design.

**Final database verification is not complete until the operator executes the final command and reviews its actual evidence.** Preparation stops here; no repeat deactivation, OTP enablement, password reset, restart, financial request or Phase6.7.4 work is performed.

### Executed correction checks and preservation observation

- `python3 -m unittest discover -s backend/scripts -p 'test_phase673*.py' -v`: **50 tests passed**, zero failures/errors, final run0.093s. This is15 new final-audit tests plus all35 previous operational tests. New cases reproduce both actual timelines, lower-version post-reset exclusion, valid unrevoked post-reset sign-in, retained revoked/unrevoked/late-revoked pre-reset families, equality/ambiguous/currently-usable boundaries, absent historical rows, strict-vs-limited modes, unexplained version2, active eligibility/unconsumed-grant rejection, missing baseline without creation, exact deactivation archive selection, available/unavailable authentic fingerprints and complete mocked already-disabled final-mode execution. No live HTTP/database/backup operation was used by tests.
- Bash syntax passed for the modified verify wrapper and existing diagnostic/disable wrappers. The modified verifier, existing adjusted fixture module and new regression module compiled syntactically. `git diff --check` passed.
- No Java/frontend suite rerun or packaging: no application/runtime/proxy code changed. Existing283/634 application baselines remain previously verified evidence, not newly executed results. No service/DB/password/OTP/financial operation was performed during preparation. Existing failed evidence and nonexistent pre-baseline were not overwritten.
- Initial Git index SHA256 `6910d12004bbd3833e0783ea5e6b32f790981eccdb8ff7f277b1c4d3c7f76abb`; final observed `3a92cedfcccac2555164b32a971cc9d6492d795549e0a4419368e90f84f14c2a`. Staged binary diff hashes changed from `0806293ee214768881b61d29ba1a6900d55921571a48f63f4a9263ab748011cd` to `2d992a724410a77eb26aceb2a36244e2dc4ee072547ae7c384b22a016b3a7afe`. Patch-block comparison shows concurrent external staging of `backend/scripts/test_phase673_final_audit.py`. No staging/index-write command was issued; external staging was left untouched rather than restored. No unchanged-index claim is made, and unrelated work was retained.

**Stop state:** verifier correction and final-mode preparation complete; operator execution of the single read-only `final` command is pending. Recovery is operator-confirmed disabled and must stay disabled. Expected final result is limited verification, not a fabricated full historical certification. Do not mark final database verification or Phase6.7.3 closeout complete before reviewing the operator's actual final evidence.

## Operator final read-only audit evidence

Current checks verified with documented evidence limitations. Strict full certification is not claimed. Protected evidence: `/Users/bhupirao/.config/paymesh-demo/otp-step17-verify-final-20261115T041143Z-1rl7fa8i/evidence.json`. No reset/deactivation/restart/financial action performed.

## DEFINITIVE PHASE 6.7.3 CLOSEOUT — November 15, 2026

**IMPLEMENTATION COMPLETE**

**LOCAL-DEMO VERIFICATION COMPLETE WITH DOCUMENTED EVIDENCE LIMITATIONS**

**GO FOR CONTINUED LOCAL-DEMO DEVELOPMENT**

**NOT PRODUCTION SECURITY CERTIFICATION**

This definitive section supersedes earlier pending activation/audit/deactivation/closeout statements while preserving them as historical records. The operator executed the guarded final read-only command successfully. The agent read the actual protected evidence at `~/.config/paymesh-demo/otp-step17-verify-final-20261115T041143Z-1rl7fa8i/evidence.json`, using a non-secret whitelist, and confirmed success=true, stage=read-only-final-verified, result=VERIFIED_WITH_DOCUMENTED_EVIDENCE_LIMITATIONS and strictFullCertification=false. No unrestricted full audit certification is asserted.

### Final verification totals and evidence categories

| Category | Verified result | Evidence boundary |
| --- | --- | --- |
| Isolated Java | **283 passed**, zero failures/errors/skips | Previously executed isolated PostgreSQL suite; not rerun for documentation |
| Mocked frontend | **634 checks passed** | Previous JavaScript/proxy mocks; not native browser certification |
| Mocked operational | **50 tests passed** | Previous operational regression execution; no live mutation |
| Live browser | **30 checks passed**: 8 persistent-session +22 Merchant/Admin/OTP | Operator-confirmed, not independently automated observations |
| Final live read-only audit | **VERIFIED_WITH_DOCUMENTED_EVIDENCE_LIMITATIONS** | Actual protected final evidence plus operator terminal result |

V10 migration succeeded. Guarded authenticated additional Admin API deployment succeeded. The dedicated enabled ACTIVE ADMIN-only account and enabled PENDING_APPROVAL MERCHANT-only account were provisioned successfully through the supported authenticated Admin API and merchant registration paths, respectively. Each has **one successful LOCAL_DEMO_PASSWORD_RESET**. Operator browser confirmation covers old-password rejection, new-password acceptance, prior-session rejection, correct portal isolation, preserved pending/admin states and no automatic sign-in; those observations remain distinct from database/source verification.

### Final database/runtime state verified by the operator-run audit

- Actual users|merchants|memberships|registrations|payments|refunds: **6|4|4|2|6|4** in the guarded paymesh_demo database. Existing operational Admin and both dedicated account roles/status/enabled state, designated eligibility, reset-audit targets/source, authenticated Admin creation actor and grant conditions passed current checks.
- Recovery capability is **false**. No enabled demo recovery eligibility or outstanding unconsumed challenges/grants remained under the final verifier's strict current-state assertions. No reactivation or repeat deactivation is required.
- All eight financial tables exactly matched the protected pre-OTP archive: payments, refunds, payment_gateway_transactions, idempotency_keys, simulated_gateway_outcomes, webhook_events, reconciliation_jobs and reconciliation_attempts. This is row-content verification, not merely matching counts.
- The protected pre-deactivation archive comparison verified **exact account/password/financial rows**. It covers all account/role/registry/membership/registration rows plus all eight financial tables, including password hash preservation in memory without displaying hashes. Existing operational account rows also matched the authentic available archive evidence. This is not a newly invented pre-audit fingerprint or fresh password-login test.
- Java readiness, direct/proxied payment health and frontend availability passed. Recorded service identities at final verification: Java9556 on127.0.0.1:18080, frontend4255 on127.0.0.1:5500, Python80995 on127.0.0.1:8000 and llama.cpp79855 on127.0.0.1:8082. The final verifier checked identity/bindings and preserved frontend/Python/LLM identities against existing evidence. These are observations at the final evidence capture, not newly polled services during documentation editing.
- Persistent-session functionality remains available with the existing guarded cookie/session configuration and prior browser sign-off. Disabling the local OTP flow did not remove persistent sessions.
- The recovery key remains securely stored in protected external configuration but unused by the disabled flow. It was **not erased or removed from the configuration chain**; no key content was read/displayed or changed during this documentation closeout.
- Neither archive was restored into a database. No actual test restore is claimed. Final verification performed no reset, session mutation, account creation, financial operation or service restart.

### Limitations retained explicitly

1. **HISTORICAL_EVIDENCE_UNAVAILABLE for both dedicated accounts.** Each retained family was post-reset; no retained pre-reset families independently certify historical revocation. Missing history is not a historical PASS or proof of cleanup/deletion. Deleted families and legacy no-sid JWT inventories cannot be reconstructed; no live JWT acceptance/replay was tested by this audit.
2. Merchant authorization version2 includes an **ADDITIONAL_INCREMENT_UNEXPLAINED**. Its captured lower-version post-reset family must not be treated as a pre-reset family. No operation, including Logout All, is invented as the cause; safe available audit metadata does not explain the increment.
3. Activation/deactivation account/password/financial **fingerprints are UNAVAILABLE_NOT_RECORDED**. Authentic archive row comparisons passed, but they are not relabeled as fingerprint evidence.
4. Pre-audit fingerprints are **UNAVAILABLE_NO_SUCCESSFUL_PRE_AUDIT**. The original pre-audit failed and no successful historical fingerprint baseline exists. Failed evidence is preserved; no baseline was fabricated, overwritten or retroactively created.
5. Operator-confirmed browser outcomes are separate from automated mocks and read-only database evidence. The successful final command verifies current mandatory state and authentic archive comparisons with limitations; it does not provide unrestricted historical/production certification.
6. The on-screen OTP workflow is **deliberately insecure** and does not establish account ownership. It must **never be enabled in a public deployment**. Keep the capability disabled. Public production-grade password recovery remains **unimplemented** and requires separate ownership-proof/security design. Local HTTP exceptions and private loopback custody do not qualify as production security.

These limitations are accepted for continued private local-demo development, not erased by the GO decision. A future separately approved disposable-account controlled event could establish new historical proof if required; it would not reconstruct this missing original history and is not required or executed for this limited closeout.

### Documentation-only handoff and next phase

Updated this report, the existing root README Project status/current implementation section, the existing PROGRESS Current Step/Phase6.7.3 entries, and frontend README's existing Phase6.7.3 section. No new roadmap structure was invented. Historical implementation/test/failed-audit records and protected evidence remain intact.

**Phase 6.7.4 Admin approval development may begin on a separate instruction.** It has not begun in this task. Docker/deployment/public recovery remain separately scoped future work. No application changes, database connections/writes, OTP operation, password reset, service restart, browser testing or full test rerun occurred during this documentation task. No staging/commit/reset/clean/restore command was issued. Current Git observations and final diff hygiene are recorded below.

### Documentation closeout Git/hygiene verification

Initial/final observed Git index SHA256 matched `3a92cedfcccac2555164b32a971cc9d6492d795549e0a4419368e90f84f14c2a`. Initial/final staged binary diffs compared byte-identical, SHA256 `2d992a724410a77eb26aceb2a36244e2dc4ee072547ae7c384b22a016b3a7afe`. Previously reported concurrent external staging (including the final-audit regression file) remains preserved in the existing index; no restoration or staging action was attempted. No new external staged-content difference was observed during this documentation batch.

`git status --short` showed349 existing entries:169 AM,176 staged-added,4 untracked. The edited frontend report/README remain AM; root README/PROGRESS remain pre-existing untracked files. This is not a clean-worktree claim, and the broad existing staged/unstaged work was not attributed to this documentation task. Only the four enumerated documentation files were edited. An initial diff check caught three newly introduced Markdown hard-break trailing spaces; those were removed, and final `git diff --check` passed. No test was rerun to make this documentation-only hygiene claim.
