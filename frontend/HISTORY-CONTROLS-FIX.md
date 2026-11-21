# Saved-history controls after chat completion

## Root cause and correction

Run 44875247889 reached the title-fill action after real inference and a visible
assistant answer. Conversation transport emits its completed saved turn before
returning to the chat model. At that instant model.busy is still true, so the
store's history-render callback disables management controls. Merchant and Admin
models subsequently clear busy in finally and emit their model state; the shared
presentation rendered the answer/composer but did not refresh history.

The correction in assets/js/chat/presentation.js calls
`history?.render(store.state())` from the existing model render callback after
scope synchronization. It uses the latest store snapshot and current model state.
There is no new listener, subscription, asynchronous work, network request or
change to canManage, store guards, ownership checks or API contracts. The timer
updates elapsed text directly and does not cause repeated history rendering.
History rendering preserves the typed title when the selected ID is unchanged.
Store busy, external locks, missing selection and deletion uncertainty remain
subject to the existing view rules. Scope loss clears selection before rendering.

## Regression coverage

`tests/history-state.test.mjs` runs the actual shared presentation and history-view
modules with the existing offline DOM and synthetic store/model boundary. It
covers both Merchant and Admin: busy → success, busy → failure, store operation
locks, external locks, lost eligibility, retained title edits, native form/button
handlers for rename/list/load/delete, one subscription and no duplicate handlers.
The Python wrapper includes these 12 cases in frontend test discovery. These are
not real model, backend ownership or native Chromium tests; existing model/store,
bootstrap/bookmark, authorization and browser suites remain necessary.

The prepared deploy/browser-e2e/offline.test.mjs previously asserted the *absence*
of history rendering in the model callback as evidence of the defect. That one
assertion/comment now expects its presence. Its actual-view stale-property
reproduction remains valid: changing a closure flag alone does not update DOM.
The other five prepared browser diagnostic files are unchanged. Browser journey
assertions, strict RAG_LLM/SUCCEEDED checks and timeouts are unchanged.

## Release requirements

No existing image contains this new presentation change. Do not overwrite any
v1.0.0 tag or digest. After separately approved commit/push, prepare the candidate
workflow/helper source pin for that exact approved commit and recompute the full
runtime-context fingerprint. The app.js-only hash is insufficient: this fix is in
chat/presentation.js. Keep app.js verification and add/verify the corrected file's
hash in candidate evidence. The current candidate workflows pin the older source;
running them unchanged would rebuild the old code.

Build only a uniquely identified local frontend candidate on a disposable GitHub
runner, with no registry login/push. Verify source revision, runtime-context content,
presentation hash and image configuration identity. Record configuration digest
as such, never as a registry digest. Run that exact image with the existing locked
Java, Python and llama images and fresh disposable PostgreSQL. Keep the complete
three-test Chromium suite, real Qwen requirement, authentication pacing and every
history assertion. Retain sanitized diagnostics and verify project-owned container
and volume removal after success or failure. Do not alter the original v1.0.0
verification contract. Failure means stop and retain evidence, not retry or relax
assertions.

No images were built, published or executed, and no services were changed during
this implementation. Native Chromium success remains unverified.

## Offline results and release blockers

- New lifecycle suite: 12/12 passed; the same tests with only the new render call
  removed fail 6/12, confirming sensitivity to the original defect.
- Existing frontend JS: 1,563 assertions across 20 suites passed.
- Frontend/proxy Python: 60/60 passed, including the new lifecycle wrapper.
- Session-bootstrap integration: 13/13 passed.
- Browser helper/reporter: 60/60 passed.
- Deployment regression: 193/194 passed. The sole failure is
  test_pinned_runtime_context_matches_reviewed_bytes: the corrected frontend has
  fingerprint d8ccb142df61fbe71c16bc7f65f761230e0c83e80cd762f9724b34703273c01e,
  while the old candidate is deliberately pinned to
  27abd26312820b76229de8867f30674b50396d7f03dd2a8ca7d905dc79623a12.
  Do not relax this guard or claim all deployment tests passed. Source/context
  repinning must be coordinated with the new immutable candidate after approval.
- Syntax, YAML/JSON and whitespace checks passed.

Concurrent index activity was detected: the new lifecycle JS test became staged
without any staging command in this task. No index repair/reset/stash was attempted.
All unrelated existing working files match the initial snapshot. Future commit
preparation must isolate the approved diff and preserve that concurrent index.
