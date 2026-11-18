"""Loopback-only OpenAI-compatible transport; no runtime is bundled."""
from typing import Protocol
import httpx
from app.config import Settings
from app.services.generation_budget import run_bounded


class GenerationFailure(Exception):
    def __init__(self, reason: str):
        self.reason = reason
        super().__init__(reason)


class Provider(Protocol):
    def generate(self, messages: list[dict[str, str]]) -> str: ...


class LocalHTTPProvider:
    def __init__(self, config: Settings, *, output_schema: dict | None = None):
        # Revalidate even if constructed via an unchecked model_copy.
        self.config = Settings.model_validate(config.model_dump())
        # llama.cpp b4514 reads schema directly under json_object response_format.
        self.response_format = {'type': 'json_object'}
        if output_schema is not None:
            self.response_format['schema'] = output_schema

    def generate(self, messages: list[dict[str, str]]) -> str:
        return run_bounded(lambda: self._generate(messages))

    def _generate(self, messages: list[dict[str, str]]) -> str:
        c = self.config
        if not c.generation_enabled:
            raise GenerationFailure('DISABLED')
        if sum(len(m['content']) for m in messages) > c.context_chars:
            raise GenerationFailure('CONTEXT_LIMIT')
        try:
            with httpx.Client(timeout=c.generation_timeout, follow_redirects=False, trust_env=False) as client:
                with client.stream('POST', c.inference_url, json=dict(model=c.model_name, messages=messages, temperature=0.1, max_tokens=c.max_output_tokens, response_format=self.response_format, stream=False)) as response:
                    if response.status_code != 200:
                        raise GenerationFailure('UNAVAILABLE')
                    body = bytearray()
                    for data in response.iter_bytes():
                        body.extend(data)
                        if len(body) > 16384:
                            raise GenerationFailure('INVALID_RESPONSE')
            import json
            payload = json.loads(body)
            choice = payload['choices'][0]
            if choice.get('finish_reason') != 'stop':
                raise ValueError
            content = choice['message']['content']
            if not isinstance(content, str) or len(content) > 2048:
                raise ValueError
            return content
        except httpx.TimeoutException:
            raise GenerationFailure('TIMEOUT') from None
        except httpx.HTTPError:
            raise GenerationFailure('UNAVAILABLE') from None
        except (ValueError, KeyError, IndexError, TypeError):
            raise GenerationFailure('INVALID_RESPONSE') from None
