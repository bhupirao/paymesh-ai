# Frontend v1.0.1: verified-image publication procedure

Status: IMPLEMENTED AND OFFLINE-TESTED ONLY. No publication/dispatch is authorized
by this document. Target: `bhupirao/paymesh-frontend:v1.0.1`, linux/amd64 only.
All four v1.0.0 tags, digests, workflows and release contracts remain immutable.

## Prerequisites and separate approvals

1. Review/approve the focused implementation commit/push separately.
2. In Docker Hub's paymesh-frontend repository, separately authorize configuring
   Settings → General → Tag mutability: specific immutable tags, exact RE2 pattern
   `^v1[.]0[.]1$` (or all tags immutable). Do not modify existing tags. The helper
   verifies enabled policy through the Hub API; missing/unknown/mutable policy fails
   closed. Read-only inspection found enabled=false; v1.0.1 returned HTTP404.
   Merely checking tag absence cannot close a concurrent-publisher race.
3. Keep dockerhub-publication: reviewer bhupirao, main-only branches, administrator
   bypass disabled, existing environment-only DOCKERHUB_USERNAME/TOKEN. Use least
   privilege credentials with write access to this repository, no delete permission.
4. After review, separately approve dispatch of Frontend v1.0.1 verified publication
   on main. It has no arbitrary namespace/tag/source inputs. Do not enable or use
   the original four-image v1.0.0 publication workflow.

Docker documentation: [immutable tags](https://docs.docker.com/docker-hub/repos/manage/hub-images/immutable-tags/)
and [settings schema](https://docs.docker.com/reference/api/hub/latest/schemas/immutable_tags_settings/).
The API/settings feature may change; an unrecognized response requires review, not bypass.

## Exact-image chain

The verify job uses the fixed frontend source and content hashes in
[RELEASE-EVIDENCE.md](RELEASE-EVIDENCE.md). It builds only frontend, extracts and
hashes app.js and chat/presentation.js, starts it with the unchanged digest-locked
Java/Python/llama and fresh PostgreSQL, and runs all three Chromium tests/all ten
stages. RAG_LLM/SUCCEEDED plus knowledge references remain mandatory. Mocking,
fallback-only results, skipped tests, retries and relaxed assertions cannot satisfy
the release gate.

After final counts pass, export the exact local image archive and an allowlisted
proof. Always retain sanitized diagnostics and run original ownership-guarded stack
and image cleanup. Only after both container/volume absence and candidate-image
cleanup pass, seal the proof and upload exactly frontend.tar/proof.json for one day.
A failed test, teardown, seal or artifact upload prevents the publish job.

The publish job requires the protected environment's approval *after* verify succeeds.
Approve within the one-day transfer-artifact retention period; expired artifacts
fail closed and require a separately approved fresh run, never a blind retry.
The operator reviews that run's tests/cleanup and fixed destination before approving.
It checks environment rules, historical successful run, Hub policy and tag absence
again. It downloads only the same-run artifact ID, verifies workflow SHA/name/run,
archive and proof checksums, then loads that exact image. It validates config ID,
source labels and runtime configuration without rebuilding. No downloaded model or
database/credential files enter the image. This archive is code, not a database backup.
The ordinary read-only token gains actions:read only for workflow/artifact metadata.
No repository-write permission is needed.

Only then log in via password-stdin (captured output, private temporary auth config),
tag the newly built candidate as v1.0.1 and push that one tag once. This tags a NEW
candidate, never retags an existing published image. Server-side immutable policy
prevents a concurrent overwrite; absence is rechecked immediately before login/push.
The original frontend v1.0.0 remains unchanged. No latest tag is created.

Resolve the tag through anonymous registry authentication, verify the actual
manifest bytes/content digest and config digest, then anonymously pull by that
registry digest and check linux/amd64/source/config identity. publication.json
records distinct registryManifestDigest and imageConfigDigest plus source/content,
real Chromium and cleanup witnesses. The candidate's old local config ID is not
reused or mislabeled as a registry digest. Rebuild base tags can change; the newly
built artifact must pass the full suite again before it can be pushed.

## Failure handling

No automatic retry, image deletion, overwrite or rollback is implemented. Verify-job
failure means no publication. Failure after the push may mean partial completion:
inspect the tag/digest and sanitized publication.json before any further action.
Do not rerun this version if the tag now exists. A failure record conservatively
states publicationMayHaveOccurred; it never falsely certifies absence. Docker auth
config is removed in finally; no raw command output or exception enters logs.
The disposable runner removes remaining transferred archives on destruction; no
local Mac resources or persistent project volumes are used.

Post-publication work requires separate review: commit the actual registry digest,
prepare a new digest-pinned deployment overlay with unchanged backends, and verify
the published artifact. Do not edit the historical v1.0.0 image lock. Source-available
copyright/third-party notices remain unchanged. This is not public production hosting.
