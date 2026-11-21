# PayMesh AI verified release evidence

Recorded audit evidence; not a newly executed application suite or security certification.

| Scope | Evidence |
| --- | --- |
| Published-source API E2E | [44652430877](https://github.com/bhupirao/paymesh-ai/actions/runs/44652430877), source cefa7df83a5bf16d011e82041c95e2d93b9c637b, eight stages, real inference |
| Published-image API E2E and explicit cleanup | [44793055710](https://github.com/bhupirao/paymesh-ai/actions/runs/44793055710), historical successful baseline |
| Corrected candidate Chromium | [44877848710](https://github.com/bhupirao/paymesh-ai/actions/runs/44877848710), workflow commit 2d2f6dad99443849a15b4b86879b594eb7b4e967 |
| Chromium result | 3/3 tests, all ten journey stages, modelInferenceVerified=true, chat completion/rendering observed, zero retries |
| Cleanup | containersAbsent=true, volumesAbsent=true, candidateImageAbsent=true, temporaryPayloadRemoved=true |

The corrected frontend source is `a15410f2eb2c7d987c142fd7e3758eb237c6c70d`.
Its canonical 115-file runtime fingerprint is
`d8ccb142df61fbe71c16bc7f65f761230e0c83e80cd762f9724b34703273c01e`.
chat/presentation.js is
`8f1bec53de24ee2d9aa5301d47f11513959cc816071d1ca69467abcca1b78780`.
The tested local image config ID was
`sha256:61462eed1da56a997759dfef98742003bcb049fbe661a69040c8dec90b5bb27d`.
That candidate was cleaned up, was never published, and has no registry digest.

## Published v1.0.0 artifacts (unchanged)

All four tags were independently readable anonymously with linux/amd64 metadata.

| Image | Registry digest |
| --- | --- |
| bhupirao/paymesh-java:v1.0.0 | sha256:22649c06e406681e4ea699a60ebcf1d537068ec1091b0b72c678a749c792eb2b |
| bhupirao/paymesh-python:v1.0.0 | sha256:29edd8acb856f9a19067592e9fb384e43ce74a060b1b6dabe04d747f0bfe65ee |
| bhupirao/paymesh-frontend:v1.0.0 | sha256:388718b672a9b944348a40257a56d212f1a6e4cb6ad372376a4e03ba5b1b2412 |
| bhupirao/paymesh-llama:v1.0.0 | sha256:09a63d5e9312e4126b90cdc927045cbb69a654b66dd722e3823c53d4066bf74e |

## Proposed frontend v1.0.1

Not published. Registry digest: UNKNOWN until actual publication and verification.
See [the separate manual-only procedure](FRONTEND-V1.0.1-RELEASE.md).
The ten Chromium stages cover registration, approval, dashboard/session/role checks,
payments, merchant isolation, real investigation, refunds, public checkout,
Merchant/Admin chat/history and cross-tab logout. This is bounded Chromium API/UI
coverage, not exhaustive accessibility, performance or production-security proof.
No prompts, answers, account credentials, cookies or checkout URLs are retained here.

## Frontend v1.0.1 preparation checks (2026-11-21)

214 deployment tests passed, including 18 new publication safety tests. Separately,
60 browser helper tests, 1,563 frontend JS assertions, 60 frontend/proxy tests,
13 bootstrap and 12 history lifecycle cases passed. Some Node suites are invoked
inside Python wrappers; these counts must not be added as independent totals.
All Docker/network publication operations in new unit tests are mocked. No new
Chromium run, image build or registry publication occurred during this preparation.
