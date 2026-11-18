import test_admin_proxy as base
from unittest.mock import patch,MagicMock
from merchant_proxy import allowed_merchant,SPA
from dev_server import allowed
import unittest
# Own class reuses helper functions only; do not inherit and double-count existing tests.
class MerchantProxyTests(unittest.TestCase):
    setUpClass=classmethod(base.AdminProxyTests.setUpClass.__func__)
    tearDownClass=classmethod(base.AdminProxyTests.tearDownClass.__func__)
    call=base.AdminProxyTests.call
    def test_exact_routes_and_direct_navigation(self):
        for route in SPA:self.assertEqual(200,self.call('GET',route)[0])
        for route in ('dashboard','payments','refunds','profile'):self.assertTrue(allowed('GET','/api/v1/merchant/'+route))
        self.assertTrue(allowed('POST','/api/v1/merchant/profile/password'))
    def test_identity_query_and_method_boundaries(self):
        for route in ('/api/v1/merchant/pay\nments','/api/v1/merchant/payments?merchantId=OTHER','/api/v1/merchant/payments?userId=x','/api/v1/merchant/profile?role=ADMIN','/api/v1/merchant/dashboard?page=0','/api/v1/merchant/payments?size=101','/api/v1/merchant/payments?page=0&page=1','/api/v1/merchant/payments?sort=sql','/api/v1/merchant/payments?search=%0a','/api/v1/merchant/payments?search=%ZZ'):
            self.assertFalse(allowed_merchant('GET',route),route)
        self.assertFalse(allowed('POST','/api/v1/merchant/payments'));self.assertFalse(allowed('GET','/api/v1/merchant/profile/password'))
    def test_bearer_forwarded_cookie_not_forwarded_and_fixed_target(self):
        response=MagicMock(status=200);response.read.return_value=b'{"items":[]}';response.getheader.return_value=None;c=MagicMock();c.getresponse.return_value=response
        with patch('dev_server.http.client.HTTPConnection',return_value=c) as ctor:
            path='/api/v1/merchant/payments?currency=INR&page=0&size=25';self.assertEqual(200,self.call('GET',path,headers={'Authorization':'Bearer synthetic','Cookie':'pm_refresh='+'x'*43})[0]);self.assertEqual(('127.0.0.1',18080),ctor.call_args.args);self.assertEqual(path,c.request.call_args.args[1]);self.assertNotIn('Cookie',c.request.call_args.kwargs['headers'])
    def test_body_and_origin_limits(self):
        self.assertEqual(413,self.call('POST','/api/v1/merchant/profile/password','x'*4097,{'Content-Type':'application/json'})[0]);self.assertEqual(403,self.call('GET','/api/v1/merchant/dashboard',headers={'Origin':'https://evil.invalid'})[0])
if __name__=='__main__':unittest.main()
