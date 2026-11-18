from decimal import Decimal
from enum import StrEnum
from typing import Annotated, Literal
from uuid import UUID
from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, field_validator, model_validator
from pydantic.alias_generators import to_camel


class Model(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True, extra="forbid", str_strip_whitespace=True)


class PaymentStatus(StrEnum):
    CREATED = "CREATED"
    PROCESSING = "PROCESSING"
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"
    REFUNDED = "REFUNDED"


Money = Annotated[Decimal, Field(gt=0, max_digits=19, decimal_places=2)]
Short = Annotated[str, Field(min_length=1, max_length=100)]


class Gateway(Model):
    id: UUID
    payment_id: UUID
    gateway_name: Short
    gateway_transaction_id: UUID | None = None
    status: Literal["SUCCESS", "FAILED", "TIMEOUT"]
    error_code: Annotated[str, Field(max_length=100)] | None = None
    error_message: Annotated[str, Field(max_length=512)] | None = None
    created_at: AwareDatetime
    updated_at: AwareDatetime


class Refund(Model):
    refund_id: UUID
    payment_id: UUID
    amount: Money
    status: Literal["SUCCESS"]
    created_at: AwareDatetime

    @field_validator("amount", mode="before")
    @classmethod
    def no_float(cls, value):
        if isinstance(value, (float, bool)):
            raise ValueError("Send money as a decimal string or integer")
        return value


class Webhook(Model):
    id: UUID
    payment_id: UUID
    status: Literal["RECEIVED", "PROCESSED", "IGNORED", "DEFERRED", "FAILED"]
    # Projected from the parsed payload, never the raw payload or headers.
    gateway_transaction_id: UUID
    outcome: Literal["SUCCESS", "FAILED", "TIMEOUT", "UNKNOWN"]
    occurred_at: AwareDatetime


class Reconciliation(Model):
    id: UUID
    payment_id: UUID
    outcome: Literal["SUCCESS", "FAILED", "TIMEOUT", "UNKNOWN"] | None = None
    status_before: PaymentStatus
    status_after: PaymentStatus
    result: Literal["RESOLVED", "RETRY", "EXHAUSTED", "SKIPPED"]
    created_at: AwareDatetime


class InvestigationRequest(Model):
    payment_id: UUID
    amount: Annotated[Decimal, Field(gt=0, max_digits=14, decimal_places=2)]
    currency: Annotated[str, Field(pattern=r"^[A-Z]{3}$")]
    payment_status: PaymentStatus
    payment_method: Short
    gateway_transactions: Annotated[list[Gateway], Field(max_length=100)] | None = None
    refunds: Annotated[list[Refund], Field(max_length=100)] | None = None
    webhooks: Annotated[list[Webhook], Field(max_length=100)] | None = None
    reconciliation: Annotated[list[Reconciliation], Field(max_length=100)] | None = None
    collected_at: AwareDatetime

    @field_validator("amount", mode="before")
    @classmethod
    def no_float(cls, value):
        if isinstance(value, (float, bool)):
            raise ValueError("Send money as a decimal string or integer")
        return value

    @model_validator(mode="after")
    def consistent_snapshot(self):
        for name, key in (("gateway_transactions", "id"), ("refunds", "refund_id"), ("webhooks", "id"), ("reconciliation", "id")):
            rows = getattr(self, name) or []
            if len({getattr(r, key) for r in rows}) != len(rows):
                raise ValueError("Duplicate evidence IDs")
            for row in rows:
                if row.payment_id != self.payment_id:
                    raise ValueError("Evidence belongs to another payment")
                for attr in ("created_at", "updated_at", "occurred_at"):
                    timestamp = getattr(row, attr, None)
                    if timestamp and timestamp > self.collected_at:
                        raise ValueError("Evidence postdates collection")
                if isinstance(row, Gateway) and row.updated_at < row.created_at:
                    raise ValueError("Gateway update predates creation")
        if sum((r.amount for r in self.refunds or []), Decimal(0)) > self.amount:
            raise ValueError("Successful refunds exceed payment amount")
        return self


class CustomerView(Model):
    title: str
    summary: str
    what_happened: str
    next_action: str
    requires_user_action: bool


class TechnicalView(Model):
    observed_payment_status: PaymentStatus
    root_cause: str
    root_cause_certainty: Literal["CONFIRMED", "LIKELY", "INCONCLUSIVE"] = "INCONCLUSIVE"
    supporting_evidence: list[str]
    technical_explanation: str
    recommended_actions: list[str]
    certainty: Literal["CONFIRMED", "LIKELY", "INCONCLUSIVE"]


class KnowledgeReference(Model):
    document_id: str
    chunk_id: str
    title: str
    sources: list[str]
    score: float


class InvestigationResponse(Model):
    investigation_id: UUID
    payment_id: UUID
    investigation_status: Literal["COMPLETED", "INCONCLUSIVE"]
    scenario: Literal["CREATED", "PROCESSING", "GATEWAY_TIMEOUT", "SUCCESS", "WEBHOOK_RECOVERY", "RECONCILIATION_RECOVERY", "FAILED", "PARTIAL_REFUND", "FULL_REFUND", "UNRESOLVED_REFUND", "INCONCLUSIVE"]
    generated_at: AwareDatetime
    customer_view: CustomerView
    technical_view: TechnicalView
    evidence_references: list[str]
    limitations: list[str]
    analysis_mode: Literal["DETERMINISTIC", "RAG_ASSISTED", "RAG_LLM"] = "DETERMINISTIC"
    knowledge_references: list[KnowledgeReference] = Field(default_factory=list)
    generation_status: Literal["DISABLED", "NOT_ATTEMPTED", "SUCCEEDED", "NO_RELEVANT_CONTEXT", "RETRIEVAL_UNAVAILABLE", "TIMEOUT", "UNAVAILABLE", "INVALID_RESPONSE", "VALIDATION_FAILED", "CONTEXT_LIMIT"] = "DISABLED"
