"""Pure snapshot analysis: no network, storage, or financial actions."""
from datetime import datetime, timezone
from decimal import Decimal
from uuid import uuid4
from app.schemas.investigation import InvestigationRequest, InvestigationResponse, CustomerView, TechnicalView


def investigate(e: InvestigationRequest) -> InvestigationResponse:
    refs = ["paymentStatus", "amount", "currency", "collectedAt"]
    limits = ["Supplied evidence is not authenticated or fetched from Java.", "Snapshot analysis cannot verify bank debit, settlement, or refund arrival."]
    for field, alias in (("gateway_transactions", "gatewayTransactions"), ("refunds", "refunds"), ("webhooks", "webhooks"), ("reconciliation", "reconciliation")):
        rows = getattr(e, field)
        if rows is None:
            limits.append(f"{alias} evidence is unavailable; absence does not prove no event occurred.")
        else:
            refs.extend(f"{alias}[{i}]" for i in range(len(rows)))
    gateways = e.gateway_transactions or []
    statuses = {g.status for g in gateways}
    total = sum((r.amount for r in e.refunds or []), Decimal(0))
    scenario = "INCONCLUSIVE"
    summary = "The supplied evidence does not establish a consistent payment outcome."
    detail = "Review the current payment status with authorized support."
    action = "Review the payment status or contact authorized support before making another payment or refund."
    certainty = "INCONCLUSIVE"
    requires = True
    conflict = (
        len(statuses & {"SUCCESS", "FAILED"}) > 1
        or (e.payment_status in {"SUCCESS", "REFUNDED"} and bool(statuses - {"SUCCESS"}))
        or (e.payment_status == "FAILED" and bool(statuses - {"FAILED"}))
        or (e.payment_status == "CREATED" and bool(gateways))
        or (e.payment_status == "PROCESSING" and bool(statuses & {"SUCCESS", "FAILED"}))
        or (total > 0 and e.payment_status not in {"SUCCESS", "REFUNDED"})
        or (total == e.amount and e.payment_status != "REFUNDED")
        or any(w.status == "PROCESSED" and w.outcome in {"SUCCESS", "FAILED"} and w.outcome != ("SUCCESS" if e.payment_status == "REFUNDED" else e.payment_status) for w in e.webhooks or [])
        or any(r.result == "RESOLVED" and (r.outcome != r.status_after or r.status_before != "PROCESSING" or r.status_after != ("SUCCESS" if e.payment_status == "REFUNDED" else e.payment_status)) for r in e.reconciliation or [])
    )
    if conflict:
        detail = "Supplied lifecycle or financial evidence conflicts; no definitive outcome inferred."
    elif e.payment_status == "REFUNDED" and total != e.amount:
        scenario = "UNRESOLVED_REFUND"
        summary = "Your payment is marked refunded, but the supplied refund records are incomplete."
        detail = "A full successful refund total is required to corroborate REFUNDED."
    elif total:
        scenario = "FULL_REFUND" if total == e.amount else "PARTIAL_REFUND"
        summary = ("The refund was recorded as successful in the simulated payment system." if scenario == "FULL_REFUND" else "A partial refund was recorded as successful in the simulated payment system.")
        detail = f"Original amount: {e.amount:.2f} {e.currency}; successful refunds: {total:.2f}; remaining amount: {e.amount-total:.2f}. This does not confirm bank arrival."
        certainty = "CONFIRMED"
        action = "Review the refund record; contact authorized support if you need help."
        requires = False
    elif e.payment_status == "SUCCESS":
        scenario, certainty = "SUCCESS", "CONFIRMED"
        summary = "Your payment was completed successfully. You do not need to pay again."
        detail = "Payment snapshot records SUCCESS; no historical timeout is inferred."
        for w in e.webhooks or []:
            if w.status == "PROCESSED" and w.outcome == "SUCCESS" and any(g.gateway_transaction_id == w.gateway_transaction_id and g.status == "SUCCESS" and w.occurred_at >= g.created_at for g in gateways):
                scenario = "WEBHOOK_RECOVERY"
                detail = "A matching processed SUCCESS webhook supports confirmation through webhook recovery; it does not establish a previous timeout."
                break
        if scenario == "SUCCESS" and any(r.result == "RESOLVED" and r.status_before == "PROCESSING" and r.status_after == "SUCCESS" and r.outcome == "SUCCESS" for r in e.reconciliation or []):
            scenario = "RECONCILIATION_RECOVERY"
            detail = "Reconciliation audit records PROCESSING to SUCCESS, supporting delayed confirmation through reconciliation."
        if scenario != "SUCCESS":
            summary += " Confirmation was completed through " + ("a webhook." if scenario == "WEBHOOK_RECOVERY" else "reconciliation.")
        action, requires = "No further payment is needed.", False
    elif e.payment_status == "CREATED":
        scenario, certainty = "CREATED", "CONFIRMED"
        summary = "Your payment has been created but has not been processed yet."
        detail = "The supplied payment status is CREATED."
        action, requires = "Check the payment status or contact authorized support.", False
    elif e.payment_status == "PROCESSING":
        scenario = "GATEWAY_TIMEOUT" if "TIMEOUT" in statuses else "PROCESSING"
        certainty = "CONFIRMED"
        summary = "Your payment is taking longer than expected. Please wait for confirmation before making another payment."
        detail = "No final outcome is confirmed." + (" The gateway snapshot records TIMEOUT; this is not proof of failure." if scenario == "GATEWAY_TIMEOUT" else " The payment is PROCESSING.")
        action, requires = "Wait for confirmation; contact authorized support if the status remains unresolved.", False
    elif e.payment_status == "FAILED":
        scenario, certainty = "FAILED", "CONFIRMED"
        reasons = {"UNSUPPORTED_CURRENCY": "The simulated gateway does not support this currency.", "INVALID_AMOUNT": "The simulated gateway rejected the amount."}
        reason = next((reasons[g.error_code] for g in gateways if g.status == "FAILED" and g.error_code in reasons), "The exact reason could not be determined from the supplied evidence.")
        summary = "Your payment was marked as failed. " + reason
        detail = reason + " No bank debit outcome is established."
        if reason.startswith("The exact"):
            certainty = "INCONCLUSIVE"
    # Separate confirmed snapshot observations from root-cause inference.
    cause = "The underlying cause could not be determined from the supplied evidence."
    cause_certainty = "INCONCLUSIVE"
    if scenario == "FAILED" and not reason.startswith("The exact"):
        cause, cause_certainty = reason, "CONFIRMED"
    title = scenario.replace("_", " ").title()
    customer_detail = summary
    if scenario in {"PROCESSING", "GATEWAY_TIMEOUT"}:
        title = "Your payment is still being processed"
        customer_detail = "We are still waiting for the final payment confirmation."
        action = "Please wait for an update. If your payment remains unresolved, contact support."
    elif scenario == "CREATED":
        title = "Your payment has been created"
        customer_detail = "Your payment is waiting to be processed."
    elif scenario in {"SUCCESS", "WEBHOOK_RECOVERY", "RECONCILIATION_RECOVERY"}:
        title = "Your payment was successful"
        customer_detail = "Your payment has been confirmed."
        if scenario != "SUCCESS":
            summary = "Your payment was completed successfully. You do not need to pay again. Confirmation arrived after an additional check."
            customer_detail = "Your payment was confirmed after an additional check."
    elif scenario == "UNRESOLVED_REFUND":
        title = "Your refund needs a review"
        customer_detail = "We need more refund information to confirm the full amount."
    elif scenario in {"PARTIAL_REFUND", "FULL_REFUND"}:
        customer_detail = detail
    elif scenario == "INCONCLUSIVE":
        title = "Your payment needs a review"
        customer_detail = "There is not enough consistent information to confirm what happened."
    return InvestigationResponse(
        investigation_id=uuid4(), payment_id=e.payment_id,
        investigation_status="INCONCLUSIVE" if certainty == "INCONCLUSIVE" else "COMPLETED",
        scenario=scenario, generated_at=datetime.now(timezone.utc),
        customer_view=CustomerView(title=title, summary=summary, what_happened=customer_detail, next_action=action, requires_user_action=requires),
        technical_view=TechnicalView(observed_payment_status=e.payment_status, root_cause=cause, root_cause_certainty=cause_certainty, supporting_evidence=refs, technical_explanation=detail, recommended_actions=[action], certainty=certainty),
        evidence_references=refs, limitations=limits)
