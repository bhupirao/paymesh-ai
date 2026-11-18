# Phase 5.4 — Java + Python Integration

**Completed — November 14, 2026.** Next: Phase 6 — Frontend Dashboard.

## Architecture and trust boundary

`POST /api/v1/payments/{paymentId}/investigate` → existing signed JWT validation →
`EvidenceCollector` → `BusinessAccess.actor()` and scoped `payment(..., false)` →
detached normalized snapshot → one-slot admission gate → `RestClient` →
`POST http://127.0.0.1:8000/api/v1/investigations` → strict response validation →
Java provenance envelope with the original Python response under `investigation`.

There is no request body or caller-supplied destination. The existing route catalog
adds this POST to ADMIN/MERCHANT JWT routes; default deny remains. Active, verified
merchant ownership is checked with the existing database authorization predicate.
Admins retain existing cross-merchant authorization. Missing and inaccessible payments
both return 404 before secondary evidence collection or Python. Inactive merchants,
revoked memberships and invalid tokens cannot collect evidence. Authorization applies
at collection time; revocation after the snapshot does not cancel an in-flight call.
No admin audit write is added to this read-only snapshot operation.

Python is unchanged. Its direct-input limitation, “Supplied evidence is not authenticated
or fetched from Java.”, is preserved verbatim inside the nested response. The sibling
`evidenceProvenance.source = JAVA_AUTHORIZED_DATABASE_SNAPSHOT` describes the Java
boundary only. Its collection timestamp, explicit unavailable-evidence reasons and
scope distinguish this path from arbitrary synthetic requests to Python. This is an
application trust assertion, not a cryptographic attestation or a claim that Python
authenticates direct requests. Bank debit, settlement and refund arrival remain unverified.

## Snapshot and mapping

A separate proxied service method uses `REQUIRES_NEW`, `REPEATABLE_READ`, read-only,
five-second transaction timeout. PostgreSQL MVCC provides one snapshot for authorization,
payment and all histories. The existing shared account-administration advisory lock
is reused; no payment row write lock is taken. No financial writes, audit writes,
repository saves or remote calls occur inside collection. The transaction and its
connection are released before HTTP; the controller forbids ambient transactions,
and the HTTP client separately rejects active transactions. Open-in-view is already disabled.
Collection time is taken after reads, still inside the transaction; the snapshot itself
was established by the first database read. It is a historical view, not a guarantee
that payment state remains unchanged during inference.

| Python request field | Actual Java/database source and handling |
|---|---|
| paymentId, paymentStatus, currency, paymentMethod | Authorized Payment entity; no customer or merchant identifiers forwarded |
| amount | Payment BigDecimal → exact decimal string, positive, Python precision 14 / scale 2 bound |
| collectedAt | UTC Instant after collection |
| gatewayTransactions | payment_gateway_transactions: id, payment_id, gateway_name, gateway_transaction_id, current observed status, created_at, updated_at |
| errorCode / errorMessage | Only UNSUPPORTED_CURRENCY and INVALID_AMOUNT codes allowed; arbitrary codes/messages withheld; errorMessage always null |
| refunds | refunds: refund_id, payment_id, positive BigDecimal amount as string, SUCCESS, created_at; idempotency key excluded |
| webhooks | webhook_events: id, payment_id, processing status, occurred_at; SQL JSON projection of only gatewayTransactionId and status (as outcome); raw payload, event ID, detail and headers excluded |
| reconciliation | reconciliation_attempts: id, payment_id, outcome, status_before, status_after, result, created_at; detail excluded |

No historical timeout is inferred from a current gateway SUCCESS. Reconciliation
transitions come from persisted attempts. Webhook processing status and parsed outcome
are distinct. Collections are deterministically ordered by ID and bounded with LIMIT 101.
101 rows reject the entire investigation with 422, including refunds, rather than
silently truncating financial totals. Empty history is `[]`. Unsupported gateway states
such as INITIATED or UNKNOWN, unsupported refund state or an unprojectable webhook
make the entire respective collection `null` with an envelope reason. Remaining
histories stay available. Python adds its existing unavailable-evidence limitations.
Malformed stored JSON fails collection safely (503); it is never forwarded.
Schema-incompatible timestamps, currencies, amounts, transitions, duplicate IDs or
successful refund totals above the payment amount fail 422. No pagination is presented
as a complete investigation. Serialized request size is also capped at Python's
131072-byte default. If Python is configured with a lower limit, its rejection becomes
502; align that setting operationally.

## HTTP behavior and errors

No dependencies or migrations added. RestClient uses Spring's JDK request factory,
a dedicated JDK HttpClient with direct connections and redirects NEVER. Only an HTTP
origin with literal host 127.0.0.1 is accepted; userinfo, non-root path, query and fragment
are rejected. No JWT, settlement credential or request header is forwarded. No retry
loop is configured. One remote investigation runs per Java instance; concurrent requests
receive sanitized 503 without queuing after authorization. This gate does not regulate
calls made directly to Python or other Java instances, and a timed-out Python operation
may continue server-side; cancellation is not claimed.

Defaults: enabled false; base URL http://127.0.0.1:8000; connection timeout 2000 ms;
response timeout 45000 ms; response cap 262144 bytes. Bounds: connection 1–10000 ms,
response 1–120000 ms, response bytes 1024–1048576. The Spring 6.2 JDK factory's timeout
covers waiting for response and consumption of its wrapped body stream. 45 seconds
allows headroom above observed local inference latency; it is configurable.

JSON is read through a max+1 byte bound before parsing. Duplicate keys, trailing JSON,
missing/extra response fields, incorrect primitive types, invalid UUID/timestamp,
unsupported enum, nonfinite score and mismatched payment ID are rejected. RAG_LLM
requires SUCCEEDED; legitimate RAG_ASSISTED and DETERMINISTIC outputs are preserved.
Java never substitutes or fabricates an investigation.

Errors retain ApiErrorResponse shape: 401 missing/invalid token; 403 denied role;
404 missing/inaccessible payment; 422 excessive/incompatible evidence; 502 timeout,
unavailability, non-2xx (including redirect), malformed/oversized/mismatched response;
503 disabled, busy, or database evidence unavailable. Upstream bodies and exception
messages are never included. Existing payment exception handling is unchanged.

## Files

Added under `src/main/java/com/paymesh/backend/investigation/`:
EvidenceCollector.java, EvidenceValidator.java, AiInvestigationClient.java,
InvestigationResponseValidator.java, InvestigationController.java,
InvestigationFailure.java, InvestigationErrors.java.

Added under `src/test/java/com/paymesh/backend/investigation/`:
InvestigationIntegrationTest.java and AiInvestigationClientTest.java.

Modified: BusinessEndpointCatalog.java (one POST route), application.properties,
.env.example, API-REFERENCE.md, README-DEMO.md, scripts/test-isolated.sh (bounded
Spring test-context cache to leave isolated PostgreSQL connection headroom).
This report is new. No Python, payment-processing, entity, repository, migration,
backup or protected configuration files were changed.

## Verification results

Final required command: `cd backend && bash scripts/test-isolated.sh`.
Result: **226 tests passed, 0 failures, 0 errors, 0 skipped**, BUILD SUCCESS in
2 minutes 38 seconds, completed 2026-11-14 10:30:48 IST. This includes all existing
199 tests plus seven new signed-JWT/database integration tests and 20 mock HTTP tests.
The actual isolated target was `paymesh_isolated_1794632285_82950` on port 55441,
data directory `/var/folders/t4/6jmrc0x96h12j8wz82xlnhbw0000gn/T/paymesh-isolated-test.A03QJn/data`.
The test cluster was stopped by the script and its files retained. Neither demo database
was used by tests. Final log: `/tmp/paymesh-phase54-tests-verified.log`.

The new tests verify authorized merchant/admin use, missing/invalid tokens, cross-merchant
and inactive merchant rejection before Python, missing payments, exact decimal strings,
real gateway/refund/webhook/reconciliation mapping, privacy filtering, empty versus
unavailable histories, overflow rejection, read-only repeatable-read transaction settings,
no transaction/connection during remote invocation, unchanged payment/refund records,
busy admission, RAG_LLM and legitimate fallbacks, disabled configuration, invalid JSON,
missing required fields, unsupported enums, wrong payment ID, oversized responses,
non-2xx, redirects, unavailable service, header and body timeouts and unsafe destinations.

After that pass, `mvn -DskipTests package` returned **BUILD SUCCESS** in 6.577 seconds,
completed 2026-11-14 10:31:33 IST. Artifact:
`backend/target/paymesh-backend-0.0.1-SNAPSHOT.jar`. Inspection confirmed all new
integration classes are in BOOT-INF/classes. SHA-256:
`1b88b58cb1a071abbcc5531f5a4917ef89ae78d0fe30a84bd1e79a1428e24ede`.
Build log: `/tmp/paymesh-phase54-package.log`. `git diff --check` passed and all three
documented shell command blocks passed `bash -n`.
The first sandbox attempt failed at initdb shared-memory allocation (Operation not
permitted). The approved isolated run passed the existing 199 tests but its five new
integration tests failed context startup because retained pools exhausted PostgreSQL's
100-client limit: 204 run, 0 failures, 5 errors. No financial assertion failed in that
run. The isolated test runner now bounds the Spring context cache to eight pools,
leaving connection headroom; the final complete suite passed against another fresh cluster.
Tests use mock upstream HTTP responses and signed JWT fixtures, never a real LLM.
Python source is unchanged; a Python regression/pip-check rerun is therefore not required.
Java automated tests: **226 passed**. Python automated tests: **102 previously passed**.
The combined reported total is **328**, not a fresh combined run.

## Live integration verification — November 14, 2026

These are the supplied completed live verification results, recorded during this
documentation-only finalization; no services or live tests were run again here.
Java readiness returned **UP** on port **18080** after the corrected startup.
Python health was **UP** on port **8000**, configured **RAG_LLM**.
llama.cpp health was **OK** on port **8082**.

| Verification | Payment / caller | HTTP | Observed duration | Result |
|---|---|---|---|---|
| Webhook recovery | `c072351f-4646-4288-b8ca-6758d4e521f3`, Merchant A | 200 | 11.54 s | SUCCESS; WEBHOOK_RECOVERY; RAG_LLM/SUCCEEDED |
| Full refund | `f1c5e798-fa14-438c-972d-d1a6247a5ffb`, Merchant A | 200 | 10.87 s | REFUNDED; FULL_REFUND; RAG_LLM/SUCCEEDED |
| Refund history | Full-refund payment, Merchant A | 200 | 0.18 s | Two successful refunds: INR 200 + INR 800 = INR 1000; remaining INR 0 |
| Reconciliation recovery | `c6f797c0-c810-4730-bac2-19cb8504a87d`, Merchant B | 200 | 10.01 s | SUCCESS; RECONCILIATION_RECOVERY; RAG_LLM/SUCCEEDED |
| Cross-merchant access | Merchant A investigating Merchant B's payment | 404 | 0.03 s | Access rejected |
| Unauthenticated investigation | No credentials | 401 | 0.03 s | Access rejected |

All three successful investigations returned `JAVA_AUTHORIZED_DATABASE_SNAPSHOT`
provenance, `COMPLETED` investigation status, matching payment IDs, knowledge
references and explicit limitations. Real LLM generation succeeded for all three
authenticated scenarios. Both successful refund records were referenced in the
full-refund investigation. Persisted reconciliation evidence supports the
PROCESSING to SUCCESS transition.

Mean observed end-to-end investigation latency was approximately **10.81 seconds**
across these three requests. This is a small serial observation, not a load-test benchmark.
No new financial records were created or modified during live investigation verification.

The initial Java restart failed with `Demo gateway fault simulation requires the guarded datasource and enabled Flyway migrations`
because Flyway was disabled. Correcting startup to `--spring.flyway.enabled=true`
succeeded and readiness returned UP. The initial full-refund request returned 404
because its UUID omitted the letter `d` after the final hyphen. A read-only PostgreSQL
lookup confirmed the correct ID above; the rerun succeeded.
Python outage and malformed upstream responses were covered by automated tests,
not by deliberate live service shutdown.

## Ownership verified, read-only

The lookup used protected configuration, explicit paymesh_demo at 127.0.0.1:5432,
user paymesh_demo_user and PostgreSQL default_transaction_read_only=on.

| Existing payment | Merchant | Login | Observed status |
|---|---|---|---|
| c072351f-4646-4288-b8ca-6758d4e521f3 | DEMO_MERCHANT_A | demo-merchant-a | SUCCESS |
| c6f797c0-c810-4730-bac2-19cb8504a87d | DEMO_MERCHANT_B | demo-merchant-b | SUCCESS |
| f1c5e798-fa14-438c-972d-d1a6247a5ffb | DEMO_MERCHANT_A | demo-merchant-a | REFUNDED |

The older README's port-15432 fresh-Compose instructions describe a different setup.
For this phase use the existing port-5432 database; do not create or recreate databases
or accounts and do not run provisioning commands.

## Exact guarded manual restart

The following is a future operator runbook; it was not executed during documentation
finalization. PID 81338 is historical and must not be assumed current. Inspect the
current listener, Java process identity and backend working directory before any
restart. Never stop Python or llama.cpp for this Java-only restart. Commands start
Java in the foreground; use a separate terminal for readiness checks.
Hibernate remains validate-only and settlement scheduling remains disabled.
Flyway must be enabled for the existing guarded demo gateway fault simulation.
The database identity guard and loopback binding remain required.

```bash
/bin/bash <<'BASH'
set -euo pipefail
set +x
cd "$HOME/Developer/paymesh-ai/backend"
test -s target/paymesh-backend-0.0.1-SNAPSHOT.jar
listener_pid=$(lsof -t -nP -iTCP:18080 -sTCP:LISTEN | sort -u)
case "$listener_pid" in ''|*[!0-9]*) echo 'Expected one listener PID'; exit 1;; esac
expected_pid="$listener_pid"
ps -p "$expected_pid" -o pid=,comm=
lsof -a -p "$expected_pid" -d cwd -Fn
case "$(ps -p "$expected_pid" -o comm=)" in *java) ;; *) echo 'Refusing unexpected process'; exit 1;; esac
lsof -a -p "$expected_pid" -d cwd -Fn | grep -Fx "n$PWD" >/dev/null
set -a
source "$HOME/.config/paymesh-demo/demo.env"
source "$HOME/.config/paymesh-demo/secrets.env"
set +a
if [ -z "${PAYMESH_DB_PASSWORD:-}" ]; then
  IFS= read -r -s -p 'Demo database password: ' PAYMESH_DB_PASSWORD </dev/tty
  printf '\n' >/dev/tty
fi
: "${PAYMESH_DB_PASSWORD:?Missing demo database password}"
export PAYMESH_DB_PASSWORD
export PAYMESH_DB_URL=jdbc:postgresql://127.0.0.1:5432/paymesh_demo
export PAYMESH_DEMO_DB_URL="$PAYMESH_DB_URL"
export PAYMESH_DB_USER=paymesh_demo_user
export PAYMESH_JWT_PRIVATE_KEY_FILE="$HOME/.config/paymesh-demo/jwt-private.pem"
export PAYMESH_JWT_PUBLIC_KEY_FILE="$HOME/.config/paymesh-demo/jwt-public.pem"
# Verify the actual database/user before stopping the old server. Read only.
target=$(PGPASSWORD="$PAYMESH_DB_PASSWORD" PGOPTIONS='-c default_transaction_read_only=on' \
  psql -X -h 127.0.0.1 -p 5432 -U paymesh_demo_user -d paymesh_demo -At -v ON_ERROR_STOP=1 \
  -c "SELECT current_database() || ':' || current_user")
test "$target" = 'paymesh_demo:paymesh_demo_user'
test "$(lsof -t -nP -iTCP:18080 -sTCP:LISTEN | sort -u)" = "$expected_pid"
case "$(ps -p "$expected_pid" -o comm=)" in *java) ;; *) exit 1;; esac
lsof -a -p "$expected_pid" -d cwd -Fn | grep -Fx "n$PWD" >/dev/null
kill -TERM "$expected_pid"
for attempt in $(seq 1 30); do
  if ! kill -0 "$expected_pid" 2>/dev/null; then break; fi
  sleep 1
done
if kill -0 "$expected_pid" 2>/dev/null; then echo 'Old Java still alive; refusing replacement'; exit 1; fi
if lsof -t -nP -iTCP:18080 -sTCP:LISTEN >/dev/null; then echo 'Port occupied; refusing replacement'; exit 1; fi
exec java -jar target/paymesh-backend-0.0.1-SNAPSHOT.jar \
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
BASH
```

Confirm readiness in another terminal:

```bash
curl --noproxy '*' --fail --silent --show-error http://127.0.0.1:18080/actuator/health/readiness
curl --noproxy '*' --fail --silent --show-error http://127.0.0.1:8000/health
```

## Exact authenticated, read-only live investigation commands

No creation, processing, refund, webhook injection or reconciliation endpoints are
called. Login is interactive through the existing protected helper; capture its output
because the helper itself writes the token to stdout. Tokens/passwords are never echoed
or passed as curl/ps arguments. Run serially to protect the local model. Avoid shell tracing.

```bash
/bin/bash <<'BASH'
set -euo pipefail
set +x
set -a
source "$HOME/.config/paymesh-demo/demo.env"
source "$HOME/.config/paymesh-demo/secrets.env"
set +a
source "$HOME/.config/paymesh-demo/helpers.sh"
if [ -z "${PAYMESH_DB_PASSWORD:-}" ]; then
  IFS= read -r -s -p 'Demo database password: ' PAYMESH_DB_PASSWORD </dev/tty
  printf '\n' >/dev/tty
fi
: "${PAYMESH_DB_PASSWORD:?Missing demo database password}"
export PAYMESH_DB_PASSWORD
# Check current ownership again before choosing either account. Never query paymesh_db.
PGPASSWORD="$PAYMESH_DB_PASSWORD" PGOPTIONS='-c default_transaction_read_only=on' \
  psql -X -h 127.0.0.1 -p 5432 -U paymesh_demo_user -d paymesh_demo -v ON_ERROR_STOP=1 \
  -c "SELECT payment_id,merchant_id,status FROM payments WHERE payment_id IN ('c072351f-4646-4288-b8ca-6758d4e521f3','c6f797c0-c810-4730-bac2-19cb8504a87d','f1c5e798-fa14-438c-972d-d1a6247a5ffb') ORDER BY payment_id"
export PAYMESH_VERIFICATION_TOKEN
PAYMESH_VERIFICATION_TOKEN=$(paymesh_login demo-merchant-a)
python3 - <<'PY'
import json, os, urllib.request, urllib.error
opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
for payment in ('c072351f-4646-4288-b8ca-6758d4e521f3', 'f1c5e798-fa14-438c-972d-d1a6247a5ffb'):
    request = urllib.request.Request('http://127.0.0.1:18080/api/v1/payments/' + payment + '/investigate',
        method='POST', headers={'Authorization': 'Bearer ' + os.environ['PAYMESH_VERIFICATION_TOKEN']})
    try:
        with opener.open(request, timeout=55) as response:
            result = json.load(response)
        assert result['evidenceProvenance']['source'] == 'JAVA_AUTHORIZED_DATABASE_SNAPSHOT'
        assert result['investigation']['paymentId'] == payment
        print(json.dumps(result, indent=2))
    except urllib.error.HTTPError as error:
        raise SystemExit('Investigation failed: HTTP ' + str(error.code))
PY
unset PAYMESH_VERIFICATION_TOKEN
export PAYMESH_VERIFICATION_TOKEN
PAYMESH_VERIFICATION_TOKEN=$(paymesh_login demo-merchant-b)
python3 - <<'PY'
import json, os, urllib.request, urllib.error
payment = 'c6f797c0-c810-4730-bac2-19cb8504a87d'
opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
request = urllib.request.Request('http://127.0.0.1:18080/api/v1/payments/' + payment + '/investigate',
    method='POST', headers={'Authorization': 'Bearer ' + os.environ['PAYMESH_VERIFICATION_TOKEN']})
try:
    with opener.open(request, timeout=55) as response:
        result = json.load(response)
    assert result['evidenceProvenance']['source'] == 'JAVA_AUTHORIZED_DATABASE_SNAPSHOT'
    assert result['investigation']['paymentId'] == payment
    print(json.dumps(result, indent=2))
except urllib.error.HTTPError as error:
    raise SystemExit('Investigation failed: HTTP ' + str(error.code))
PY
unset PAYMESH_VERIFICATION_TOKEN
BASH
```

For the measured configuration, inspect `investigation.analysisMode` and
`generationStatus`; RAG_LLM/SUCCEEDED is expected when local generation succeeds.
RAG_ASSISTED or DETERMINISTIC is legitimate fallback, not proof of live LLM success.
Expected scenarios are WEBHOOK_RECOVERY, FULL_REFUND and RECONCILIATION_RECOVERY
only if the actual collected evidence supports them; do not force a scenario.

## Remaining limits

Financial decisions remain deterministic; the model performs constrained wording
selection. Bank debit, settlement and refund arrival are not verified. Docker runtime,
remote CI and production deployment remain separate future verification tasks.


This is a loopback demo trust boundary, not production network authentication for
Python. Local users/processes can still call Python directly. Lexical RAG and constrained
local wording selection remain unchanged. Current gateway rows are observations, not
an immutable attempt-status timeline. Null evidence is explicit uncertainty. Oversized
histories require a future aggregate/pagination contract, not silent truncation.
The 100-row and byte bounds may reject legitimate large histories; no incomplete
financial total is portrayed as complete. Future migrations and broader production
rate limiting/attestation are outside this phase.

## Historical implementation Git preservation and execution notes

Before implementation, `git status --porcelain=v1` contained 120 `AM`, 114 `A ` and
four `??` entries. The repository already had substantial staged and unstaged work.
The initial complete status is saved at `/tmp/paymesh-phase54-status.txt`, and the
initial exact staged binary diff at `/tmp/paymesh-phase54-index.patch`. Neither file
contains protected configuration from outside Git. The index SHA-256 before changes was
`1548bce336428293592c8b241c807d82a23fe99091b38d01599897a41ab119ad`.
No git add, commit, push, reset, clean or other index-mutating command was used.
Existing unstaged work was preserved by additive edits to the working files.

The second full isolated run executed 226 tests: zero assertion failures, two errors
from a new isolation test's Mockito setup invoking the MANDATORY transaction proxy
outside a transaction and its unfinished stubbing affecting the following test.
All 20 mock HTTP tests and the original 199 tests passed in that run. The spy setup
was corrected to target the underlying bean, and a fresh complete run followed.
The Java process's current working directory was verified as this project's backend;
a sandboxed `ps` inspection was denied, while `lsof` confirmed all three original
listeners and PIDs unchanged. The manual restart's `ps` guard is intended for the
operator's terminal outside that sandbox. No process-control command was executed.

Final Git status: 121 `AM`, 113 `A ` and seven `??` entries. All initial paths remain.
The only changed status category among pre-existing paths is BusinessEndpointCatalog.java
(`A ` → `AM`); newly untracked phase artifacts are this report and the main/test
investigation directories. All other phase edits are additive changes to files already
marked `AM` initially. Complete final status: `/tmp/paymesh-phase54-status-final.txt`.
Final `.git/index` SHA-256 is identical to the initial hash above; the staged binary
diff is byte-for-byte identical (`cmp` passed). **Existing Git index preserved.**

## Documentation finalization scope

This finalization updates only this report, root README.md and PROGRESS.md. Earlier
build, test and process-inspection notes above describe historical implementation
work. No implementation code, dependencies, migrations, configuration, frontend files,
database records or running services were changed during documentation finalization.
No rebuild, restart, stop, commit, push or Git index mutation was performed.
