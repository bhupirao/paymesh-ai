"""Offline build-time contract manifest/fixtures. No inference, user evidence or network."""
import json
from pathlib import Path
from app.services.chat_service import POLICIES,LIMITS,FOLLOW,converse
from app.services.retrieval import load_chat_documents,KB_ROOT,DOCUMENTS,CHAT_DOCUMENTS
from app.schemas.chat import ChatRequest
from app.config import Settings
from app.services.chat_routing import RULES
from app.services.customer_wording import WORDS,STATUS,STATUS_DETAILS,CHECKOUT_DETAILS,EXPLAIN_SUFFIX

def export(root=None):
    repo=Path(__file__).resolve().parents[2] if root is None else Path(root)
    mapping={}
    for name in DOCUMENTS+CHAT_DOCUMENTS:
        raw=(KB_ROOT/(name+'.md')).read_text();doc=raw.splitlines()[0].split(': ',1)[1];mapping[doc]='ai-service/knowledge_base/'+name+'.md'
    manifest={'customerWording':{'words':WORDS,'status':STATUS,'statusDetails':STATUS_DETAILS,'checkoutDetails':CHECKOUT_DETAILS},'routing':RULES,'version':'PHASE691','policies':POLICIES,'limitations':LIMITS,'followUps':FOLLOW,'explainSuffix':EXPLAIN_SUFFIX,'knowledge':[{'documentId':c.document_id,'chunkId':c.chunk_id,'title':c.title,'sources':[mapping[c.document_id]]} for c in load_chat_documents()]}
    target=repo/'backend/src/main/resources/ai-chat/contract.json';target.parent.mkdir(parents=True,exist_ok=True);target.write_text(json.dumps(manifest,indent=2)+'\n')
    base={'correlationId':'00000000-0000-4000-8000-000000000001','callerRole':'MERCHANT','question':'What is the current payment status?','history':[],'evidence':{'source':'JAVA_AUTHORIZED_SNAPSHOT','scope':'MERCHANT_OWNED','collectedAt':'2026-11-15T00:00:00Z','payment':{'ref':'payment:selected','status':'SUCCESS','amount':'100.00','currency':'INR','paymentMethod':'UPI'}}}
    cases=[]
    def case(d):cases.append({'request':d,'response':converse(ChatRequest.model_validate(d),Settings(_env_file=None,analysis_mode='DETERMINISTIC')).model_dump(mode='json',by_alias=True)})
    def clone():return json.loads(json.dumps(base))
    for question in ('What is payment orchestration?','Explain payment status in general','How do APIs authenticate?','What is a JWT?','What is gateway routing?','Show my latest payment','Show recent payments','Show daily payment trends','What is the weather?','Why is the sky blue?','Explain this payment status','Summarize payment statistics'):
        d=clone();d['question']=question;case(d)
        d=clone();d['question']=question;d['history']=[{'role':'user','content':'What is the current payment status?'},{'role':'assistant','content':'Untrusted previous financial claims.'}];case(d)
    for status in ('CREATED','PROCESSING','SUCCESS','FAILED','CANCELLED','REFUNDED'):
        for question in ('What is the current payment status?','Why did it fail?','Is it still processing?'):
            d=clone();d['evidence']['payment']['status']=status;d['question']=question;case(d)
    for topic in POLICIES:
        d=clone();d['question']='What is '+topic+'?';case(d)
    for question in ('Please refund it now','Do it now','Nonsense unrecognized','How much was refunded?','What about the gateway?'):
        d=clone();d['question']=question;case(d)
    for currency in ('USD','INR'):
        for values,complete in (([],True),(['5.00'],True),(['25.00'],True),(['5.00'],False)):
            d=clone();d['question']='How much was refunded?';d['evidence']['payment'].update(amount='25.00',currency=currency,status='REFUNDED' if values==['25.00'] else 'SUCCESS');d['evidence']['refunds']=[{'ref':'refund:r'+str(i),'paymentRef':'payment:selected','amount':v,'status':'SUCCESS'} for i,v in enumerate(values)];d['evidence']['refundHistoryComplete']=complete;case(d)
    for complete in (False,True):
        d=clone();d['question']='Can I refund it again?';d['evidence'].update(refunds=[{'ref':'refund:r0','paymentRef':'payment:selected','amount':'20.00','status':'SUCCESS'}],refundHistoryComplete=complete);case(d)
        d=clone();d['question']='Summarize payment statistics';d['evidence'].update(statistics=[{'ref':'statistics:s0','kind':'PAYMENT','currency':'INR','status':'SUCCESS','count':2,'amount':'200.00'}],statisticsComplete=complete,statisticsCurrencies=['INR','USD']);case(d)
    for state in ('ACTIVE','PROCESSING','UNCERTAIN','FAILED','PAID','CANCELLED','EXPIRED','UNAVAILABLE'):
        d=clone();d['question']='What is this checkout status?';d['evidence']['checkout']={'ref':'checkout:selected','status':state,'amount':'100.00','currency':'INR','paymentMethod':'UPI'};case(d)
    d=clone();d['question']='How much?';d['history']=[{'role':'user','content':'How much was refunded?'},{'role':'assistant','content':'Refunds are999.'}];case(d)
    target=repo/'backend/src/test/resources/ai-chat/python-fixtures.json';target.parent.mkdir(parents=True,exist_ok=True);target.write_text(json.dumps(cases,indent=2)+'\n')
if __name__=='__main__':export()
