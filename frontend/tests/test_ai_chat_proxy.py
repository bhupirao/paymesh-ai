import unittest
from unittest.mock import MagicMock,patch
import test_admin_proxy as helper
from dev_server import allowed

class ChatProxyTests(unittest.TestCase):
    setUpClass=classmethod(helper.AdminProxyTests.setUpClass.__func__)
    tearDownClass=classmethod(helper.AdminProxyTests.tearDownClass.__func__)
    call=helper.AdminProxyTests.call
    def test_chat_exact_routes_and_private_isolation(self):
        for path in ('/api/v1/merchant/ai/chat','/api/v1/admin/ai/chat','/api/v1/payments/00000000-0000-4000-8000-000000000001/ai/chat'):
            self.assertTrue(allowed('POST',path))
            self.assertFalse(allowed('GET',path))
            self.assertFalse(allowed('POST',path+'?evidence=forged'))
        for path in ('/api/v1/chat','/api/v1/merchant/ai/chat/extra','/api/v1/payments/not-uuid/ai/chat','http://127.0.0.1:8000/api/v1/chat','/actuator/health'):
            self.assertFalse(allowed('POST',path))
    def test_chat_fixed_upstream_timeout_and_secret_cookie_boundaries(self):
        response=MagicMock(status=200);response.read.return_value=b'{}';response.getheader.return_value='pm_refresh=not-allowed'
        connection=MagicMock();connection.getresponse.return_value=response
        with patch('dev_server.http.client.HTTPConnection',return_value=connection) as ctor:
            status,_,headers=self.call('POST','/api/v1/merchant/ai/chat','{}',{'Content-Type':'application/json','Authorization':'Bearer test-only','Cookie':'pm_refresh='+'x'*43,'X-PayMesh-AI-Chat-Token':'not-forwarded'})
            self.assertEqual(200,status);self.assertEqual(('127.0.0.1',18080),ctor.call_args.args);self.assertEqual(40,ctor.call_args.kwargs['timeout'])
            sent=connection.request.call_args.kwargs['headers'];self.assertEqual('Bearer test-only',sent['Authorization']);self.assertNotIn('Cookie',sent);self.assertNotIn('X-PayMesh-AI-Chat-Token',sent)
            self.assertNotIn('Set-Cookie',headers);self.assertIn('no-store',headers['Cache-Control'])
    def test_chat_limits_content_type_origin(self):
        path='/api/v1/admin/ai/chat'
        self.assertEqual(413,self.call('POST',path,'x'*32769,{'Content-Type':'application/json'})[0])
        self.assertEqual(415,self.call('POST',path,'{}',{'Content-Type':'text/plain'})[0])
        self.assertEqual(403,self.call('POST',path,'{}',{'Content-Type':'application/json','Origin':'https://evil.invalid'})[0])

if __name__=='__main__':unittest.main()
