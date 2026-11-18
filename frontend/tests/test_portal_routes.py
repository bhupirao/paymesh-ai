"""New portal static-route checks; no business requests or live server changes."""
import http.client
import sys
from pathlib import Path
import threading
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from dev_server import Handler, ThreadingHTTPServer, FRONTEND_ROUTES, allowed

class PortalRouteTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown(); cls.server.server_close(); cls.thread.join()

    def get(self, path, method='GET'):
        connection = http.client.HTTPConnection('127.0.0.1', self.server.server_port, timeout=3)
        connection.request(method, path)
        result = connection.getresponse()
        value = result.status, result.read(), dict(result.getheaders())
        connection.close()
        return value

    def test_exact_routes_and_refresh(self):
        self.assertEqual(len(FRONTEND_ROUTES), 24)
        for path in sorted(FRONTEND_ROUTES):
            for _ in range(2):
                with self.subTest(path=path):
                    status, body, headers = self.get(path)
                    self.assertEqual(status, 200)
                    self.assertIn(b'Get Started as Merchant', body)
                    self.assertIn(b'id="portal-shell"', body)
                    self.assertEqual(headers['Cache-Control'], 'no-store')
                    self.assertIn("frame-ancestors 'none'", headers['Content-Security-Policy'])

    def test_unknown_and_nested_routes_denied(self):
        for path in ['/admin/signup','/merchant/anything','/merchant/dashboard/details','/admin','/unknown','/signup','/assets/missing.js']:
            with self.subTest(path=path): self.assertEqual(self.get(path)[0], 404)

    def test_frontend_routes_are_get_only(self):
        for path in FRONTEND_ROUTES:
            with self.subTest(path=path): self.assertEqual(self.get(path, 'POST')[0], 405)

    def test_legacy_test_pages_and_alias(self):
        for path in ['/index.html','/assets/js/tests.html','/assets/js/auth-tests.html','/assets/js/payment-tests.html','/assets/js/refund-tests.html','/assets/js/investigation-tests.html','/assets/js/qa-tests.html','/assets/js/portal-tests.html']:
            with self.subTest(path=path): self.assertEqual(self.get(path)[0], 200)

    def test_no_route_canonicalization_bypass(self):
        for path in ['/merchant/%6cogin','/merchant//login','/merchant/../admin/login','/merchant/login?token=x','/admin/login/..']:
            with self.subTest(path=path): self.assertEqual(self.get(path)[0], 400)

    def test_signup_is_not_a_business_endpoint(self):
        self.assertEqual(self.get('/api/v1/auth/signup', 'POST')[0], 404)
        self.assertEqual(self.get('/api/v1/merchants', 'POST')[0], 404)

    def test_registration_allowlist_is_exact(self):
        self.assertTrue(allowed('POST', '/api/v1/auth/register'))
        for method in ['GET','PUT','DELETE','HEAD']:
            self.assertFalse(allowed(method, '/api/v1/auth/register'))
        for path in ['/api/v1/auth/register/extra','/api/v1/auth/approve','/api/v1/auth/verify','/api/v1/auth/signup']:
            self.assertFalse(allowed('POST', path))

    def test_registration_limits_and_origin(self):
        self.assertEqual(self.get('/api/v1/auth/register')[0],404)
        conn = http.client.HTTPConnection('127.0.0.1', self.server.server_port, timeout=3)
        conn.request('POST','/api/v1/auth/register',b'x'*16385)
        response=conn.getresponse(); self.assertEqual(response.status,413);response.read();conn.close()
        conn = http.client.HTTPConnection('127.0.0.1', self.server.server_port, timeout=3)
        conn.request('POST','/api/v1/auth/register',b'{}',{'Origin':'https://evil.example','Content-Type':'application/json'})
        response=conn.getresponse();self.assertEqual(response.status,403);response.read();conn.close()

if __name__ == '__main__': unittest.main()
