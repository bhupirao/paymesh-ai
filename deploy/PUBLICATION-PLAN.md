# Publication gates and proposed commits

No staging operation or publication was performed. `origin` is now configured to
https://github.com/bhupirao/paymesh-ai.git; the source checkout remains on unborn
`main`. An isolated, reviewed initial commit is prepared separately to preserve
the existing mixed staging. Docker Hub namespace is `bhupirao`.
Do not silently create a new GitHub repository or use a guessed account.

Proposed focused commits AFTER explicit staging approval:

1. `Import verified PayMesh application and phase documentation` — review the
   existing application staging AND all unstaged corrections together; the current
   index contains earlier versions of several modified files. Do not commit the
   existing index blindly. Exclude protected operational data and sanitize reports
   before public release. No history exists here to rewrite.
2. `Add isolated amd64 container stack and manual image publication` — root
   `.dockerignore`, container ignore additions in `.gitignore`, all `deploy/` files,
   and `.github/workflows/container-images.yml`. Existing unrelated CI/staging is
   preserved. Show the exact final file list and destination branch before committing
   or pushing. Do not use `git add .` against this mixed workspace.

Proposed Docker Hub repositories (namespace confirmed as bhupirao):

- bhupirao/paymesh-java:v1.0.0
- bhupirao/paymesh-python:v1.0.0
- bhupirao/paymesh-frontend:v1.0.0
- bhupirao/paymesh-llama:v1.0.0

Review repository visibility explicitly. No database data, accounts, model weights,
backups, keys or private runtime configuration are image contents. PostgreSQL is the
upstream `postgres:16.16-bookworm` image, not an uploaded PayMesh database image.

Remote builds: manually dispatch `container-images.yml` with publication OFF first.
It validates Compose through the real Docker plugin on the runner, builds four
amd64 images sequentially and checks architecture. No model weights are downloaded.
This is image-build validation, NOT application E2E. Before publication configure
GitHub environment `dockerhub-publication` with required reviewers and restrict it
to the approved branch. Set DOCKERHUB_USERNAME and a scoped DOCKERHUB_TOKEN as
protected environment secrets, never workflow inputs. Protected reviewers must
verify the selected source revision, namespace, exact tags and actual disposable
E2E results. The manual publish flag plus E2E acknowledgement is not itself proof
of test execution. Workflow cannot push Git changes and does not auto-run on push.
Third-party action major tags should be replaced with reviewed commit pins before
security-sensitive public production use.

Local publication scan is heuristic, not certification. It checks excluded artifact
paths, oversized files and key/token patterns without printing values. Earlier
working-tree findings included three literal private-key delimiters: two Java tests
encode generated in-memory keys, and a scanner unit test supplies only the delimiter.
The staged blob check found the same two Java helper delimiters. No static private-key
payload was established by those findings. Review these findings and any new scan
results; do not bypass a genuine credential finding. No indexed file exceeded 10 MiB.
