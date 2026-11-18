# Step49.5A.4A — correlated Qwen diagnostics and native process verification

Status: IMPLEMENTED / OFFLINE TESTED. Not activated. No live process inspection, inference,
HTTP request, service restart, database access or credential/configuration change was performed
for this correction. Prior protected activation evidence and diagnostic files are unchanged.

## Correction and privacy boundary

`converse` passes the already validated internal request correlation to each diagnostic rejection
site. Only canonical lowercase UUIDv4 (36 characters) is accepted for recording. The appender
now writes exactly `correlationId` and an existing allowlisted `reasonCode` to its existing
protected mode600 file. No question, completion, exception text, token or financial data is
recorded. File/directory ownership, no-follow descriptor traversal, single-hardlink requirement,
nonblocking append lock,64KiB bound and best-effort behavior remain intact. A missing/invalid
correlation suppresses recording; it never changes generation or public fallback behavior.

No API schema fields were added. The existing internal ChatRequest/ChatResponse correlationId
contract remains unchanged; diagnostic records/reasons are not returned through that contract
or Java public responses. The UUID is not passed to the model. JSON/schema/intent/variant/alias
validation, approved answer selection, RAG, credentials, model, timeout and financial facts
are unchanged. Existing success/fallback response equality tests still pass.

The new `internal-diagnostic` operator mode generates a cryptographically random UUIDv4. It
uses the existing verifier's knowledge-only synthetic question/history, first checks that an
invalid service token returns401, then sends exactly one authenticated request. No automatic
retry, login, Java chat call, conversation persistence, financial/account operation or database
connection exists in this path. Browser/Java credentials are never forwarded.

Protected verifier evidence retains the UUID for matching. Terminal output includes only fixed
status messages, evidence paths and `DIAGNOSTIC_REASON=<allowlisted code|NO_MATCHING_RECORD>`.
All diagnostic rows must have exactly the two permitted fields. Duplicate JSON keys, duplicate
correlations (including unrelated duplicates), missing/invalid IDs, arbitrary codes/fields and
malformed records fail closed. Valid unrelated records are ignored for attribution. A matching
record must be unique. A successful generation conflicting with a matching validation-failure record is rejected.
The sink inode must remain the same and earlier bytes must remain an
unchanged prefix. A preexisting match is rejected. Neither an empty sink nor NO_MATCHING_RECORD
proves successful validation; only the authenticated, correlation-checked structured response
can establish RAG_LLM/SUCCEEDED. A VALIDATION_FAILED result without a matching record remains
unattributed. A successful generation marker does not override later diagnostic integrity errors;
check the exit status and protected evidence success field as well.

## Native process verification

`phase697a_process.py` uses read-only macOS `sysctl(CTL_KERN,KERN_PROCARGS2,pid)` binary launch
data: bounded native argc, executable plus NUL padding, argc NUL-terminated arguments, then
NUL-terminated environment entries. Values containing spaces, tabs, newlines, Unicode, empty
strings or equals signs are preserved. No textual `ps eww` environment output is parsed.
Malformed/truncated/oversized data, invalid UTF-8, duplicate/malformed keys and inaccessible or
unsupported interfaces stop the procedure without inference. No textual fallback exists.

`proc_pidinfo(PROC_PIDTBSDINFO)` validates the PID, operator UID and start seconds/microseconds.
Identity is compared before/after the binary snapshot, before inference and after the attempt.
Fresh protected activation evidence must bind the AI/Java/llama identities at microsecond
precision. Existing listener/cwd/loopback checks remain in use (textual ps is used only for
nonsecret executable/start metadata, not environment parsing). Python argv must retain exact
loopback uvicorn arguments and --no-access-log. Java's protected configuration locations and
credential equality are checked without printing values. OTP and checkout controls must be
false, AI chat true. Unsupported property encodings/Java environment overrides fail closed.

This is kernel-exposed launch state, not proof of arbitrary later in-process getenv/config
changes. The authenticated probe tests the actual Python credential. No claim is made that it
executes Java's HTTP client. Native system-call behavior/permissions on the live machine have
not been exercised by this patch: isolated tests mock the native boundary. Failure on the
operator machine must stop before inference, never trigger a textual parsing fallback.

## Changed files (this correction only)

- `ai-service/app/services/chat_validation_diagnostics.py`: validate/record UUIDv4 correlation.
- `ai-service/app/services/chat_service.py`: explicit correlation propagation, unchanged validation.
- `ai-service/tests/test_chat_validation_diagnostics.py`: update existing reason-record assertions;
  ten additional invalid-ID/concurrent/propagation cases.
- `backend/scripts/phase697a_process.py`: native binary process snapshot and identity fences.
- `backend/scripts/phase697a_diagnostic.py`: protected correlation matching, token/config checks,
  single-attempt orchestration and evidence gates.
- `backend/scripts/phase697a_ai_verify.py`: optional internal request ID/key injection; new mode.
- `backend/scripts/verify-phase697a-ai.sh`: exact additional mode allowlist.
- `backend/scripts/test_phase697a_diagnostic.py`:44 new offline operational tests.
- `ai-service/README.md`: follow-up note.
- This report.

`app/config.py` and other earlier working-tree changes were not edited for this correction.
Git diff against HEAD includes prior work; it must not be interpreted as this patch's inventory.

## Actual automated verification

- Complete Python suite: **286 passed**, including49 diagnostic tests (39 existing +10 new).
  One existing Starlette/HTTPX deprecation warning.
- Complete operational mocked suite: **195 passed** (151 previous +44 new).
- Bash/Python syntax and git diff --check: passed.
- Java/frontend not rerun; no corresponding source/contracts were changed.
- Existing staged binary diff checksum preserved. No Git staging/commit/reset/clean operation.

New cases cover whitespace/Unicode/equals/empty environment values, malformed/duplicate keys,
truncated binary layouts, native-call errors and ABI size, microsecond PID reuse, missing
credentials, configuration protection, missing/duplicate/malformed/unrelated correlations,
protected sink metadata, no-record semantics, exact single authenticated attempt, failures
without retries, incorrect response correlation, missing activation baseline and mocked whole
workflow behavior. All HTTP/process/kernel interactions in workflow tests are mocked.

## Separate proposed activation sequence — NOT EXECUTED / approval required

1. Review a new Python-only launcher against the current PID/start/cwd/executable/listener and
   this correction. Do not reuse the old whitespace-splitting restart helper or its frozen
   source hashes. The old Step49.5A.3 evidence is intentionally insufficient for the new mode.
2. Use native binary snapshots for read-only environment verification. If native access or
   layout validation fails, stop before any service change. Preserve the full reviewed Python
   launch environment, service key, RAG_LLM/Qwen settings/timeouts and --no-access-log.
3. Only after separate explicit restart approval, create a new owner700 protected run directory
   and an exclusive new mode600 `chat-validation-diagnostics.jsonl`. Do not truncate, overwrite,
   convert or delete any previous diagnostics/evidence. Reload only verified Python with the
   existing environment plus the new sink path; do not change credentials or restart Java,
   frontend, llama.cpp or PostgreSQL. Health/OpenAPI checks must not invoke inference.
4. The new protected activation evidence must retain the existing `beforeServices`,
   `newPythonIdentity`, `diagnosticFile`, `success=true`, `diagnosticsEnabled=true` fields and
   `sourceHashes` for exactly app/config.py, app/services/chat_service.py and
   app/services/chat_validation_diagnostics.py. It must additionally record
   `nativeProcessIdentities` for `ai`, `java`, `llm`, each as
   `[pid, start_seconds, start_microseconds, operator_uid]`, obtained through the reviewed
   native helper after reload/health validation. Never fabricate these fields or alter old evidence.
5. Separately approve ONE synthetic inference attempt. Future operator command:

   ```bash
   /bin/bash "$HOME/Developer/paymesh-ai/backend/scripts/verify-phase697a-ai.sh" internal-diagnostic
   ```

   Confirmation: `VERIFY_PHASE697_SINGLE_CORRELATED_DIAGNOSTIC`.
   Then enter the new protected diagnostic activation evidence.json path. No token input,
   token export or token argument is required: the native Python snapshot and active protected
   Java fragments supply/verify the existing key in memory.
6. The verifier creates a fresh protected `otp-step17-phase697a-internal-diagnostic-<UTC>-<suffix>`
   directory containing sanitized evidence.json. Expected generation-success marker:
   `PRIVATE_AUTH_AND_RAG_LLM_SUCCEEDED; no raw prompt/answer retained`. A validation fallback
   retains its existing safe failure message plus `DIAGNOSTIC_REASON=<fixed code>` only if a
   unique matching record exists. `NO_MATCHING_RECORD` means attribution is unavailable.
   A zero exit status and success=true are required for overall success; never infer success
   from a single earlier terminal line.
7. On failure, stop. Do not automatically repeat inference, restart services, edit records,
   rotate credentials or truncate diagnostics. Preserve the failed evidence and request identity
   privately for review. An unavailable/full/busy sink can omit a record without changing public
   fallback; a process/metadata mismatch must fail closed. Removal of the diagnostic setting
   requires a separately reviewed Python-only reload preserving credentials and all other settings.

## Remaining limitations

A Python-only reload and new protected native-identity evidence are required; neither was
performed. The old /tmp command and old PID-bound restart scripts must not be reused. Native
syscalls are unit-tested through mocks only. Protected local evidence is not tamper-proof
against the same OS account or a privileged attacker. UUID collisions are negligible, not a
formal exactly-once guarantee. The nonblocking writer can omit records; no matching record
must remain UNKNOWN. Model inference and the exact live validation cause remain unverified.
No previous phase's live verification gap or historical evidence limitation is closed.
