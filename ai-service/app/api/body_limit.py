"""Bound investigation bodies before downstream JSON parsing, including chunked input."""
from starlette.responses import JSONResponse


class InvestigationBodyLimit:
    def __init__(self, app, max_bytes: int):
        self.app, self.max_bytes = app, max_bytes

    async def __call__(self, scope, receive, send):
        if scope['type'] != 'http' or scope['path'].rstrip('/') != '/api/v1/investigations':
            return await self.app(scope, receive, send)
        for key, value in scope.get('headers', []):
            if key.lower() == b'content-length':
                try:
                    if int(value) > self.max_bytes:
                        return await JSONResponse({'detail': 'Request too large'}, status_code=413)(scope, receive, send)
                except ValueError:
                    return await JSONResponse({'detail': 'Invalid request'}, status_code=400)(scope, receive, send)
        body = bytearray()
        while True:
            message = await receive()
            if message['type'] == 'http.disconnect':
                return
            body.extend(message.get('body', b''))
            if len(body) > self.max_bytes:
                return await JSONResponse({'detail': 'Request too large'}, status_code=413)(scope, receive, send)
            if not message.get('more_body', False):
                break
        delivered = False

        async def replay():
            nonlocal delivered
            if not delivered:
                delivered = True
                return {'type': 'http.request', 'body': bytes(body), 'more_body': False}
            return await receive()

        await self.app(scope, replay, send)
