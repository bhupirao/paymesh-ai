import unittest
from unittest.mock import patch,MagicMock
import test_admin_proxy as base
from checkout_proxy import allowed_checkout,checkout_page
class CheckoutProxyTests(unittest.TestCase):
 setUpClass=classmethod(base.AdminProxyTests.setUpClass.__func__)
 tearDownClass=classmethod(base.AdminProxyTests.tearDownClass.__func__)
 call=base.AdminProxyTests.call
 token='a'*43
 def test_exact_paths(self):
  root='/api/v1/checkout/'+self.token
  for method,path in [('GET',root),('GET',root+'/status'),('POST',root+'/pay')]:self.assertTrue(allowed_checkout(method,path))
  for method,path in [('POST',root),('GET',root+'/pay'),('PUT',root+'/pay'),('GET',root+'?token=x'),('GET',root+'/refund'),('GET',root+'/../x'),('GET',root+'a'),('GET',root.replace(self.token,'a'*42))]:self.assertFalse(allowed_checkout(method,path),(method,path))
 def test_public_document_has_no_portal_bootstrap(self):
  status,body,headers=self.call('GET','/checkout/'+self.token);self.assertEqual(200,status);self.assertIn(b'/assets/js/checkout/page.js',body);self.assertNotIn(b'/assets/js/app.js',body);self.assertNotIn(b'installPersistence',body);self.assertEqual('no-referrer',headers['Referrer-Policy']);self.assertFalse(checkout_page('/checkout/../index.html'))
 def test_strips_auth_and_cookies_fixed_target(self):
  reply=MagicMock(status=200);reply.read.return_value=b'{}';reply.getheader.return_value=None;c=MagicMock();c.getresponse.return_value=reply
  with patch('dev_server.http.client.HTTPConnection',return_value=c) as ctor:
   self.assertEqual(200,self.call('POST','/api/v1/checkout/'+self.token+'/pay','{"confirmed":true}',{'Content-Type':'application/json','Origin':'http://127.0.0.1:'+str(self.server.server_port),'X-PayMesh-Checkout':'1','Authorization':'Bearer synthetic','Cookie':'pm_refresh='+'x'*43,'Idempotency-Key':'synthetic'})[0]);self.assertEqual(('127.0.0.1',18080),ctor.call_args.args);h=c.request.call_args.kwargs['headers'];self.assertNotIn('Cookie',h);self.assertNotIn('Authorization',h);self.assertEqual('1',h['X-PayMesh-Checkout']);self.assertEqual('synthetic',h['Idempotency-Key'])
 def test_origin_size_and_wrong_routes(self):
  path='/api/v1/checkout/'+self.token+'/pay';self.assertEqual(403,self.call('POST',path,'{}',{'Content-Type':'application/json'})[0]);self.assertEqual(413,self.call('POST',path,'x'*4097,{'Content-Type':'application/json'})[0]);self.assertEqual(403,self.call('POST',path,'{}',{'Content-Type':'application/json','Origin':'https://evil.invalid','X-PayMesh-Checkout':'1'})[0]);self.assertEqual(404,self.call('GET','/api/v1/checkout/'+self.token+'/refunds')[0])
