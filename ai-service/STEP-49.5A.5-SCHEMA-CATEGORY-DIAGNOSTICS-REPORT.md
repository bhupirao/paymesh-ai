# Step49.5A.5 — protected fixed schema-category diagnostics

Implemented and offline-tested, NOT activated. The exact live Qwen failure category remains
unknown until separate Python-only reload and single-request approvals. No live inference,
HTTP request, process inspection/restart, database operation or credential change was performed.
Previous protected evidence and raw model output were not read or modified during this patch.

## Fixed codes and derivation

Only these category codes are accepted:

- REQUIRED_FIELD_MISSING
- FIELD_TYPE_MISMATCH
- EXTRA_FIELD_FORBIDDEN
- ENUM_VALUE_INVALID
- NESTED_STRUCTURE_INVALID
- ROOT_STRUCTURE_INVALID
- MULTIPLE_SCHEMA_FAILURES
- UNKNOWN_SCHEMA_FAILURE

The mapper reads only structured Pydantic `type` and `loc` labels from errors with input,
context and URL excluded. It never emits a location or field name. A required known field
with type=missing maps to REQUIRED_FIELD_MISSING; strict string/list type errors map to
FIELD_TYPE_MISMATCH; extra_forbidden maps to EXTRA_FIELD_FORBIDDEN without emitting the
untrusted extra key. A variant literal error maps to ENUM_VALUE_INVALID. Invalid items in
known string-list fields map to NESTED_STRUCTURE_INVALID. Non-object root model errors map
to ROOT_STRUCTURE_INVALID. Repeated errors in one category collapse; mixed recognized
categories map to MULTIPLE_SCHEMA_FAILURES. Missing, malformed, unrecognized or more than32
structured errors map to UNKNOWN_SCHEMA_FAILURE. Messages, rejected input and context are
not inspected or serialized. These codes describe the category, not a failed field or value.

The existing coarse reason remains SCHEMA_MISMATCH, except the existing sole-variant literal
case still uses INVALID_VARIANT. Strict JSON/duplicate-key/nonfinite/schema/intent/alias
validation and public VALIDATION_FAILED fallback are unchanged. Model, prompt, inference
endpoint, budgets/timeouts, RAG retrieval, authentication and Java behavior are unchanged.
No malformed completion is repaired or accepted.

## Protected record and correlation

Schema rejection records now have exactly correlationId, reasonCode and schemaFailureCode.
The first is the existing canonical UUIDv4; the other two must be approved constants. For
non-schema rejections the original two-field record remains unchanged; attaching a schema
code to another reason is rejected. A missing schema category defaults to the fixed UNKNOWN
code, never dynamic text. Missing/malformed correlation suppresses writing. Unknown category
values are rejected. No field names, paths, values, prompts, completions, exception strings,
credentials or financial information enter records.

Existing owner700 directory/owner600 regular-file/single-link/no-follow checks,64KiB bound,
nonblocking append lock and best-effort behavior remain. Concurrent appends are separated by
request correlation, not a claimed quiet interval. A locked/full/unavailable sink can still
omit a record; no record is not validation success.

The operational reader accepts historical two-field records without inventing a category.
For a newly matching schema-failure request, strict mode requires a valid schemaFailureCode.
Malformed/unknown fields or codes, duplicate JSON keys, duplicate request IDs, missing IDs and
contradictory successful-generation records fail closed. Valid unrelated requests cannot supply
a category for this request. Only sanitized matching category/code labels are printed; UUIDs
remain in protected verifier evidence. The new protected verifier field is
`diagnosticSchemaFailureCode`; optional terminal output is `SCHEMA_FAILURE_CODE=<fixed code>`.
No API response field or public fallback metadata was added.

## Files changed

- `app/services/chat_validation_diagnostics.py`: fixed mapper, writer allowlist and schema-only field.
- `app/services/chat_service.py`: pass the derived category at the existing validation rejection.
- `tests/test_chat_validation_diagnostics.py`: update exact schema-record assertions.
- `tests/test_chat_schema_mismatch_diagnosis.py`: preserve earlier coarse ambiguity tests while
  asserting fixed-category presence; valid responses/fallback equality remain checked.
- `tests/test_chat_schema_failure_codes.py`:45 new offline cases.
- `../backend/scripts/phase697a_diagnostic.py`: strict category validation and correlated evidence.
- `../backend/scripts/test_phase697a_diagnostic.py`:8 additional operational cases; existing
  synthetic schema-rejection workflow fixture now supplies its fixed category.
- `../backend/scripts/phase697a_python_reload.py`: future activation diagnosticSchemaVersion=3
  and refreshed hashes only for the three existing reviewed manifest entries changed here.
  Existing pinned PID/start/native identities and all refusal/confirmation guards are retained.
- `README.md`: current follow-up note.
- This report.

No other application code or protected configuration/evidence files were changed by this patch.
Earlier reports remain historical records of the coarse version2 evidence and UNKNOWN result.

## Actual verification

- Complete isolated Python suite: **351 passed**, including45 new category tests. One existing
  Starlette/HTTPX deprecation warning.
- Complete mocked operational suite: **234 passed**, including8 new category-reader cases.
- Bash/Python syntax and git diff --check passed.
- Git staged binary diff checksum matches this task's initial snapshot; no staging operations.

Tests exercise every category, unknown/malformed/oversized structured errors, malicious extra
keys and values, mixed/same-category errors, missing correlation, writer rejection of arbitrary
metadata, public route privacy, unchanged fallback and valid selections, concurrent unrelated
IDs, duplicate/malformed records, strict missing-category rejection, historical compatibility
and equality of writer/reader allowlists. HTTP/inference and operational process interactions
are mocked; Python tests block real network connections.

## Safe activation plan — separate approvals required

1. Do not execute the old pinned launcher now. The running Python instance was reloaded by the
   operator since the launcher's original reviewed PID. Re-review current native PID/start,
   owner, cwd/executable, loopback listeners, full binary environment and protected credential
   equality without printing values. Re-pin only after that source/read-only review. Do not
   disable stale-PID/source-hash checks or fabricate/modify previous activation evidence.
2. Review the existing guarded Python-only mechanism with these updated diagnostic sources.
   Preserve every launch environment value except a new sink path, matching private service
   key, RAG_LLM mode, Qwen URL/model/timeouts and --no-access-log. Keep Java, frontend, llama.cpp
   and PostgreSQL unchanged. Preserve the old diagnostic file and all previous evidence.
3. After explicit reload approval, use the reviewed mechanism:

   ```bash
   /bin/bash "$HOME/Developer/paymesh-ai/backend/scripts/reload-phase697a-python-diagnostics.sh"
   ```

   Confirm NO_PUBLIC_PROXY_OR_TUNNEL, then
   RELOAD_ONLY_PYTHON_WITH_CORRELATED_DIAGNOSTICS. It must create a new protected directory,
   exclusive mode600 sink and new evidence with diagnosticSchemaVersion3, current source hashes
   and native identities. Its metadata-only health/OpenAPI checks do not perform inference.
   Success marker remains PYTHON_CORRELATED_DIAGNOSTICS_READY; INFERENCE_NOT_PERFORMED.
4. After successful reload AND separate approval for one synthetic request:

   ```bash
   /bin/bash "$HOME/Developer/paymesh-ai/backend/scripts/verify-phase697a-ai.sh" internal-diagnostic
   ```

   Confirm VERIFY_PHASE697_SINGLE_CORRELATED_DIAGNOSTIC and enter the fresh activation evidence
   path. One invalid-token authorization check precedes exactly one authenticated synthetic
   inference request. There is no automatic retry or financial/conversation/database operation.
5. A matching schema rejection should show DIAGNOSTIC_REASON=SCHEMA_MISMATCH (or existing
   INVALID_VARIANT) and SCHEMA_FAILURE_CODE=<allowlisted category>. No matching record remains
   an evidence limitation. Do not infer a specific failed field, repair the model or loosen
   validation from category labels alone. Successful inference requires the existing validated
   RAG_LLM/SUCCEEDED result and successful final verifier evidence, not an earlier marker alone.
6. On any failure, stop and preserve sanitized evidence. Do not retry inference, force-kill,
   restart blindly, rotate credentials or truncate diagnostics. Missing records, unknown/mixed
   categories and future unsupported error labels remain honest limitations.

Python-only reload is required for this application patch. It has NOT occurred. No generation
fix has been made; the previously observed exact failed constraint cannot be reconstructed.

## Guarded reload readiness follow-up — preparation only

Read-only native verification matched Python PID49458 (microsecond start identity), Java43617,
frontend41673 and llama.cpp79855 to the successful protected activation evidence ending
`20261117T164456Z-f79jquhf/evidence.json`. Loopback/cwd/owner checks, current reviewed source
hashes, protected credential equality, required model/settings and mode600 sink checks passed.
No HTTP, reload, inference or database request was made. The running service still has the
previous diagnostic implementation.

The existing reload launcher is now re-pinned to those verified identities and that successful
prior evidence. It validates the existing correlated record instead of requiring an empty old
sink, and checks that the old sink's inode and bytes remain unchanged through the operation.
Malformed historical records still stop preflight. A new exclusive mode600 sink and separate
version3 evidence are created only on future operator invocation, after the existing private
attestation and reload confirmations. All stale identity/hash guards remain enabled.

Offline verification:17 launcher tests passed, including preservation of a valid historical
SCHEMA_MISMATCH record; complete mocked operational suite235 passed. Bash/Python syntax and
git diff --check passed. Git index matches this follow-up's initial snapshot. Python351 remains
the previous full-suite result, not rerun for this launcher-only preparation. Changed files in
this follow-up: phase697a_python_reload.py, test_phase697a_python_reload.py and this report.

The activation/inference commands and confirmation phrases above remain exact. No activation
was executed. The fresh protected evidence path will be printed after activation; never select
the old version2 evidence for the new diagnostic attempt. If identity/source/sink/health checks
fail, stop and preserve evidence without rerunning, force-killing, restoring or retrying inference.

## Outgoing-schema compatibility correction — offline verified, not activated

The isolated b4514/ec7f3ac C++ audit demonstrated that an array with minItems0/maxItems0
converts to a negative repetition bound `{0,-1}`. Grammar initialization fails; the offline
sampler then leaves synthetic candidates unfiltered. This demonstrates a converter defect,
not the exact unretained historical model output.

Only outgoing alias-array schema construction in chat_service.py is corrected. Empty arrays
now use const=[] and omit minItems/maxItems. Nonempty arrays retain their exact bounds and
alias enums. The existing Selection model, required properties, extra-field prohibition,
strict JSON/type/enum/intent/alias validation, prompt, transport format, authentication, RAG,
model, timeout/output budgets, diagnostics and public fallback remain unchanged. No completion
is repaired. The guarded reload manifest refreshes only chat_service.py's reviewed hash; its
pinned process identities and confirmation/refusal guards remain intact.

Files changed in this correction:

- app/services/chat_service.py (outgoing schema only).
- tests/test_chat_empty_array_grammar.py (27 new mocked transport/validation cases).
- ../backend/scripts/phase697a_python_reload.py (one reviewed source-hash entry only).
- This existing report (no additional milestone).

New tests exercise both BASE/EXPLAIN responses through the actual mocked HTTP adapter, all
required fields/no extra properties, unchanged Selection schema, zero/nonzero branches for
both alias arrays, preserved bounds/enums, configured transport settings and21 invalid
synthetic responses. An initial new fixture incorrectly assumed the private live alias and
30-second configured timeout were test defaults; assertions were corrected to use Settings
values. Production settings were never changed.

Complete isolated Python suite: **378 passed** (351 previous +27 new), one existing
Starlette/HTTPX warning. Complete mocked operational suite: **235 passed**. Syntax and git
diff --check passed; the staged index matches this correction's initial snapshot.

The existing isolated temporary harness was run again on the schema captured from the
corrected converse path, not a manually patched schema. Grammar initialization passed and
`{0,-1}` was absent. BASE, EXPLAIN and pretty JSON were accepted; all21 Python-invalid
fixtures were rejected. One Python-valid reordered-object fixture remains rejected by the
converter's narrower property-order grammar, unchanged by this correction. No model was
loaded and no HTTP inference occurred in the harness. Temporary audit files remain under
/tmp/paymesh-selection-grammar-8uks949u/corrected-outgoing.*; original audit inputs/results
were preserved. The server binary/libraries and tracked llama.cpp sources were not modified.

A Python-only reload is required to load the corrected request construction. It has not been
performed; live Qwen success remains unverified. Next safe action is a read-only review and
re-pin of the existing guarded Python-only reload mechanism against current process identities
and this source hash, followed by separate operator approval. Do not execute an old PID-bound
launcher or retry inference automatically. Java, frontend, PostgreSQL and llama.cpp need no
change for this correction.

## Corrected-schema reload readiness — preparation only

Read-only native checks verified Python50828, Java43617, frontend41673 and llama.cpp79855;
owner/start microseconds, cwd and loopback listeners matched successful version3 activation
evidence `otp-step17-python-correlated-diagnostics-reload-20261117T170549Z-smlgqpzt/evidence.json`.
Protected credential equality, mode600 sink and current reviewed hashes passed. The corrected
chat_service.py source hash differs from that running activation, as expected before reload.

The existing launcher is re-pinned to these actual native identities and the successful
version3 prior evidence. The corrected-source manifest was already current and verified.
Old nonempty diagnostics/evidence are retained; the future operation creates a new exclusive
sink and fresh version3 evidence. A new fully mocked round-trip test confirms the reload's
fresh evidence is accepted by internal-diagnostic and leads to one authenticated synthetic
request, after the negative authentication probe, without persisting credentials.

Actual offline results:18 launcher tests passed; complete mocked operational suite236 passed;
Bash/Python syntax and git diff --check passed. The index matches this preparation's initial
snapshot. Python378 remains the previous full-suite result, not rerun for this operational
re-pin. Files changed here: existing launcher, its test file and this report. No application
code/settings, protected file, service or database was modified during preparation.

The reload/inference commands and confirmation phrases above remain exact. After separate
approval run the repository reload wrapper (not an old /tmp script), require its success marker
and success=true fresh evidence, then obtain separate approval before internal-diagnostic.
Enter only the newly printed activation evidence.json path. If any guard or health check
fails, stop and retain evidence without retries, forced kills, automatic recovery or inference.
No reload or inference was executed during this preparation; live Qwen success remains pending.
