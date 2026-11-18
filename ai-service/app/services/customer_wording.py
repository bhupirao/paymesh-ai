"""Presentation of already-validated facts. No arithmetic, access decisions or data reads."""
WORDS={
 'unsupported':'I can explain payment records, but I cannot make payments, issue refunds, change access or share private information. Use the appropriate account action to proceed.',
 'clarify':'Please select a payment or clarify what you would like to know. Finding the latest payment and daily trends is not available in chat yet.',
 'missing_payment':'Please select a payment so I can explain its status, refunds or gateway activity.',
 'refund_unavailable':'Refund history is unavailable, so the refunded total and remaining eligible amount cannot be confirmed.',
 'refund_partial_history':'Available refund entries show {refunded}. The history is incomplete, so the total refunded and remaining eligible amount are unknown.',
 'refund_ineligible':'Available refund entries show {refunded}. This payment is not refund eligible in its recorded status.',
 'refund_none':'No refunds have been recorded for this payment. The total refunded amount is {refunded}, and {remaining} remains potentially eligible for refund, subject to verification.',
 'refund_some':'The total refunded amount is {refunded}. {remaining} remains potentially eligible for refund, subject to verification.',
 'refund_full':'The total refunded amount is {refunded}. No recorded amount remains eligible for another refund.',
 'gateway_missing':'Gateway information is unavailable. I cannot confirm what happened at the gateway.',
 'gateway_empty':'No gateway activity is included in the available records. This does not prove that no activity occurred.',
 'gateway_records':'Recorded gateway activity: {observations}. These records do not confirm bank settlement or explain the underlying cause.',
 'failure':'This payment is recorded as failed. The available records do not establish the reason.',
 'not_failure':'This payment is recorded as {status}. The records do not establish a previous failure or its cause.',
 'processing':'This payment is still processing. A timeout does not mean it failed. Check its status before attempting another payment.',
 'not_processing':'This payment is recorded as {status}, rather than processing. The records do not confirm a previous timeout or recovery.',
 'statistics_missing':'Complete payment and refund totals are unavailable. A few recent records cannot establish the overall totals.',
 'statistics_complete':'Recorded activity: {summary}. Payment and refund totals are separate for each currency; these are not available balances or bank settlements.',
 'statistics_incomplete':'Available activity entries: {summary}. These are partial subtotals, not complete payment or refund totals.',
 'checkout_missing':'Link details are unavailable, so I cannot confirm whether this link can be paid.',
 'checkout':'This payment link is {status}. {detail}',
 'status':'This payment is recorded as {status}. {detail}',
}
STATUS={'CREATED':'created','PROCESSING':'processing','SUCCESS':'successful','FAILED':'failed','CANCELLED':'cancelled','REFUNDED':'fully refunded','ACTIVE':'active','UNCERTAIN':'unresolved','PAID':'paid','EXPIRED':'expired','UNAVAILABLE':'unavailable'}
STATUS_DETAILS={'CREATED':'Processing has not started.','PROCESSING':'The outcome is not yet confirmed; avoid making a duplicate payment.','SUCCESS':'This is a simulated payment record, not confirmation of bank settlement.','FAILED':'The underlying reason is not established.','CANCELLED':'No future payment outcome is guaranteed.','REFUNDED':'Recorded refunds do not confirm that funds have reached the bank.'}
CHECKOUT_DETAILS={'ACTIVE':'Eligibility and expiry must be checked before payment.','PROCESSING':'An attempt is still processing; do not submit another payment.','UNCERTAIN':'The outcome is unknown; check the existing attempt before trying again.','PAID':'It cannot be paid again, even if its payment was later refunded.','FAILED':'Another attempt requires a confirmed failure and fresh eligibility and expiry checks.','EXPIRED':'It cannot accept a new payment.','CANCELLED':'It cannot accept a new payment.','UNAVAILABLE':'Its eligibility for payment is not confirmed.'}
EXPLAIN_SUFFIX=' Recorded information may change; verify current details before taking action.'
def amount(fact):return ('$' if fact.currency=='USD' else '₹')+fact.amount

def customer_answer(req,intent,topic,financial,policies):
 e=req.evidence;p=e.payment if e else None;facts={f.kind:f for f in financial}
 def text(key,**values):return WORDS[key].format(**values)
 if intent=='UNSUPPORTED':return text('unsupported')
 if intent=='INSUFFICIENT_EVIDENCE':return text('clarify')
 if intent=='KNOWLEDGE':return policies[topic][3]
 if intent=='CHECKOUT':
  if not e or not e.checkout:return text('checkout_missing')
  state=e.checkout.status;return text('checkout',status=STATUS[state],detail=CHECKOUT_DETAILS[state])
 if intent=='STATISTICS':
  if not e or e.statistics is None:return text('statistics_missing')
  summary='; '.join(f'{f.currency} {"payments" if f.kind=="PAYMENT_AGGREGATE" else "refunds"}: {f.count}, totalling {amount(f)}' for f in financial)
  return text('statistics_complete' if e.statistics_complete else 'statistics_incomplete',summary=summary or 'no complete totals are available')
 if not p:return text('missing_payment')
 status=STATUS[p.status]
 if intent=='REFUND_SUMMARY':
  total=facts.get('OBSERVED_SUCCESSFUL_REFUNDS');remaining=facts.get('REMAINING_REFUNDABLE')
  if not total:return text('refund_unavailable')
  if not e.refund_history_complete:return text('refund_partial_history',refunded=amount(total))
  if not remaining:return text('refund_ineligible',refunded=amount(total))
  if remaining.amount=='0.00':return text('refund_full',refunded=amount(total))
  return text('refund_none' if total.amount=='0.00' else 'refund_some',refunded=amount(total),remaining=amount(remaining))
 if intent=='GATEWAY':
  if e.gateways is None:return text('gateway_missing')
  if not e.gateways:return text('gateway_empty')
  labels={'MOCK_RAZORPAY':'Simulated Razorpay','MOCK_STRIPE':'Simulated Stripe','MOCK_ROUTER':'Simulated routing'}
  return text('gateway_records',observations=', '.join(labels[g.gateway_name]+' — '+g.status.lower() for g in e.gateways))
 if intent=='PAYMENT_FAILURE':return text('failure') if p.status=='FAILED' else text('not_failure',status=status)
 if intent=='PROCESSING':return text('processing') if p.status=='PROCESSING' else text('not_processing',status=status)
 return text('status',status=status,detail=STATUS_DETAILS[p.status])
