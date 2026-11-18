"""Internal only. The future Java caller must authenticate/authorize/minimize before this call."""
from fastapi import APIRouter, Depends, Request
import hmac
import re
from fastapi.responses import JSONResponse
from app.config import settings
from app.schemas.chat import ChatRequest, ChatResponse
from app.services.chat_service import converse
router = APIRouter()

def get_chat_settings():
    return settings

@router.post('/api/v1/chat', response_model=ChatResponse,
             description='Internal supplied-snapshot conversation. Role/source labels are NOT authentication. Java authorization required upstream; no financial tools or data fetching.')
def chat(request: ChatRequest, http_request: Request, config=Depends(get_chat_settings)):
    key=config.chat_service_token.get_secret_value() if config.chat_service_token else ''
    if not config.chat_api_enabled or not re.fullmatch(r'[A-Za-z0-9_-]{64,128}',key):
        return JSONResponse(status_code=503,content={'detail':'Internal chat unavailable.'})
    supplied=http_request.headers.getlist('X-PayMesh-AI-Chat-Token')
    if len(supplied)!=1 or not hmac.compare_digest(supplied[0].encode('utf-8'),key.encode('ascii')):
        return JSONResponse(status_code=401,content={'detail':'Internal authentication required.'})
    try:
        return converse(request, config)
    except Exception:
        # No raw questions, validation errors, provider payloads or exception text in logs/output.
        return JSONResponse(status_code=503, content={'detail': 'Conversation analysis unavailable.'})
