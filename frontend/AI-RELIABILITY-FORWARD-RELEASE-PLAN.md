# AI reliability forward-only release preparation

Status: **BLOCKED — runtime identity/configuration gate unavailable. Not activated.**
This plan is not an exact rollback plan and creates no new project phase.

## Resumed checkpoint and current blocker

The fresh coordinator, Python launcher and 17 offline operational tests were completed.
The remaining work was to verify current protected launch configuration and V14 metadata,
copy/freeze the release and produce a pinned manifest. No previous release directory
was overwritten. No new forward release directory exists.

The preparation attempt stopped at its first listener lookup, before copying files,
querying migration metadata or creating a release directory. Read-only follow-up checks
found no visible listener on18080/8000/5500/8082 and no native/ps identity for the formerly
pinned Java43617, Python53060, frontend56916 or llama.cpp79855. Why those processes are
unavailable is UNKNOWN. No service was started, stopped, restarted or replaced by this
preparation. Do not reinterpret this as an application defect or successful release.
Do not re-pin arbitrary PIDs or reuse previous kernel environment snapshots.

## Approved candidates reverified

Java: backend/target/paymesh-backend-0.0.1-SNAPSHOT.jar
SHA256: 6f6a2e27659ff338fb01163819a1a8cf2112d694e579515e7d64256eac0d96ba

Python: 40 approved app/JSON/knowledge/requirements files, canonical sorted-path/hash JSON
manifest SHA256: 9ef4ccc9e6ed7a989eea1d924f2ddcbffa93e124ce0b63cb9598dbb481f68006.

Candidate test baselines: Java412, Python442, frontend1605; not rerun for deployment
preparation. No application source, model, credentials or validation behavior changed.
The original versions remain unavailable; the accepted strategy is forward-only.

## Prepared code and gates

- backend/scripts/prepare_ai_reliability_forward.py: explicit --prepare-only entry point;
  native identity, exact working-directory/loopback listener, protected configuration
  and private-token equality checks. Verifies the approved candidate hashes and a fresh
  read-only V14 history/checksum query. Copies new app/JAR/venv and operational helpers
  into a unique protected directory. Hashes copied dependencies/external interpreter,
  preserves symlink targets, smoke-checks import provenance without credentials or
  inference, then sets mode400 files/mode500 directories and macOS user-immutable flags.
  None of this copy/freeze stage has completed yet. The existing expected identities
  intentionally remain stale and fail closed pending a new approved runtime review.
- backend/scripts/ai_reliability_python_launch.py: fresh Python launch specification
  using the copied venv/app, exact loopback Uvicorn arguments and --no-access-log.
  Preserves model/timeout/token settings, changes only reviewed launcher/import-cache,
  diagnostic-sink and chat-gate values. Rejects PYTHONPATH/PYTHONHOME overrides.
- backend/scripts/ai_reliability_forward.py: separately confirmed backup, activation
  and degraded modes; inert on import. Requires the protected immutable manifest and
  rehashes payload, runtimes and existing configuration before operations. Native
  PID/microsecond-start fences prevent PID reuse. No hard kill, restart retry, model
  call, login, financial mutation, migration or automatic restore is implemented.
- backend/scripts/test_ai_reliability_forward.py: 17 mocked operational tests passed.

The old rejected Python launcher and historical protected evidence are unchanged.
A source-pinned release launcher is not usable until the copied bundle and manifest
exist and their current process/configuration gate has passed.

## Degraded recovery feasibility and limits

Java AiChatClient has an independent paymesh.ai.chat.enabled gate. false returns safe
AI_UNAVAILABLE without contacting Python. Python PAYMESH_AI_CHAT_API_ENABLED=false
independently returns503 for chat. Payment/refund orchestration does not depend on
these flags. Existing investigation settings are preserved; disabling chat does not
promise that unrelated investigation inference is disabled. Saved-history APIs and
conversation management are not blanket-disabled by the inference gate.

The degraded mode uses the SAME verified NEW Java/Python release with both chat gates
false; it is not old-version rollback. Core application startup/payment availability
cannot be guaranteed if the new Java release itself has a startup defect. No financial
or account action is used to test recovery. No degraded switch happens automatically.
If native identity was not captured for a partially started process, or any identity,
port, configuration or database fingerprint differs, recovery stops for operator review.
An activation-evidence-based degraded attempt is intended before browser/inference
writes; changed conversation/session records require a fresh reviewed backup/baseline,
not ignoring integrity differences.

## Future backup and restoration validation — not executed

Backup requires a separately approved maintenance window, no other writers and an
interactive terminal. PostgreSQL16 tools at /Library/PostgreSQL/16/bin are required.
Target: only paymesh_demo, paymesh_demo_user,127.0.0.1:5432. Credentials remain in memory
and child-process environment, never arguments/output. All verification transactions
explicitly require READ ONLY, validated database/user/server identity and UTC/ISO
serialization. Statement and lock timeouts are bounded.

The backup mode checks V1–V14 checksums, storage reserve of three database sizes plus
1GiB, then fingerprints all eight financial tables and account/role/registry/membership/
registration/lifecycle/security/session/recovery/link/checkout/conversation tables.
It creates one protected custom-format pg_dump archive, verifies pg_restore --list and
complete extraction to /dev/null, records SHA256 and repeats the fingerprints. Archive,
evidence and logs use mode600 under a unique mode700 directory. No row content or
credential is printed. The archive contains sensitive records and requires protected
storage and retention. These checks establish readability, not a successful restore.
Per-table reads are separate repeatable-read transactions; maintenance quiescence is
required and before/after comparison does not prove absence of every possible ABA write.

A test restore needs separate approval and a NEW isolated PostgreSQL16 cluster/database
on a reviewed unused port other than5432 (for example55449), with explicit temporary
data-directory marker and loopback binding. Verify its data_directory and database name
before pg_restore. Restore only to that disposable target with --no-owner --no-acl;
compare migration history, table counts and the same canonical UTC row fingerprints,
constraints and ownership relationships. Never restore over live paymesh_demo or the
original database. No automatic destructive restore is a recovery option. Do not claim
restore validation until actual isolated execution evidence exists. External secrets,
OS/runtime configuration and old binaries are not recovered by a database archive.

## Future maintenance sequence — NOT authorized for execution

1. Operator confirms the current host/service state and approves a fresh startup/
   configuration review for unavailable services. Recover/review protected launch inputs
   without printing them. No service start is authorized by this preparation.
2. Reverify native identities, commands, cwd, app-only loopback bindings and shared token.
   Retain the accepted PostgreSQL exception: wildcard5432, TLS off and unverified HBA/PF
   remain a separate unresolved risk. No PostgreSQL change is permitted.
3. After successful re-pinning, run the preparer with --prepare-only. It must produce
   PREPARED_NOT_ACTIVATED, an immutable new release directory and release-manifest.json.
   An import smoke check is not model inference. Ensure the manifest/payload checksum
   and helper provenance are recorded before requesting deployment approval.
4. Separately approve backup and, if required, isolated restore validation. The future
   command form is <release>/python/.venv/bin/python -B
   <release>/ops/ai_reliability_forward.py backup <release>. This is a template because
   no release directory exists. Required phrases: NO_PUBLIC_PROXY_OR_TUNNEL and
   BACKUP_ONLY_PAYMESH_DEMO_NO_RESTORE. Expected: BACKUP_VERIFIED_NO_RESTORE.
5. Review the protected backup evidence, exact native pins and maintenance quiescence.
   Separately approve activation. Command form adds activate <release> <backup-evidence>.
   Required phrase: ACTIVATE_FORWARD_ONLY_AI_RELEASE_NO_OLD_ROLLBACK (plus private
   network attestation). No inference or browser mutations are included.
6. The coordinator verifies V14/fingerprints and backup SHA, stops only verified Java
   gracefully, then only verified Python. It starts one copied Python process, checks
   health/OpenAPI, then starts one Java process using the immutable JAR. Existing flags
   and environment are preserved except explicit chat gates and migration/write safety:
   Flyway disabled, SQL initialization never, Hibernate validate, conversation scheduled
   cleanup disabled, OTP and checkout simulation false. Re-enabling retention needs its
   own later review; do not silently lose that configuration change.
7. Bounded waits: graceful stop30seconds/service, listener startup60seconds/service,
   metadata HTTP10seconds/request. Single health requests; no automatic service restart.
   Validate Java readinessUP, payment healthRUNNING and OTP capabilityfalse; verify
   token/config compatibility without invoking chat. Recheck database fingerprints and
   preserved frontend/llama/PostgreSQL OS identities. Expected successful marker:
   FORWARD_SERVICES_READY_INFERENCE_NOT_TESTED. Health is not inference proof.
8. On failure, preserve protected logs/evidence and stop. No restart, inference retry,
   cleanup SQL or restore. If the explicit degraded procedure is safe after reviewing
   recorded partial identities, separately approve degrade <release> <activation-evidence>
   with USE_NEW_RELEASE_WITH_CHAT_DISABLED_NO_ROLLBACK. Expected successful marker:
   NEW_RELEASE_CHAT_DISABLED_NOT_A_ROLLBACK. Do not invoke this on unrelated evidence.
9. Only after successful activation and separate live-test approval: browser hard refresh,
   controlled synthetic Merchant/Admin checks and designated conversation cleanup.
   Frontend handler, llama.cpp and PostgreSQL are not restarted by the prepared plan.

## Stop conditions / confidentiality

Stop before termination for missing/wrong identity, non-loopback application listener,
source/runtime/config pin mismatch, missing/mismatched private token, changed V14 history,
unverified archive or database difference. Stop after startup on process exit, timeout,
wrong launch state, failed health, enabled OTP, integrity difference or preserved-service
identity change. A failed startup may leave Java or Python unavailable; forward-only
recovery does not guarantee restoration of previous availability.

Future activation creates mode600 protected-launch-state.json containing exact launch
environments for partial-start recovery. This file DOES contain credentials and must
never be printed, uploaded, committed or included in sanitized reports. Only its path
and checksum appear in sanitized evidence. Logs are mode600 and must be reviewed
privately. Existing secret files are preserved, not copied into public artifacts.

## Verification and Git state

17 operational mocked tests passed after necessary guard refinements. Python syntax
checks passed. Full application suites were not needlessly rerun; their stated totals
remain prior baselines. No backup, restore, inference, login, conversation mutation,
service change or database write occurred. The failed preparer stopped before its V14
metadata query and copy/freeze stage. Git diff whitespace checks are recorded in handoff.

Index at resumed checkpoint and final read-only diagnosis:
f3bca148e9eeb2f12548522e8299ae002ee0b1ed946e64d3b7fa1f1b0cc4be8a.
Earlier external staging changed the prior3b9c20... checksum; no staging commands were
executed and no attempt was made to restore or alter external additions.
