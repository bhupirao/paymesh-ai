# Phase 4.4C.1 — Configuration and Operational Security Hardening

## Executive summary

Implemented the guarded demo-only initial ADMIN CLI target, disabled SQL
statement/bind logging by default, and added repository/build-context ignore
rules for local credentials, signing material, database backups, local archives,
and generated build output. Updated the account and demo instructions. No
payment, refund, gateway, webhook, reconciliation, or migration behavior was
changed.

**Verdict: CONDITIONAL PASS for controlled local development/demo.** The three
in-scope findings are addressed. This is not a production-readiness assessment.

## Preflight findings

- Repository root: `/Users/bhupirao/Developer/paymesh-ai` (from
  `git rev-parse --show-toplevel`).
- Before edits, the working tree had **190 staged entries, 95 unstaged entries,
  and 6 untracked paths**. It contained extensive pre-existing changes and local
  backup/archive paths. Nothing was reset, cleaned, discarded, staged, committed,
  or removed. The Git index was not altered.
- The root `.gitignore` existed as an untracked local file; it was updated in
  place and remains unstaged. Existing useful rules were retained.
- A tracked-filename scan found `.env.example` as the only credential-like
  tracked filename. It contains placeholders only; no tracked or staged private
  keys, credential files, database dumps, or backup archives were found.
- Existing local backup/archive paths were left in place. The new ignore rules
  hide them from future untracked-file discovery; they do not remove them and do
  not protect already tracked files.
- `scripts/test-isolated.sh` was inspected before execution. It initializes a
  marked temporary PostgreSQL data directory under `/private/tmp`, selects a
  separate `paymesh_isolated_*` database on port **55441** (and explicitly
  refuses port 5432), confirms PostgreSQL's actual data directory, supplies
  isolated test connection variables, and has an EXIT trap that stops the
  temporary server. The existing `IsolatedDatabaseGuard` remains in place.

## Files changed for this phase

- `../.gitignore` — added scoped ignore patterns while preserving existing
  rules and the `.env.example` exception.
- `.dockerignore` — excludes local secrets, keys/key stores, database backup
  formats and ZIP archives from a Docker build context; preserves
  `.env.example`. Docker configuration was not otherwise changed.
- `src/main/java/com/paymesh/backend/security/accounts/InitialAdminProvisioner.java`
  — requires and validates an explicit demo target, asks for two confirmations,
  pins its offline datasource, and verifies the connection before bootstrap.
- `src/main/java/com/paymesh/backend/security/accounts/DemoDatabaseGuard.java`
  — adds configuration-conflict checks and strict offline datasource checks;
  preserves the general URL/database verification used by the running demo
  application.
- `src/main/java/com/paymesh/backend/security/accounts/MerchantAccountProvisioner.java`
  — applies the shared conflicting-configuration checks and the strict offline
  datasource verification to the existing offline merchant command.
- `src/main/resources/application.properties` — disables SQL statements,
  Hibernate SQL formatting, and Hibernate JDBC bind logging by default.
- `src/test/java/com/paymesh/backend/security/accounts/InitialAdminProvisionerGuardTest.java`
  — added focused target, confirmation, mismatch, and password-confirmation
  regression tests.
- `src/test/java/com/paymesh/backend/security/accounts/DemoDatabaseGuardTest.java`
  — covers allowed/rejected URLs, datasource override conflicts, actual target
  checks, and the offline datasource identity/user requirement.
- `src/test/java/com/paymesh/backend/security/accounts/InitialAdminProvisionerStartupTest.java`
  — verifies pinned demo datasource arguments and non-web startup protections
  without redirecting the isolated test database.
- `README-ACCOUNTS.md` — documented the guarded ADMIN command, confirmations,
  target verification, and safe credential handling.
- `README-DEMO.md` — documented the same guarded offline flow and clarified
  that already provisioned demo accounts must not be recreated.
- `README-DEPLOY.md` — documented default-off SQL logging.
- `PHASE-4.4C.1-OPERATIONAL-HARDENING-REPORT.md` — this implementation and
  verification report.

No V1–V8 migration, application database, payment record, source configuration
outside this scope, Dockerfile, Compose file, or CI configuration was changed.

## Initial ADMIN target protection (M-01)

The CLI now fails closed before creating a Spring context unless
`PAYMESH_DEMO_DB_URL` is present and exactly matches a loopback PostgreSQL URL
for database `paymesh_demo` (`localhost` or `127.0.0.1`, optional valid port,
no URL options). It rejects blank/missing values, `paymesh_db`, other database
names, remote addresses, DNS names, malformed URLs, and invalid ports.

Before startup, it checks environment and JVM-property overrides for datasource
URL, username, type, JNDI, extra datasource settings, Spring config locations,
imports, and application JSON. Conflicts are rejected without printing their
values. The CLI accepts no command-line arguments and does not fall back to the
normal application's datasource.

The non-web context is pinned to the validated URL, user
`paymesh_demo_user`, and `DriverManagerDataSource`; JNDI datasource
autoconfiguration is excluded. Flyway and settlement scheduling are disabled,
Hibernate is restricted to schema validation, and the context factory is
non-web. Immediately before bootstrap, the provisioner verifies the datasource
implementation, JDBC metadata URL, connected database user, and
`SELECT current_database()` result. A mismatch or connection error prevents
account and audit writes. The existing transactional bootstrap, role/audit
checks, password hashing, advisory lock, and duplicate ADMIN protection remain
in effect.

The operator must type both exact confirmations:

1. `BOOTSTRAP ADMIN IN paymesh_demo`
2. `PROVISION INITIAL ADMIN`

Passwords are collected with non-echoing console prompts, checked for a match,
and cleared from character buffers. The CLI does not accept passwords through
arguments or print them. No migrations run; the V8 schema and role data must
already exist.

The offline initial ADMIN CLI is now deliberately **demo-only**. No separate
non-demo bootstrap mode was added. If a non-demo bootstrap workflow becomes
necessary, it needs its own explicit target contract and independent fail-closed
validation; there is no implicit production bypass.

## Default SQL logging (M-04)

`application.properties` now sets:

- `spring.jpa.show-sql=false`
- `spring.jpa.properties.hibernate.format_sql=false`
- `logging.level.org.hibernate.SQL=OFF`
- `logging.level.org.hibernate.orm.jdbc.bind=OFF`

No SQL debug profile or opt-in was added. Other datasource, JWT, webhook,
settlement, Flyway, and demo simulation settings were preserved. This change
does not claim that application-level diagnostic logging is a substitute for
reviewing any separately configured database/proxy logging.

## Git/build-context secret protection (M-05)

The root `.gitignore` retains the existing IDE/build/environment rules and now
ignores local `.env`/secret env files, local secret directories, generated JWT
key directories, private-key and key-store extensions, database dump/backup
formats, the local `backend-backup/` directory, and the known generated backend
ZIP archives. Maven `target/` output was already ignored. `.env.example` remains
available and unignored.

`.dockerignore` received corresponding narrow exclusions for secrets, key
material, database backup formats, and ZIP files. The Dockerfile and Compose
files were not modified.

`git check-ignore -v --no-index` confirmed ignore matches for local `.env`,
`.env.local`, `secrets.env`, `jwt-private.pem`, generated JWT key paths,
`.secrets`, the local backup directory, known ZIP archives, and Maven target
output. A separate check confirmed `.env.example` is **not** ignored. Ignore
rules do not remove or untrack files that are already in Git; no such actual
credential file was found in the tracked filename scan.

## Test results

Ran the complete suite only with `bash scripts/test-isolated.sh`.

- Tests: **196**
- Failures: **0**
- Errors: **0**
- Skipped: **0**
- Build: **BUILD SUCCESS**
- Isolated PostgreSQL: **stopped successfully**; the runner printed `server
  stopped` from its EXIT trap.
- Follow-up `pg_ctl ... status` against that same temporary data directory
  confirmed **no server running**.
- Database target: a fresh `paymesh_isolated_*` database in the marked temporary
  data directory on port 55441.

The tests include exact valid target acceptance; missing, malformed, remote,
wrong-database, and conflicting override rejection; actual connection URL,
database name, datasource type, and user checks; no writes after rejected
confirmation/target; fixed datasource arguments; non-web context behavior;
existing password confirmation; and the existing duplicate/concurrent initial
ADMIN integration coverage.

## Database and runtime safety

The existing `paymesh_db` and `paymesh_demo` databases were not contacted or
modified. The test run used only the runner's marked temporary database. No
ADMIN or merchant account was created. No keys or secrets were generated or
rotated. The running backend was not stopped or restarted. No Docker command
was run.

## Finding resolution

| Finding | Status | Evidence |
|---|---|---|
| M-01 — Initial ADMIN provisioning could use the default datasource | **Resolved for the supported demo bootstrap workflow** | Explicit URL validation, conflicting-override rejection, pinned non-web datasource, actual connection verification, two operator confirmations, and regression coverage. No non-demo bootstrap contract exists. |
| M-04 — SQL logging enabled by default | **Resolved** | Hibernate SQL, formatting, and JDBC bind logging are explicitly off in `application.properties`. |
| M-05 — Missing tracked Git ignore protection | **Resolved for future untracked local files** | Root `.gitignore` and `.dockerignore` rules added; `git check-ignore` verified intended cases. `.env.example` remains unignored. No actual tracked credential file was found. |

## Compatibility, limitations, and deferred work

- Initial ADMIN bootstrap now only supports the local `paymesh_demo` target. Do
  not use it for a non-demo database.
- The CLI requires an interactive terminal and a pre-existing V8 schema; an
  operator must not rerun it when an ADMIN already exists.
- Ignore files protect future untracked files only. If a credential is later
  staged or tracked, it needs explicit incident handling and possibly history
  remediation; ignore rules alone are insufficient.
- This phase does not implement deployment architecture, health/readiness
  changes, CI/CD, production migration credentials, production secret
  management, or production certification.
- Existing demo and main databases were intentionally not queried to validate
  their current contents; only the isolated suite was used for database-backed
  testing.

## Safe operator commands

Only use the offline command if the initial ADMIN genuinely does not exist. The
demo accounts are already provisioned; do not recreate them. If the existing
packaged artifact is available, from the backend directory load the protected
local environment without shell tracing, then invoke the interactive command.
This phase ran tests, not `package`, so it does not assert that a JAR is currently
present:

```bash
set +x
set -a
. "$HOME/.config/paymesh-demo/demo.env"
. "$HOME/.config/paymesh-demo/secrets.env"
set +a
java -Dloader.main=com.paymesh.backend.security.accounts.InitialAdminProvisioner \
  -cp target/paymesh-backend-0.0.1-SNAPSHOT.jar \
  org.springframework.boot.loader.launch.PropertiesLauncher
```

The environment must provide `PAYMESH_DEMO_DB_URL` for local `paymesh_demo`,
`PAYMESH_DB_USER=paymesh_demo_user`, and `PAYMESH_DB_PASSWORD`. Review the
resolved target locally without printing credentials, then type both exact
confirmations only when provisioning is intended. Do not run migrations as part
of this command.

Do not provision accounts in the existing installation merely to test the
workflow. The automated tests validate target safety with mocks and the isolated
test fixture.

## Recommended next phase

Continue with a separately scoped operational-readiness phase after review of
this report. Keep health/readiness, container deployment, and CI/CD as distinct
changes with their own isolation and deployment validation. Do not infer
production readiness from this hardening work or the passing isolated tests.
