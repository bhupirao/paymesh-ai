# Step49.5A.1 — Safe Qwen selection-validation diagnostics

Implemented and offline-tested; **not activated**. No service restart, live inference, database operation, model/timeout/credential change, Java/frontend behavior change or Git staging was performed. The previously observed failure remains RAG_ASSISTED/VALIDATION_FAILED; its exact historical cause is still unknown. This patch cannot reconstruct discarded model output.

## Scope and public behavior

The existing LocalHTTPProvider and inference budgets are unchanged. After the provider returns a bounded completion string, chat selection parsing still rejects duplicate/non-finite/invalid JSON, strict Pydantic schema violations, invalid variants, intent mismatches and incorrect/duplicate/missing aliases. The Selection schema, prompt, approved answer variants, exact money logic, citations and Java trust manifest are unchanged.

Fixed diagnostics describe this validation boundary, not a new acceptance rule. Public ChatRequest/ChatResponse and Java/frontend contracts are **unchanged**. Expected selection rejections still return the existing grounded RAG_ASSISTED/VALIDATION_FAILED fallback. Existing non-string/overlong completion handling remains INVALID_RESPONSE. Unexpected internal validation exceptions retain the existing UNAVAILABLE fallback. No detailed diagnostic field, reason, sink path or exception is added to responses, ordinary application logs or terminal output. Successful structured responses remain byte-for-field equivalent in tests.

## Fixed reason mapping

| Protected reasonCode | Condition | Existing public behavior |
|---|---|---|
| INVALID_JSON | Inner completion text is invalid JSON or contains non-finite JSON values | VALIDATION_FAILED |
| DUPLICATE_JSON_KEY | Duplicate key at any JSON object depth | VALIDATION_FAILED |
| SCHEMA_MISMATCH | Wrong root/type, missing/extra fields, strict field/type violations, or multiple schema errors | VALIDATION_FAILED |
| INVALID_VARIANT | Sole Pydantic error is the variant literal constraint (not BASE/EXPLAIN) | VALIDATION_FAILED |
| INTENT_MISMATCH | Schema-valid intent differs from deterministic recognized intent | VALIDATION_FAILED |
| EVIDENCE_ALIAS_MISMATCH | Evidence alias length/set differs, including missing/duplicate/invented aliases | VALIDATION_FAILED |
| KNOWLEDGE_ALIAS_MISMATCH | Knowledge alias length/set differs, including missing/duplicate/invented aliases | VALIDATION_FAILED |
| OTHER_VALIDATION_FAILURE | Unexpected parser/schema exception, or non-string/overlong completion guard | UNAVAILABLE for unexpected exceptions; existing INVALID_RESPONSE for the guard |

Precedence: JSON parse/duplicate rejection, strict schema, intent, evidence aliases, knowledge aliases. Diagnostics record the first rejected condition. Multiple schema errors take SCHEMA_MISMATCH rather than claiming that only the variant was wrong. Outer HTTP envelope/finish-reason/transport failures keep their existing GenerationFailure statuses; this patch does not recategorize them as inner selection failures.

No exception text, rejected field name/value, question, completion, financial fact, correlation ID, user ID, alias or credential is written. The only record shape is:

```json
{"reasonCode":"INVALID_JSON"}
```

## Protected opt-in sink

New internal setting: `PAYMESH_AI_CHAT_VALIDATION_DIAGNOSTICS_FILE` / `Settings.chat_validation_diagnostics_file`. Default None: disabled, no diagnostic filesystem access or record. The setting is excluded from Settings serialization/repr and therefore also from provider-side bounded settings clones. This prevents sink availability from altering generation behavior during configuration revalidation.

The file must already exist, be a current-owner regular file mode600, have one hard link, and be named exactly `chat-validation-diagnostics.jsonl`. It must be within `~/.config/paymesh-demo/`; that root and every descendant directory must be current-owner mode700. Relative/outside paths, traversal, symlinks (file or directory), wrong ownership/mode/name and missing files are refused. Directory-relative O_NOFOLLOW descriptors prevent symlink traversal at append time. No file is created/truncated/rotated by application code.

Only allowlisted constant codes can be appended. Each record uses a single O_APPEND write with a nonblocking exclusive lock; the log is bounded to64KiB. Startup rejects an invalid explicitly configured sink. Request-time permission/availability/lock/size failures suppress recording without changing the original fallback or printing exception details. No record therefore does not prove validation success: inspect sink availability and capacity privately. Only fixed codes are retained; there is no request-level attribution. For the later approved diagnostic, use a fresh empty sink and a single synthetic request without concurrent chat traffic.

## Changed files

- Modified `app/services/chat_service.py`: strict validation factored into a reason-aware helper; public fallback preserved.
- Modified `app/config.py`: optional protected sink setting/startup validation, excluded from serialization/repr.
- Created `app/services/chat_validation_diagnostics.py`: fixed-code, protected, bounded JSONL appender.
- Created `tests/test_chat_validation_diagnostics.py`:39 isolated synthetic cases.
- Updated `README.md` with this opt-in operational note.
- Created this report.

No LocalHTTPProvider, Java, frontend, model, timeout, service token, dependency, migration or active configuration file was changed by this patch.

## Actual verification

- Full Python suite: **276 passed**, including39 new diagnostic tests. One existing Starlette/HTTPX deprecation warning.
- Full offline operational regression suite: **151 passed**. Contract literal and Python→Java exported fixture drift checks remain green.
- Python syntax and git diff --check: passed.
- Java412/frontend1558 remain previous baselines, not rerun; no corresponding source/contract change.

Tests cover all eight codes; malformed/non-finite/duplicate JSON; missing/extra/wrong-type fields; invalid intent/variant; missing/duplicate/incorrect aliases; success equality; exact public fallback equality; HTTP response privacy; disabled diagnostics; unknown-code refusal; owner/mode/symlink/hardlink/path protections; full/locked/unavailable sink behavior; runtime permission changes; and unchanged existing investigation/chat regressions. Network is mocked/denied. No live model or service endpoint was called.

An initial new test found that sink permission changes could affect provider Settings revalidation. Excluding the operational sink from Settings serialization fixed that issue; the complete final suite passed. This exclusion does not change existing public response models or generation settings.

## Safe activation — separate approval required

**Python-only reload is required** to load this patch; Java, frontend and llama.cpp need no change. Do not run an old PID-bound activation script or change inference settings/credentials. Before a future approved reload, verify current Python PID/start/cwd/loopback binding and preserve all reviewed existing Python environment values, matching shared key, RAG_LLM mode and --no-access-log.

Future operator preparation, **not executed here**:

```bash
set +x
umask 077
# First verify ~/.config/paymesh-demo remains current-owner mode700 and not a symlink.
diag_dir=$(mktemp -d "$HOME/.config/paymesh-demo/chat-validation-XXXXXXXX")
chmod 700 "$diag_dir"
( set -C; : > "$diag_dir/chat-validation-diagnostics.jsonl" )
chmod 600 "$diag_dir/chat-validation-diagnostics.jsonl"
export PAYMESH_AI_CHAT_VALIDATION_DIAGNOSTICS_FILE="$diag_dir/chat-validation-diagnostics.jsonl"
```

The separately reviewed Python-only launcher must explicitly pass this variable in the **child environment**, not merely set it in an unrelated shell. The earlier Step493 launcher filters its Python environment and must not be blindly reused; it also targets old identities and restarts Java unnecessarily. Preserve existing model, timeout, key and all generation/transport settings. Check Python health and OpenAPI metadata after the approved reload; these are not inference proof.

Only after an additional explicit live-test approval, run one existing synthetic internal probe using the already reviewed private token-loading procedure. A fallback remains a fallback; do not relax validation or repeat automatically. Read only validated reason codes from the protected sink, never dump model output. There is no reason to perform Merchant/Admin login, load real financial evidence, create conversations or touch financial records for this diagnosis.

## Recovery and limitations

If startup rejects the sink, stop and review file path/owner/mode rather than weakening protection. Running services/configuration have not been changed by this implementation. If a future reload fails, preserve protected logs/evidence; do not restart blindly. To disable diagnostics during a separately approved recovery reload, remove/unset only `PAYMESH_AI_CHAT_VALIDATION_DIAGNOSTICS_FILE`, retaining the same current application, credentials and inference settings. No Java/database rollback is needed for this Python-only diagnostic patch.

A full/busy/unavailable sink may omit a reason; it never turns a failure into success. The log has no correlation IDs/timestamps or message contents; attribution requires a controlled single-request window. Protected backups or operator copies may retain reason-only records. This does not establish the historical failure category until a newly approved synthetic attempt is observed. No live activation or inference is claimed.
