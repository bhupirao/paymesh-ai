# Account and merchant provisioning — Phase 2 historical notes

> **Historical implementation note:** The Phase 2 statements below describe the state at that milestone and are not the current HTTP security state. JWT login and protected business routes were added later. For the current contract see [API-REFERENCE.md](API-REFERENCE.md), [README-JWT.md](README-JWT.md), and [README-BUSINESS-SECURITY.md](README-BUSINESS-SECURITY.md). The offline provisioning behavior below remains relevant; there are still no public registration or account-provisioning APIs.

This phase adds internal account services and JPA mappings for V8. It does not add
JWTs, Spring Security web filters, login/registration endpoints, or provisioning
HTTP APIs. Existing payment/refund/webhook/settlement routes are unchanged; their
planned JWT/merchant enforcement is a later, separately approved phase.

Only `spring-security-crypto` is added, using the Boot 3.5.7 BOM. PasswordEncoder
uses BCrypt strength 12 by default; `paymesh.accounts.bcrypt-strength` may be tuned
between 10 and 16 after measurement. Passwords require at least 12 Unicode code
points, at most 72 UTF-8 bytes, no NUL, and valid Unicode. Oversized input is
rejected, never truncated. Logins are stripped/lowercased and limited to 3–255
ASCII characters (letters, digits, dot, underscore, @, +, hyphen). Merchant IDs
are **never** trimmed, case-folded, or normalized.

## Initial ADMIN: guarded, explicit offline demo command

Initial ADMIN provisioning is restricted to the explicitly configured local
`paymesh_demo` database. It requires `PAYMESH_DEMO_DB_URL` to be exactly a local
PostgreSQL URL naming `paymesh_demo`, `PAYMESH_DB_USER=paymesh_demo_user`, and a
nonblank `PAYMESH_DB_PASSWORD` supplied securely in the environment. There is no
fallback to the normal application's default `paymesh_db` datasource. The URL is
validated before Spring starts, and after context startup the provisioner checks
the actual `DataSource` type, JDBC metadata URL, connected database name, and
connected database user before it calls the account bootstrap service.

The offline context is pinned to the validated URL and expected database user,
uses a direct `DriverManagerDataSource`, excludes JNDI datasource configuration,
and ignores external Spring configuration locations. Conflicting datasource URL,
username, type, JNDI, external config-location, application JSON, or alternate
datasource environment/system overrides are rejected or pinned before context
startup. Fixed command-line settings
disable Flyway and settlement scheduling, require Hibernate schema validation,
and force a non-web context. Provisioning requires two exact interactive
confirmations: `BOOTSTRAP ADMIN IN paymesh_demo` and the existing
`PROVISION INITIAL ADMIN`. It then prompts for login and password twice without
echo, validates confirmation, and clears password arrays. Credentials are not
accepted as arguments, logged, or printed. No migration runs: V8 schema and role
reference data must already exist.

From the already packaged artifact, after securely loading the required database
environment values, the exact command remains:

```bash
java -Dloader.main=com.paymesh.backend.security.accounts.InitialAdminProvisioner \
  -cp target/paymesh-backend-0.0.1-SNAPSHOT.jar \
  org.springframework.boot.loader.launch.PropertiesLauncher
```

The command accepts no application arguments and is never an application runner
or HTTP endpoint. Normal application startup does not invoke it. Existing ADMIN
and merchant demo accounts are already provisioned; do not rerun bootstrap or
recreate accounts. A transaction-scoped advisory lock and existing bootstrap
audit/role checks prohibit concurrent or repeated initial ADMIN creation. The
command is not an account recovery bypass if the existing ADMIN is disabled.

By default, SQL statement and JDBC bind-value logging are disabled. The
application properties also disable formatted SQL output. Do not enable sensitive
SQL diagnostics in a shared demo environment.

A transaction-scoped PostgreSQL advisory lock serializes account administration
across instances. Bootstrap refuses if **any** ADMIN assignment exists, including
disabled accounts, or if a successful bootstrap audit already exists. User, role
assignment and success audit commit atomically. A concurrent/repeated bootstrap
cannot create another initial ADMIN. This command is not a recovery bypass when
all administrators are disabled; recovery requires a separately reviewed procedure.

## Internal service boundary

`AccountCredentials.authenticate(login, char[])` verifies the password and enabled
status and returns an opaque, constructor-private AuthenticatedAccount. It issues
no JWT or HTTP session. Unknown, wrong-password and disabled accounts receive the
same generic failure. Unknown-user verification uses a randomly generated dummy
BCrypt hash. Caller-owned password arrays should be cleared when no longer needed;
the encoder necessarily creates temporary JVM representations that cannot all be
explicitly erased.

Privileged AccountAdministration services require this verified principal and
recheck enabled status, authorization version and ADMIN role from the database.
They never authorize a caller by a freely supplied actor UUID, login, role, or
settlement token. Future transport code must derive the principal from verified
credentials/security context, never deserialize it from a request body.

Supported operations:

- Create MERCHANT or additional ADMIN accounts, with role assignment and auditing.
- Register a merchant as unverified/inactive without claiming it.
- Verify ownership after external business review, recording the verifying ADMIN,
  verification timestamp and an audit review reference.
- Assign/reassign active membership only to an enabled MERCHANT account and a
  verified, active merchant.
- Revoke membership without deleting history or changing financial records.
- Enable/disable accounts; refuse disabling the last enabled ADMIN.
- Check current account status, roles and verified membership.

Ownership verification is an explicit ADMIN attestation, not automated KYC or
proof based on matching a login to a merchant string. The review reference is
3–100 characters using letters/digits/dot/underscore/slash/hyphen; store a ticket
identifier, not documents, credentials or secrets. Historical registry entries
remain unverified and unclaimed until these separate actions are authorized.
Registration/verification alone never grants membership. Blank historical IDs are
preserved in the database but cannot be verified or assigned by these services.

Privileged writes use independent READ COMMITTED transactions and the common
advisory lock. This avoids stale caller persistence contexts, duplicate logins,
lost authorization versions and last-ADMIN races. Account state and membership
changes increment authorization_version. Reenabling an account or reassigning a
membership does not revive old principals; credentials must be verified again.
All future privileged writers must follow the same lock/version protocol.

## Audit and data safety

Success audits commit with the privileged change; an audit storage failure rolls
the change back. Rejected authorization/validation operations write DENIED events
after the rejected transaction closes, in a separate transaction, so rollback
does not erase the denial or retain the rejected operation's locks/connections. Bootstrap success
and duplicate-bootstrap denial are audited. Technical failures are audited after rollback when storage is available; they
propagate and cannot guarantee an audit record while the database is unavailable.

Audit metadata is constructed from fixed operation fields and a bounded review
reference, never password input, hashes, raw tokens or arbitrary request objects.
Account DTOs contain no hash; the entity's hash is also excluded from JSON. Audit
foreign keys retain actor history. Accounts and memberships are disabled/revoked,
not deleted. No V1–V8 migration, payment/refund service, webhook verifier, settlement
credential, application configuration or isolation safeguard is changed.

## Tests and remaining boundaries

Run only:

```bash
bash scripts/test-isolated.sh
```

The unchanged script creates and verifies a temporary PostgreSQL cluster, runs the
complete Maven suite, and stops the server. Additional security integration schemas
are created only within that verified database. Fixtures are retained; no existing
application database or financial records are reset.

Tests cover BCrypt salting/verification/limits, duplicate accounts, roles,
disabled/stale principals, verified memberships, revocation/reassignment, audit
rollback/redaction, historical record preservation, concurrent bootstrap and
last-ADMIN protection. Existing payment/refund/webhook/settlement regressions remain
in the full suite.

This phase does not authenticate existing HTTP business APIs. Credential services
are internal and have no HTTP rate limiter; any future login endpoint needs rate
limiting, transport security and the approved JWT lifecycle before exposure.
Ownership review is a human/organizational control, not an external identity
verification integration. No Phase 3 work is included.

## Offline MERCHANT account provisioning

There is no public account-registration endpoint. An authorized operator can use
the explicit offline command below to provision one verified merchant and its
MERCHANT login. It prompts interactively for the existing ADMIN login/password,
merchant identifier, external ownership-review reference, new MERCHANT login,
MERCHANT password and confirmation, then requires the exact phrase
`PROVISION MERCHANT`. Passwords are read without echo, are never accepted as
arguments, and the character buffers are cleared after use.

The command is restricted to a loopback PostgreSQL URL whose database name is
exactly `paymesh_demo`; it requires `PAYMESH_DEMO_DB_URL`,
`PAYMESH_DB_USER=paymesh_demo_user`, and a nonempty `PAYMESH_DB_PASSWORD` in the
environment. Before credential verification or any write, it checks both the
connected JDBC URL and `SELECT current_database()`. It refuses `paymesh_db`,
remote hosts, URL query options, and other database names. The offline context
is pinned to non-web mode, disables Flyway and settlement scheduling, and uses
Hibernate schema validation. It pins a direct JDBC datasource and excludes JNDI
datasource lookup so external pool/JNDI settings cannot redirect the command.
The existing `paymesh_demo` database must already
have the current schema; this command does not create a database or run
migrations.

After the operator has built the jar and safely configured those three
environment values for the dedicated demo database, run:

```bash
java -Dloader.main=com.paymesh.backend.security.accounts.MerchantAccountProvisioner \
  -cp target/paymesh-backend-0.0.1-SNAPSHOT.jar \
  org.springframework.boot.loader.launch.PropertiesLauncher
```

The command authenticates the ADMIN through `AccountCredentials`; the resulting
opaque credential is then revalidated for enabled status and ADMIN role by the
existing account authorization transaction. It registers a new merchant, or
can claim an existing unverified, inactive historical merchant registry row
after the operator supplies the external review reference and confirms the
operation. It then verifies ownership, creates the MERCHANT account, assigns
membership, and commits the related success audit events atomically. Existing
verified or active merchant state is refused; ownership is never overwritten.
Historical merchants are never automatically claimed or verified.

An ordinary failure rolls back all provisioning writes and success audits. If
the client loses its database connection during commit, the outcome may be
uncertain; inspect the result through an authorized administrative process
before retrying. A retry after a committed operation is rejected by duplicate
merchant/login checks and never changes existing ownership, credentials, or
membership. This command does not provide recovery or overwrite behavior.

## Authenticated additional Admin API

Additional administrators can now be created through `POST /api/v1/admin/accounts` using a real existing ACTIVE ADMIN's verified Bearer JWT. This invokes AccountAdministration.createAdminAccount and its existing lock/current-account authorization/transaction/audit; InitialAdminProvisioner remains bootstrap-only. Request fields are login/password/confirmPassword only; the server assigns enabled ACTIVE ADMIN-only state. No automatic OTP eligibility is assigned. See API-REFERENCE.md for safe metadata/errors and body limits.

For the private Phase6.7.3 disposable OTP demonstration, do not put passwords/JWTs into curl arguments or shell history. After a separately approved deployment, use the hidden-terminal operator helper:

```bash
cd "$HOME/Developer/paymesh-ai"
/bin/bash backend/scripts/deploy-phase673-admin-api.sh
/bin/bash backend/scripts/activate-phase673-otp-demo.sh
# After browser demonstration, disable the insecure local feature:
/bin/bash backend/scripts/disable-phase673-otp-demo.sh
```

The first command performs a verified backup and Java-only restart with OTP disabled; it creates no accounts. The second separately authenticates operational demo-admin privately and uses the real Admin API/merchant registration API after another verified backup. It never resets/replaces existing accounts or operational passwords. All commands are operator-run only, not automatically executed by implementation/testing. The Phase6.7.3 report contains prerequisites, exact prompts, failure recovery and remaining manual checks. No new Flyway migration is required.
