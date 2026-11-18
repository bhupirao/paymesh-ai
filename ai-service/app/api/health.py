from typing import Literal
from fastapi import APIRouter
from pydantic import BaseModel
from app.config import settings

router = APIRouter()

class Health(BaseModel):
    service: str = "PayMesh AI Investigation Service"
    status: Literal["UP"] = "UP"
    mode: Literal["deterministic", "rag_assisted", "rag_llm"] = "deterministic"
    configuredAnalysisMode: str = "DETERMINISTIC"
    modelConnectivity: Literal["NOT_VERIFIED"] = "NOT_VERIFIED"

class Readiness(Health):
    scope: str = "Deterministic snapshot validation and investigation only; no external dependencies are required or probed."

@router.get("/health", response_model=Health)
def health():
    return Health(mode=settings.analysis_mode.lower(), configuredAnalysisMode=settings.analysis_mode)

@router.get("/api/v1/health/readiness", response_model=Readiness)
def readiness():
    return Readiness(mode=settings.analysis_mode.lower(), configuredAnalysisMode=settings.analysis_mode)
