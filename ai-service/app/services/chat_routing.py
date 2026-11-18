"""Bounded phrase/frame routing, independent of model output and financial authorization.

A decision's confidence is categorical rule specificity, never a probability. History
is consulted only for an exact elliptical follow-up and only its nearest user turn.
Unknown, conflicting and unsupported retrieval requests fail to clarification.
"""
import json
import re
from dataclasses import dataclass
from pathlib import Path
RULES=json.loads(Path(__file__).with_name('chat_routing.json').read_text())

@dataclass(frozen=True)
class Decision:
    intent: str
    topic: str
    confidence: str
    reason: str

def decide(question, history=(), payment_status=None):
    q=question.lower().strip()
    match=lambda pattern:bool(re.search(pattern,q))
    concept=match(RULES['concept']) and not match(RULES['personal'])
    # Authorization/action boundaries are independent of topic recognition.
    if match(r'ignore.{0,40}(instructions|rules|previous)|system prompt|developer prompt|\b(password|secret|cvv|otp|sql|shell)\b|other merchant|another merchant|\b(select|drop|delete)\s+.*\b(from|table)\b') or match(r'^(please\s+)?(refund|pay|charge|process|create|cancel|approve|suspend|execute|run|transfer|delete|update)\b|\b(do it now|refund it now|make a payment)\b') or match(r'\b(i want you to|can you|could you|would you)\s+(please\s+)?(refund|pay|process|create|cancel|transfer|execute)\b') or match(r'\b[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}\b'):
        return Decision('UNSUPPORTED','lifecycle','HIGH','SAFETY_BOUNDARY')
    if match(RULES['unsupportedQuery']):
        return Decision('INSUFFICIENT_EVIDENCE','lifecycle','NONE','UNSUPPORTED_RETRIEVAL')
    candidates=[(topic,intent) for topic,intent,pattern in RULES['topics'] if match(pattern)]
    # Generic payment/status mentions cannot override a specific domain topic.
    if len(candidates)>1:
        candidates=[c for c in candidates if c[0]!='lifecycle'] or candidates
    # A timeout is a specific gateway outcome; refund/gateway language identifies scope.
    if any(t=='timeout' for t,_ in candidates):candidates=[c for c in candidates if c[0]!='routing']
    if any(t=='refunds' for t,_ in candidates):candidates=[c for c in candidates if c[0] not in ('failure','statistics')]
    if any(t=='api' for t,_ in candidates) and any(t=='security' for t,_ in candidates):candidates=[c for c in candidates if c[0]!='api']
    if ('lifecycle','PAYMENT_STATUS') in candidates:candidates=[c for c in candidates if c!=('lifecycle','KNOWLEDGE')]
    candidates=list(dict.fromkeys(candidates))
    if re.fullmatch(RULES['follow'],q):
        prior=next((m for m in reversed(history) if m.role=='user'),None)
        previous=decide(prior.content) if prior else None
        if not candidates and previous and previous.intent not in ('UNSUPPORTED','INSUFFICIENT_EVIDENCE'):
            if q.startswith('why') and payment_status and previous.intent not in ('KNOWLEDGE','STATISTICS','CHECKOUT'):
                return Decision('PAYMENT_FAILURE' if payment_status=='FAILED' else 'PROCESSING' if payment_status=='PROCESSING' else 'PAYMENT_STATUS','failure' if payment_status=='FAILED' else 'timeout' if payment_status=='PROCESSING' else 'lifecycle','CONTEXTUAL','EXPLICIT_FOLLOW_UP')
            return Decision(previous.intent,previous.topic,'CONTEXTUAL','EXPLICIT_FOLLOW_UP')
    if len(candidates)!=1:return Decision('INSUFFICIENT_EVIDENCE','lifecycle','NONE','AMBIGUOUS_OR_UNKNOWN')
    topic,intent=candidates[0]
    if concept:intent='KNOWLEDGE'
    elif intent=='KNOWLEDGE' and topic=='lifecycle':return Decision('INSUFFICIENT_EVIDENCE','lifecycle','NONE','MISSING_QUESTION_SCOPE')
    return Decision(intent,topic,'HIGH' if concept or match(RULES['personal']) else 'BOUNDED','EXPLICIT_CONCEPT' if concept else 'DOMAIN_REQUEST')
