import http.client
from pathlib import Path
import sys
import threading
import unittest
from unittest.mock import MagicMock,patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from dev_server import Handler,ThreadingHTTPServer,allowed,FRONTEND_ROUTES
from admin_proxy import allowed_admin
CLIENT_CONNECTION=http.client.HTTPConnection

class AdminProxyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server=ThreadingHTTPServer(('127.0.0.1',0),Handler);cls.thread=threading.Thread(target=cls.server.serve_forever,daemon=True);cls.thread.start()
    @classmethod
    def tearDownClass(cls):cls.server.shutdown();cls.server.server_close();cls.thread.join()
    def call(self,method,path,body=None,headers=None):
        c=CLIENT_CONNECTION('127.0.0.1',self.server.server_port,timeout=3);c.request(method,path,body,headers or {});r=c.getresponse();out=(r.status,r.read(),dict(r.getheaders()));c.close();return out
    def test_exact_admin_methods_and_static_pages(self):
        for path in ('dashboard','merchants','merchant','pending','payments','refunds','audit','accounts','profile'):
            self.assertIn('/admin/'+path,FRONTEND_ROUTES);self.assertEqual(200,self.call('GET','/admin/'+path)[0])
        for path in ('dashboard','merchants','payments','refunds','audit','accounts','profile'):self.assertTrue(allowed('GET','/api/v1/admin/'+path))
        for path in ('approve','reject','suspend','reactivate'):self.assertTrue(allowed('POST','/api/v1/admin/merchant/'+path))
        self.assertFalse(allowed('POST','/api/v1/admin/dashboard'));self.assertFalse(allowed('GET','/api/v1/admin/profile/password'))
    def test_query_bounds_duplicate_and_origin_security(self):
        for query in ('size=101','page=-1','page=1&page=2','sort=sql','merchantId=%0A','url=http://evil','currency=EUR','search=%ZZ'):
            self.assertFalse(allowed_admin('GET','/api/v1/admin/payments?'+query))
        self.assertTrue(allowed_admin('GET','/api/v1/admin/payments?page=0&size=25&currency=INR&from=2026-01-01T00%3A00%3A00Z'))
        self.assertEqual(403,self.call('GET','/api/v1/admin/dashboard',headers={'Origin':'https://evil.invalid'})[0])
    def test_query_forwarded_to_fixed_java_without_cookie_or_forwarded_identity(self):
        response=MagicMock(status=200);response.read.return_value=b'{"items":[]}';response.getheader.return_value=None
        connection=MagicMock();connection.getresponse.return_value=response
        with patch('dev_server.http.client.HTTPConnection',return_value=connection) as ctor:
            path='/api/v1/admin/payments?page=0&size=25&currency=USD'
            status,_,_=self.call('GET',path,headers={'Authorization':'Bearer test-only','Cookie':'pm_refresh='+'x'*43,'X-Forwarded-For':'evil'})
            self.assertEqual(200,status);self.assertEqual(('127.0.0.1',18080),ctor.call_args.args)
            args=connection.request.call_args;self.assertEqual(path,args.args[1]);self.assertEqual('Bearer test-only',args.kwargs['headers']['Authorization']);self.assertNotIn('Cookie',args.kwargs['headers']);self.assertNotIn('X-Forwarded-For',args.kwargs['headers'])
    def test_admin_body_limit_content_type_and_unsupported_targets(self):
        self.assertEqual(413,self.call('POST','/api/v1/admin/merchant/approve','x'*4097,{'Content-Type':'application/json'})[0])
        self.assertEqual(415,self.call('POST','/api/v1/admin/profile/password','not-json',{'Content-Type':'text/plain'})[0])
        for path in ('/api/v1/admin/settlement','/api/v1/admin/secret','/api/v1/admin/payments/../../actuator','/api/v1/admin/payments?url=http://localhost:8000'):
            self.assertIn(self.call('GET',path)[0],(400,404))
    def test_auth_cookies_still_restricted_to_existing_auth_routes(self):
        response=MagicMock(status=200);response.read.return_value=b'{}';response.getheader.return_value='pm_refresh=bad'
        connection=MagicMock();connection.getresponse.return_value=response
        with patch('dev_server.http.client.HTTPConnection',return_value=connection):
            status,_,headers=self.call('POST','/api/v1/admin/accounts','{}',{'Content-Type':'application/json'})
            self.assertEqual(200,status);self.assertNotIn('Set-Cookie',headers);self.assertIn('Content-Security-Policy',headers)

if __name__=='__main__':unittest.main()
