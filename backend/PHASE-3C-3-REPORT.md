# Phase 3C.3 implementation report

## Changes

`JwtSecurityConfiguration` now grants public access only to POST
`/api/v1/auth/login`. Every other request matched by `/api/v1/auth/**` is denied,
including valid ADMIN and MERCHANT JWT holders. Existing JWT decoding and
authentication remain configured, so invalid tokens still receive 401 and valid
authenticated callers denied by this policy receive 403.

The JWT test-only probe moved from `/api/v1/auth/**` to `/api/v1/_test/probe`.
It has no production handler and receives the normal unmatched-route default-deny
policy; no production security exception was added. The existing public login
path, payment authorization, merchant isolation, webhook HMAC, settlement token
checks and bounded request filter are unchanged.

## Modified files

- `src/main/java/com/paymesh/backend/security/auth/JwtSecurityConfiguration.java`
  — changed remaining auth namespace requests from authenticated to deny-all.
- `src/test/java/com/paymesh/backend/security/auth/JwtAuthenticationIntegrationTest.java`
  — moved test-only probe outside auth namespace and added valid ADMIN/MERCHANT,
  unknown path, non-POST login and anonymous denial coverage.
- `README-BUSINESS-SECURITY.md` — documented auth namespace default-deny policy.
- `PHASE-3C-3-REPORT.md` — this report.

No V1–V8 migration, application database record, or operational account was
modified or created.

## Regression coverage

Tests verify POST login remains public, absent authentication on non-POST login
and unknown auth routes returns 401, valid MERCHANT and ADMIN JWTs receive 403
for all non-login auth namespace routes, and the relocated test probe does not
create a security exception. Existing JWT signature/claim/account checks and
payment, webhook, settlement and request-size tests ran in the full suite.

## Test result

Command: `bash scripts/test-isolated.sh`

Result: **168 tests, 0 failures, 0 errors, 0 skipped; BUILD SUCCESS.** The guarded
script reported `server stopped` after the run. Only its verified isolated
PostgreSQL cluster was used.

No Phase 3C.4 work was started.
