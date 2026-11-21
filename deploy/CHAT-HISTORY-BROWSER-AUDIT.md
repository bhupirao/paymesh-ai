# Chat and saved-history browser audit

## Observed failure

Candidate Chromium run [44875247889](https://github.com/bhupirao/paymesh-ai/actions/runs/44875247889)
used `b0d906e99626ae22aaabe305cb5282559105fcf1`. Both accessibility tests passed.
The journey passed its first eight stages, including actual Qwen investigation,
refunds and public checkout. The chat/history stage failed after 18,446 ms.

The exact failing statement was `getByLabel('Conversation title', {exact:true}).fill(...)`
at journey.spec.js:242. It was not a chat-response wait. The preceding strict
modelSuccess check accepted the observed message POST response, requiring RAG_LLM,
SUCCEEDED and nonempty knowledge references. The assistant answer was visibly rendered
and its nonempty text assertion passed before title filling. The sanitized artifact's
last HTTP 200 alone does not identify an endpoint; the successful responseFor/body
execution identifies the awaited conversation-message POST by source control flow.
No raw response was retrieved or retained. Admin chat and later history checks were
not reached; the overall reporter correctly did not mark complete AI coverage verified.

## Confirmed application defect

In frontend/assets/js/chat/presentation.js, store.onChange renders history while
`canManage` depends on the chat model's `state.busy`. In conversations/store.js,
transport emits the saved completed turn *before* returning to the chat model.
The Merchant/Admin models clear busy in their finally blocks and emit their own
render afterward. That render updates the transcript/composer but never renders
history. conversations/view.js therefore leaves the title, rename and delete
controls disabled from the previous busy render.

An offline regression executes the actual history-view implementation: a selected
conversation rendered while the model is busy disables the title; clearing the
model busy flag does not update that DOM property; rendering history again enables
it. Source checks document the missing presentation update. The historical live
artifact does not directly record the title's disabled property, so that live
property remains unobserved; the defect itself is source-confirmed and reproduces
the precise actionability failure. Increasing timeouts cannot correct stale state.

No production source was changed. A separately authorized correction should render
history from the current store snapshot when model eligibility/busy state changes,
with regression tests covering send completion, failure, scope changes and locks.
It requires a new immutable candidate frontend image. Keep all v1.0.0 images intact.
Do not unlock controls by DOM manipulation, reload to bypass the defect, or remove
the rename assertion.

## Contract audit

| Operation | Source contract / browser assertion | Result |
| --- | --- | --- |
| Merchant create | First explicit question creates owned conversation; POST requestId/context | Compatible; message reached |
| Message / real Qwen | POST messages requestId/expectedVersion/question; COMPLETED turn.response | Strict model check passed before failure |
| Assistant rendering | .ai-assistant .ai-answer visible and nonempty | Passed before failing statement |
| History management readiness | Conversation title enabled after completed send | Application defect; blocked |
| List / search | GET conversations page/size/search; Load saved conversations; owned total | Source compatible; later live check not reached |
| Load | GET messages; native replacement confirmation; historical answer visible | Source compatible; later live check not reached |
| Rename | POST rename expectedVersion/title; Current title and updated selected version | Valid selector/API; disabled control blocks test |
| Delete | Native confirm; POST delete expectedVersion; deleted=true; clear selection/bookmark | Source compatible; same stale-control risk |
| Admin / ownership | Separate portal path; owner/role validation; Merchant B/Admin list isolation | Assertions retained; not reached in this run |
| Bookmark / refresh | Subject/session/role/context-scoped history pointer; no new message POST | Candidate bootstrap fix retained; later live check not reached |
| Logout / cross-tab | Native logout and protected-route redirects, shared session invalidation | Assertions retained; later live check not reached |

The message observer deadline remains 70 seconds, frontend chat request deadline
45 seconds (creation separately bounded), action/expect deadlines 15 seconds and
journey budget 900 seconds. No timeout or retry was changed. The completed chat
response and rendered answer rule out an inference wait at the failing statement.

## Diagnostic-only changes

Add CHAT_ANSWER_RENDERED and HISTORY_TITLE_FILLED checkpoints, including visible
and enabled title assertions before filling. Preserve every existing assertion
and actual browser interaction. Record only boolean chat-response-completed and
assistant-rendering-observed witnesses. Reporter revalidates types and state
consistency, discards unknown payload fields, and emits fixed codes/booleans only.
Existing action-specific route/HTTP categories remain sanitized; title readiness
has no HTTP request, so no old HTTP 200 is attributed to that action.

## Validation and next step

Offline tests do not certify native browser success. Do not rerun the unchanged
candidate expecting diagnostics to fix the application. Obtain approval for the
narrow production presentation-state correction and a new candidate image first.
No workflow, application image lock, application source, database or service is
changed by this audit.

Offline validation: 194 deployment tests, 60 Node helper/reporter tests, 13 bootstrap
integration tests, 1,563 frontend JavaScript assertions across 20 suites, and 59
frontend/proxy tests passed. Syntax, workflow/Compose YAML, release-lock JSON and
Git whitespace checks passed. The original Git index checksum remained unchanged;
only the five browser diagnostic/test files and this report were modified.
