# Customer wording — prepared activation

Status: **PREPARATION PASS; NOT ACTIVATED** (2026-11-18).

The change inventory is in [the wording report](AI-CHAT-CUSTOMER-WORDING-REPORT.md). No application source was changed during release preparation. The running frozen release and protected configuration remain untouched.

## Prepared payload

New protected, owner-read-only/user-immutable bundle:

`~/.config/paymesh-demo/customer-wording-release-d0qsjrww`

- Manifest SHA-256: `304a61db48ff2b1d75ac57a17235c2236c4fa49605e67b100b6b7e6de2422c40`
- Java JAR SHA-256: `6c558771caacccd793ca27df9e638dc5ee98d13ea14adf407341bb44722b572a`
- Python 41-file source manifest SHA-256: `deea01be28081a8c513ce45cb8ccc0b311fc9bbfe40e6732a9f4a767ec41d12f`
- 1,760 payload files pinned, including copied dependencies, frontend assets and launcher helpers. Existing external runtime/configuration pins are retained.
- Java differs from the current JAR only in `ChatRules.class`, `CustomerWording.class` and `ai-chat/contract.json`.
- Python adds `app/services/customer_wording.py` and updates `app/services/chat_service.py`. Existing strict output validation remains unchanged.
- Five production frontend modules differ: `chat/render.js`, `chat/presentation.js`, `merchant-ai/model.js`, `payment-ai/model.js`, `payment-ai/view.js` (under `frontend/assets/js`). The handler and its proxy configuration are unchanged.

The independently rehashed current immutable release, `ai-reliability-cold-release-z6t8msoo`, is retained for a separately approved application recovery. This recovers the currently running AI reliability version, not the older unavailable pre-reliability deployment. No previous artifact or evidence was overwritten.

## Verification performed

- Java: **8 targeted contract/transport tests passed**, followed by successful Maven packaging. Only synthetic mock HTTP listeners were used.
- Python: **12 customer-wording tests passed** during preparation. The prior complete suite result is **454 passed**, not a new full-suite run.
- Frozen Python runtime reproduces **all 83 cross-language contract fixtures**. The packaged Java manifest exactly matches the reviewed generated manifest.
- All 20 offline mocked JavaScript suites: **1,563 assertions passed**. Prior proxy/security result: **57 passed**, not rerun during this preparation.
- **19 mocked launcher checks passed**, covering preserved settings, exact targets/order, database drift, changed pins, failed-child no-retry behavior and recovery guards.
- Python syntax, release file rehashes and `git diff --check` passed.
- The Git index stayed at `d9643fc29c04f1a169f2c04937c6563953457484a5164a9ef4971509ced4fcef` during bundle preparation, then changed concurrently to `f6edf9dd92809280bef5a5db78e0f5c8e011872e2686dee4640d660598ac78ec` by the final check. No index-writing operation was performed; external staging was preserved.

Read-only native inspection verified the running identities (PID, microsecond start time and UID), commands, environments, working directories and exact IPv4 loopback listeners:

| Service | PID | Port |
| --- | ---: | ---: |
| llama.cpp | 3753 | 8082 |
| Python | 4391 | 8000 |
| Java | 4970 | 18080 |
| Frontend | 5036 | 5500 |

Health metadata, Python chat route registration, Merchant/Admin HTML routes and unauthenticated conversation-list denial passed. Credential values were compared privately, not displayed or copied into the manifest. No chat, login, refresh or inference request was made.

Two fresh read-only repeatable-read database snapshots matched and ended with ROLLBACK. V1–V14 checksums/success match. **Current** counts are users/merchants/memberships/registrations/payments/refunds **6|4|4|2|7|4**, with conversations/creation journals/requests/messages **6|7|11|22**. These differ from the older cold-start backup baseline; preparation did not create those records. Activation preserves this fresh baseline, including all existing financial/account/conversation fingerprints, rather than assuming old counts still apply.

The existing protected backup checksum and archive listing passed. It predates the current additional records; it is not a complete current-data recovery point. No new backup or restore was performed or added to the activation command. Application recovery does not restore the database.

## Exact activation command — requires separate operator approval

Close all PayMesh tabs and API clients first. Keep them closed until preservation checks finish. Do not execute this command merely because preparation passed.

```bash
release="$HOME/.config/paymesh-demo/customer-wording-release-d0qsjrww"
"$release/python/.venv/bin/python" -B "$release/ops/customer_wording_activate.py" activate "$release"
```

Required terminal confirmations:

1. `PAYMESH_CLIENTS_CLOSED_NO_PUBLIC_PROXY`
2. `ACTIVATE_MATCHED_CUSTOMER_WORDING_ONCE`

The operator-approved launcher:

1. Rehashes the new and recovery payloads, external runtimes and protected configuration; fences current native identities, commands, environments, directories and listeners; verifies private authentication compatibility and health.
2. Requires the exact fresh V14/database fingerprints to remain unchanged. Existing database credentials are read privately from the verified current Java environment, never printed, persisted or passed in argv.
3. Creates an exclusive one-attempt marker and fresh protected evidence/log directory. Stops only verified frontend → Java → Python, gracefully, with 30-second stop deadlines and no force kill.
4. Preserves llama.cpp and PostgreSQL; starts Python → Java → frontend once each. There is no old Java client paired with new Python during this sequence.
5. Uses the following exact command construction, with all current environment/configuration values preserved privately:
   - Python: `RELEASE/python/.venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --no-access-log`, cwd `RELEASE/python`.
   - Java: the verified current Java executable, `-jar RELEASE/java/paymesh.jar`, followed by the exact existing verified Java flags, cwd unchanged. `--spring.flyway.enabled=false`, Hibernate validate, SQL initialization never, OTP/checkout controls disabled, scheduling/cleanup disabled and `PAYMESH_DEMO_GATEWAY_TIMEOUT_ENABLED=false` remain enforced. No credentials are added to argv.
   - Frontend: `RELEASE/python/.venv/bin/python -B RELEASE/frontend/dev_server.py`, cwd `RELEASE/frontend`, retaining the approved loopback-only handler configuration.
6. Creates a fresh mode-600 diagnostic sink; preserves previous diagnostic files. Bounds Python health startup to 60 seconds, Java to 90, frontend to 30. A final bounded metadata request may extend the deadline by at most its timeout. Native metadata capture may be polled for three seconds during exec; this does not retry a service start.
7. Checks process identity/environment, loopback binding, readiness, payment health, disabled OTP, Python endpoint registration, HTML routes, unauthenticated boundaries, retained services and identical database fingerprints. No inference or authorized conversation request occurs.

Expected success marker: **`CUSTOMER_WORDING_ACTIVE_NO_INFERENCE`**.

Runtime evidence is created separately at:
`~/.config/paymesh-demo/customer-wording-activation-*/evidence.json`
with mode-600 logs and diagnostics in the same protected mode-700 directory. The exact path is printed without secrets. The current launcher's implementation is frozen and hash-pinned inside the new bundle.

## Failure and recovery

On any failure: **stop**, preserve evidence and successfully started services, and inspect protected logs locally. Do not rerun activation, delete attempt markers, paste raw logs, restore data or improvise service replacements. No automatic recovery is performed.

Only after reviewing the actual failed activation evidence and separately approving recovery:

```bash
release="$HOME/.config/paymesh-demo/customer-wording-release-d0qsjrww"
"$release/python/.venv/bin/python" -B "$release/ops/customer_wording_activate.py" recover "$release" \
  "$HOME/.config/paymesh-demo/ACTUAL-CUSTOMER-WORDING-ACTIVATION/evidence.json"
```

Replace the evidence path with the actual protected run. Required confirmation: `RESTORE_PRE_WORDING_RELEASE_ONCE`, then PostgreSQL password through private `/dev/tty` input (not saved). Recovery rechecks the unchanged database, old/new artifacts and retained services; fences only identified rollout children, retains still-running original services and starts missing original services once from the old immutable release. Private configuration reconstructability was compared against the current native environments during preparation. No inference, migration or database restore occurs.

An unrecorded/ambiguous child, changed database, changed configuration or failed old-release startup requires manual review; this is not an unconditional availability guarantee. Expected recovery marker: **`PRE_WORDING_RELEASE_RESTORED_NO_INFERENCE`**.

## Remaining verification

No services were restarted during preparation. PostgreSQL network exposure remains the previously accepted private-demo exception. Real browser wording, mobile presentation, legacy saved-answer display and Admin Technical details still need supervised verification after activation. A browser hard refresh is needed after the frontend replacement. Live inference and conversation mutations are separate approvals; health is not evidence of answer quality. All earlier phase limitations remain open.
