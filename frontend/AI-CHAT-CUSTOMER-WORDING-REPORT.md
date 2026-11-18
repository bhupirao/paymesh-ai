# AI chat customer wording and presentation

Implemented and verified offline on 2026-11-18. Not activated.

## Findings and changes

Python chat uses a finite approved answer set. Java independently reconstructs and validates the exact answer, citations and money facts. Updating Python alone would cause Java to reject the new text. Both formatters and their generated internal manifest now share customer wording; public request/response fields and strict validation remain unchanged. Intent selection, monetary arithmetic, database queries, authorization and payment/refund operations are unchanged.

Answers lead with the requested information. For a USD 25.00 successful payment with complete empty refund history:

> No refunds have been recorded for this payment. The total refunded amount is $0.00, and $25.00 remains potentially eligible for refund, subject to verification.

Incomplete history remains explicitly incomplete, without an authoritative remaining amount. Fully refunded and ineligible payments have separate explanations. Currency symbols prefix the existing exact decimal strings; no new calculation or floating-point conversion is introduced. Statistics keep payment/refund amounts and currencies separate. Status, gateway, checkout and guidance templates use readable wording and retain uncertainty and settlement limitations.

The shared Merchant/Admin/payment-chat renderer displays the answer first. Expandable **Sources and amounts** uses friendly labels and omits duplicate original-payment/link amounts already shown in context. Empty metadata does not produce empty headings/bullets. Text and clipboard actions remain safe; links use the existing authorized payment callback.

Only a current ACTIVE Admin session receives the collapsed **Technical details** presentation, containing intent, mode, generation status, original limitations, aliases, document identifiers and full monetary facts. There is no separate support/technical role in this implementation. This is a presentation gate, not new API field authorization: existing authorized API metadata remains unchanged. Model execution is not presented as proof of correctness.

Saved records are not rewritten. Older answers containing implementation wording show an older-format notice in the normal view, with existing exact amounts still available; their original text remains available to Admins in Technical details. Users may explicitly ask again for fresh wording. No automatic AI call is made.

## Files touched for this change

- `ai-service/app/services/customer_wording.py` — presentation-only approved templates.
- `ai-service/app/services/chat_service.py` — wording integration and guidance text.
- `ai-service/scripts/export_chat_contract.py` — shared wording manifest and refund fixtures.
- `ai-service/tests/test_customer_wording.py`, `ai-service/tests/test_chat.py` — wording, completeness and existing financial/security regressions.
- `backend/src/main/java/com/paymesh/backend/chat/CustomerWording.java`, `ChatRules.java` — independent matching wording validation.
- `backend/src/main/resources/ai-chat/contract.json`, `backend/src/test/resources/ai-chat/python-fixtures.json` — regenerated internal artifacts; 83 synthetic cross-language cases.
- `frontend/assets/js/chat/render.js`, `chat/presentation.js` — shared answer presentation and plain-language notices.
- `frontend/assets/js/merchant-ai/model.js`, `payment-ai/model.js`, `payment-ai/view.js` — customer-facing context/status wording.
- `frontend/assets/js/customer-wording-tests.js`, `merchant-ai-tests.js`, `admin-ai-tests.js`, `payment-ai-tests.js` — presentation regressions.
- This report.

## Actual verification

- Complete Python suite: **454 passed**, including 12 new customer-wording cases. One existing Starlette/httpx deprecation warning.
- Targeted Java `ChatContractTest,AiChatClientTest`: **8 passed**, including 83 synthetic Python/Java answer comparisons and mocked transport. Temporary mock listeners required sandbox permission; no live database or inference was used. Full isolated Java suite was not rerun.
- All 20 JavaScript suites with the existing offline mock DOM: **1,563 assertions passed**, including 15 new customer-presentation assertions. These are not native browser/layout checks.
- Frontend proxy/security suite: **57 tests passed**.
- Total frontend checks newly executed: **1,620**.
- Python and JavaScript syntax checks and `git diff --check`: passed.
- Git index checksums changed concurrently during verification. No staging, reset, restore, commit or other index write was performed by this work; external changes were left untouched.

## Activation and remaining verification

Running services use the frozen release, not these workspace edits. A browser hard refresh alone cannot deploy this change. With separate operator approval, prepare a matched Java/Python release containing the updated wording manifest, build/test the Java artifact, and use the reviewed guarded activation procedure. Update the frozen frontend assets through its approved deployment/reload procedure as well. Preserve current disabled Flyway/demo-simulation settings and all protected configuration. Do not reuse old source pins for modified code.

After activation, manually verify Merchant/Admin/payment chat, complete and incomplete refund answers, separate INR/USD figures, Admin-only Technical details, saved older answers, copy/follow-up actions and mobile layout. Existing live verification gaps remain open. No restart, inference, login, database operation or saved-conversation modification was performed here.
