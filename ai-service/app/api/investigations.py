from fastapi import APIRouter, Depends
from app.config import settings
from app.schemas.investigation import InvestigationRequest, InvestigationResponse
from app.services.rag_service import enrich

router = APIRouter()


def get_settings():
    return settings


@router.post('/api/v1/investigations', response_model=InvestigationResponse,
             description='Internal synthetic-evidence-only local endpoint. Evidence is supplied, unauthenticated, and never retrieved from Java. No financial actions.')
def create_investigation(evidence: InvestigationRequest, config=Depends(get_settings)):
    return enrich(evidence, config)
