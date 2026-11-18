import ipaddress
from urllib.parse import urlsplit
from typing import Literal
from pydantic import SecretStr, Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from app.services.chat_validation_diagnostics import validate_sink


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix='PAYMESH_AI_', env_file='.env', extra='ignore')
    host: str = '127.0.0.1'
    port: int = Field(default=8000, ge=1, le=65535)
    analysis_mode: Literal['DETERMINISTIC', 'RAG_ASSISTED', 'RAG_LLM'] = 'DETERMINISTIC'
    generation_enabled: bool = False
    chat_api_enabled: bool = False
    chat_validation_diagnostics_file: str | None = Field(default=None, max_length=1024, exclude=True, repr=False)
    chat_service_token: SecretStr | None = None
    inference_url: str = 'http://127.0.0.1:8080/v1/chat/completions'
    model_name: str = Field(default='local-model', min_length=1, max_length=100, pattern=r'^[A-Za-z0-9_.:/-]+$')
    generation_timeout: float = Field(default=10, ge=1, le=30)
    max_output_tokens: int = Field(default=128, ge=32, le=512)
    context_chars: int = Field(default=12000, ge=6000, le=24000)
    retrieval_top_k: int = Field(default=3, ge=1, le=5)
    retrieval_context_chars: int = Field(default=3000, ge=100, le=6000)
    retrieval_threshold: float = Field(default=.12, gt=0, le=1)
    request_body_bytes: int = Field(default=131072, ge=1024, le=262144)

    @field_validator('chat_validation_diagnostics_file')
    @classmethod
    def protected_chat_diagnostic_sink(cls, value):
        return validate_sink(value)

    @field_validator('inference_url')
    @classmethod
    def loopback_url(cls, value):
        try:
            url = urlsplit(value)
            address = ipaddress.ip_address(url.hostname or '')
            if url.scheme != 'http' or not address.is_loopback or url.username or url.password or url.query or url.fragment or url.path != '/v1/chat/completions' or not url.port:
                raise ValueError
        except ValueError:
            raise ValueError('Inference URL must be an HTTP loopback IP with explicit port and /v1/chat/completions path') from None
        return value

    @model_validator(mode='after')
    def generation_mode(self):
        if self.analysis_mode == 'RAG_LLM' and not self.generation_enabled:
            raise ValueError('RAG_LLM requires generation_enabled=true')
        return self


settings = Settings()
