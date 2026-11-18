from conversation_proxy import allowed_conversation
from chat_proxy import allowed_chat
from checkout_proxy import allowed_checkout, checkout_page
"""Loopback-only PayMesh static server and fixed-target business proxy."""
from admin_proxy import allowed_admin, SPA
from merchant_proxy import allowed_merchant, SPA as MERCHANT_SPA
from urllib.parse import urlsplit
import http.client
from http.cookies import SimpleCookie
import json
from pathlib import Path
import re
import socket
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

ROOT = Path(__file__).resolve().parent
UUID = r'[0-9a-fA-F]{8}(?:-[0-9a-fA-F]{4}){3}-[0-9a-fA-F]{12}'
BASE = '/api/v1/payments'
AUTH_COOKIE_PATHS = frozenset('/api/v1/auth/' + p for p in ('login', 'refresh', 'logout', 'logout-all'))
AUTH_POST_PATHS = frozenset('/api/v1/auth/' + p for p in ('refresh', 'logout', 'logout-all', 'password/forgot', 'password/verify-otp', 'password/reset'))
ROUTES = [('GET', r'/api/v1/auth/password/capabilities')] + [('POST', re.escape(p)) for p in AUTH_POST_PATHS] + [('POST', r'/api/v1/auth/login'), ('POST', r'/api/v1/auth/register'), ('POST', BASE), ('GET', BASE + '/health'),
          ('GET', BASE + '/' + UUID),
          ('GET', BASE + '/' + UUID + r'/(gateway-transactions|refund|refunds)'),
          ('POST', BASE + '/' + UUID + r'/(process|refund|investigate)')]
FRONTEND_ROUTES = frozenset({'/', '/merchant/signup', '/merchant/login',
                             '/merchant/dashboard', '/admin/login', '/admin/dashboard', '/merchant/forgot-password', '/admin/forgot-password'}) | SPA | MERCHANT_SPA
MIME = {'.html': 'text/html; charset=utf-8', '.css': 'text/css; charset=utf-8',
        '.js': 'text/javascript; charset=utf-8'}


def allowed(method, path):
    return allowed_conversation(method,path) or allowed_chat(method,path) or allowed_checkout(method,path) or allowed_merchant(method,path) or allowed_admin(method, path) or any(method == m and re.fullmatch(p, path) for m, p in ROUTES)


class Handler(BaseHTTPRequestHandler):
    # No request paths, credentials, bodies or headers in logs.
    def log_message(self, *args):
        pass

    def setup(self):
        super().setup()
        self.connection.settimeout(10)

    def reply(self, status, body, content_type='application/json', extra=None):
        self.send_response(status)
        self.send_header('Content-Type', content_type)
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('Referrer-Policy', 'no-referrer')
        self.send_header('Content-Security-Policy', "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'")
        self.send_header('Connection', 'close')
        for key, value in (extra or {}).items():
            self.send_header(key, value)
        self.end_headers()
        self.close_connection = True
        self.wfile.write(body)

    def error(self, status, message):
        self.reply(status, json.dumps({'status': status, 'message': message}).encode())

    def do_GET(self):
        self.handle_request()

    def do_POST(self):
        self.handle_request()

    def handle_request(self):
        expected = '127.0.0.1:' + str(self.server.server_port)
        if self.headers.get_all('Host') != [expected]:
            return self.error(403, 'Invalid host')
        origin = self.headers.get('Origin')
        if origin is not None and origin != 'http://' + expected:
            return self.error(403, 'Invalid origin')
        if self.headers.get('Sec-Fetch-Site') == 'cross-site':
            return self.error(403, 'Cross-site request denied')
        path = self.path
        if self.requestline.split()[1].startswith('//'):
            return self.error(400, 'Invalid path')
        validation_path = urlsplit(path).path if (allowed_conversation(self.command,path) or allowed_admin(self.command,path) or allowed_merchant(self.command,path)) else path
        if not re.fullmatch(r'/[a-zA-Z0-9/_.-]*', validation_path) or '..' in validation_path or '//' in validation_path:
            return self.error(400, 'Invalid path')
        if self.headers.get('Transfer-Encoding') or self.headers.get('Expect'):
            return self.error(400, 'Unsupported framing')
        lengths = self.headers.get_all('Content-Length', [])
        if len(lengths) > 1 or (lengths and not re.fullmatch(r'[0-9]{1,9}', lengths[0])):
            return self.error(400, 'Invalid content length')
        size = int(lengths[0]) if lengths else 0
        limit = 8192 if allowed_conversation(self.command,path) else 32768 if allowed_chat(self.command,path) else 4096 if path.startswith('/api/v1/checkout/') or path == '/api/v1/auth/login' or (path.startswith('/api/v1/admin/') or path.startswith('/api/v1/merchant/')) else 16384
        if size > limit:
            return self.error(413, 'Request too large')
        if self.command == 'GET' and size:
            return self.error(400, 'GET body denied')
        if path.startswith('/api/'):
            if not allowed(self.command, path):
                return self.error(404, 'Route not available')
            if self.command == 'POST' and size and self.headers.get('Content-Type', '').split(';')[0] != 'application/json':
                return self.error(415, 'JSON required')
            if path.startswith('/api/v1/checkout/') and len(self.headers.get_all('Origin',[]))>1:
                return self.error(403,'Invalid origin')
            if (path in AUTH_POST_PATHS or path.startswith('/api/v1/checkout/') and self.command=='POST') and (origin != 'http://' + expected or self.headers.get('X-PayMesh-Checkout' if path.startswith('/api/v1/checkout/') else 'X-PayMesh-CSRF') != '1'):
                return self.error(403, 'Origin and CSRF header required')
            return self.proxy(path, size)
        if self.command != 'GET':
            return self.error(405, 'Method not allowed')
        target = ROOT / ('checkout.html' if checkout_page(path) else 'index.html' if path in FRONTEND_ROUTES else path[1:])
        # Static assets only; never serve source, reports, dotfiles or symlinks outside root.
        if (not checkout_page(path) and path not in FRONTEND_ROUTES and path != '/index.html' and not path.startswith('/assets/')) or target.suffix not in MIME:
            return self.error(404, 'File not available')
        if not target.resolve().is_relative_to(ROOT) or not target.is_file():
            return self.error(404, 'File not available')
        self.reply(200, target.read_bytes(), MIME[target.suffix])

    def proxy(self, path, size):
        connection = http.client.HTTPConnection('127.0.0.1', 18080, timeout=40 if (allowed_chat(self.command,path) or allowed_conversation(self.command,path) and self.command=='POST' and path.endswith('/messages')) else 55 if path.endswith('/investigate') else 15)
        try:
            body = self.rfile.read(size)
            if len(body) != size:
                return self.error(400, 'Incomplete request')
            headers = {key: self.headers[key] for key in ('Authorization', 'Content-Type', 'Idempotency-Key') if key in self.headers}
            if allowed_checkout(self.command,path):
                headers.pop('Authorization',None)
                if self.headers.get('Origin'):headers['Origin']=self.headers['Origin']
                if self.headers.get('X-PayMesh-Checkout')=='1':headers['X-PayMesh-Checkout']='1'
            if path in AUTH_COOKIE_PATHS:
                cookie = self.headers.get('Cookie', '')
                if len(self.headers.get_all('Cookie', [])) > 1 or len(cookie) > 4096:
                    return self.error(400, 'Invalid session cookie')
                entries = [part.strip() for part in cookie.split(';') if part.strip().startswith('pm_refresh=')]
                matches = [part.split('=', 1)[1] for part in entries if re.fullmatch(r'pm_refresh=[A-Za-z0-9_-]{43}', part)]
                if entries and (len(entries) != 1 or len(matches) != 1):
                    return self.error(400, 'Invalid session cookie')
                if len(matches) == 1:
                    headers['Cookie'] = 'pm_refresh=' + matches[0]
            if path.startswith('/api/v1/auth/') and self.headers.get('Origin'):
                headers['Origin'] = self.headers['Origin']
                if self.headers.get('X-PayMesh-CSRF') == '1':
                    headers['X-PayMesh-CSRF'] = '1'
            headers['Accept'] = 'application/json'
            connection.request(self.command, path, body=body, headers=headers)
            response = connection.getresponse()
            if 300 <= response.status < 400:
                return self.error(502, 'Upstream redirect denied')
            payload = response.read(524289)
            if len(payload) > 524288:
                return self.error(502, 'Upstream response too large')
            extra = {key: response.getheader(key) for key in ('Retry-After', 'WWW-Authenticate') if response.getheader(key)}
            if path in AUTH_COOKIE_PATHS:
                value = response.getheader('Set-Cookie')
                if value:
                    parsed = SimpleCookie()
                    try:
                        parsed.load(value)
                        item = parsed.get('pm_refresh')
                        valid = item is not None and len(parsed) == 1 and re.fullmatch(r'[A-Za-z0-9_-]{43}|', item.value) and item['path'] == '/api/v1/auth' and item['httponly'] and item['samesite'] == 'Strict' and not item['domain']
                    except Exception:
                        valid = False
                    if len(value) > 1024 or '\r' in value or '\n' in value or not valid:
                        return self.error(502, 'Invalid session cookie')
                    extra['Set-Cookie'] = value
            self.reply(response.status, payload, 'application/json', extra)
        except (TimeoutError, socket.timeout):
            self.error(504, 'Request timed out; verify state before retrying')
        except (OSError, http.client.HTTPException):
            self.error(502, 'Payment service unavailable')
        finally:
            connection.close()


if __name__ == '__main__':
    server = ThreadingHTTPServer(('127.0.0.1', 5500), Handler)
    server.daemon_threads = True
    print('PayMesh foundation: http://127.0.0.1:5500 (Ctrl-C to stop this server)')
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
