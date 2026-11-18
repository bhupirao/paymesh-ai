import pytest
from tests.test_chat import data,answer,refunds
@pytest.mark.parametrize('currency,symbol',[('USD','$'),('INR','₹')])
def test_zero_refunds_answer_question_first_with_exact_amounts(data,currency,symbol):
 data['evidence']['payment'].update(amount='25.00',currency=currency)
 r=answer(refunds(data,()))
 assert r.answer==f'No refunds have been recorded for this payment. The total refunded amount is {symbol}0.00, and {symbol}25.00 remains potentially eligible for refund, subject to verification.'
 assert [(f.kind,f.amount) for f in r.money_facts][-2:]==[('OBSERVED_SUCCESSFUL_REFUNDS','0.00'),('REMAINING_REFUNDABLE','25.00')]
@pytest.mark.parametrize('values,complete,status,phrase',[(('20.00',),True,'SUCCESS','potentially eligible'),(('20.00',),False,'SUCCESS','unknown'),(('100.00',),True,'REFUNDED','No recorded amount remains'),((),True,'CREATED','not refund eligible')])
def test_refund_eligibility_and_completeness_preserved(data,values,complete,status,phrase):
 data['evidence']['payment']['status']=status;r=answer(refunds(data,values,complete));assert phrase in r.answer
 assert not any(word in r.answer for word in ('Java','Python','RAG','LLM','REFUND_SUMMARY','deterministic'))
@pytest.mark.parametrize('question',['What is idempotency?','What is authorization?','What is this payment status?','Explain this gateway','How does checkout work?','Show my latest payment'])
def test_normal_answers_do_not_expose_implementation(data,question):
 data['question']=question;r=answer(data)
 assert not any(word in r.answer for word in ('Java','Python','RAG','LLM','snapshot','REFUND_SUMMARY','authorized Java'))
