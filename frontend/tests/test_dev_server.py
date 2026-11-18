import http.client
from pathlib import Path
import sys
import threading
import unittest
from unittest.mock import patch, MagicMock
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from dev_server import Handler, ThreadingHTTPServer, allowed


class ProxyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join()

    def call(self, method, path, body=None, headers=None):
        client = http.client.HTTPConnection('127.0.0.1', self.server.server_port, timeout=3)
        client.request(method, path, body, headers or {})
        response = client.getresponse()
        result = response.status, response.read(), dict(response.getheaders())
        client.close()
        return result

    def test_shell_and_security_headers(self):
        status, body, headers = self.call('GET', '/')
        self.assertEqual(status, 200)
        self.assertIn(b'Sign in to your workspace', body)
        self.assertIn("connect-src 'self'", headers['Content-Security-Policy'])
        self.assertEqual(headers['Cache-Control'], 'no-store')

    def test_assets(self):
        self.assertEqual(self.call('GET', '/assets/js/api/client.js')[0], 200)

    def test_source_and_report_not_exposed(self):
        for path in ['/dev_server.py', '/README.md', '/.git/config']:
            self.assertEqual(self.call('GET', path)[0], 404)

    def test_path_validation(self):
        for path in ['/../README.md', '/assets/%2e%2e/README.md', '/api/v1/payments?url=x', '//example.com', '/assets/../index.html']:
            self.assertEqual(self.call('GET', path)[0], 400)

    def test_forbidden_routes(self):
        for path in ['/api/v1/payments', '/api/v1/merchants', '/api/v1/settlement/payments/x/reconcile', '/api/v1/webhooks/mock-stripe', '/api/v1/investigations']:
            self.assertEqual(self.call('GET', path)[0], 404)
        self.assertEqual(self.call('GET', '/actuator/env')[0], 404)

    def test_origin_host(self):
        self.assertEqual(self.call('GET', '/', headers={'Host': 'evil.example'})[0], 403)
        self.assertEqual(self.call('POST', '/api/v1/auth/login', headers={'Origin': 'https://evil.example'})[0], 403)

    def test_body_limits(self):
        self.assertEqual(self.call('POST', '/api/v1/auth/login', b'x' * 4097)[0], 413)
        self.assertEqual(self.call('POST', '/api/v1/payments', b'x' * 16385)[0], 413)

    def test_framing(self):
        self.assertEqual(self.call('POST', '/api/v1/auth/login', headers={'Transfer-Encoding': 'chunked'})[0], 400)
        self.assertEqual(self.call('POST', '/api/v1/auth/login', headers={'Content-Length': '-1'})[0], 400)
        self.assertEqual(self.call('POST', '/api/v1/auth/login', b'x')[0], 415)

    def test_allowlist_methods(self):
        payment = '/api/v1/payments/12345678-1234-1234-1234-123456789abc'
        self.assertTrue(allowed('POST', payment + '/investigate'))
        self.assertTrue(allowed('GET', payment + '/refunds'))
        self.assertFalse(allowed('POST', payment + '/refunds'))
        self.assertFalse(allowed('DELETE', payment))

    def proxy_result(self, status=200, payload=b'{}', upstream_headers=None):
        upstream = MagicMock()
        response = upstream.getresponse.return_value
        response.status = status
        response.read.return_value = payload
        response.getheader.side_effect = lambda key: (upstream_headers or {}).get(key)
        with patch('dev_server.http.client.HTTPConnection', return_value=upstream):
            # Construct client before patch to avoid replacing test transport.
            self.client.request('POST', '/api/v1/auth/login', b'{}', {'Content-Type': 'application/json', 'Authorization': 'Bearer test-only', 'Cookie': 'secret', 'X-Forwarded-For': 'evil'})
            result = self.client.getresponse()
            output = result.status, result.read(), dict(result.getheaders())
        return output, upstream

    def test_fixed_target_and_headers(self):
        self.client = http.client.HTTPConnection('127.0.0.1', self.server.server_port)
        output, upstream = self.proxy_result(429, upstream_headers={'Retry-After': '60'})
        self.client.close()
        self.assertEqual(output[0], 429)
        self.assertEqual(output[2]['Retry-After'], '60')
        forwarded = upstream.request.call_args.kwargs['headers']
        self.assertEqual(forwarded['Authorization'], 'Bearer test-only')
        self.assertNotIn('Cookie', forwarded)
        self.assertNotIn('X-Forwarded-For', forwarded)

    def test_redirect_and_oversized_response(self):
        for status, payload in [(302, b''), (200, b'x' * 524289)]:
            self.client = http.client.HTTPConnection('127.0.0.1', self.server.server_port)
            output, upstream = self.proxy_result(status, payload)
            self.client.close()
            self.assertEqual(output[0], 502)
            upstream.close.assert_called_once()

    def test_upstream_unavailable(self):
        client = http.client.HTTPConnection('127.0.0.1', self.server.server_port)
        upstream = MagicMock()
        upstream.request.side_effect = OSError
        with patch('dev_server.http.client.HTTPConnection', return_value=upstream):
            client.request('GET', '/api/v1/payments/health')
            response = client.getresponse()
            self.assertEqual(response.status, 502)
            response.read()
        client.close()


if __name__ == '__main__':
    unittest.main()
