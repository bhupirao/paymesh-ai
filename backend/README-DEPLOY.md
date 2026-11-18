# PayMesh AI backend deployment

PayMesh AI is a **simulated payment backend**. Mock Razorpay, Mock Stripe,
refunds, webhook recovery, and reconciliation do not contact payment providers
or move money. This repository is for controlled local development and portfolio
demonstration; it is not production certified.

## Requirements

- Java 21, Maven, and PostgreSQL for host-run development.
- Docker Compose v2 for the database-only demo or normal local container stack.
- Flyway migrations V1–V8 are applied at normal application startup. The offline
  account provisioners disable Flyway and require an existing schema.
- SQL statement, Hibernate bind-value, and formatted SQL logging are disabled by
  default.

## Guarded local demo

The supported demo topology runs the backend on the host at
`127.0.0.1:18080` and PostgreSQL alone in a fresh Compose project. The database
is published only on `127.0.0.1:15432`, uses database/user `paymesh_demo` /
`paymesh_demo_user`, and persists in a separate named volume. This stack does
not use or copy data from either application database or the older host database
on port 5432. Existing accounts and records on those databases remain separate.

Use a new external environment file; do not overwrite the existing
`$HOME/.config/paymesh-demo/demo.env`:

```bash
umask 077
cp demo-compose.env.example "$HOME/.config/paymesh-demo/demo-compose.env"
${EDITOR:-vi} "$HOME/.config/paymesh-demo/demo-compose.env"
docker compose --project-name paymesh-demo-db \
  --env-file "$HOME/.config/paymesh-demo/demo-compose.env" \
  -f compose.demo.yaml up -d
docker compose --project-name paymesh-demo-db \
  --env-file "$HOME/.config/paymesh-demo/demo-compose.env" \
  -f compose.demo.yaml ps
```

The external file must set `PAYMESH_DEMO_DB_PASSWORD`; it is not a tracked
secret store. Start the host backend only after PostgreSQL is healthy, with the
loopback URL `jdbc:postgresql://127.0.0.1:15432/paymesh_demo`, the demo profile,
the existing external JWT key and webhook/settlement configuration, timeout
simulation explicitly enabled, scheduling disabled, and `PORT=18080` /
`SERVER_ADDRESS=127.0.0.1`. The demo target is intentionally loopback-only to
preserve `DemoDatabaseGuard`.

This is a **fresh independent database**. It has no copied payments or
provisioned accounts. The application startup applies V1–V8; then the guarded
offline initial ADMIN and merchant commands may provision new demo accounts
after explicit confirmation. The existing database accounts and payment rows
must not be recreated or migrated by this demo stack.

Stop the demo database container without deleting its data:

```bash
docker compose --project-name paymesh-demo-db \
  --env-file "$HOME/.config/paymesh-demo/demo-compose.env" \
  -f compose.demo.yaml down
```

Do not add `-v`; that would delete the dedicated demo volume.

## Separate normal-mode local container stack

`compose.yaml` is a separate local container topology with project
`paymesh-local-container`, database `paymesh_container`, its own internal-only
database, named volume, and backend published only to host loopback (default
`127.0.0.1:18081`). It does not enable the demo profile or gateway timeout
simulation. Supply its required values through a protected external env file
based on `.env.example`; mount an external JWT key directory read-only. The
configuration expects the webhook HMAC secrets and settlement token as
environment values, not Docker secret files.

```bash
umask 077
cp .env.example "$HOME/.config/paymesh-demo/container-compose.env"
${EDITOR:-vi} "$HOME/.config/paymesh-demo/container-compose.env"
docker compose --project-name paymesh-local-container \
  --env-file "$HOME/.config/paymesh-demo/container-compose.env" \
  -f compose.yaml up --build -d
```

This container stack is infrastructure for local evaluation, **not a complete
authenticated merchant workflow**. Initial ADMIN and merchant provisioning is
currently demo-database-only; no non-demo bootstrap route exists. Do not claim
that the fresh normal-mode container database is ready for merchant payment
processing without an authorized account-provisioning design.

Stop while preserving its data with:

```bash
docker compose --project-name paymesh-local-container \
  --env-file "$HOME/.config/paymesh-demo/container-compose.env" \
  -f compose.yaml down
```

Do not add `-v`. The name-scoped volume is separate from the guarded demo
volume and host PostgreSQL data.

## Health and readiness

- `GET /api/v1/payments/health` remains the static payment service status; it
  does not test database availability.
- `GET /actuator/health` is aggregate health.
- `GET /actuator/health/liveness` uses only application liveness state and does
  not fail because PostgreSQL is temporarily unavailable.
- `GET /actuator/health/readiness` includes readiness state and the PostgreSQL
  health contributor.

Health component details are hidden. Only these health routes are public;
Actuator discovery (`/actuator`) and `/actuator/info` remain ADMIN-only. Other
Actuator endpoints are not exposed and are denied by the security fallback.

## API and authentication

See [API-REFERENCE.md](API-REFERENCE.md) for the source-backed route, DTO,
authentication, idempotency, and response contract. Business APIs use RS256
JWTs with a 15-minute lifetime; there is no refresh-token endpoint. Webhooks
retain independent HMAC authentication, and settlement operations use the
separate settlement bearer token. Never put credentials in command arguments,
terminal output, or tracked files.

## Tests and CI

Run the full suite only through the guarded isolated PostgreSQL runner:

```bash
bash scripts/test-isolated.sh
```

The runner verifies a marked temporary non-5432 PostgreSQL cluster and stops it
on exit. GitHub Actions runs that script on pull requests and relevant pushes,
then packages the JAR and validates/builds the container configuration. Local
success does not imply that a GitHub-hosted workflow has run.

Phase 4.4 final local verification: **199 tests passed, zero failures, errors,
or skips**; the isolated PostgreSQL process stopped successfully; and
`mvn clean package -DskipTests` built the executable JAR. Docker runtime
validation could not run in the current environment because the Docker CLI,
Compose plugin, and daemon were unavailable. The workflow has not yet run on
GitHub.

## Deferred limitations

This backend does not implement real gateway integrations, public/non-demo
ADMIN provisioning, production migration/runtime identity separation,
distributed rate limiting, managed secret rotation, production TLS/ingress,
database-enforced aggregate refund constraints beyond application locking,
Kubernetes, or GenAI. Review [README-DEMO.md](README-DEMO.md) before creating any
payment or refund records.
