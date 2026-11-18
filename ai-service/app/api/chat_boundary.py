"""Bound and validate chat bytes before JSON/Pydantic parsing, including streamed bodies."""
import json
import re
from starlette.responses import JSONResponse

class ChatBoundary:
    def __init__(self, app, max_bytes=32768):
        self.app, self.max_bytes = app, max_bytes
    async def __call__(self, scope, receive, send):
        if scope['type'] != 'http' or scope['path'].rstrip('/') != '/api/v1/chat':
            return await self.app(scope, receive, send)
        async def error(code, text):
            await JSONResponse({'detail': text}, status_code=code, headers={'Cache-Control':'no-store','Pragma':'no-cache','X-Content-Type-Options':'nosniff','Referrer-Policy':'no-referrer'})(scope,receive,send)
        if scope['path'] != '/api/v1/chat': return await error(404,'Route unavailable.')
        if scope.get('query_string'): return await error(400,'Chat query parameters are not supported.')
        if scope['method'] != 'POST': return await error(405,'Method not allowed.')
        headers=scope.get('headers',[])
        types=[v.split(b';')[0].strip().lower() for k,v in headers if k.lower()==b'content-type']
        if types != [b'application/json']: return await error(415,'JSON required.')
        lengths=[v for k,v in headers if k.lower()==b'content-length']
        if len(lengths)>1 or lengths and not re.fullmatch(rb'[0-9]{1,10}',lengths[0]): return await error(400,'Invalid chat request.')
        if lengths and int(lengths[0])>self.max_bytes: return await error(413,'Chat request too large.')
        body=bytearray()
        while True:
            message=await receive()
            if message['type']=='http.disconnect': return
            body.extend(message.get('body',b''))
            if len(body)>self.max_bytes: return await error(413,'Chat request too large.')
            if not message.get('more_body',False): break
        def pairs(values):
            out={}
            for k,v in values:
                if k in out: raise ValueError()
                out[k]=v
            return out
        try:
            json.loads(body.decode('utf-8'),object_pairs_hook=pairs,parse_constant=lambda _: (_ for _ in ()).throw(ValueError()))
        except (ValueError,UnicodeError,RecursionError): return await error(422,'Invalid chat request.')
        delivered=False
        async def replay():
            nonlocal delivered
            if not delivered:
                delivered=True
                return {'type':'http.request','body':bytes(body),'more_body':False}
            return await receive()
        async def private_send(message):
            if message['type']=='http.response.start':
                message=dict(message);message['headers']=list(message.get('headers',[]))+[(b'cache-control',b'no-store'),(b'pragma',b'no-cache'),(b'x-content-type-options',b'nosniff'),(b'referrer-policy',b'no-referrer')]
            await send(message)
        await self.app(scope,replay,private_send)
