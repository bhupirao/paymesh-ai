# Step49.5A.5 — schema mismatch diagnosis

Outcome: exact failed field/constraint UNKNOWN. No generation or validation correction is
justified by retained evidence. No application code, model settings, credentials or operational
configuration changed. No live inference, HTTP request, restart, database or financial action.

## Authentic evidence

Reviewed protected files (not modified):

- `~/.config/paymesh-demo/otp-step17-phase697a-internal-diagnostic-20261117T164605Z-cl13r0gl/evidence.json`
- `~/.config/paymesh-demo/otp-step17-python-correlated-diagnostics-reload-20261117T164456Z-f79jquhf/evidence.json`
- The protected reason-only JSONL identified by the activation evidence, through the existing
  safe reader. No raw model completion was read, printed or persisted.

Activation success=true, diagnostic schema version2, source hashes match the three current
reviewed application files. Verification internalAuthenticationVerified=true, analysisMode
RAG_ASSISTED, generationStatus VALIDATION_FAILED, actualInferenceProven=false, knowledgeCount1,
moneyFactCount0. Diagnostic attribution MATCHED_REQUEST; exactly matching reason SCHEMA_MISMATCH.
The diagnostic row contains only correlationId and reasonCode. It cannot identify a field/type.
No raw correlation UUID or protected content is reproduced here.

## Source findings

Selection requires exactly intent:string, variant:BASE|EXPLAIN, evidence:list[string],
knowledge:list[string]; strict=True and extra=forbid. JSON rejects duplicates/nonfinite values.
A sole variant literal error maps to INVALID_VARIANT; any other Pydantic ValidationError
(including a variant error combined with a missing field) maps to SCHEMA_MISMATCH. Exact intent
and alias-set checks run only after schema validation succeeds. Thus the observed reason does
not distinguish missing fields, types, extra fields, non-object roots, nested values or combined
errors. Authentication/retrieval passed for this request; successful validated RAG_LLM generation
was not certified. SCHEMA_MISMATCH is a validator outcome, not evidence of a transport timeout.

Prompt instructions and generated JSON Schema agree on these four fields. The adapter submits
response_format.type=json_object with response_format.schema. The available local llama.cpp
`examples/server/utils.hpp` lines595–603 explicitly maps this form to json_schema, including an
alternative json_schema form. No configuration incompatibility has been demonstrated. This
source inspection does not certify which code the running binary executes or whether the model
honored every schema constraint. Changing the format, prompt, alias, timeout, schema or parsing
rules on this evidence would be speculative.

## Offline reproduction

New tests use synthetic fixtures only. Sixteen different invalid selections produce the same
SCHEMA_MISMATCH record: four missing fields, primitive/list/item type errors, nested objects,
extra fields, non-object roots and combined literal/missing errors. Both approved variants
continue to pass, generated schema/adapter formatting remains strict, and fallback responses
remain identical with diagnostics enabled/disabled. These fixtures reproduce the observed
*classification*, not the unretained actual model completion or its exact root cause.

Files created: this note and `tests/test_chat_schema_mismatch_diagnosis.py`. No production
source changes. Existing protected evidence, source hashes and activation scripts remain intact.

## Proposed next safe diagnostic enhancement — NOT implemented

Keep SCHEMA_MISMATCH as the coarse reason. Add an optional bounded `schemaFailureCodes` list
only to protected correlated records, from an explicit fixed allowlist, such as MISSING_INTENT,
MISSING_VARIANT, MISSING_EVIDENCE, MISSING_KNOWLEDGE, TYPE_INTENT, TYPE_EVIDENCE, TYPE_KNOWLEDGE,
TYPE_EVIDENCE_ITEM, TYPE_KNOWLEDGE_ITEM, INVALID_VARIANT, ROOT_NOT_OBJECT, UNEXPECTED_FIELD,
OTHER_SCHEMA_CONSTRAINT. Never copy generated field names, field paths, input, messages,
exception text, values or completions. Deduplicate/cap the fixed list; safely collapse unknown
constraints to OTHER_SCHEMA_CONSTRAINT. Extract only allowlisted labels from Pydantic errors
with input/context/url excluded. No free-form diagnostic field may be emitted.

Update the protected reader to validate the additional field and match the exact request UUID;
reject malformed/duplicate/mismatched records. Preserve mode600/no-follow/size/append controls,
existing public responses/fallbacks and output validation. Add tests for every fixed code,
malicious extra-field names, multiple errors, public privacy, concurrency and missing evidence.
This requires separate implementation approval; it is not a model-generation fix.

After that enhancement is approved, implemented and offline-tested, separately review a
Python-only reload with fresh pinned source hashes/process identities, preserving all current
settings and evidence. Do not reuse the old pinned reload script: its PID and source gates
are tied to the earlier service instance. Then separately approve one correlated synthetic
request. Do not rerun inference merely to collect another coarse SCHEMA_MISMATCH.

No Python reload is required for the present test/documentation-only additions. A later
application diagnostic enhancement would require a Python-only reload. Exact model-output
root cause and any resulting generation correction remain pending new attributable evidence.

## Actual verification results

- Complete isolated Python suite: **306 passed**, including20 new synthetic diagnosis tests.
  One existing Starlette/HTTPX deprecation warning.
- Complete mocked operational suite: **226 passed**.
- New test syntax and git diff --check: passed.
- Initial collection failed because the new test imported a fixture module without its
  `tests.` package prefix. That test-only import was corrected; the final complete suite
  passed. No application behavior was changed to resolve it.
- Git index checksum matches this task's initial snapshot. No staging operation occurred.
- Neither suite made live AI/service/database requests; inference/network behavior is mocked.
