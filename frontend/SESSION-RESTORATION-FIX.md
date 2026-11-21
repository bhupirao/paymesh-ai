# Protected-route and conversation restoration fix

Status: implemented and verified offline; no commit, push, build, publication or activation.
Reviewed remote main: `6245d7794397dbb7dd1727e6865cc550a1952c15`.

## Root cause and scope

Previously `app.js` constructed its router and conversation stores, then started `persistence.restore()` without awaiting it. A refreshed document has no memory-only session yet:

1. The router resolved an AI/payments deep link as unauthenticated and replaced the current history entry with the login path and null state.
2. This erased both the requested route and `history.state.paymeshConversation`.
3. A successful refresh installed the validated session, causing login to resolve to the dashboard rather than the original page.
4. Independently, eager conversation stores had already subscribed to session changes. Hydration looked like an account replacement to those stores, which cleared the bookmark even if the router did not erase it.

The only application change is startup ordering in `assets/js/app.js`: install persistence and await the existing refresh before constructing the workspace, router or chat stores. An unexpected rejected restoration clears the memory-only session before ordinary routing. The same refresh, cookie, CSRF header, token validation, version/epoch fencing and timeouts are retained. No route, backend API, rate limit, bookmark format or ownership rule changes.

After successful restoration, the existing router sees the current authenticated session on its first resolution. A permitted deep link remains unchanged, preserving its history entry; the existing owner/session/role-bound bookmark loader performs an authorized history GET. Without a session, ordinary login redirection remains. Wrong-role access is still denied. During pending bootstrap, the private shell remains initially hidden; no private workspace is mounted. Static public content can remain visible until initialization finishes. Users can navigate elsewhere during the pending refresh; initialization uses the current location, not a captured return URL.

No access token, answer, prompt or conversation content is written to history or persistent browser storage. Server authorization remains authoritative for every history read. A stale/foreign bookmark is cleared without retrieving its conversation. Logout, cross-tab revocation and late-refresh protection remain unchanged.

## Files for this correction

- `frontend/assets/js/app.js`: await restoration before mounting session-sensitive components; remove the old trailing fire-and-forget restore.
- `frontend/tests/session-bootstrap.test.mjs`: dependency-free VM module-graph regression suite.
- `frontend/tests/test_session_bootstrap.py`: integrates the module tests with frontend Python discovery and checks production bootstrap ordering.
- `frontend/SESSION-RESTORATION-FIX.md`: this report and future release procedure.

The seven pre-existing browser-test correction files are preserved byte-for-byte, including the AI refresh URL/answer assertions. Router, session, persistence, bookmark and store source files are unchanged. Existing workflows, Dockerfiles, Compose files and v1.0.0 digest locks are unchanged.

## Regression coverage and results

The 13 new Node cases execute actual `app.js` startup, persistence, session, router, bookmark and conversation-store modules. Rendering adapters are stubbed; this is not a native browser test. Cases cover:

- Merchant and Admin AI refresh with a valid owner/session-bound pointer and automatic authorized GET.
- Merchant payments refresh and unrelated history-state preservation.
- Unauthenticated, failed and wrong-role restoration.
- Logout and subsequent protected navigation.
- Cross-tab revocation after restoration and while a refresh is pending.
- Rejection of another owner/session's bookmark.
- Malicious route inputs and public navigation during bootstrap.
- The former startup order, reproduced in memory with the same real modules, demonstrably losing the route and bookmark. Production files are not reverted for this test.

Fresh checks:

- 20 existing frontend JavaScript suites: **1,563 assertions passed**.
- New bootstrap module suite: **13 tests passed**, also invoked by one frontend Python test; do not double-count these as independent browser scenarios.
- Full frontend Python/proxy discovery: **59 tests passed**.
- Deployment discovery: **160 tests passed**, including 16 JDK-only checks against the unchanged Java limiter.
- Existing browser helper/reporter suite: **50 tests passed**, also invoked by deployment discovery.
- JavaScript/Python syntax, YAML/JSON parsing, targeted security checks and `git diff --check`: passed.

The local Node18 compatibility runner for the 20 historical suites used an isolated temporary ESM copy, the existing mock DOM, and a test-only standards-compatible URLSearchParams.size getter (missing in this older Node). No production polyfill or dependency was added. An initial proxy run could not bind ephemeral mock sockets inside the sandbox; the permitted rerun used disposable loopback test servers and passed. Early historical-suite harness failures were corrected in the temporary runner (output-format recognition, timer handling and the Node18 getter), without altering application/test assertions.

No full backend or AI-service suite was rerun: neither implementation changed. No Chromium, Docker or inference ran locally. Native focus, layout, timing, actual cookie restoration and complete historical-answer rendering must still pass the disposable Chromium workflow.

Reproduce targeted tests without Docker:

```sh
node --experimental-vm-modules frontend/tests/session-bootstrap.test.mjs
python3 -B -m unittest discover -s frontend/tests -p 'test_*.py'
python3 -B -m unittest discover -s deploy -p 'test_*.py'
node deploy/browser-e2e/offline.test.mjs
```

## Separately approved new-image verification

The current published frontend digest contains the older `app.js`. `deploy/Dockerfile.frontend` copies `frontend/assets` into the image; changing local source cannot update that immutable artifact. Java, Python, llama.cpp and PostgreSQL do not need rebuilding for this fix.

1. Review and separately approve a focused commit/push containing this fix and its tests, preserving the independent browser-test patch and original staging.
2. Prepare a manual-only runner procedure pinned to that exact new commit. Keep existing SHA-pinned Actions, read-only workflow token, no environment secrets for build-only validation, and publication reviewer protections. Do not enable or repurpose the existing v1.0.0 publication gate: it deliberately pins the older tested source.
3. On a disposable linux/amd64 runner, run offline frontend/deployment checks and build only the frontend with the existing Dockerfile. Example **future runner command**, not executed here:

   ```sh
   docker buildx build --platform linux/amd64 \
     --file deploy/Dockerfile.frontend \
     --label "org.opencontainers.image.revision=$APPROVED_SOURCE_SHA" \
     --provenance=false --sbom=false --load \
     --tag paymesh-frontend:bootstrap-candidate .
   ```

   Single-platform loading avoids the previously corrected manifest-list exporter conflict. Record the resulting image/config identity and exact source label. A locally built candidate is not evidence of a published-artifact test.
4. Test that candidate only in a separately reviewed runner-only candidate configuration with fresh synthetic data and scoped cleanup. Preserve real Chromium interactions and RAG_LLM/SUCCEEDED checks; never present the old v1.0.0 source E2E as evidence for the changed frontend.
5. After separate publication authorization and environment approval, publish under a **new unused candidate/release tag**, for example a reviewed `v1.0.1-rc.1`, and record its actual immutable registry digest. Do not overwrite any v1.0.0 tag or fabricate the future digest.
6. Prepare a new release/candidate manifest and Compose configuration that pin only the new frontend digest and retain the other three published v1.0.0 digests. Identity verification must validate per-image source revisions: new frontend commit, existing Java/Python/llama application revision. The current release helper hard-codes the v1.0.0 manifest and one common source SHA; changing only Compose would correctly fail its identity gate. Add a separate explicit candidate contract rather than disabling checks or rewriting historical release metadata.
7. After review/approval, point the manual browser workflow/bootstrap at that new contract and run one coordinated disposable Chromium verification. Preserve existing scenarios, automatic refresh assertions, diagnostics, zero retries and scoped volume cleanup. Keep the publication workflow disabled outside its separately approved publication window.
8. On failure, retain sanitized evidence and tear down only the owned disposable project. Do not automatically retry, rewrite v1.0.0 tags, restart local services or alter local data. Retain all old release manifests and successful run evidence.

Development source is ready for separately approved commit/push. Full release verification remains pending a new frontend artifact and actual disposable Chromium execution; offline success does not certify browser E2E.

## Concurrent Git index observation

During validation, the index checksum changed independently of this task's commands. The three newly created test/documentation paths appeared staged (the two test files also have later working-tree edits). No staging, commit, reset or other index mutation command was issued. Those entries were not reverted or reconciled. All seven pre-existing browser-test working files remain byte-identical to their starting fingerprints. A later commit operation must re-inspect and isolate the intended diff rather than assume the original index is unchanged.
