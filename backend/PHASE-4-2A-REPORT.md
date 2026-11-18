# Phase 4.2A — Offline merchant provisioning report

## Modified files

- `src/main/java/com/paymesh/backend/security/accounts/MerchantAccountProvisioner.java` — new explicit console entry point.
- `src/main/java/com/paymesh/backend/security/accounts/DemoDatabaseGuard.java` — new fail-closed JDBC target and connected-database verifier.
- `src/main/java/com/paymesh/backend/security/accounts/AccountAdministration.java` — atomic provisioning facade operation.
- `src/main/java/com/paymesh/backend/security/accounts/AccountAdministrationTransactions.java` — transactional provisioning orchestration using existing audited account operations.
- `src/main/java/com/paymesh/backend/security/accounts/InitialAdminProvisioner.java` — shared offline startup arguments for the validated demo target.
- `src/test/java/com/paymesh/backend/security/accounts/DemoDatabaseGuardTest.java` — new target and connected-database guard tests.
- `src/test/java/com/paymesh/backend/security/accounts/AccountProvisioningIntegrationTest.java` — workflow, rejection, rollback, historical ownership and payment-preservation tests.
- `src/test/java/com/paymesh/backend/security/accounts/InitialAdminProvisionerStartupTest.java` — offline demo datasource argument assertions.
- `README-ACCOUNTS.md` — offline merchant-provisioning instructions and command.

No migration, Compose file, financial service, payment/refund record, or application database was changed.

## Provisioning command

After the operator separately configures the dedicated demo datasource environment and builds the jar, run exactly:

```bash
java -Dloader.main=com.paymesh.backend.security.accounts.MerchantAccountProvisioner \
  -cp target/paymesh-backend-0.0.1-SNAPSHOT.jar \
  org.springframework.boot.loader.launch.PropertiesLauncher
```

The command accepts no arguments and requires a secure interactive console. It prompts for the existing ADMIN login/password, merchant identifier, external ownership-review reference, new MERCHANT login/password/confirmation, and the explicit phrase `PROVISION MERCHANT`. Passwords are not echoed or passed as arguments, and prompt character arrays are cleared.

Required environment configuration:

- `PAYMESH_DEMO_DB_URL=jdbc:postgresql://127.0.0.1:5432/paymesh_demo` (or a loopback URL with the same database name)
- `PAYMESH_DB_USER=paymesh_demo_user`
- `PAYMESH_DB_PASSWORD` set securely in the process environment

## Authentication, ownership and transaction design

The command authenticates the supplied ADMIN credentials through `AccountCredentials`. Its opaque principal is revalidated by the existing account authorization service inside the privileged transaction, including current enabled status, authorization version and ADMIN role. A non-ADMIN, disabled account, or stale principal is rejected. No caller-supplied UUID, role, public registration endpoint, or fabricated principal is used.

`AccountAdministration.provisionMerchant` performs registration when the merchant ID is new, or accepts only an existing unverified and inactive historical registry row. It then requires the explicit external review reference, verifies ownership, creates a BCrypt-hashed MERCHANT account, assigns membership, and writes the existing success audit events in the same `REQUIRES_NEW`/`READ_COMMITTED` transaction. The existing authorization checks and audit requirements are reused. A preexisting verified or active merchant, duplicate login, invalid review reference, or other failure is rejected without overwriting ownership or committing partial provisioning. A retry after a rolled-back attempt can start cleanly; a retry after committed or commit-uncertain work is refused by duplicate/ownership checks and must be reviewed through an authorized admin process.

Historical merchant rows are never verified automatically. The command can claim an unverified, inactive historical row only after an authenticated ADMIN explicitly supplies the review reference and confirms the operation. Existing payments are never reassigned or updated; an integration test confirms the payment record remains unchanged.

## Database safeguards

The command requires `PAYMESH_DEMO_DB_URL`, validates an exact local PostgreSQL `paymesh_demo` target, rejects `paymesh_db`, remote hosts, URL options, malformed ports, and other database names, and pins the DB login to `paymesh_demo_user`. It limits configuration to the packaged application properties, pins a direct JDBC datasource and the datasource URL/user/password properties, excludes JNDI datasource lookup, and fixes the startup properties to non-web mode, Flyway disabled, Hibernate `validate`, and settlement scheduling disabled. The non-web context factory from `InitialAdminProvisioner` remains in force even if Spring configuration attempts to select a web context.

Before credential verification (which can create a denial audit) or provisioning writes, the command compares the connected JDBC metadata URL with the validated target and checks `SELECT current_database()` equals `paymesh_demo`. Schema validation may read database metadata during context startup, but no migration or provisioning write occurs before the connected-database check. The command does not create a database; the V8 schema must already be present.

## Tests and results

The full regression suite was run only with:

```bash
bash scripts/test-isolated.sh
```

Final result: **179 tests run, 0 failures, 0 errors, 0 skipped; BUILD SUCCESS.** The suite verified the temporary PostgreSQL cluster and its data directory before testing, and confirmed server shutdown on completion (`server stopped`). Existing isolation safeguards and the script were not modified.

Coverage includes successful ADMIN-authorized provisioning; invalid credentials; non-ADMIN, disabled and stale ADMIN rejection; required ownership-review reference; duplicate merchant/account refusal; atomic rollback; historical merchant explicit attestation with payment preservation; local-only demo target and actual connected database checks; offline startup argument hardening; and existing merchant authorization rules.

## Safety and remaining limitations

- No operational ADMIN or MERCHANT account was created. Test accounts existed only as isolated test fixtures.
- No demo database, key, or secret was created. `paymesh_db` was not accessed or modified.
- No normal application server or Compose stack was started; no Flyway migrations were run against any non-test database.
- The supported database target is intentionally limited to loopback PostgreSQL `paymesh_demo`; remote demo provisioning is not supported by this command.
- Commit connection loss can leave the caller uncertain whether PostgreSQL committed. The command warns operators to verify state through an authorized administrative process before retrying; it never overwrites an existing verified merchant or login.
- The external ownership review remains an organizational process. The command records the supplied reference but does not perform KYC or independently validate the evidence.

Phase 4.2A is complete. Phase 4.2B has not started.
