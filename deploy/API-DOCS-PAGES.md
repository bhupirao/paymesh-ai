# Public, read-only API documentation

Target: **https://bhupirao.github.io/paymesh-ai/**

Status: **prepared; not deployed or publicly verified**. The README link remains
explicitly pending. No repository settings, commits, pushes or deployments were
performed during implementation.

## What the interviewer can explore

A responsive landing page explains the five-service architecture, Merchant/Admin
role boundaries, JWTs, refresh sessions and financial ownership. Swagger UI
provides six existing operations, grouped as Authentication, Browser sessions and
Payments. Login, token, session, payment request/response and health schemas are
checked against Java controller/DTO source.

The existing `backend/openapi/paymesh-demo.json` is a **selected subset**. It does
not contain merchant-management, refund or AI-investigation paths, so the site
does not invent them. It links to `backend/API-REFERENCE.md` on GitHub for the
fuller implementation reference. Backend availability is irrelevant to reading
this site: GitHub Pages hosts no Java, Python, PostgreSQL or model service.

The input demo specification remains unchanged. The builder generates a
presentation copy, retaining exactly its paths, methods and status codes while
adding source-validated schemas, tags and explanatory descriptions. If the source
fields/routes change, the build fails for review. This is not an exhaustive
runtime-generated OpenAPI contract.

## Static-only security

- `supportedSubmitMethods: []` and `tryItOutEnabled: false`.
- Authorization UI components are inert; no token-entry flow or stored auth.
- `persistAuthorization: false`, `withCredentials: false`, `validatorUrl: null`.
- Request interceptor permits **only GET of the exact local OpenAPI JSON**;
  other methods, API paths, external origins, queries and fragments are rejected.
  Credentials are omitted and request headers cleared.
- CSP restricts scripts and connections to this static origin; forms and objects
  are disabled. Inline styles are permitted for Swagger UI, never inline scripts.
- No CDN, analytics, API credentials, customer fixtures or payment data.
- Output is an exact ten-file allowlist. Only that directory is uploaded, never
  the repository, runtime config, model weights, database files or demo evidence.
- Official Swagger UI 5.35.1 assets are copied from the existing hash-checked
  vendor directory. No duplicate Swagger bundle is added to Git history.
- Swagger's LICENSE/NOTICE are shipped. The official OpenAPI validation schema's
  upstream Apache license is retained separately for the build tool. These do not
  grant an open-source license to project-authored code; the source-available
  README notice remains unchanged.

## Offline commands

Run from the prepared repository root (no Docker, backend or model needed):

```sh
python3 -B -m unittest discover -s deploy -p 'test_api_docs.py'
node deploy/api_docs.test.mjs
python3 -m venv /tmp/paymesh-pages-validator
/tmp/paymesh-pages-validator/bin/python -m pip install --require-hashes --only-binary=:all: -r deploy/requirements-pages.txt
/tmp/paymesh-pages-validator/bin/python -B deploy/build_api_docs.py --formal --output /tmp/paymesh-api-docs
```

Use a new output directory: the builder refuses to overwrite an existing one.
The formal validator checks both input and generated specs against the vendored,
SHA-256-pinned official OpenAPI 3.0 schema. Unit tests themselves use the standard
library and do not add dependencies to existing release workflows. The validator
is installed only in the new Pages build's isolated venv; the six dependencies
are exact-version/hash locked. The source and provenance of the validation schema
are in `openapi-schema-manifest.json`.

The static artifact can be previewed with any static file server. Serve it under
`/paymesh-ai/` when checking the target subpath. Browser rendering and real GitHub
Pages deployment remain separate verification steps; passing offline tests does
not prove the target URL is live.

## GitHub settings — manual changes, separate approval

No settings have been changed. Before separately approving deployment:

1. **Settings → Pages → Build and deployment → Source: GitHub Actions.**
   Keep the default `github.io` URL, no custom domain/CNAME needed. Enable Enforce
   HTTPS if GitHub offers that control for this site.
2. Under **Settings → Actions → General**, preserve selected Actions and full-SHA
   enforcement. Add these exact direct references without removing existing ones:

   ```text
   actions/configure-pages@45bfe0192ca1faeb007ade9deae92b16b8254a0d
   actions/upload-pages-artifact@fc324d3547104276b827a68afc52ff2a11cc49c9
   actions/deploy-pages@368f82528645a54fb793d4d04e342629a3f51346
   ```

   The official upload action is composite and uses this pinned dependency;
   allow it too:

   ```text
   actions/upload-artifact@bbbca2ddaa5d8feaa63e36b76fdaad77386f024f
   ```

   Existing checkout pin `d23441a48e516b6c34aea4fa41551a30e30af803` is reused.
   Action SHAs were resolved from the official `actions/*` release repositories.
   Direct action metadata uses Node 24; `ubuntu-24.04` supports that runtime.
   The reviewed references are recorded in `pages-action-pins.json`.
3. Create/review environment **github-pages**: restrict deployment to `main`.
   For explicit deployment approval, select reviewer `bhupirao`, leave self-review
   permitted for this solo project, and disable administrator bypass. No secret
   values or deployment credentials are needed: Pages uses GitHub OIDC.
4. Keep the Docker Hub publication workflow disabled and its protections intact.
   This documentation workflow does not reference Docker Hub or demo environments.

Official instructions:
- [Custom Pages workflows](https://docs.github.com/en/pages/getting-started-with-github-pages/using-custom-workflows-with-github-pages)
- [Publishing source settings](https://docs.github.com/en/pages/getting-started-with-github-pages/configuring-a-publishing-source-for-your-github-pages-site)

## Publication procedure — not authorized yet

1. Separately review/approve a focused commit and normal push of these docs files.
2. Configure the settings above after separate approval.
3. Separately approve execution, then Actions → **Publish read-only REST API
   documentation** → Run workflow → `main`. It is **manual-only**: pushes, PRs,
   schedules and existing release workflows cannot trigger this deployment.
4. The build runs source/static security checks, JS tests, formal OpenAPI
   validation, reads existing Pages configuration (`enablement: false`) and uploads
   only the generated artifact. Build permissions: `contents: read`, `pages: read`.
5. The dependent deployment job requests only `pages: write`, `id-token: write`,
   targets `github-pages`, and waits for any configured environment approval.
   Do not bypass a protection rule. No deploy starts if the build fails.
6. Open the deployment's actual URL and verify the title, all six operations,
   schemas, GitHub links, local asset loading, absence of Try it out/token entry,
   desktop/mobile layout and keyboard focus. Network inspection should show static
   assets/spec only, never Java/FastAPI/model/payment requests.
7. Only after independent public-URL verification, update README's pending label
   through a separately reviewed documentation change. Do not claim deployment
   success merely from the prepared workflow or a successful local build.

The stable URL lasts while the repository/Pages service remains enabled and
available; there is no hosting uptime guarantee. This does not host the PayMesh
application or replace the short-lived authenticated acceptance demo.

## Failure and recovery

- Missing allowlist entry, Pages configuration or environment approval: stop and
  correct that setting only with approval. Do not broaden all-Actions policy or
  disable SHA enforcement to get a green deployment.
- Validation/integrity failure: no deployment job runs. Review contract drift;
  do not remove the checks or manufacture API schemas.
- Build/upload/deployment failure normally leaves the previous Pages deployment
  available. Verify its actual state rather than assuming success or rollback.
- For a bad deployed site, disable only this workflow to prevent new manual
  deployments, or redeploy a reviewed previous documentation revision. Any Pages
  unpublishing/settings change requires separate approval. Application services,
  database records, immutable Docker images and demo workflows are unaffected.
- No deletion, force push, image rebuild, tunnel, paid hosting or model download
  is part of this process.
