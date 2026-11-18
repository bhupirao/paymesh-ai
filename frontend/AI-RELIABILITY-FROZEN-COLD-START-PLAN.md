# Frozen forward-only AI reliability cold-start release

Status: **PREPARATION PASS — NO SERVICES STARTED.**

Approved final bundle:
`~/.config/paymesh-demo/ai-reliability-cold-release-z6t8msoo`

Manifest SHA-256:
`d4b2cef5398783fc24b49ea72afc32e4806e5f8b335a63df17e1e9e2ca9dca87`

Sanitized preparation evidence:
`~/.config/paymesh-demo/ai-cold-release-preparation-yesu08mh/evidence.json`

The earlier `ai-reliability-cold-release-fgfbmmqu` candidate is preserved unchanged
but superseded. Do not activate it. Its degraded failure-path review prompted the
corrected final bundle above. No previous protected artifact was overwritten.

## Verified contents and identity

- Java JAR SHA256: `6f6a2e27659ff338fb01163819a1a8cf2112d694e579515e7d64256eac0d96ba`.
- Python40-file manifest SHA256: `9ef4ccc9e6ed7a989eea1d924f2ddcbffa93e124ce0b63cb9598dbb481f68006`.
- 1,758 payload files independently rehashed, including the copied venv/dependencies,
  app, knowledge documents, frontend static/proxy files and operational launch helpers.
- Files are owner-read-only400; directories500, with macOS user-immutable flags.
  Symlinks and external interpreter/JVM/model/server hashes are pinned. These flags
  prevent ordinary accidental writes; they are not protection against an administrator
  or the owner deliberately clearing flags. Each future execution rehashes the bundle.
- Python imports were tested from the copied venv/app and the exact conversation query
  allowlists were checked by importing the copied frontend handler without binding a port.
- Existing Java/Python private service tokens match. Secret files remain external,
  current-owner mode600 and hash-pinned. No password or token is copied into the release
  manifest. Existing JWT keypair correspondence was verified. The public key's existing
  mode644 is allowed only as an owner-controlled non-group/world-writable public file;
  private keys and secret configuration still require600. No key permission changed.

## Model and frontend

Existing llama.cpp binary: `~/Developer/paymesh-tools/llama.cpp/build/bin/llama-server`.
SHA256: `8a48b6c90204b752021adbd99ddb66c9b447d71f6ce4333a205be0527ab2bcc8`.
Offline version metadata identifies commit `ec7f3ac`, matching the previously reviewed
b4514 implementation. No server was started for version/help inspection.

Existing model: `~/Developer/paymesh-tools/models/qwen2.5-0.5b-instruct-q4_k_m.gguf`.
SHA256: `74a4da8c9fdbcd15bd1f6d01d621410d31c6fc00986f5eb687824e7b93d7a9db`.
GGUF3 metadata identifies qwen2 / qwen2.5-0.5b-instruct / fileType15 (Q4_K_M).
These are current artifact pins, not a fabricated historical checksum comparison.

Reviewed proposed launch: explicit local model, alias paymesh-qwen,127.0.0.1:8082,
context4096, two CPU threads, one parallel slot, GPU layers0 and --log-disable. Context,
thread and parallel settings match the Phase5.3B recorded runtime. Required flags were
verified in the actual binary help. Model loading/health/inference remain unexecuted.

Frontend starts the copied corrected handler from the bundle on127.0.0.1:5500.
No old PID or running handler is reused. After a later approved cold start, browser hard
refresh is required. No additional frontend reload is needed after that initial start.

## Database and backup

Fresh private /dev/tty authentication compared the complete read-only snapshot with the
verified backup baseline at2026-11-18T16:32:06Z and ended with ROLLBACK. Passwords were not
printed, saved or passed as command-line arguments. V1–V14/checksums and all recorded
fingerprints/counts match. Financial/account entity counts are6|4|4|2|6|4; conversation
counts are3 conversations /4 creation journals /5 requests /10 messages. Sessions,
security/recovery, checkout/link and all eight financial tables were included in the
comparison. No new backup or restore was performed for this preparation.

Backup:
`~/.config/paymesh-demo/v14-pre-cold-start-backup-20261118T161201Z-sg04p91w/paymesh_demo-v14.dump`
SHA256: `581740dd25113f463096f00177d8f4db4c33b6e7f578c92b318936d246dbefe2`.
Checksum, pg_restore --list and full extraction to /dev/null were reverified. This is
archive readability, not a successful test restore. No restore is authorized.

The database connection remains only paymesh_demo/paymesh_demo_user/127.0.0.1:5432.
Java startup explicitly sets Flyway disabled, SQL init never, Hibernate validate,
OTP=false, checkout simulation=false and settlement scheduling=false. Scheduled
conversation cleanup is disabled for this maintenance release to preserve records.
Re-enabling retention later needs separate review. The accepted PostgreSQL wildcard /
TLS-off / unknown HBA-PF risk is unchanged; PostgreSQL is never restarted or reconfigured.

## Exact future startup command — separate approval required

Do not run until the operator approves this exact final manifest and a maintenance
window. Close all PayMesh browser tabs and other API clients first: restored cookies or
background clients could legitimately change session/conversation rows and make the
preservation gate fail. No backup/restore, browser login or inference is included.

```bash
release="$HOME/.config/paymesh-demo/ai-reliability-cold-release-z6t8msoo"
"$release/python/.venv/bin/python" -B "$release/ops/ai_reliability_cold.py" start "$release"
```

Exact required confirmations:
- `NO_PUBLIC_PROXY_OR_TUNNEL`
- `COLD_START_VERIFIED_FORWARD_RELEASE_NO_EXACT_ROLLBACK`

Then enter the database password privately through /dev/tty. It is not saved. A failed
authentication or baseline comparison ends the attempt without retry or service start.
Every application port must be free; an occupied port stops rather than starting a
duplicate or guessing another process's identity. This is a newly reviewed cold-start
configuration, not recovery of the lost previous process environments.

Startup order is exactly llama.cpp → Python → Java → frontend. Only one process is
created per service; PID/microsecond start identity, executable command, cwd, environment
and exact IPv4 loopback listener are checked. Startup health polling is bounded within
that one attempt: llama90seconds, Python60, Java90 and frontend30, with bounded HTTP
requests (up to10seconds each). No process restart or inference retry occurs. A final
in-flight HTTP check can extend the polling deadline by its bounded request timeout.

Checks: llama/Python health, Python OpenAPI chat registration, Java readinessUP, payment
healthRUNNING, OTP capabilityfalse, Merchant/Admin AI HTML routes200, unauthenticated
conversation list queries401/403, fresh V14/database fingerprints unchanged. Private
configuration compatibility is established without a live chat call; runtime
Java→Python inference/authentication E2E remains a separate future approval.

Expected success marker: `COLD_START_READY_NO_INFERENCE`.
New protected mode700 run directory /mode600 logs, diagnostic sink and sanitized evidence
are created only when the command is later approved and executed. The password exists
only in memory and the Java/psql child environments; it is absent from argv and evidence.

## Explicit degraded recovery — NOT exact rollback

Java paymesh.ai.chat.enabled=false disables private chat transport independently of
payments/refunds. Python PAYMESH_AI_CHAT_API_ENABLED=false returns503 for chat without
inference. Existing investigation configuration is preserved; disabling chat is not a
claim that every investigation route is disabled. Saved-history APIs remain authorized
and available; they are not blanket-disabled by the inference gate.

Only after reviewing the exact failed/successful cold-start evidence and separately
approving degraded recovery:

```bash
release="$HOME/.config/paymesh-demo/ai-reliability-cold-release-z6t8msoo"
"$release/python/.venv/bin/python" -B "$release/ops/ai_reliability_cold.py" degrade "$release" \
  "$HOME/.config/paymesh-demo/REVIEWED-COLD-START-RUN/evidence.json"
```

REVIEWED-COLD-START-RUN must be replaced with actual startup evidence, not preparation
or backup evidence. Required confirmations are the same private-network attestation and
`NEW_RELEASE_CHAT_DISABLED_FORWARD_RECOVERY_ONLY`; password is again private terminal
input. No inference is needed for this recovery.

It fences and gracefully replaces only recorded new Java/Python processes. Verified
existing llama/frontend processes are preserved. If llama never started or exited and
its port is empty, chat-disabled core recovery can proceed without starting llama. If
frontend never started or exited with its port empty, one reviewed copied-frontend
startup is allowed within the separately approved recovery operation. Unknown/live
unrecorded processes are never stopped. A partial child without a captured native
identity requires manual review. No automatic recovery is invoked on startup failure.

Expected success marker: `NEW_RELEASE_CHAT_DISABLED_NOT_OLD_ROLLBACK`.
If the new Java release cannot itself start, this does not guarantee core availability.
Exact previous-version rollback is unavailable. Changed data requires a new reviewed
baseline/backup; never ignore differences or restore automatically.

## Stop conditions and remaining limits

Stop for changed source/runtime/config/model hashes, occupied unexpected ports,
credential mismatch, changed backup/evidence, failed authentication, V14/data mismatch,
startup exit/timeout, non-loopback binding, launch mismatch, bad health, unexpected OTP
capability or data changes. Preserve protected evidence and any successfully started
processes for review; do not blindly restart, kill, repair, migrate or restore.

Preparation did not run cold-start commands, bind any application port, run inference,
log in, mutate conversations, create another backup, restore, change PostgreSQL or
modify financial/account data. Live startup, real AI relevance and native browser
conversation restore/rename/delete checks remain pending. Prior evidence limitations
remain open. Model health alone does not prove generation or answer quality.

## Files and offline verification

New files:
- backend/scripts/ai_reliability_cold.py
- backend/scripts/prepare_ai_reliability_cold.py
- backend/scripts/seal_ai_reliability_cold.py
- backend/scripts/test_ai_reliability_cold.py
- this report

Modified operational helper: backend/scripts/ai_reliability_forward.py (public-key
ownership/hash/non-writeable permission guard; secret mode600 checks unchanged).
Historical launchers and protected evidence were not overwritten.

15 cold-start mocked tests and17 forward-release mocked tests passed; startup order,
independent chat disabling, exact targets, token privacy, no duplicate starts, failed
startup single attempt and partial/retained-service recovery are covered. These tests
use synthetic credentials/processes and are not live startup evidence. Copied Python
and frontend import checks passed; file/model/runtime pins were independently rechecked.
Application baselines Java412/Python442/frontend1605 were not rerun.

Index changed concurrently from92cc4525... at task start to
c14632e0fa23b9f8225789dbfdff504359f62090d660055fd0ef459cddd430c9 during preparation.
The final stage/seal/verification interval was stable. No index-writing Git command was
executed; concurrent additions were preserved. Final syntax/whitespace results are
reported in the handoff. This is private-demo readiness, not production certification.
