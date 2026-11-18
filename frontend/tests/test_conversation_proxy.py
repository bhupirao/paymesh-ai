import unittest
from unittest.mock import MagicMock,patch
import test_admin_proxy as helper
from dev_server import allowed
class ConversationProxyTests(unittest.TestCase):
    setUpClass=classmethod(helper.AdminProxyTests.setUpClass.__func__)
    tearDownClass=classmethod(helper.AdminProxyTests.tearDownClass.__func__)
    call=helper.AdminProxyTests.call
    uid='00000000-0000-4000-8000-000000000001'
    def test_exact_role_paths(self):
        for role in ('merchant','admin'):
            b='/api/v1/'+role+'/ai/conversations';u=self.uid
            for method,p in [('POST',b),('GET',b+'?page=0&size=5&search=hello'),('GET',b+'/'+u),('GET',b+'/creations/'+u),('GET',b+'/'+u+'/messages'),('GET',b+'/'+u+'/requests/'+u)]+[('POST',b+'/'+u+'/'+a) for a in ('messages','rename','delete')]:
                self.assertTrue(allowed(method,p),(method,p))
    def test_history_queries_reach_java_handler(self):
        response=MagicMock(status=200);response.read.return_value=b'{}';response.getheader.return_value=None
        connection=MagicMock();connection.getresponse.return_value=response
        for role in ('merchant','admin'):
            base='/api/v1/'+role+'/ai/conversations'
            for path in (base+'?page=0&size=5&search=Saved+title',base+'/'+self.uid+'/messages?page=0&size=5'):
                with patch('dev_server.http.client.HTTPConnection',return_value=connection):
                    status,_,headers=self.call('GET',path,headers={'Authorization':'Bearer synthetic-only'})
                    self.assertEqual(200,status)
                    self.assertEqual(path,connection.request.call_args.args[1])
                    self.assertEqual('no-store',headers['Cache-Control'])

    def test_static_chat_assets_are_not_cached(self):
        for path in ('/assets/js/conversations/store.js','/assets/js/conversations/bookmark.js'):
            status,_,headers=self.call('GET',path)
            self.assertEqual(200,status);self.assertEqual('no-store',headers['Cache-Control'])

    def test_bad_routes_and_queries(self):
        b='/api/v1/admin/ai/conversations'
        for m,p in [('DELETE',b),('GET',b+'?ownerId=evil'),('GET',b+'?size=11'),('GET',b+'?page=0&page=1'),('POST',b+'?role=ADMIN'),('GET',b+'/not-uuid'),('GET',b+'/'+self.uid+'/sql'),('POST','/api/v1/chat')]:
            self.assertFalse(allowed(m,p),(m,p))
    def test_body_origin_and_cookie_boundary(self):
        p='/api/v1/merchant/ai/conversations/'+self.uid+'/messages'
        self.assertEqual(413,self.call('POST',p,'x'*8193,{'Content-Type':'application/json'})[0])
        self.assertEqual(403,self.call('POST',p,'{}',{'Content-Type':'application/json','Origin':'https://evil.invalid'})[0])
        response=MagicMock(status=200);response.read.return_value=b'{}';response.getheader.return_value='pm_refresh=forbidden'
        connection=MagicMock();connection.getresponse.return_value=response
        with patch('dev_server.http.client.HTTPConnection',return_value=connection) as ctor:
            status,_,headers=self.call('POST',p,'{}',{'Content-Type':'application/json','Authorization':'Bearer test-only','Cookie':'pm_refresh='+'x'*43})
            self.assertEqual(200,status);self.assertEqual(('127.0.0.1',18080),ctor.call_args.args);self.assertEqual(40,ctor.call_args.kwargs['timeout'])
            self.assertNotIn('Cookie',connection.request.call_args.kwargs['headers']);self.assertNotIn('Set-Cookie',headers)
if __name__=='__main__':unittest.main()
