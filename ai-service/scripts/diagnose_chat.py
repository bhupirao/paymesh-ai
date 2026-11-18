"""OPT-IN synthetic knowledge-only inference. Never reads accounts/evidence or starts a server."""
import argparse
import json
from uuid import uuid4
from app.config import Settings
from app.schemas.chat import ChatRequest
from app.services.chat_service import converse


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--confirm-local-inference', action='store_true')
    args=parser.parse_args()
    if not args.confirm_local_inference:
        parser.error('Explicit --confirm-local-inference required; no request was made')
    config=Settings(_env_file=None,analysis_mode='RAG_LLM',generation_enabled=True,
                    inference_url='http://127.0.0.1:8082/v1/chat/completions',model_name='paymesh-qwen',
                    generation_timeout=15,max_output_tokens=128)
    # MERCHANT is a schema label here, not a claim that an account was authenticated.
    request=ChatRequest(correlation_id=str(uuid4()),caller_role='MERCHANT',question='What is idempotency?')
    result=converse(request,config)
    print(json.dumps({'syntheticKnowledgeOnly':True,'intent':result.intent,'analysisMode':result.analysis_mode,
                      'generationStatus':result.generation_status,'knowledgeReferenceCount':len(result.knowledge_references),
                      'financialFactsAbsent':not result.money_facts}))
    return 0 if result.generation_status=='SUCCEEDED' else 1

if __name__=='__main__':raise SystemExit(main())
