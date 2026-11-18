# Guarded offline recovery — disposable pending Merchant

## Scope

Prepared only; no live database connection, reset, service restart or OTP activation
was performed. The operator reports V11 deployed and counts6/4/4/2/6/4. This utility
is not a public recovery mechanism and does not prove account ownership: the offline
operator must already hold authorized local OS/database custody. It cannot target
other accounts or approve a Merchant. Phase6.8 is outside scope.

## Implementation and safeguards

`DisposableMerchantPasswordRecovery` follows the existing standalone Admin recovery
pattern: real System.console, no arguments, explicit recovery mode, exact confirmation,
hidden database/new-password/confirmation prompts, sanitized stage diagnostics and
best-effort clearing of char arrays. The clean-environment command below rejects
Spring/logging/JVM configuration overrides. No web server, component scan, bootstrap,
Flyway, SQL initialization or financial scheduler starts. Public schema validation
is pinned. Passwords are not logged or supplied in arguments/environment. JDBC and
BCrypt necessarily use some immutable internal strings that cannot be reliably erased.

The existing AdminRecoveryDatabaseGuard is reused unchanged: literal JDBC URL,
metadata validation and actual current_database/current_user/host(inet_server_addr())/
port must be paymesh_demo/paymesh_demo_user/127.0.0.1/5432. The Merchant mode is separately
required before calling this common strict guard; this does not invoke Admin recovery.

The transaction acquires AccountAdministrationLock, normalizes and requires exactly
`otp-merchant-demo@example.test`, enabled/PENDING_APPROVAL/MERCHANT-only. It requires
one inactive membership and matching registration, inactive/unverified registry,
PENDING_APPROVAL V11 lifecycle with no approval timestamp, no enabled demo recovery
eligibility, and the enabled V10 account security-change trigger. Any mismatch stops.

It uses existing AccountPasswords (12 Unicode code points minimum,72 UTF-8 bytes
maximum, no NUL/malformed Unicode), BCrypt and matching confirmation. Only password
hash, updated_at and authorization_version change on the user. The V10 trigger
atomically revokes session families and consumes outstanding challenges/reset grants.
Old signed tokens fail the existing current authorization-version checks, including
legacy tokens without a session ID. Existing AccountAudit records
`DISPOSABLE_MERCHANT_PASSWORD_RECOVERED`, resource ACCOUNT/target UUID, SUCCESS,
null authenticated actor and source `offline_operator_recovery`. No fabricated Admin
actor. Password/version/trigger effects/audit commit together or roll back.

Account UUID/login/enabled/status/roles, Merchant verification/lifecycle, membership,
registration and financial rows are not mutated. No REST endpoint, migration,
dependency or production session/recovery setting is added or changed. Existing Admin
recovery remains unchanged. OTP must stay disabled; V10-only activation tools are not
used. The utility is intentionally unavailable after approval/suspension/rejection.

## Exact Mac operator command — ONLY after explicit live-reset approval

The JAR must first be built from the tested source. Packaging does not deploy it:

```bash
cd "$HOME/Developer/paymesh-ai/backend"
mvn package -DskipTests
```

Recommended one-command launcher after approval and packaging:

```bash
/bin/bash "$HOME/Developer/paymesh-ai/backend/scripts/recover-disposable-merchant-password.sh"
```

The launcher checks interactive input/output and the packaged recovery class, selects
Java21 and clears inherited environment before executing the standalone utility.
It does not start or stop the web application. The expanded equivalent follows.

In a real private Mac Terminal tab, without tracing, pipes, heredocs, output capture
or background execution:

```bash
cd "$HOME/Developer/paymesh-ai/backend"
set +x
java_bin="$(/usr/libexec/java_home -v 21)/bin/java"
env -i HOME="$HOME" PATH="/usr/bin:/bin:/usr/sbin:/sbin" \
  PAYMESH_OFFLINE_MERCHANT_RECOVERY=RESET_DISPOSABLE_PENDING_MERCHANT \
  PAYMESH_DEMO_DB_URL=jdbc:postgresql://127.0.0.1:5432/paymesh_demo \
  PAYMESH_DB_USER=paymesh_demo_user \
  "$java_bin" \
  -Dloader.main=com.paymesh.backend.security.accounts.DisposableMerchantPasswordRecovery \
  -cp target/paymesh-backend-0.0.1-SNAPSHOT.jar \
  org.springframework.boot.loader.launch.PropertiesLauncher
recovery_status=$?
unset java_bin
printf 'Recovery exit status: %s\n' "$recovery_status"
unset recovery_status
```

Interactive prompts:

1. Type exactly `RESET DISPOSABLE MERCHANT PASSWORD IN paymesh_demo`.
2. Enter exactly `otp-merchant-demo@example.test` as the target email.
3. Enter database password privately (hidden).
4. Enter new Merchant password privately (hidden), then matching confirmation.

Expected success: `Disposable pending MERCHANT password reset successfully; prior
access tokens are invalidated.` Cancellation or any failure must not be blindly
retried. In particular, an uncertain commit requires privately inspecting the account
version and recovery audit before retrying; do not publish hashes or credentials.

## Operator checklist

Before approval/execution: verify the reviewed JAR and current protected backup,
that OTP capabilities remains false, and that lifecycle testing has not already
changed the target from pending. Do not change settings or restart any service.
The transaction rechecks target identity/state and eligibility rather than trusting
this checklist. No password belongs in chat, shell history or screenshots.

After a confirmed reset, the operator may sign in through Merchant Login with the
new password, verify the pending approval notice, reject the old password and
confirm old sessions no longer authorize requests. Do not create/process/refund
payments for verification. Review one accurate offline recovery audit and unchanged
ownership/registration/financial data using existing authorized read-only procedures.
OTP should remain false. These browser/live checks have not been executed by the agent.

## Files

Created:

- backend/scripts/recover-disposable-merchant-password.sh
- backend/src/main/java/com/paymesh/backend/security/accounts/DisposableMerchantPasswordRecovery.java
- backend/src/main/java/com/paymesh/backend/security/accounts/DisposableMerchantPasswordRecoveryTransaction.java
- PHASE-6.7.4-DISPOSABLE-MERCHANT-PASSWORD-RECOVERY-REPORT.md

Modified:

- backend/src/main/java/com/paymesh/backend/security/accounts/AccountAudit.java — honest offline Merchant success event.
- backend/src/test/java/com/paymesh/backend/security/accounts/AdminPasswordRecoveryIntegrationTest.java — isolated narrow-target, policy/state/role guards, BCrypt replacement, V10 revocation, audit rollback, secret-safe output and ownership/financial snapshots.

## Executed verification

Final results are recorded below after the isolated suite and packaging complete.

- Full required `cd backend; bash scripts/test-isolated.sh`: **300 tests passed,
  zero failures/errors/skips**, including the new comprehensive regression and
  existing offline Admin recovery/target identity/password policy tests. The recovery
  integration class ran8 tests successfully. Existing299 tests remain in the full run.
- The harness created a fresh isolated cluster on port55441 and stopped it afterward;
  its available PostgreSQL executable reported14.20. This was not a live PostgreSQL16
  demo test. Initial sandbox initdb was refused shared-memory allocation before tests;
  the authorized isolated rerun outside that sandbox passed in4m28s.
- `bash -n backend/scripts/recover-disposable-merchant-password.sh`: passed.
- Safe launcher non-interactive refusal check: passed; no Java/database startup.
- No frontend or AI implementation changed; their suites were not rerun.

Git inspection detected concurrent external staging changes in3 patch blocks.
No staging/index modification was performed by the implementation agent; all existing
and concurrent staged content was left untouched. No unrelated source changes were
restored or overwritten. Final packaging/whitespace results follow.

`mvn package -DskipTests`: BUILD SUCCESS. Both standalone Merchant recovery
classes and V11 are present in the runnable archive. JAR SHA-256: `4570dee5746a4846d684fc0a3c445694a9c5e25de9f5b24bcbeae4364ab6abab`.
The packaged utility was not executed against any live database.

`git diff --check`: passed after documentation update. Implementation and isolated
verification are complete; live reset requires explicit operator approval.
