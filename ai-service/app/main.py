from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from app.api.body_limit import InvestigationBodyLimit
from app.api import health, investigations, chat
from app.api.chat_boundary import ChatBoundary
from app.config import settings

app = FastAPI(title="PayMesh AI Investigation Service", version="0.5.3A", description="Local snapshot investigation with optional lexical retrieval and loopback wording selection.")
app.add_middleware(InvestigationBodyLimit, max_bytes=settings.request_body_bytes)
app.add_middleware(ChatBoundary)


@app.exception_handler(RequestValidationError)
async def safe_validation_error(request, exc):
    # Do not include input, ctx, attacker-controlled field names, or parser messages.
    return JSONResponse(status_code=422, content={"detail": "Invalid chat request. Check the documented schema." if request.url.path == "/api/v1/chat" else "Invalid investigation request. Check the documented schema."})


app.include_router(health.router)
app.include_router(investigations.router)
app.include_router(chat.router)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host=settings.host, port=settings.port, access_log=False)
