# Phase 3A: JWT login and validation

Current implementation reference. See [API-REFERENCE.md](API-REFERENCE.md) for
the complete endpoint catalog and [README-DEMO.md](README-DEMO.md) for local
operator examples.

The only new production endpoint is POST `/api/v1/auth/login`. There is no public
registration, account-provisioning endpoint, refresh token, or production token
probe endpoint. No operational ADMIN account is created by this feature.

## Configuration

Supply all four environment variables together:

- `PAYMESH_JWT_PRIVATE_KEY_FILE`: local secret-mounted PKCS#8 PEM RSA private key.
- `PAYMESH_JWT_PUBLIC_KEY_FILE`: matching X.509 PEM RSA public key.
- `PAYMESH_JWT_ISSUER`: absolute issuer URI, exactly matching issued/validated tokens.
- `PAYMESH_JWT_AUDIENCE`: nonblank audience identifier without whitespace.

RSA keys must be at least 2048 bits. Restrict private-key access to the application
identity (for example mode 0600); do not commit keys, paste them into configuration,
or pass them as command-line arguments. Keys are loaded locally; there is no
untrusted jku/jwk lookup, remote discovery or generated production key fallback.
The key ID is a SHA-256 fingerprint of the public key. Malformed, partial,
weak, or mismatched configuration fails startup without printing private material.
With all four settings absent, the new login operation fails closed with 503 and
protected business APIs reject JWT authentication until keys are configured. Production deployment of login
requires the key settings, HTTPS and appropriate secret-file access controls.

## Login

POST JSON containing `login` and `password` to `/api/v1/auth/login` over HTTPS.
Use credentials provisioned through the approved Phase 2 process. The existing
AccountCredentials service performs BCrypt verification. Unknown, incorrect,
disabled, stale-version, and roleless credentials do not obtain a token.
Authentication failures return generic 401 JSON; malformed/schema-invalid bodies
return 400. Responses do not contain credentials or hashes and use no-store headers.

Request shape:

```json
{"login":"merchant-login","password":"<enter through a secure prompt>"}
```

There is no refresh-token endpoint. After the 15-minute access token expires,
authenticate again through this login flow using a secure prompt or approved
credential manager. Do not place passwords or tokens in shell history or print
the token value.

Success response fields:

```json
{
  "accessToken": "<RS256 signed access token>",
  "tokenType": "Bearer",
  "expiresIn": 900,
  "expiresAt": "<UTC expiration timestamp>"
}
```

Each token has a UUID subject and token ID, issuer, audience, issue time,
not-before, expiration, authorization_version and server-issued roles. Lifetime is
15 minutes. Decoder validation permits RS256 only, requires the temporal claims,
uses zero expiry/not-before clock skew, and rejects excessive lifetimes. Keep
application clocks synchronized. Account enabled status, authorization version
and exact current server roles are checked against PostgreSQL. Authorities are
rebuilt from server-side roles, not accepted from an arbitrary client role claim.
Account disablement or version changes invalidate existing tokens; role changes
also invalidate stale role claims even if a version increment was missed.

Authentication uses Spring's AuthenticationManager/ProviderManager, with the
existing password service behind a custom provider, and the OAuth2 Resource
Server JWT decoder/filter for bearer validation. HTTP sessions, form login,
HTTP Basic, request caching and logout sessions are disabled. JWTs must be sent
in Authorization headers; cookie authentication is not implemented.

## Rate limiting

The login filter runs before credential or JWT verification. Default budget is
10 attempts per remote client address per 60-second fixed window, counting both
successful and failed attempts. Rejections return 429 with Retry-After.

Optional environment tuning:

- `PAYMESH_LOGIN_MAX_ATTEMPTS` (1–100; default 10).
- `PAYMESH_LOGIN_WINDOW_SECONDS` (1–3600; default 60).
- `PAYMESH_LOGIN_MAX_CLIENTS` (1–100000; default 10000).

Counters are synchronized, expire, have bounded memory, and fail closed when
capacity is exhausted. The limiter uses the servlet remote address, not a raw
client-supplied X-Forwarded-For value. An explicitly trusted ingress must sanitize
forwarded headers before any server-side forwarding configuration is enabled.
Behind a proxy, clients may otherwise share one budget. Counters are per instance
and reset on restart; multi-instance production deployments require a shared
limiter/ingress budget. Per-account/distributed abuse controls remain deployment
hardening work. Apply ingress limits to header/body sizes, including chunked JSON;
the login filter also rejects declared bodies exceeding 4096 bytes.

## Current Phase 3B authorization boundary

Existing payment, refund and gateway-history APIs now require JWT authentication
and service-level merchant authorization. See [README-BUSINESS-SECURITY.md](README-BUSINESS-SECURITY.md)
for the endpoint inventory and ownership policy.

Four ordered filter chains separate public health and independently authenticated
webhook/settlement routes, protected business routes, the auth namespace, and a
default-deny fallback. Catalogs enumerate methods and paths; no public wildcard
was added. ADMIN JWTs protect actuator discovery and info. Webhook HMAC and the
opaque settlement bearer remain independent of JWT. A missing settlement bearer
returns 401, matching the approved design; missing settlement configuration still
fails closed with 503. Offline ADMIN provisioning remains non-web.

## Verification and remaining scope

Run only `bash scripts/test-isolated.sh`. The pre-Flyway guard and script remain
unchanged. Tests generate temporary RSA keys at runtime, never use committed
private keys, and store account fixtures only in verified isolated PostgreSQL.
The protected transport probe is test-only and is excluded from production and
other application contexts.

Coverage includes valid/invalid login, disabled accounts, signature tampering,
wrong issuer/audience/key, unsupported algorithms, missing/expired/future claims,
revoked authorization versions, current roles, statelessness, key validation,
rate-limit expiry/concurrency, missing configuration, unchanged HMAC/settlement
handling and existing payment/refund behavior.

There is no refresh-token/recovery implementation or multi-key rotation overlap. A key
replacement invalidates old-key tokens; plan rollout accordingly. Refresh tokens and later security phases are outside this implementation.
