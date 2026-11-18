"""Fixed container edge; reuse exact proxy paths, CSP and cookie restrictions.
External Origin is checked before translating to the existing private Java Origin.
Java/Python/model loopback requirements and local cookie policy stay unchanged.
"""
from http.server import ThreadingHTTPServer
from dev_server import Handler

class ContainerHandler(Handler):
    def log_message(self, *args):
        pass  # Never access-log checkout tokens or request URLs.

    def proxy(self, path, size):
        origin = self.headers.get('Origin')
        if origin is not None and self.headers.get_all('Origin') != ['http://127.0.0.1:15500']:
            return self.error(403, 'Invalid origin')
        if origin is not None:
            self.headers.replace_header('Origin', 'http://127.0.0.1:5500')
        try:
            return super().proxy(path, size)
        finally:
            if origin is not None:
                self.headers.replace_header('Origin', origin)

if __name__ == '__main__':
    ThreadingHTTPServer(('0.0.0.0', 15500), ContainerHandler).serve_forever()
