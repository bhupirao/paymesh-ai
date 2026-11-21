# Candidate Chromium checkout failure audit and test correction

## Evidence and confirmed cause

Failed run: [44872953666](https://github.com/bhupirao/paymesh-ai/actions/runs/44872953666), workflow commit85de5b8302c3417be003ef8556fa52bcce32a743; frontend sourcea4171a5c090224622d584d45caa0d06e7997be9b. Sanitized stdout and artifact agree: line168, PAYMENT_LINK_AND_CUSTOMER_CHECKOUT, action timeout15s, elapsed162254ms, Chromium succeeded, last completed action PORTAL_NAVIGATION. Candidate image/config/source identity and all five health checks passed. Container/volume and candidate-image cleanup passed.

Exact original statement:

```js
await root.getByLabel('Currency',{exact:true}).selectOption('USD');
```

CONFIRMED test defect: the actual field builder creates a label containing both text and a select with option text. For currency the label text is `CurrencyINRUSD`; for payment method it is `Payment methodUPICARD` (or `Payment methodCARD` after changing currency). Exact bare-label matching cannot select these controls.

This was checked against the exact locked playwright-core1.65.1 npm source archive, verified against package-lock's SHA-512 integrity before inspection. Its getElementLabels uses elementText over the label's descendants, including options; internal exact text matching compares the normalized full string. An isolated, non-browser execution of those actual selector functions rejects both original bare labels. The production frontend field builder is also exercised by a portable offline regression. No Playwright package/browser was installed, and no third-party source was added to the repository.

The main-tag GitHub source endpoint for this version was unavailable; the integrity-verified locked npm package, not a guessed source version, was used. This is a source/selector reproduction, not a retained live DOM snapshot.

The next Payment method exact-label selector had the same demonstrated defect and is corrected together. No timeout increase, retry or production UI modification is needed.

The link POST sits later in the source and was never reached. Thus201 does not prove payment-link creation, checkout submission or customer payment. The last awaited response observation before navigation is the final successful refund201. The old artifact records only the status, not an endpoint identity; no wire-level request identifier is claimed. Navigation itself completed its expected create-route assertion. The new first checkpoint also verifies that the visible create form, rather than the list filter, is present.

## Test-side corrections

- Scope currency and method to the actual `select[name="currency"]` and `select[name="paymentMethod"]` controls inside the links workspace. Assert create-form visibility and selected USD/CARD values. Existing Amount/customer-reference entry and review/confirmation remain.
- Capture and validate the201 link response, then open its generated same-origin token URL in the existing unauthenticated customer context.
- Wait for the real native checkout status GET; require an active25.00 USD/CARD checkout, and assert the fixed method is visibly displayed.
- Preserve review/back/review/explicit confirmation and the200 PAID response/receipt. Receipt reload waits for the actual status response and confirms PAID without another pay request.
- Add real Merchant UI readback: Refresh link → PAID, Open authorized payment → SUCCESS, matching payment details and enabled refund input with25.00 USD displayed. These are reads, not another refund or financial mutation. Final fixture counts remain two payments, two refunds, one link/attempt and zero retained test conversations.
- Keep all existing conversation, refresh, role-isolation, model-success and logout assertions. Add action-scoped safe context to AI/history/refresh/logout failures; no unsupported success is substituted.

## Actual checkout contract

The requested conceptual flow needs two distinctions: creating a payment is not required before creating a link, and the customer does not freely select a payment method on public checkout. The link fixes that method.

| Operation | Actual UI/API contract | Status/evidence |
|---|---|---|
| Earlier payment exercise | Merchant creates/processes13.25 INR and refunds it3.25 +10.00 before the checkout stage | Passed natively in this run; separate payment from checkout |
| Create link | Merchant create route, named currency/amount/method fields, Review link, Confirm create payment link; POST `/api/v1/merchant/payment-links`, Idempotency-Key, amount/currency/paymentMethod/customerReference/description/expiryHours |201 new link,200 replay; creates no payment yet; fresh suite requires201 |
| Share/open | Read-only generated checkout URL; same-origin `/checkout/{43-character-token}` | Only anonymous browser navigation; raw URL never retained |
| Checkout read | GET `/api/v1/checkout/{token}/status`, no cookies/bearer; exact amount string, currency, fixed method, canPay and status |200 ACTIVE initially; no customer method-selector assumption |
| Consent | Pay — review simulated payment, focused confirmation, Back to checkout, repeat review, Confirm Pay | UI required; no direct API replacement |
| Execution | POST checkout pay, `{confirmed:true}`, Idempotency-Key and X-PayMesh-Checkout; proxy/backend origin restrictions remain |200 PAID expected for successful mock payment;202 uncertain/processing would fail this success scenario |
| Payment association | Checkout execution creates a new payment/attempt; Merchant Refresh link exposes paymentId and PAID | Public receipt does not need to reveal the private payment UUID |
| Merchant verification | Open authorized payment, GET payment, details/refund history loaded through ordinary UI | SUCCESS,25.00 USD, refund eligible; no extra refund submitted |
| Money parsing | Link/checkout amounts are strings; PaymentResponse amount is BigDecimal JSON numeric, normalized losslessly by the real frontend client | Synthetic browser readback uses existing exactAmount normalization, no arithmetic; displayed25.00 USD also asserted |
| Authorization | Merchant-owned link creation/read; anonymous bearerless token checkout; fixed-origin/CSRF/idempotency and role checks | Unchanged production implementation |

The inspected frontend modules match the pinned candidate source. Java PaymentLinkController, CheckoutController, PaymentLinks, CheckoutTransactions and PaymentResponse match the published backend application revisioncefa7df83a5bf16d011e82041c95e2d93b9c637b. Python/Qwen contracts and all image locks are unchanged.

## Remaining journey: native evidence versus audit

| Stage | Result and remaining uncertainty |
|---|---|
| Desktop/mobile validation | Both passed natively in44872953666 |
| Registration/pending account/logout | Passed natively |
| Admin login/search/approval | Passed natively; pacing worked for these requests |
| Dashboard refresh/role protection | Passed natively |
| Payment processing/list and Merchant A/B denial | Passed natively |
| AI investigation | Passed natively in12.564s through strict RAG_LLM/SUCCEEDED/knowledge-reference assertions |
| Partial/full refund | Passed natively; total13.25 INR and zero remaining asserted |
| Link create selectors | Both source-confirmed defects fixed; new actual execution needed |
| Customer checkout/receipt and Merchant readback | Source contracts match; not reached previously; runtime UNKNOWN |
| Merchant/Admin chat | Native send controls, correct saved-message route/response structure, strict modelSuccess retained; runtime UNKNOWN |
| Saved list/load/rename/delete | Existing declared labels are text-input labels, not select-option labels; expectedVersion and owner/role handling retained; runtime UNKNOWN |
| Bookmark/refresh restoration | Existing source-pinned bootstrap fix and automatic URL/answer assertions retained; offline bootstrap13cases pass; full native saved-answer refresh UNKNOWN |
| Logout/cross-tab/protected routes | Existing session and BroadcastChannel behavior/assertions retained; final-stage runtime UNKNOWN |
| Cleanup | Latest actual run confirms scoped containers/volumes and candidate build resources removed |

The old aggregate modelInferenceVerified=false is truthful because Merchant/Admin chat did not run; it does not negate the separately passed investigation-model stage. No additional production defect is demonstrated by this checkout timeout. No new frontend image/source revision is needed for these test-side selector corrections; the existing candidate workflow can rebuild its unchanged approved frontend source.

## Diagnostics and attribution

New fixed action codes cover create-form readiness, currency/method selection, review, customer navigation, payment consent/receipt and Merchant readback. Reporter output retains source basename/line, pending and completed action codes, expected UI category, actual route category, scoped HTTP endpoint category and last relevant numeric status.

Only allowlisted categories enter evidence. Checkout URLs become PUBLIC_CHECKOUT; tokens, queries, hashes, resource IDs, credentials, cookies, prompts, answers and raw errors are never serialized. The status is considered relevant only when a response observer resolves for the active checkpoint's expected endpoint category. A selector failure before any corresponding request yields lastRelevantHttpStatus=null, even if lastObservedHttpStatus remains201 from an earlier operation. Unknown/malformed or mismatched context is discarded. This is UI/test attribution, not a distributed trace or a new application response contract.

## Real execution strategy and approval boundary

The existing manual Candidate frontend Chromium E2E workflow already supplies a disposable Linux runner, the corrected frontend source, three immutable backend images, synthetic credentials, fresh PostgreSQL, real Qwen and guarded cleanup. No local Docker/browser/model execution is needed.

After separately approved commit/push, propose one new full workflow run on that new main revision. Keep its frontend source pin, all three tests, one worker, zero retries and every browser stage. Do not use grep/skip to bypass the user/approval prerequisites or the remaining journey. The full run is the focused reproduction: it reaches the corrected link controls after the same verified setup, exercises actual checkout, then continues to chat/history/refresh/logout. No workflow dispatch is authorized by this patch.

One run is justified by the two reproducible selector fixes and the completed remaining-contract audit. Its success is not guaranteed by offline results. Further runtime failures must be interpreted from the new safe action/route/endpoint evidence, not guessed from old status201.

## Verification results

- 194 deployment tests passed, including three new checkout policy checks; unchanged Java limiter checks remain included.
- 57 browser helper/reporter tests passed, including six new field/route/correlation/malformed-diagnostic/money-contract tests.
- 13 bootstrap integration cases passed.
- 20 existing frontend JS suites passed 1,563 assertions; full frontend/proxy discovery passed 59 tests using isolated mock listeners.
- Syntax, YAML/JSON, targeted secret checks, protected release/workflow fingerprints and git diff --check passed.

These are offline counts, not new native browser results. No Java/Python application implementation changed, so their complete suites were not rerun. No commit, push, dispatch, image build/publication, local Docker, model download or live financial/account/conversation operation occurred. The locked Playwright source archive was read only for diagnosis and was not installed or committed.
