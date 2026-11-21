"""Loopback-only adapter behind OTP-protected cloudflared. Never logs traffic.

This is NOT an authentication substitute: the supervisor must verify the pinned
Quick Tunnel authorizer before activating this adapter. No direct public bind.
"""
import html
import http.client
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import re
import time
from urllib.parse import urlsplit

class Denied(Exception):
    pass

def need(ok):
    if not ok:
        raise Denied('EDGE_REQUEST_DENIED')

def public_host(url):
    need(bool(re.fullmatch(r'https://[a-z0-9]+(?:-[a-z0-9]+)*\.trycloudflare\.com',url)))
    return urlsplit(url).hostname

def one(headers,name,required=False):
    values=headers.get_all(name,[])
    need(len(values)<=1 and (not required or len(values)==1))
    return values[0] if values else None

def request_headers(headers,method,target,host):
    need(one(headers,'Host',True)==host)
    need(target.startswith('/') and not target.startswith('//') and '\\' not in target
         and not any(ord(c)<32 or ord(c)==127 for c in target) and '#' not in target)
    need(not one(headers,'Forwarded') and not one(headers,'Transfer-Encoding')
         and not one(headers,'Upgrade') and not one(headers,'Proxy-Authorization'))
    # Cloudflare may provide these canonical values, never a client-controlled
    # chain. None is used for client identity or to expand rate-limit capacity.
    for name,expected in [('X-Forwarded-Host',host),('X-Forwarded-Proto','https')]:
        need(one(headers,name) in (None,expected))
    value=one(headers,'X-Forwarded-For')
    if value:
        import ipaddress
        try: ipaddress.ip_address(value)
        except ValueError: raise Denied('EDGE_REQUEST_DENIED') from None
    # Reject unrecognized forwarding schemes rather than passing them onward.
    for name in headers.keys():
        if name.lower().startswith(('x-forwarded-','x-original-','x-rewrite-')):
            need(name.lower() in ('x-forwarded-host','x-forwarded-proto','x-forwarded-for'))
    origin=one(headers,'Origin')
    need(origin in (None,'https://'+host))
    need(method in ('GET','HEAD','POST'))
    if method=='POST': need(origin=='https://'+host)
    out={'Host':'127.0.0.1:15500','Connection':'close','Accept-Encoding':'identity'}
    for name in ('Accept','Content-Type','Authorization','X-PayMesh-CSRF','X-PayMesh-Checkout','Idempotency-Key'):
        value=one(headers,name)
        if value is not None:
            need(len(value)<=8192);out[name]=value
    if origin: out['Origin']='http://127.0.0.1:15500'
    # Do not disclose Cloudflare Access assertions/cookies to the application.
    cookie=one(headers,'Cookie')
    if cookie:
        need(len(cookie)<=16384)
        parsed=SimpleCookie()
        try: parsed.load(cookie)
        except Exception: raise Denied('EDGE_REQUEST_DENIED') from None
        if 'pm_refresh' in parsed:
            token=parsed['pm_refresh'].value
            need(bool(re.fullmatch('[A-Za-z0-9_-]{43}',token)))
            out['Cookie']='pm_refresh='+token
    return out

def secure_cookie(raw):
    need(len(raw)<=4096)
    parsed=SimpleCookie()
    try: parsed.load(raw)
    except Exception: raise Denied('EDGE_RESPONSE_DENIED') from None
    need(set(parsed)=={'pm_refresh'})
    item=parsed['pm_refresh']
    need(bool(re.fullmatch('[A-Za-z0-9_-]{43}|',item.value)) and item['path']=='/api/v1/auth'
         and bool(item['httponly']) and item['samesite']=='Strict' and not item['domain'])
    item['secure']=True
    return item.OutputString()

CSP="default-src 'none'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'"

class Edge(ThreadingHTTPServer):
    daemon_threads=True
    request_queue_size=16
    def handle_error(self,request,client_address):
        # Never let socket-level exceptions emit raw traceback/address data.
        print('DEMO_EDGE_CONNECTION_FAILED')
    def __init__(self,root,credentials,deadline):
        self.root=Path(root);self.credentials=credentials;self.deadline=deadline
        self.host=None;self.active=False
        super().__init__(('127.0.0.1',15501),Handler)

class Handler(BaseHTTPRequestHandler):
    server_version='DemoEdge'
    def log_message(self,*args): pass
    def setup(self):
        super().setup();self.connection.settimeout(10)
    def do_GET(self): self.handle_demo()
    def do_HEAD(self): self.handle_demo()
    def do_POST(self): self.handle_demo()
    def send_safe(self,status,data,kind='text/plain; charset=utf-8',headers=()):
        self.send_response(status)
        for name,value in [('Content-Type',kind),('Content-Length',str(len(data))),('Cache-Control','no-store'),('Pragma','no-cache'),('Referrer-Policy','no-referrer'),('X-Content-Type-Options','nosniff'),('X-Frame-Options','DENY'),('Strict-Transport-Security','max-age=3600'),*headers]:
            self.send_header(name,value)
        if self.path.startswith(('/docs','/_demo')):self.send_header('Content-Security-Policy',CSP)
        self.end_headers()
        if self.command!='HEAD':
            try:self.wfile.write(data)
            except (BrokenPipeError,ConnectionResetError):pass
    def handle_demo(self):
        try:
            if not self.server.active or time.monotonic()>=self.server.deadline:
                self.send_safe(410,b'Demo unavailable');return
            headers=request_headers(self.headers,self.command,self.path,self.server.host)
            length=one(self.headers,'Content-Length')
            need(length is None or bool(re.fullmatch('[0-9]{1,6}',length)))
            size=int(length or '0');need(size<=32768)
            need(self.command=='POST' or size==0)
            body=self.rfile.read(size) if size else None
            need(not size or len(body)==size)
            if self.path.startswith(('/docs','/_demo')):
                need(self.command in ('GET','HEAD'))
                if self.path=='/_demo/start':
                    rows=''.join('<li>'+html.escape(role)+': <code>'+html.escape(user)+'</code> / <code>'+html.escape(password)+'</code></li>' for role,user,password in self.server.credentials)
                    data=('<!doctype html><meta charset="utf-8"><title>Private acceptance demo</title><h1>Synthetic demo credentials</h1><p>Temporary, simulated payments only. Never share these credentials.</p><ul>'+rows+'</ul><a href="/merchant/login">Merchant portal</a> · <a href="/admin/login">Admin portal</a> · <a href="/docs/">Read-only API documentation</a>').encode()
                    self.send_safe(200,data,'text/html; charset=utf-8');return
                files={'/docs/':('deploy/swagger-ui/index.html','text/html; charset=utf-8'),'/docs/docs.js':('deploy/swagger-ui/docs.js','text/javascript'),'/docs/swagger-ui.css':('deploy/swagger-ui/swagger-ui.css','text/css'),'/docs/swagger-ui-bundle.js':('deploy/swagger-ui/swagger-ui-bundle.js','text/javascript'),'/docs/openapi.json':('backend/openapi/paymesh-demo.json','application/json')}
                need(self.path in files);p,kind=files[self.path]
                self.send_safe(200,(self.server.root/p).read_bytes(),kind);return
            # No redirects followed; no arbitrary upstream or public backend ports.
            connection=http.client.HTTPConnection('127.0.0.1',15500,timeout=45)
            try:
                connection.request(self.command,self.path,body=body,headers=headers)
                response=connection.getresponse();data=response.read(2_097_153)
                need(len(data)<=2_097_152)
                outgoing=[]
                for name,value in response.getheaders():
                    if name.lower()=='set-cookie':outgoing.append(('Set-Cookie',secure_cookie(value)))
                    elif name.lower()=='location':
                        need(value.startswith('/') and not value.startswith('//') and '\\' not in value)
                        outgoing.append(('Location',value))
                self.send_safe(response.status,data,response.getheader('Content-Type','application/octet-stream'),outgoing)
            finally: connection.close()
        except Denied:
            self.send_safe(403,b'Request denied')
        except Exception:
            self.send_safe(502,b'Demo temporarily unavailable')
