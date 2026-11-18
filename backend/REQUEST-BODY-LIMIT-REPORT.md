# Bounded request reading implementation report

## Change

Added `BoundedRequestBodyFilter` for POST `/api/v1/auth/login` (4 KiB) and both
mock webhook endpoints (64 KiB). It rejects a declared oversized body immediately
and otherwise reads no more than one byte beyond the route limit, including when
the request has unknown/chunked content length. Oversize requests receive 413
before controller argument parsing. Accepted request bytes are buffered only up
to the configured bound and replayed unchanged to Spring MVC.

Webhook request bytes are not parsed, decoded, normalized, or reserialized by the
filter. `WebhookController` still passes the exact byte array to `WebhookIngress`,
which verifies the signature over those bytes before JSON parsing or persistence.
The old login filter's declared-length-only check was removed because the servlet
filter now enforces the actual read limit.

## Modified files

- `src/main/java/com/paymesh/backend/security/BoundedRequestBodyFilter.java` —
  bounded exact-route request buffering and 413 response.
- `src/main/java/com/paymesh/backend/security/auth/LoginRateLimitFilter.java` —
  removed the incomplete Content-Length-only check.
- `src/test/java/com/paymesh/backend/security/BoundedRequestBodyFilterTest.java` —
  added exact-limit, unknown-length/chunked-style, and declared oversized-body tests.
- `src/test/java/com/paymesh/backend/security/BoundedRequestBodyHttpIntegrationTest.java` —
  added embedded-server random-port and chunked HTTP integration coverage.
- `REQUEST-BODY-LIMIT-REPORT.md` — this report.

## Regression coverage

The new tests assert that bodies at the limit are preserved byte-for-byte, unknown
length bodies are rejected after consuming at most limit plus one byte, and
oversized bodies are rejected before reaching the controller. Existing
`SettlementIntegrationTest` validates signed provider webhook requests and raw
payload auditing; it passed with the filter enabled.

Phase 3C.2 added real HTTP/1.1 requests through an embedded server on a random
port using a streaming publisher without a known content length. Tests verify 413
for oversized login and both webhook routes, multibyte UTF-8 byte counting,
no webhook inbox/database side effects after rejection, and ordering relative to
MVC parsing and login rate limiting. Ten regular login attempts reach the
fail-closed unconfigured-login response; the next gets 429, while an oversized
login still gets 413 before MVC. Existing signed webhook tests verify raw-body
signature preservation.

The first full run passed the new HTTP tests but later hit PostgreSQL's connection
limit while another test context loaded. The random-port context now uses a
two-connection Hikari pool and closes after its class; the complete rerun passed.

Full suite command: `bash scripts/test-isolated.sh`.

Final Phase 3C.2 result: **167 tests, 0 failures, 0 errors, 0 skipped; BUILD
SUCCESS.** This includes three real HTTP integration tests and four bounded-body
unit tests.

The guarded script confirmed the isolated PostgreSQL server stopped (`server
stopped`). No application database was used. No Flyway migration or financial
business logic was changed.

## Remaining considerations

This application filter limits the three routes above. Apply matching limits at
the reverse proxy/server edge as defense in depth, and extend the exact route
catalog if a future endpoint accepts large or sensitive bodies. The filter buffers
accepted request bodies in memory, bounded at 64 KiB per webhook request. Confirm
production connector and proxy behavior for chunked bodies and align edge limits
with the application caps.
