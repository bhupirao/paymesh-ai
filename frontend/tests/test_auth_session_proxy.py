import http.client
import sys
from pathlib import Path
import threading
import unittest
from unittest.mock import MagicMock, patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from dev_server import Handler,ThreadingHTTPServer,allowed
class AuthSessionProxyTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.server=ThreadingHTTPServer(('127.0.0.1',0),Handler);cls.thread=threading.Thread(target=cls.server.serve_forever,daemon=True);cls.thread.start()
 @classmethod
 def tearDownClass(cls):cls.server.shutdown();cls.server.server_close();cls.thread.join()
 def call(self,path,headers=None,method='POST'):
  c=http.client.HTTPConnection('127.0.0.1',self.server.server_port);c.request(method,path,b'{}' if method=='POST' else None,headers or {});r=c.getresponse();out=r.status,r.read(),dict(r.getheaders());c.close();return out
 def good(self):return {'Origin':'http://127.0.0.1:'+str(self.server.server_port),'X-PayMesh-CSRF':'1','Content-Type':'application/json'}
 def test_exact_routes_and_direct_forgot_pages(self):
  for p in ['refresh','logout','logout-all','password/forgot','password/verify-otp','password/reset']:self.assertTrue(allowed('POST','/api/v1/auth/'+p));self.assertFalse(allowed('GET','/api/v1/auth/'+p))
  self.assertTrue(allowed('GET','/api/v1/auth/password/capabilities'))
  for p in ['/merchant/forgot-password','/admin/forgot-password']:self.assertEqual(self.call(p,method='GET')[0],200)
  self.assertFalse(allowed('POST','/api/v1/auth/password/approve'))
 def test_cookie_mutations_require_origin_and_csrf(self):
  for p in ['refresh','logout','logout-all','password/forgot','password/verify-otp','password/reset']:self.assertEqual(self.call('/api/v1/auth/'+p,{'Content-Type':'application/json'})[0],403)
 def proxy(self,path,headers,cookie):
  client=http.client.HTTPConnection('127.0.0.1',self.server.server_port);upstream=MagicMock();response=upstream.getresponse.return_value;response.status=200;response.read.return_value=b'{}';response.getheader.side_effect=lambda name:{'Set-Cookie':cookie}.get(name)
  with patch('dev_server.http.client.HTTPConnection',return_value=upstream):
   client.request('POST',path,b'{}',headers);r=client.getresponse();out=r.status,r.read(),dict(r.getheaders())
  client.close();return out,upstream
 def test_only_approved_refresh_cookie_and_headers_forwarded(self):
  headers=self.good();headers['Cookie']='unrelated=secret; pm_refresh='+'a'*43;headers['X-Forwarded-For']='evil'
  cookie='pm_refresh='+'b'*43+'; Path=/api/v1/auth; HttpOnly; SameSite=Strict'
  out,up=self.proxy('/api/v1/auth/refresh',headers,cookie);self.assertEqual(out[0],200);self.assertEqual(out[2]['Set-Cookie'],cookie)
  forwarded=up.request.call_args.kwargs['headers'];self.assertEqual(forwarded['Cookie'],'pm_refresh='+'a'*43);self.assertNotIn('X-Forwarded-For',forwarded);self.assertEqual(forwarded['X-PayMesh-CSRF'],'1')
 def test_cookie_never_forwarded_to_business_or_recovery(self):
  headers=self.good();headers['Cookie']='pm_refresh='+'a'*43
  for path in ['/api/v1/payments','/api/v1/auth/password/forgot']:
   out,up=self.proxy(path,headers,None);self.assertEqual(out[0],200);self.assertNotIn('Cookie',up.request.call_args.kwargs['headers'])
 def test_malformed_duplicate_cookie_and_upstream_cookie_rejected(self):
  headers=self.good();headers['Cookie']='pm_refresh='+'a'*43+'; pm_refresh='+'b'*43
  self.assertEqual(self.call('/api/v1/auth/refresh',headers)[0],400)
  for bad in ['pm_refresh=x; Path=/; HttpOnly; SameSite=Strict','other=secret; Path=/api/v1/auth; HttpOnly; SameSite=Strict','pm_refresh='+'a'*43+'; Path=/api/v1/auth; HttpOnly; SameSite=None']:
   self.assertEqual(self.proxy('/api/v1/auth/refresh',self.good(),bad)[0][0],502)
