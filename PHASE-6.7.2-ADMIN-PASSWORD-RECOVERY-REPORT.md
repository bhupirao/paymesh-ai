# Phase 6.7.2 — Offline ADMIN password recovery

## Implementation summary

Added an explicitly invoked Java console utility for resetting the password of an **existing enabled ACTIVE ADMIN-only account**, such as `demo-admin`. It never deletes/recreates the user or creates an initial administrator. No recovery REST endpoint, frontend change, dependency or migration was added. The utility has not been executed against the live demo database. Existing services were not restarted.

Inspected existing AccountAdministration/Transactions, AccountPasswords/PasswordConfiguration, AccountAdministrationLock, InitialAdminProvisioner/Bootstrap/BootstrapTransaction, DemoDatabaseGuard, AppUser/repositories, JWT account-version validation, AccountAudit/SecurityAuditEvent, configuration and isolated tests before implementation. Existing provisioning is deliberately not used as a forgotten-password bypass.

## Files changed

Created:

- `backend/src/main/java/com/paymesh/backend/security/accounts/AdminPasswordRecovery.java` — interactive console command and minimal offline context.
- `backend/src/main/java/com/paymesh/backend/security/accounts/AdminRecoveryDatabaseGuard.java` — exact configuration/connected-target guard.
- `backend/src/main/java/com/paymesh/backend/security/accounts/AdminPasswordRecoveryTransaction.java` — locked atomic reset, not component-scanned by the web application.
- `backend/src/test/java/com/paymesh/backend/security/accounts/AdminPasswordRecoveryGuardTest.java`.
- `backend/src/test/java/com/paymesh/backend/security/accounts/AdminPasswordRecoveryIntegrationTest.java`.
- This report.

Modified:

- `AppUser.java`: package-private hash replacement method increments existing authorization version and updatedAt, with overflow rejection. UUID/login/createdAt/enabled/account status remain unchanged.
- `AccountAudit.java`: mandatory-transaction offline recovery success writer with null actor fields.

Existing unrelated staged/unstaged changes remain in place. No historical migration, account provisioning policy, financial service, Python implementation, dependency, secret or live configuration change was made.

## Security design

### Operator boundary

This is a local OS/database-custody recovery mechanism, not authenticated administrator self-service. It requires an actual interactive Java Console, zero application arguments, `PAYMESH_OFFLINE_ADMIN_RECOVERY=RESET_EXISTING_ADMIN`, and the exact typed confirmation `RESET ADMIN PASSWORD IN paymesh_demo`. No console (including redirected stdin) or password argument is accepted. The existing username is prompted visibly; the database password, new account password and confirmation are prompted through `Console.readPassword`, without echo.

Only `jdbc:postgresql://127.0.0.1:5432/paymesh_demo` and `paymesh_demo_user` are accepted. localhost aliases, other ports, other databases, query parameters and other database users are rejected. Before JPA startup, the pinned DriverManagerDataSource verifies JDBC metadata and actual `current_database`, `current_user`, `inet_server_addr`, and `inet_server_port`. The guard runs again before transaction writes. There is no original paymesh_db fallback or connection attempt. Conflicting datasource/configuration overrides are rejected, as are inherited SPRING_ configuration, logging/Hibernate overrides and JVM environment-option injection. The clean-environment command below avoids accidentally inheriting the active demo server's settings.

The database password is read inside Java rather than exported in shell history, passed as an argument or retrieved from a running process. JDBC necessarily retains an immutable password String transiently; the datasource password reference is cleared afterward and temporary char arrays are overwritten in finally. JVM/driver/BCrypt internal copies and GC cannot be securely erased by this utility. Do not use shell tracing, debugger heap dumps or terminal recording.

### Startup isolation

The console uses the existing non-web application/context factory but a separate minimal source, with **no component scan of the main application**. RecoveryConfiguration intentionally lacks @Configuration/@Component so ordinary web application scanning cannot load it. It imports account repositories/entities, password configuration, the existing administration lock, audit and the reset transaction only. It does not import InitialAdminBootstrap, credentials-authentication runners, financial services, settlement scheduling, JWT keys or AI integrations.

Flyway, SQL initialization, datasource/JNDI auto-configuration and task-scheduling auto-configuration are excluded. The verified datasource is registered directly rather than property-bound. Hibernate is pinned to public-schema validate-only, non-web mode is enforced, and SQL/bind/root logging is disabled. Missing V9 schema fails validation; this utility does not migrate or repair it. Existing BCrypt cost configuration is reused (default 12; accepted existing range 10–16). No unrelated startup writes are intended or permitted by the minimal context.

### Reset transaction and auditing

After matching confirmation and verifying the datasource, the reset transaction acquires the existing cross-process AccountAdministrationLock, normalizes the username with AccountCredentials.normalizeLogin, and requires an existing enabled ACTIVE ADMIN. Merchant-only, disabled, pending, missing and mixed ADMIN+MERCHANT accounts are rejected. Rejecting mixed-role accounts is a deliberate extra safeguard against modifying any account carrying merchant privileges.

AccountPasswords enforces the unchanged password policy: at least 12 Unicode code points, at most 72 UTF-8 bytes, no NUL/malformed Unicode. The utility does not weaken or duplicate BCrypt hashing. Only the user's password_hash, authorization_version and updated_at change. Roles, username, UUID, created_at, enabled and approval state are preserved. Existing JWT validators compare authorization_version with persisted state, invalidating old access tokens after commit. A live application restart is not required for that version check.

The same transaction writes `ADMIN_PASSWORD_RECOVERED`, outcome SUCCESS, resource type ACCOUNT and resource UUID. Both `actor_user_id` and `actor_identifier` are null; metadata is exactly `{"source":"offline_operator_recovery"}`. It does not claim the affected administrator authenticated the recovery or invent an operator identity. Existing audit infrastructure persists this record atomically with the password/version changes. Failure, including failure to write the success audit, rolls back all three changes. No separate success or denial record is fabricated after a failed commit.

The command prints fixed cancellation/success/failure messages, never the supplied password, hash, raw exception or SQL details. Failure exits nonzero; it makes no automatic retry. A lost connection during commit may leave the operator uncertain even though transaction atomicity is preserved: inspect account/audit state privately before deciding whether to retry. Never assume a network error proves rollback.

## Tests and verification

Only the documented isolated runner is used for Java tests:

```bash
cd "$HOME/Developer/paymesh-ai/backend"
bash scripts/test-isolated.sh
```

The runner creates a fresh marked PostgreSQL cluster on 55441, verifies its actual data directory, runs the suite and stops only that temporary cluster. No test connects to the demo/original database. The recovery transaction tests replace the production target guard with a test-only mock so real integration writes remain inside the isolated recovery schema. Separate guard tests mock JDBC to verify exact production identity rejection. This mock is not an operator option or production bypass.

New coverage includes successful existing-admin reset, new password succeeds/old fails, UUID/login/roles/enabled/status preservation, prior authorization invalidation (a real signed pre-reset JWT receives HTTP 401 after reset), missing/merchant/disabled/pending/mixed-role rejection, invalid password/mismatch rejection, audit-failure rollback, identity-guard failure before writes, unchanged financial/account-association tables, no password/hash/raw-error output, exact mode/confirmation/configuration/actual JDBC target checks, and startup isolation (no web server, Flyway, runners or settlement scheduler). Final counts/results are recorded below. No live recovery or live login is claimed.

## Exact Mac terminal commands — documentation only; live recovery awaits approval

Run these only after explicit approval for the real reset. Building does not perform recovery or start a service. Java tests must continue using the isolated script above.

```bash
cd "$HOME/Developer/paymesh-ai/backend"
mvn package -DskipTests
```

Use a real interactive macOS Terminal tab. Do not run through a heredoc, pipe, IDE console without Console support, shell tracing or background/redirected execution. The following starts only the standalone recovery command, not the web application:

```bash
cd "$HOME/Developer/paymesh-ai/backend"
set +x
java_bin="$(/usr/libexec/java_home -v 21)/bin/java"
env -i HOME="$HOME" PATH="/usr/bin:/bin:/usr/sbin:/sbin" \
  PAYMESH_OFFLINE_ADMIN_RECOVERY=RESET_EXISTING_ADMIN \
  PAYMESH_DEMO_DB_URL=jdbc:postgresql://127.0.0.1:5432/paymesh_demo \
  PAYMESH_DB_USER=paymesh_demo_user \
  "$java_bin" \
  -Dloader.main=com.paymesh.backend.security.accounts.AdminPasswordRecovery \
  -cp target/paymesh-backend-0.0.1-SNAPSHOT.jar \
  org.springframework.boot.loader.launch.PropertiesLauncher
recovery_status=$?
unset java_bin
printf 'Recovery exit status: %s\n' "$recovery_status"
unset recovery_status
```

The existing Spring Boot PropertiesLauncher selects the explicit utility main class from the runnable JAR; no dependency installation or extra classpath generation is required. No plaintext password appears in the shell command or environment.

At the prompts:

1. Type exactly `RESET ADMIN PASSWORD IN paymesh_demo` (anything else cancels).
2. Enter the existing username `demo-admin`.
3. Enter the existing **database user** password privately at `Demo database password (hidden)`; this is not the forgotten administrator login password.
4. Enter your new administrator password privately and confirm it at the second hidden prompt.
5. Expect the fixed success message only after the transaction commits. No confirmation, password or hash is printed. Exit 1/failure message requires private inspection before any retry. Typing Ctrl-C before the update cancels; a disconnect during/after commit needs the same uncertainty procedure.

You do not need to source demo.env/secrets.env or expose JWT/HMAC/settlement credentials for recovery. Do not supply `PAYMESH_DB_PASSWORD` in command arguments or paste it into chat. If the database user's password is also unknown, this utility cannot recover it and must not weaken PostgreSQL authentication. Resolve database access through a separately authorized private operator process.

## Live activation checklist — not performed

- Obtain approval for this specific administrative password change; previous signup activation approval is not used as recovery approval.
- Verify the current demo database and migration state privately; V9 must already be present. Confirm `demo-admin` is the intended enabled ACTIVE ADMIN-only user, without dumping credential hashes.
- Follow the existing protected backup policy if a recovery backup is required; never overwrite backups or automatically restore one. No new backup was made in this implementation phase.
- Verify Java 21 and build the reviewed artifact. Review any concurrent repository changes before using it.
- Execute the exact interactive command above. It verifies actual connection identity before allowing writes and needs no web/frontend/Python/llama restart.
- After a confirmed commit, sign in privately through http://127.0.0.1:5500/admin/login with the new password. Old password must no longer authenticate; existing sessions/tokens must fail their authorization-version check. Do not copy tokens into chat or logs.
- Privately inspect the recovery audit resource UUID and null actor/source metadata if verification is needed. Check user UUID/roles/status and financial records are unchanged. Do not create/process/refund/investigate a payment as a recovery check.
- Stop here. No merchant approval, password-recovery email, persistent sessions, Docker or next-phase work is included.

## Limitations and preservation

This demo-specific utility assumes local OS/database operator custody and is restricted to one literal target and public schema. It is not a production break-glass custody/approval system, distributed MFA recovery or self-service reset. Audit source identifies the mechanism, not a verified human. A production process needs independently reviewed operator authentication, access controls and backup/restore policy.

No live account update, database connection, migration, financial request, service restart, secret/configuration change or original paymesh_db/8080 access occurred during implementation. Temporary test databases and synthetic passwords/keys are isolated. No staged work was changed by the agent; final index observations and diff checks are recorded below.


### Preservation observations for this implementation

Initial Git index SHA-256: `80252ae4ba0a9051f6517706609f24f82a8bebc875a46d656d58b00053707daf`. Initial staged binary diff SHA-256: `f39eaa6316e7b5afa1aa86eef9e150b1d8524bbf9e05788619fcb7ed252dd51b`. Intermediate observations matched both values. The final check detected concurrent external staging: final index SHA-256 `f0c8610b9428c6fc7c5efbf2df3c66fbfa7d1f459e7f4824be08b5d17ac5d3f7`, staged binary diff SHA-256 `bfa72c70a1a3ea8577c057adeb9b5bb87001e8fd9800113d0d35e64a4f37e4d9`. These external changes were left untouched; no staging/index operation was issued by the agent.

Observed service listeners during implementation: Java 96717/18080, frontend 96829/5500, Python 80995/8000 and llama.cpp 79855/8082. These reflect the user's current runtime, not historical PIDs in earlier reports. No stop/start/restart command was issued by the agent.

The interactive Console/operator workflow remains a manual verification item; it was not driven against live credentials. The automated tests cover the guard/transaction/minimal context and output privacy using synthetic credentials only. An initial sandbox attempt could not initialize PostgreSQL shared memory (no Java tests ran); the approved isolated runner then passed its first 241-test development run. A final full run covers the strengthened signed-JWT and seeded-record preservation assertions.

## Final results

- `bash scripts/test-isolated.sh`: **241 tests passed, 0 failures, 0 errors, 0 skipped; BUILD SUCCESS**. This includes 231 existing regressions and 10 new recovery tests (4 guard tests + 6 integration tests). Final full run took approximately 3 minutes 6 seconds; its temporary PostgreSQL cluster stopped successfully. Local log: `/tmp/paymesh-admin-recovery-final-tests.log`.
- `mvn package -DskipTests`: **BUILD SUCCESS**, 6.487 seconds. This was a packaging command, not bare Maven testing or a live application startup. The runnable JAR contains the command, minimal context, transaction and target guard classes. Local build log: `/tmp/paymesh-admin-recovery-package.log`.
- `git diff --check`: passed. Concurrent external staging changed the final hashes as recorded above; it was reported and left untouched. No git add/commit/push/reset/clean/restore was issued.
- No live reset, live database connection, REST reset endpoint or service restart was performed. The operator Console flow and real `demo-admin` login remain pending explicit approval and manual execution.

Implementation, isolated testing, packaging verification and documentation are complete. Stop here and await approval before any live password recovery.

## Confirmed runtime bug correction — PostgreSQL inet address formatting

This section supersedes the earlier runtime-ready claim and earlier 241-test counts for the recovery utility. The previous tests mocked the address as a plain host string and did not exercise PostgreSQL's actual inet-to-text conversion. That coverage gap allowed a valid local database to be rejected before the new-password prompt.

### Confirmed cause and correction

The operator's real read-only PostgreSQL query established:

| Expression | Value |
| --- | --- |
| `inet_server_addr()` | `127.0.0.1` |
| `inet_server_addr()::text` | `127.0.0.1/32` |
| `host(inet_server_addr())` | `127.0.0.1` |
| `inet_server_addr()::text = '127.0.0.1'` | false |
| `host(inet_server_addr()) = '127.0.0.1'` | true |

Those live observations were supplied by the operator; the agent did not issue a live database query. `AdminRecoveryDatabaseGuard` now uses this exact identity query:

```sql
SELECT current_database(), current_user, host(inet_server_addr()), inet_server_port()
```

The comparison remains exactly `127.0.0.1`, with no CIDR trimming heuristic, relaxed host aliases or broader network permissions. Database `paymesh_demo`, user `paymesh_demo_user`, port 5432, literal configured JDBC URL, datasource type and JDBC metadata checks remain unchanged.

`DemoDatabaseGuard.verifyOfflineProvisionerDatabase()` and its private connection verifier were inspected. They verify DriverManagerDataSource type, exact configured/metadata URL, metadata username and actual current_database; they do not use inet-to-text address formatting. No additional formatting defect was identified there, and that class was left unchanged. No live connection was used to claim an additional metadata verification result.

### Safer diagnostics

The CLI now records its current stage and prints fixed messages distinguishing:

- Invalid offline configuration: no reset attempted.
- Database connection or identity verification failure: no password reset performed; check the approved target and credentials privately.
- Password validation/confirmation failure: no reset attempted; existing 12-code-point/72-UTF-8-byte/NUL/Unicode policy is unchanged.
- Offline Spring context initialization failure: no reset transaction started.
- Reset transaction failure or uncertain commit: no automatic retry; verify account/audit state privately.
- Post-commit context cleanup failure: accurately states that reset committed and warns against automatically repeating it.

Database verification failures use a sanitized exception category without raw JDBC messages or nested causes. A repeated identity check failure inside the reset still receives the database category. Password policy validation is shared with AccountPasswords before context startup (package-private static validator, same implementation); BCrypt configuration and transactional validation/hashing remain intact. Success is printed after context cleanup, avoiding a success message followed by a cleanup-failure message.

No password, hash, raw exception message, credential, JWT or private key is included in these diagnostics. The existing hidden prompts, finally-array clearing, account/role restrictions, lock, authorization-version increment and atomic offline audit were preserved. No new endpoint, migration or dependency was added.

### Added regression coverage

The real PostgreSQL regression runs through the existing isolated test datasource over TCP. It executes the exact production identity SQL, confirms the isolated database/user and a port other than 5432, then checks the typed inet value, inet text with `/32`, host extraction and both boolean comparisons. It is a real PostgreSQL ResultSet, not a mocked address. The production demo target guard is not weakened to permit the isolated cluster.

Two additional unit tests verify distinct fixed stage diagnostics, lack of raw failure-detail echo and database-category selection for a repeated identity failure. The existing mock JDBC test was updated to the corrected SQL. All earlier recovery/regression tests remain included. Final execution and packaging results are recorded below when complete.

Changed in this correction: AdminRecoveryDatabaseGuard.java, AdminPasswordRecovery.java, AccountPasswords.java (validator access only), AdminPasswordRecoveryGuardTest.java, AdminPasswordRecoveryIntegrationTest.java and this report. AppUser, audit writer, transaction implementation, migrations, dependencies and live configuration were not changed in this correction.

### Corrected recovery procedure — do not execute before approval

Rebuild the JAR with `mvn package -DskipTests` from `~/Developer/paymesh-ai/backend`, then use the exact clean-environment PropertiesLauncher command already documented above. Do not use the earlier JAR. The mode, target, username, confirmation phrase and hidden database/new-password prompts are unchanged. Neither password belongs in command arguments or chat. After valid database verification, the utility should reach the new-password and confirmation prompts; validation then occurs before starting the minimal context.

If the database diagnostic still appears, stop and privately verify the database password and exact approved identity. Do not relax checks. If password validation fails, correct the entered policy/matching issue. If context initialization fails, inspect schema/configuration through a separately approved private procedure; do not enable Flyway or schema mutation in recovery. If transaction outcome is uncertain, inspect audit/account state before retrying. A post-commit cleanup error must not trigger another reset automatically.

No live recovery, live database connection, service restart, migration/dependency change or staging/commit operation was performed for this correction. Initial index hash: `f0c8610b9428c6fc7c5efbf2df3c66fbfa7d1f459e7f4824be08b5d17ac5d3f7`; initial staged binary diff hash: `bfa72c70a1a3ea8577c057adeb9b5bb87001e8fd9800113d0d35e64a4f37e4d9`. Listener PIDs at start: Java 96717/18080, frontend 96829/5500, Python 80995/8000, llama.cpp 79855/8082. Final preservation observations follow below.

### Runtime-fix final verification

- Complete `bash scripts/test-isolated.sh`: **244 tests passed, 0 failures, 0 errors, 0 skipped; BUILD SUCCESS**. This is the previous 241 tests plus 1 real PostgreSQL regression and 2 diagnostic tests. The isolated run completed in approximately 3 minutes 6 seconds and stopped its own temporary cluster successfully. Log: `/tmp/paymesh-admin-recovery-inet-fix-tests.log`.
- The real PostgreSQL inet regression passed without mocked ResultSet values. All 7 recovery integration tests and 6 recovery guard/diagnostic tests passed; existing financial/authentication/registration/AI regressions remained green.
- `mvn package -DskipTests`: **BUILD SUCCESS**, 6.538 seconds. Log: `/tmp/paymesh-admin-recovery-inet-fix-package.log`. Runnable JAR inspection confirmed the guard contains `host(inet_server_addr())`, no obsolete inet text query, and the staged diagnostic implementation. The utility itself was not launched against the demo database.
- `git diff --check`: passed. Final index and staged binary diff hashes match this correction's initial hashes exactly. No staging/index mutation or restore command was issued.
- Final listener PIDs remain Java 96717, frontend 96829, Python 80995 and llama.cpp 79855 on their existing ports. No live database connection, password recovery, financial mutation, service restart, configuration/secret edit, migration or dependency change occurred in this correction.

The fix is implemented, isolated-tested, packaged and documented. Live recovery and interactive Console verification remain pending the user's explicit approval. Stop here.

## Operator closeout supplied at Phase 6.7.3 kickoff

The operator reports successful offline admin recovery after the host-address fix: the same administrator's authorization version increased from 0 to 1 and ADMIN_PASSWORD_RECOVERED audit was verified. This is supplied live evidence, not an operation repeated by the agent. No further recovery execution is part of Phase 6.7.3 implementation.
