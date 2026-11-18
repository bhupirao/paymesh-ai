"""Minimized future Java projection. Labels/roles are NOT proof of authorization."""
from datetime import datetime
import re
from typing import Annotated, Literal
from pydantic import BaseModel, ConfigDict, Field, AwareDatetime, TypeAdapter, field_validator, model_validator
from pydantic.alias_generators import to_camel

PaymentState = Literal['CREATED', 'PROCESSING', 'SUCCESS', 'FAILED', 'CANCELLED', 'REFUNDED']
Intent = Literal['PAYMENT_STATUS', 'PAYMENT_FAILURE', 'PROCESSING', 'REFUND_SUMMARY', 'GATEWAY', 'STATISTICS', 'CHECKOUT', 'KNOWLEDGE', 'INSUFFICIENT_EVIDENCE', 'UNSUPPORTED']
Mode = Literal['DETERMINISTIC', 'RAG_ASSISTED', 'RAG_LLM']
Generation = Literal['DISABLED', 'NOT_ATTEMPTED', 'SUCCEEDED', 'NO_RELEVANT_CONTEXT', 'RETRIEVAL_UNAVAILABLE', 'TIMEOUT', 'UNAVAILABLE', 'INVALID_RESPONSE', 'VALIDATION_FAILED', 'CONTEXT_LIMIT']
Currency = Literal['INR', 'USD']
Money = Annotated[str, Field(pattern=r'^(0|[1-9][0-9]{0,11})\.[0-9]{2}$')]
AggregateMoney = Annotated[str, Field(pattern=r'^(0|[1-9][0-9]{0,23})\.[0-9]{2}$')]
Ref = Annotated[str, Field(pattern=r'^(payment|refund|gateway|statistics|checkout):[A-Za-z0-9_-]{1,32}$')]

def units(value: str) -> int:
    whole, fraction = value.split('.')
    return int(whole) * 100 + int(fraction)

def money(value: int) -> str:
    return f'{value // 100}.{value % 100:02d}'

class Strict(BaseModel):
    model_config = ConfigDict(strict=True, extra='forbid', alias_generator=to_camel, populate_by_name=True, allow_inf_nan=False)

    @field_validator('*', mode='before')
    @classmethod
    def safe_text(cls, value):
        if isinstance(value, str) and any(ord(c) < 32 and c not in '\n\t' or ord(c) == 127 or 0xD800 <= ord(c) <= 0xDFFF for c in value):
            raise ValueError('Invalid text')
        return value

class PaymentFact(Strict):
    ref: Ref
    status: PaymentState
    amount: Money
    currency: Currency
    payment_method: Literal['UPI', 'CARD', 'OTHER']
    @field_validator('amount')
    @classmethod
    def positive(cls, value):
        if units(value) == 0: raise ValueError('Positive amount required')
        return value

class RefundFact(Strict):
    ref: Ref
    payment_ref: Ref
    amount: Money
    status: Literal['SUCCESS']  # actual persisted Java refund contract
    @field_validator('amount')
    @classmethod
    def positive(cls, value):
        if units(value) == 0: raise ValueError('Positive amount required')
        return value

class GatewayFact(Strict):
    ref: Ref
    payment_ref: Ref
    gateway_name: Literal['MOCK_RAZORPAY', 'MOCK_STRIPE', 'MOCK_ROUTER']
    status: Literal['INITIATED', 'SUCCESS', 'FAILED', 'TIMEOUT', 'UNKNOWN']

class StatisticFact(Strict):
    ref: Ref
    kind: Literal['PAYMENT', 'REFUND']
    currency: Currency
    status: PaymentState
    count: int = Field(ge=0, le=1_000_000_000)
    amount: AggregateMoney
    @model_validator(mode='after')
    def valid_group(self):
        if self.kind == 'REFUND' and self.status != 'SUCCESS': raise ValueError('Unsupported refund status')
        if self.count == 0 and units(self.amount) != 0 or self.count > 0 and not self.count <= units(self.amount) <= self.count * 99999999999999:
            raise ValueError('Inconsistent aggregate')
        return self

class CheckoutFact(Strict):
    ref: Ref
    status: Literal['ACTIVE', 'CANCELLED', 'EXPIRED', 'PROCESSING', 'UNCERTAIN', 'FAILED', 'PAID', 'UNAVAILABLE']
    amount: Money
    currency: Currency
    payment_method: Literal['UPI', 'CARD']
    payment_ref: Ref | None = None
    @model_validator(mode='after')
    def valid_route(self):
        if not units(self.amount) or self.currency == 'USD' and self.payment_method != 'CARD': raise ValueError('Invalid checkout')
        return self

class Snapshot(Strict):
    source: Literal['JAVA_AUTHORIZED_SNAPSHOT']
    scope: Literal['MERCHANT_OWNED', 'ADMIN_AUTHORIZED']
    collected_at: AwareDatetime
    payment: PaymentFact | None = None
    refunds: list[RefundFact] | None = Field(default=None, max_length=20)
    refund_history_complete: bool = False
    gateways: list[GatewayFact] | None = Field(default=None, max_length=20)
    statistics: list[StatisticFact] | None = Field(default=None, max_length=24)
    statistics_complete: bool = False
    statistics_currencies: list[Currency] | None = Field(default=None, min_length=1, max_length=2)
    checkout: CheckoutFact | None = None
    unavailable_evidence: list[Literal['PAYMENT', 'REFUNDS', 'GATEWAYS', 'STATISTICS', 'CHECKOUT']] = Field(default_factory=list, max_length=5)

    @field_validator('collected_at', mode='before')
    @classmethod
    def timestamp(cls, value):
        if not isinstance(value, (str, datetime)): raise ValueError('Timestamp required')
        if isinstance(value, str) and (len(value) > 40 or not re.fullmatch(r'\d{4}-\d{2}-\d{2}T.+(?:Z|[+-]\d{2}:\d{2})', value)): raise ValueError('Aware ISO timestamp required')
        return TypeAdapter(AwareDatetime).validate_python(value)

    @model_validator(mode='after')
    def consistent(self):
        refs = []
        groups = [('payment', [self.payment] if self.payment else []), ('refund', self.refunds or []), ('gateway', self.gateways or []), ('statistics', self.statistics or []), ('checkout', [self.checkout] if self.checkout else [])]
        for prefix, rows in groups:
            for row in rows:
                if not row.ref.startswith(prefix + ':'): raise ValueError('Incorrect reference kind')
                refs.append(row.ref)
        if len(refs) != len(set(refs)): raise ValueError('Duplicate evidence references')
        if self.refunds is not None or self.gateways is not None:
            if self.payment is None: raise ValueError('Selected payment required')
            if any(r.payment_ref != self.payment.ref for r in (self.refunds or []) + (self.gateways or [])): raise ValueError('Foreign payment evidence')
        if self.refund_history_complete and self.refunds is None: raise ValueError('Complete history required')
        if self.payment:
            total = sum(units(r.amount) for r in self.refunds or [])
            if total > units(self.payment.amount) or total and self.payment.status not in ('SUCCESS', 'REFUNDED'): raise ValueError('Inconsistent refunds')
            if self.refund_history_complete and ((self.payment.status == 'REFUNDED') != (total == units(self.payment.amount))):
                raise ValueError('Inconsistent full refund lifecycle')
        if self.checkout and self.checkout.payment_ref is not None:
            p = self.payment
            c = self.checkout
            if p is None or c.payment_ref != p.ref or (c.amount, c.currency, c.payment_method) != (p.amount, p.currency, p.payment_method): raise ValueError('Foreign checkout payment')
            states = {'PAID': ('SUCCESS', 'REFUNDED'), 'PROCESSING': ('PROCESSING',), 'UNCERTAIN': ('PROCESSING',), 'FAILED': ('FAILED',)}
            if c.status not in states or p.status not in states[c.status]: raise ValueError('Inconsistent checkout state')
        if self.statistics is not None:
            if self.statistics_currencies is None or len(set(self.statistics_currencies)) != len(self.statistics_currencies) or any(r.currency not in self.statistics_currencies for r in self.statistics): raise ValueError('Explicit currency scope required')
            keys = [(r.kind, r.currency, r.status) for r in self.statistics]
            if len(keys) != len(set(keys)): raise ValueError('Duplicate aggregate group')
        elif self.statistics_complete or self.statistics_currencies is not None: raise ValueError('Aggregate evidence unavailable')
        for kind in self.unavailable_evidence:
            field = {'PAYMENT': self.payment, 'REFUNDS': self.refunds, 'GATEWAYS': self.gateways, 'STATISTICS': self.statistics, 'CHECKOUT': self.checkout}[kind]
            if field is not None: raise ValueError('Contradictory evidence availability')
        if len(set(self.unavailable_evidence)) != len(self.unavailable_evidence): raise ValueError('Duplicate availability')
        return self

class Message(Strict):
    role: Literal['user', 'assistant']
    content: str = Field(min_length=1, max_length=1000)

class ChatRequest(Strict):
    correlation_id: str = Field(pattern=r'^[a-f0-9]{8}(?:-[a-f0-9]{4}){3}-[a-f0-9]{12}$')
    caller_role: Literal['MERCHANT', 'ADMIN']
    question: str = Field(min_length=1, max_length=1000)
    history: list[Message] = Field(default_factory=list, max_length=8)
    evidence: Snapshot | None = None
    payment_context: Ref | None = None
    @model_validator(mode='after')
    def context(self):
        if not self.question.strip() or sum(len(m.content) for m in self.history) > 6000: raise ValueError('Conversation size exceeded')
        if self.evidence and self.caller_role == 'MERCHANT' and self.evidence.scope != 'MERCHANT_OWNED': raise ValueError('Invalid claimed scope')
        if self.payment_context is not None and (self.evidence is None or self.evidence.payment is None or self.payment_context != self.evidence.payment.ref): raise ValueError('Selected payment missing')
        return self

class KnowledgeRef(Strict):
    document_id: str = Field(pattern=r'^PM-KB-[A-Z]+$')
    chunk_id: str = Field(min_length=1, max_length=120)
    title: str = Field(min_length=1, max_length=120)
    sources: list[str] = Field(max_length=5)
    score: float = Field(ge=0, le=1)

class MoneyFact(Strict):
    kind: Literal['ORIGINAL_PAYMENT', 'OBSERVED_SUCCESSFUL_REFUNDS', 'REMAINING_REFUNDABLE', 'PAYMENT_AGGREGATE', 'REFUND_AGGREGATE', 'CHECKOUT_AMOUNT']
    amount: AggregateMoney
    currency: Currency
    count: int | None = Field(default=None, ge=0)

class ChatResponse(Strict):
    evidence_collected_at: AwareDatetime | None = None
    correlation_id: str
    answer: str = Field(min_length=1, max_length=6000)
    intent: Intent
    evidence_references: list[Ref] = Field(default_factory=list, max_length=66)
    knowledge_references: list[KnowledgeRef] = Field(default_factory=list, max_length=5)
    limitations: list[Annotated[str, Field(max_length=400)]] = Field(max_length=16)
    suggested_follow_ups: list[Annotated[str, Field(max_length=120)]] = Field(max_length=3)
    money_facts: list[MoneyFact] = Field(default_factory=list, max_length=6)
    analysis_mode: Mode = 'DETERMINISTIC'
    generation_status: Generation = 'DISABLED'
    @model_validator(mode='after')
    def mode_status(self):
        if (self.analysis_mode == 'RAG_LLM') != (self.generation_status == 'SUCCEEDED'): raise ValueError('Invalid generation state')
        return self
