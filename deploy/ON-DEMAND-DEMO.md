# Short-lived authenticated acceptance demo

This is an operator-led acceptance session on a disposable standard GitHub-hosted
runner, not permanent hosting or an availability promise. No local Docker,
PostgreSQL, model download or paid model API is required. No workflow has been
run as part of this implementation.

## Security feasibility and provider dependency

Cloudflared **2026.11.1** implements `--allowed-mail` for **Quick Tunnels**.
This was checked against the actual tagged `cmd/cloudflared/tunnel/cmd.go` and
`quick_tunnel.go`, including installation of the Quick Tunnel authorizer.
The pinned official release asset checksum is in `cloudflared-demo.json`.
The workflow verifies its checksum and CLI support, requires the protected-tunnel
startup marker, and independently checks the unauthenticated HTTPS Access login
redirect **before unlocking the origin**. There is no unauthenticated fallback.
No Cloudflare account, owned domain or payment card is required by this mechanism.
Only one exact recipient email is permitted; domains and wildcards are rejected.

References:
- [Cloudflare Quick Tunnels](https://developers.cloudflare.com/tunnel/get-started/quick-tunnels/)
- [Tagged CLI implementation](https://github.com/cloudflare/cloudflared/blob/2026.11.1/cmd/cloudflared/tunnel/cmd.go)
- [Tagged authorization integration](https://github.com/cloudflare/cloudflared/blob/2026.11.1/cmd/cloudflared/tunnel/quick_tunnel.go)
- [Known protected-session expiry report](https://github.com/cloudflare/cloudflared/issues/1752)

**Live OTP issuance/session reliability is unverified.** The provider has an open
report of very short authenticated sessions. A redirect proves a gate is present;
it does not prove email delivery or usable authenticated sessions. The operator
must validate OTP and rejection of an unlisted email during the first separately
approved run. If broken, cancel the run; do not remove `--allowed-mail` or relax
Host/Origin/header checks. The exact broker URL is deliberately fail-closed: a
provider change can block admission and requires review.

## Architecture

Internet HTTPS → Cloudflare email OTP authorizer → loopback-only demo edge
`127.0.0.1:15501` → released frontend proxy `127.0.0.1:15500` → private Java,
Python and llama services. PostgreSQL is on an internal Docker network.
The three backend images retain v1.0.0 digests; frontend uses published v1.0.1.
`demo-images.json` records these identities and the reviewed Compose checksum.
Nothing is built or published. The sole named volume is the unique project's
`container_pgdata`; it is disposable. Existing local services are never accessed.

The edge validates exact Host and Origin, refuses duplicate/unknown forwarding
schemes and forwarding chains, and never uses forwarded IPs for authorization or
rate-limit bypass. It maps the validated public origin to the existing loopback
proxy contract. It does **not** remove JWT authorization, CSRF markers or role
checks. Only the app refresh cookie is forwarded; returned cookies must already
have HttpOnly, SameSite=Strict and the exact auth path before Secure is added.
No CORS wildcard, public database/inference port or default administrator exists.

The OTP gate protects the whole demo, including public checkout and the private
credential page. Customers in this acceptance session must also be the allowed
operator. This is intentionally unsuitable for anonymous recruiter access.

## One-time GitHub configuration — operator action, not done here

1. Review and separately approve commit/push of this implementation.
2. Create environment `demo-preview`, restricted to `main`, required reviewer
   `bhupirao`, administrator bypass disabled. Do not reuse Docker Hub secrets.
3. Set environment secret **DEMO_ALLOWED_EMAIL** to the exact email that will
   receive the OTP. Do not place it in dispatch inputs or repository files.
4. Preserve selected Actions and full-SHA enforcement. Only existing approved
   checkout and upload-artifact references are used. Workflow token is read-only.
5. Ensure repository/organization policy permits short acceptance sessions.
   Standard public-repository runner usage is normally free, subject to GitHub
   allowances, fair-use rules and policy. Do not chain runs for hosting or bypass
   usage limits. No paid runner or paid API is configured.

## Manual startup, access and shutdown

After separate execution approval:

1. Actions → **Short-lived authenticated acceptance demo (no publication)** →
   Run workflow → branch **main**, select 5, 10 or 15 minutes.
2. Review/approve the `demo-preview` environment deployment yourself.
3. Wait for the five-service health, exact image identities, V1–V14, empty-data
   guard, synthetic Admin bootstrap and all three native Chromium tests. Real
   Qwen RAG_LLM/SUCCEEDED assertions and all ten journey stages remain unchanged.
   Public access is not opened if any of these fail.
4. While the session step is running, open its live log and use the
   `DEMO_AUTHENTICATED_ENTRY` link. This validated base URL is intentionally
   public and contains no credential or checkout token. GitHub may publish a
   step summary only after the step finishes, so do not wait for the Summary.
   Open `/_demo/start`, complete email OTP, then use its
   freshly generated Admin/Merchant credentials. Do not copy them to public issues
   or artifacts. Merchant signup/approval and simulated checkout remain available.
5. Merchant `/merchant/login`, Admin `/admin/login`; API docs `/docs/`.
   Docs are a controller-validated **subset**, not an exhaustive auto-generated
   OpenAPI contract. Swagger UI 5.35.1 assets are vendored with integrity hashes and
   third-party notices. Try it out, authorization persistence and external
   validation are disabled. Do not enable interactive requests without separate
   end-to-end HTTPS authentication/CSRF testing.
6. End early with **Cancel workflow**. Otherwise access expires automatically.
   The supervisor locks the edge, terminates only its own tunnel process and
   records public closure **before** project-scoped container/volume teardown.
7. Inspect `public-access-closed.json` and `sanitized-cleanup.json`. Require
   success plus `containersAbsent` and `volumesAbsent`. Missing/interrupted
   evidence is **UNKNOWN**, never successful cleanup.

Public access ends with this session. Accounts, financial records, conversations
and the database are removed only when scoped cleanup succeeds; otherwise their
removal remains unverified until runner disposal. There is no persistence/backup promise or resume
link. Another day requires a fresh manual run, new credentials and new URL.

## Resource and time bounds

One runner, one Playwright worker, Qwen2.5-0.5B Q4_K_M (~0.5 GB, checksum-verified),
llama CPU threads 2 / parallelism 1; Compose memory caps total about 2.2 GiB plus
browser/Docker/runner overhead. Require at least 8 GiB free disk before downloads.
Ubuntu 24.04 standard public runners normally provide 4 vCPU/16 GB RAM/14 GB SSD;
capacity and runtime vary. Startup commonly takes several minutes and may fail
on provider downloads. Full Chromium acceptance precedes public access; its step
is bounded to 14 minutes and never retried. No guarantees are inferred from old
successful runs.

Job maximum 55 minutes; public session maximum 15 minutes and is shortened by a
45-minute deadline measured from fixture preparation. If less than two minutes
remain, no session opens. Setup has individual bounded steps. Timeout/cancellation
can interrupt the finalizer; GitHub runner destruction closes the connection but
is **not** equivalent to verified scoped cleanup. Never claim a missing receipt
is PASS. Unexpected PID reuse also blocks cleanup rather than signalling an
unrelated process. No broad Docker prune or volume deletion is used.

## Offline and runtime verification

`python3 -B -m unittest discover -s deploy -p 'test_*.py'` covers gate, header,
Origin/CSRF forwarding, cookie security, image locks, workflow policies, read-only
Swagger, controller mappings, expiry checks and cancellation/cleanup ordering.
Existing browser and frontend/bootstrap/history suites remain unchanged.

Offline tests do **not** prove real inference, browser acceptance, tunnel OTP,
HTTPS cookies, public Host/header shape or cancellation cleanup. Those execute
only on a separately approved hosted run. The standard full browser suite runs
internally before opening access; it does not replace independent public HTTPS
cookie/CSRF checks. Swagger stays noninteractive for that reason.

Artifacts allowlist only existing sanitized browser reports and fixed lifecycle
receipts for one day. Never upload private tunnel logs, credentials, .env, raw
application logs, browser traces, screenshots, HAR or authentication state.

## Offline implementation evidence (2026-11-21)

- 262 deployment tests passed, including 48 new demo security/lifecycle tests.
- Existing unchanged browser helpers: 60 passed.
- Existing frontend suites: 1,563 JavaScript assertions and 60 Python/proxy tests passed.
- Session bootstrap: 13 passed; history lifecycle: 12 passed (also exercised by frontend wrappers).
- Java targeted offline security: 12 passed across JWT keys, rate limiter, account
  authorization and internal financial-boundary architecture. No database-backed
  Java integration suite was run for this adapter-only change.
- Syntax, YAML/JSON, vendored-asset hashes, diff checks and focused secret-pattern
  scans passed. Original release workflow/image-lock files were compared unchanged.
- Docker CLI is unavailable locally: native Compose config evaluation, five-service
  startup, real inference, native Chromium and public HTTPS/OTP are **NOT RUN**.

These are implementation checks, not a successful demo run. Source and tests are
prepared in an isolated checkout; the original repository staging/index and
working-file hashes were preserved. No commit, push, settings update, dispatch,
public tunnel or image publication was performed.


## First on-demand run investigation

Run [44900649419](https://github.com/bhupirao/paymesh-ai/actions/runs/44900649419),
source `7b830e4ad2d8128dbd8b4ec33bf18952bbbf7060`, failed on 2026-11-21.
All five services, V14/empty-data admission, three Chromium tests, all ten journey
stages and real Qwen inference passed. The serve step failed after about four
seconds. `public-access-closed.json` confirms the owned public process exited;
`sanitized-cleanup.json` confirms containers and project-owned volumes absent.

The original catch-all discarded the exception and the private tunnel log was
intentionally not uploaded. The artifact therefore cannot identify the exact
serve operation, process exit code, CLI/provider error or OTP probe result.
No successful `DEMO_OTP_GATE_VERIFIED_ACCESS_OPEN` witness was present. This is
not evidence of an application, database, browser or model failure.

Do not guess a CLI or provider fix from the generic failure. In particular, the
pinned cloudflared configuration parser explicitly accepts EOF/empty configuration;
`--config /dev/null` is not a proven fatal error. The CLI capability guard passed
before the existing finally/closure receipt could be reached.

Failure-only `sanitized-demo-serve.json` now records a fixed operation identifier,
allowlisted error/type, numeric OS error where available, child exit status captured
**before** owned termination, bounded fixed-category tunnel-output signals,
startup/hostname-observed booleans, OTP HTTP status/challenge match and whether
application access was opened. It is also emitted as one fixed-schema stdout
record. It contains no raw exception messages, log excerpts, recipient email,
URLs, headers, cookies, credentials, model content or checkout tokens. Unrecognized
provider output remains unclassified. Existing generic failure and cleanup
receipts are preserved; missing cleanup evidence remains UNKNOWN.

The next hosted run requires separate commit/push and execution approval. No
access gate, public Host/Origin rule, cookie/CSRF check, image lock or browser
assertion was relaxed. Actual live root cause remains UNKNOWN until this evidence
is captured; no automatic retry is introduced.
