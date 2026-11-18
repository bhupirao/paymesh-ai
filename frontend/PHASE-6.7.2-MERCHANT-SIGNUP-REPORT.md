# Phase 6.7.2 — Simple merchant registration and pending onboarding

## Scope and activation status

Implemented real Spring Boot/PostgreSQL merchant registration and email/password sign-in, without email verification, OTP, links, verification tokens, SMTP, Mailpit or new dependencies. New accounts are PENDING_APPROVAL and can sign in only to limited onboarding. Admin approval/rejection/suspension endpoints and UI remain Phase 6.7.4. Persistent sessions and recovery remain Phase 6.7.3; recovery delivery requires a separate secure free design.

Implementation and isolated testing only: **no live migration, registration, protected business request, financial mutation or service restart was performed**. Existing running Java/frontend proxy processes still use their previously loaded code. Static assets update immediately, so signup can display the new form before server activation; on the old proxy the new route is unavailable and receives safe failure feedback. Do not call this live-ready until the controlled activation below is approved and completed.

## Architecture and database

V9 is additive; historical migrations are unchanged. `app_users.account_status` has ACTIVE/PENDING_APPROVAL values and defaults existing provisioned accounts to ACTIVE without changing enabled flags, roles, authorization versions, merchant ownership, membership or financial rows. New users are enabled for credential authentication, have status PENDING_APPROVAL and receive only the server-assigned MERCHANT role.

Each registration creates a random `M_<UUID>` registry merchant, unverified/inactive, and an inactive membership with no administrative grant. The new `merchant_registrations` table stores first/last/business names, normalized email, mobile, business type, country, merchant/user association and timestamped terms version `demo-2026-11`. No confirmation password or plaintext password is persisted. PII is mapped privately through JPA so isolated schema configuration is respected; there is no public profile/listing endpoint.

The service transaction includes user, merchant, membership, role and registration profile. Unique normalized user login plus profile email constraints reject concurrent duplicate submissions atomically. It never claims legacy merchant IDs. Existing normalization uses ASCII-supported login policy and Locale.ROOT lowercase; frontend trims email before sending, API accepts canonical ASCII email case-insensitively. Registration duplicates return safe 409, not an overwritten account. No automatic registration retry or fabricated success.

## API contracts

`POST /api/v1/auth/register`, public JSON, no bearer or Idempotency-Key needed. Same-origin proxy allows only this exact additional method/path. Request:

```json
{"firstName":"Ada","lastName":"Example","businessName":"Example Business","email":"merchant@example.test","mobile":"+919876543210","businessType":"COMPANY","country":"IN","password":"<entered privately>","confirmPassword":"<same private input>","terms":true}
```

Names: nonblank, max 80/80/160 UTF-16 code units. Email: ASCII email policy, max 254, normalized lowercase unique. Mobile: optional `+`, 7–15 digits. Business type: SOLE_PROPRIETOR, COMPANY, PARTNERSHIP, NONPROFIT, OTHER. Country: IN, US, GB, CA, AU, OTHER. Terms must be true. Password policy reuses existing BCrypt (configured default cost 12): at least 12 Unicode code points, maximum 72 UTF-8 bytes, no NUL/malformed Unicode. Confirmation must match. This favors long unique passphrases without imposing invented composition rules. Roles, merchant ID and status are never accepted as authority from input; extra JSON fields cannot select privileges.

201, no-store/no-cache:

```json
{"accountStatus":"PENDING_APPROVAL","message":"Your account has been created successfully. You can now sign in using your email and password."}
```

400 invalid fields/mismatch/policy; 409 duplicate/conflicting persistence; 413 bounded request; 415 unsupported content type; 429 shared bounded per-address login/registration budget with Retry-After; service failures remain safe UI failures. Backend and proxy bound registration bodies at 16 KiB, login remains 4 KiB. Proxy body/response limits, fixed Java upstream, Host/Origin checks, CSP and no-store are retained. The process-local budget is not distributed abuse prevention; deployments still need reviewed edge controls. Error messages never echo passwords, raw exceptions or tokens.

`POST /api/v1/auth/login` retains `{login,password}` and its existing `{accessToken,tokenType:"Bearer",expiresIn:900,expiresAt}` response. Registered users use their email as login. JWT now includes `account_status`, alongside existing UUID subject, roles and authorization_version. No merchant identity is inferred from subject/login. Old JWTs without the new claim are compatible only with currently ACTIVE accounts. Claim/current database status mismatch invalidates the token; approval must require fresh sign-in.

## Pending-session authorization

Pending JWT roles remain MERCHANT for portal identity, but Java converts only ACTIVE accounts' roles into financial Spring authorities. Pending sessions therefore receive 403 before any payment/gateway/refund/investigation controller executes. The transactional BusinessAccess layer independently rejects non-ACTIVE users. Administrative account authorization also requires ACTIVE state, and existing verified/active merchant and membership checks remain intact. A pending user cannot gain financial access merely by guessing another merchant/payment UUID or modifying client-side state.

Frontend validates the status claim and rejects pending non-MERCHANT/mixed-role tokens. It shows only the exact awaiting-approval message, identity, expiry and logout in the Merchant portal; navigation and financial panels are hidden. The shared API client also rejects pending financial operations before fetch. Java remains the security boundary. No onboarding/profile endpoint or public approval endpoint is introduced.

Future authorized approval must atomically change account status to ACTIVE, attest merchant ownership/activate the registry, grant active membership, increment authorization version under the existing account-administration lock and audit the change. Changing the frontend or only one flag is insufficient. Existing offline administrative workflows are not exposed publicly or used to approve new live accounts here.

## Frontend lifecycle

The existing registration page now validates and submits through the same-origin API client. Password toggle, labels, inline errors, aria-busy, duplicate pending lock, fixed safe failures and exact success message are implemented. Success exposes a Sign In link; there is no automatic login. Password inputs clear as soon as a valid submission starts, and in-memory input password references clear after completion. Route leave/session change resets form/results and ignores late responses. An uncertain outcome instructs signing in before resubmitting, not assuming failure. No browser token/password storage, email delivery or financial retry was added.

Limited onboarding text: “Your account is awaiting admin approval. You will be able to accept payments once your account is approved.” Refresh still loses the memory-only session. Logout/expiry/session replacement use existing private-state clearing and stale-response protection. No financial data is requested just to enter onboarding.

## Tests

Final isolated Java results are recorded below. All existing 521 frontend checks were executed: 18 Python proxy/route test methods and 503 JavaScript assertions (10 API, 34 auth, 94 payment, 125 refund, 149 investigation, 18 QA, 73 portal). Added 39 mocked registration assertions and 2 proxy tests: **20 Python tests + 542 JavaScript assertions = 562 frontend checks**, all passing.

The browser-style JavaScript suites actually ran in the available JavaScript runtime with mocked fetch/DOM/history; this is not actual browser visual/native-form verification. Synthetic assembled-app checks separately confirmed pending Merchant dashboard visibility, hidden operations/navigation, zero business requests and logout clearing. Test page: http://127.0.0.1:5500/assets/js/registration-tests.html (39). Existing pages retain their documented counts.

Commands executed:

```bash
python3 -m unittest discover -s frontend/tests -q
cd backend
bash scripts/test-isolated.sh
```

The test runner initializes a fresh marked PostgreSQL cluster on 55441, verifies its data directory, runs Maven with a bounded context cache and stops only that temporary cluster. It never uses either existing database. Sandbox initially blocked shared-memory initialization; the approved isolated run used the required local permissions. An initial development run exposed missing test issuer/audience configuration and obsolete expectations that public registration was closed; these were corrected. Registration persistence was mapped with JPA to honor isolated schema configuration. A subsequent development run passed 230/231 tests: the remaining new test incorrectly matched the required success message word “password” as leakage. Its assertion now checks the actual secret value and password response field. Final run supersedes these development runs.

New Java integration coverage: persisted signup/hash/role/status, same credentials login, denial across all financial API operations and random payment IDs, concurrent and repeat duplicates, invalid fields/password mismatch, untrusted role/merchant/state input, explicit transaction rollback, persistence-failure rollback and stale pending token after status change. Existing active Merchant/Admin, cross-merchant, payments/refunds and AI tests run in the full isolated suite. Financial fixture mutations occur only inside that disposable test database.

## Files created/modified

Created:

- `backend/src/main/resources/db/migration/V9__merchant_registration.sql`
- `backend/src/main/java/com/paymesh/backend/security/accounts/MerchantRegistration.java`
- `backend/src/main/java/com/paymesh/backend/security/accounts/MerchantRegistrationProfile.java`
- `backend/src/main/java/com/paymesh/backend/security/auth/RegistrationController.java`
- `backend/src/test/java/com/paymesh/backend/security/auth/MerchantRegistrationIntegrationTest.java`
- `frontend/assets/js/portals/registration.js`
- `frontend/assets/js/registration-tests.html`, `registration-tests.js`
- This report.

Modified: backend AppUser, AccountTokenStateService, AccountAuthorization, JwtTokenService, JwtAccountValidator, JwtSecurityConfiguration, LoginRateLimitFilter, BusinessAccess and BoundedRequestBodyFilter for persisted scope enforcement/public bounded registration; the two JWT integration test classes for the newly supported public route. Frontend index, signup validator, portal view, session, API config/client, dev_server, route tests and README for the real form, scoped onboarding and exact proxy path. Backend API reference documents the new contract. No dependency, historical migration, Python AI or Docker change.

## Controlled live activation — not executed

1. Obtain explicit approval for demo schema migration and Java/frontend-only restart. Keep Python/LLM running. Privately confirm the currently guarded target is `paymesh_demo` on 5432 (the Phase 5.4 current runtime), not original `paymesh_db`/8080. The older Compose runbook describes a different 15432 deployment: do not change current targeting to it. Retain privately configured JWT/DB secrets; never paste or print them.
2. After testing, build the runnable artifact without running tests against the demo database:

   ```bash
   cd ~/Developer/paymesh-ai/backend
   mvn package -DskipTests
   ```

   Do not use bare `mvn test` against the live environment.
3. After approval, the operator stops only the verified current demo Java PID (83515 at this audit), with identity/port checks, then starts from the same privately loaded environment using the established Phase 5.4 launch flags below. V9 applies through Flyway at this approved startup, before JPA validate. Do not run ad-hoc SQL approval or Flyway clean/repair/baseline. Preserve the existing database backup policy without modifying archives here.

   ```bash
   java -jar target/paymesh-backend-0.0.1-SNAPSHOT.jar \
     --spring.config.location=classpath:/application.properties \
     --spring.profiles.active=demo \
     --spring.datasource.url=jdbc:postgresql://127.0.0.1:5432/paymesh_demo \
     --spring.datasource.username=paymesh_demo_user \
     --spring.flyway.enabled=true --spring.jpa.hibernate.ddl-auto=validate \
     --server.address=127.0.0.1 --server.port=18080 \
     --paymesh.settlement.scheduling-enabled=false \
     --paymesh.ai.enabled=true --paymesh.ai.base-url=http://127.0.0.1:8000 \
     --paymesh.ai.connect-timeout-ms=2000 --paymesh.ai.response-timeout-ms=45000 \
     --paymesh.ai.max-response-bytes=262144
   ```

   No passwords appear in these commands; required existing environment must be loaded privately first. The Phase 5.4 runbook contains verified process guards. Do not execute its historical hardcoded PID commands unchanged.
4. After approval, replace only the verified frontend PID (92049 at this audit) and from repository root run `python3 frontend/dev_server.py` on the same 5500 port. Its new exact registration allowlist requires this reload; static files alone cannot activate it.
5. Read-only readiness: `curl --fail http://127.0.0.1:18080/actuator/health/readiness` and `curl --fail http://127.0.0.1:5500/merchant/signup -o /dev/null`. Confirm Flyway V9 success privately without logging credentials. If activation fails, stop and review; never remove constraints or modify historical migrations to force startup.

## Manual browser checks after approved activation

- Open http://127.0.0.1:5500/merchant/signup at desktop and 375px. Check labels, Tab/focus, password visibility, matching confirmation and terms. Invalid fields must not submit. Use only disposable demo registration details and a unique privately entered passphrase; do not put credentials in console, screenshots or reports.
- Explicitly register once (this creates account/registry metadata, not a payment). Observe exact success text, cleared passwords and Sign In. Verify Network POST uses only `/api/v1/auth/register`, no email/OTP request, no role/merchant selection and no browser credential persistence. Repeated same normalized email gets safe duplicate feedback.
- Use Sign In at `/merchant/login` with that same email/password. Confirm awaiting-approval message, expiry/logout and no financial navigation/results. Refresh requires sign-in. Logout and Back must not restore private UI. New pending merchant cannot enter `/admin/dashboard`.
- Use mocked tests for financial denial. If separately authorized to check pending HTTP denial live, use browser private session without exporting tokens; do not submit live create/process/refund requests. Existing isolated tests already exercise all denial paths.
- Existing active Merchant/Admin logins must keep their full respective workspace. Use only existing authorized payment GET/gateway/refund-history checks if separately desired; no financial mutation or AI POST is needed for registration verification.
- Run all test pages including `/assets/js/registration-tests.html`; synthetic fetch only. Check mobile wrapping/status announcements and show/hide controls. Actual browser verification remains pending.

## Preservation and limitations

Initial index SHA-256 `259c1905daf72169b48f29696a116698e22718459c785ce7db9be2af9ee5462d`; initial staged binary diff SHA-256 `cd33d0770d8d90d0bce178d6fce29d8ef31d148634051626177750532761a16f`. Concurrent external staging changed these; it was reported and left untouched. The agent issued no git add/commit/push/reset/clean or restore. Later/final index SHA-256 is `7cba76bab425bc48d9aedadac4e4f5baf95526b76ebc0b249195c3c02c4e4070`; staged binary diff SHA-256 is `83a721927255001a7daca5b557db4e8597774a083ad9c6956232afdc2461a19f`. These changed externally and were left untouched.

Existing services observed unchanged: frontend PID92049/5500, Java83515/18080, Python80995/8000, llama.cpp79855/8082. No original database/8080 access, live migrations, financial records, protected configuration, secrets, archives or backups were touched. Maven build output is generated and was recreated by the documented isolated runner. No email-verification implementation existed to remove; obsolete landing preview copy was updated without deleting historical reports.

Known limits: no live activation or actual browser sign-off, no approval API/UI, no persistent login/recovery, no distributed rate limit or verified ownership of submitted email/mobile, local HTTP demo only, limited country/business enums, legal/privacy and operational abuse controls required before public launch. Duplicate 409 reveals that submitted registration conflicts; generic wording reduces detail but does not promise account-enumeration resistance. Do not expose this local development server publicly. Phase 6.7.3/6.7.4 remain separate work, with no email verification requirement introduced by this phase.

## Final verified results

- Full documented isolated Java runner: **231 tests, 0 failures, 0 errors, 0 skipped; BUILD SUCCESS**. This includes the existing 226 tests and 5 new merchant registration integration tests. The temporary cluster shut down successfully. Final run log: `/tmp/paymesh-672-java-verified.log` (local test output, not a release artifact).
- Frontend: **562 passing checks** = original 521 + 39 registration assertions + 2 proxy test methods. Python discovery: 20 tests in 1.163 seconds. JavaScript: 542 assertions with mocked runtime DOM/history/fetch. Actual browser verification is still pending.
- `git diff --check` passed; static HTML has no duplicate IDs. No email-verification token implementation/dependency was found or introduced.
- Final service listener observations retain the four PIDs above. Final index/staged diff observations retain the later external-staging hashes above. No live activation was performed. Stop after Phase 6.7.2 implementation/isolated testing.

## Controlled live activation attempt — blocked at preflight

The user explicitly approved the guarded V9 migration and Java/frontend-only restarts, conditional on successful target/process/backup checks. This attempt stopped before database access because the existing protected environment did not provide `PAYMESH_DB_PASSWORD`.

### Pre-activation observations

- Current listeners were discovered rather than assumed: Java PID 83515 on 18080; frontend Python PID 92049 on 5500; Python AI PID 80995 on 8000; llama.cpp PID 79855 on 8082.
- Process executable identities were verified with a permitted process inspection. Working directories matched backend, repository root, ai-service and the existing llama.cpp checkout respectively. No process was stopped or restarted.
- Protected demo configuration directory mode was 0700; demo.env and secrets.env were 0600, private JWT key 0600. Contents and secrets were not printed. The established demo.env/secrets.env procedure was sourced privately with shell tracing disabled.
- That environment has no nonempty database password. The read-only database command was therefore never executed. Actual database identity, Flyway history, V9 compatibility against the live schema and baseline user/merchant/payment/refund counts remain **unverified**, not assumed from historical documentation.
- Available filesystem space was approximately 5.9 GiB. Database size and dump size remain unknown. Repository documentation establishes keeping credential/dump/archive material private and excluded from Git, but a usable backup/restore procedure must still be verified before proceeding. No backup was created or existing backup touched.

### Build, migration and restart result

Not attempted: Maven package, backup, Flyway V9, Java restart and frontend restart. No new PIDs exist. No readiness/route success is claimed for an updated runtime, and no before/after database counts are available. The running services retain their previous code. There were no live registration or protected business requests, financial changes, original paymesh_db/8080 access, schema changes, restores, downgrade or Flyway clean/repair/baseline operations.

### Git preservation

Activation-attempt initial index SHA-256: `80252ae4ba0a9051f6517706609f24f82a8bebc875a46d656d58b00053707daf`; staged binary diff SHA-256: `f39eaa6316e7b5afa1aa86eef9e150b1d8524bbf9e05788619fcb7ed252dd51b`. No Git index mutation command was issued. Only this report was appended during the activation attempt. Final hash comparison is recorded below.

### Blocker resolution and later manual checks

Database credentials must be made available through an explicitly reviewed private operator mechanism; do not send the password in chat, command arguments, logs or screenshots. A hidden read in the operator's own terminal does not export a value into an already-running agent's shell. If using hidden operator input, perform the guarded preflight/activation in that same private terminal, or arrange an explicitly authorized protected credential handoff before another agent attempt. Do not change authentication rules or extract credentials from another process to bypass this blocker.

After credential availability, repeat all target/history/backup checks before building/restarting, using the controlled activation runbook above. Do not skip the protected backup or assume the current schema. Any rollback restore requires separate explicit approval; no automatic restore or downgrade is authorized by this attempt.

After a later successful activation, browser URLs are http://127.0.0.1:5500/merchant/signup, http://127.0.0.1:5500/merchant/login, http://127.0.0.1:5500/admin/login and http://127.0.0.1:5500/assets/js/registration-tests.html. The user, not the agent, should explicitly register one synthetic merchant with a privately entered passphrase, verify the exact success message and cleared password fields, select Sign In, authenticate with the same email/password and confirm the awaiting-admin-approval dashboard with no financial controls. Refresh must require sign-in; logout/Back must not restore private results. Do not perform financial mutations or an investigation. These live checks remain pending.

Final activation-attempt index and staged binary diff hashes match their initial values above exactly. Report whitespace check passed. Activation remains blocked; no further phase work began.

## Controlled activation retry — 2026-11-14 — blocked at environment check

The operator reported privately verifying `paymesh_demo:paymesh_demo_user` and launching Codex from an interactive Bash shell with `PAYMESH_DB_PASSWORD` exported. The retry checked only whether that variable was nonempty in the agent's execution environment, without printing its value or environment contents. The result was **PAYMESH_DB_PASSWORD_UNAVAILABLE**. The agent's command environment therefore did not inherit a usable value; the operator's reported identity check was not independently repeated.

As explicitly required, activation stopped at this first safety check. No database connection was attempted, including to the original `paymesh_db`. Database identity, process identity, Flyway history, V9 compatibility, disk space and baseline counts were not rechecked in this retry. No backup, Maven build, migration, service restart, readiness/payment-health request or frontend-route check was attempted. No merchant was created. No commands were issued to alter Java, frontend, Python AI or llama.cpp. No credentials were extracted from another process or alternate configuration source. No Git staging, commit, push, reset or clean command was issued; only this report was updated.

Activation remains blocked until a nonempty password is available to the actual agent execution environment through the operator's private mechanism. A later attempt must repeat every required safety and backup check before any migration or restart. Manual signup and login remain for the operator after successful activation.

## Phase 6.7.2 closeout — operator-verified evidence supplied for Phase 6.7.3

The operator confirms that Phase 6.7.2 implementation and live verification are complete: V9 was successfully applied, merchant signup and the limited pending dashboard work, and ACTIVE Merchant/Admin logins work. All six live browser security checks passed. The supplied baseline is 244 Java tests and 562 frontend checks. Current reported demo counts: 4 users, 3 merchants, 3 memberships, 1 registration, 6 payments and 4 refunds. Offline admin recovery succeeded for the existing account; its authorization version increased from 0 to 1 and ADMIN_PASSWORD_RECOVERED audit was verified. These are operator-reported verified results, not live operations repeated by the agent. They supersede the earlier blocked-activation entries. Phase 6.7.3 must not apply V10, enable demo OTP, reset passwords or restart services without separate approval.
