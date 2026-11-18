import unittest
from pathlib import Path
from unittest.mock import patch,MagicMock
import test_admin_proxy as helper
from dev_server import allowed

class PaymentAIUITests(unittest.TestCase):
    setUpClass=classmethod(helper.AdminProxyTests.setUpClass.__func__)
    tearDownClass=classmethod(helper.AdminProxyTests.tearDownClass.__func__)
    call=helper.AdminProxyTests.call
    def test_exact_payment_chat_boundaries(self):
        path='/api/v1/payments/00000000-0000-4000-8000-000000000001/ai/chat'
        self.assertTrue(allowed('POST',path))
        self.assertFalse(allowed('GET',path))
        self.assertFalse(allowed('POST',path+'?paymentId=other'))
        response=MagicMock(status=200);response.read.return_value=b'{}';response.getheader.return_value='pm_refresh=not-forwarded'
        connection=MagicMock();connection.getresponse.return_value=response
        with patch('dev_server.http.client.HTTPConnection',return_value=connection) as ctor:
            status,_,headers=self.call('POST',path,'{"question":"Why?"}',{'Content-Type':'application/json','Authorization':'Bearer synthetic','Cookie':'pm_refresh='+'x'*43,'X-PayMesh-AI-Chat-Token':'private-not-forwarded'})
            self.assertEqual(200,status)
            self.assertEqual(('127.0.0.1',18080),ctor.call_args.args)
            self.assertEqual(40,ctor.call_args.kwargs['timeout'])
            forwarded=connection.request.call_args.kwargs['headers']
            self.assertNotIn('Cookie',forwarded)
            self.assertNotIn('X-PayMesh-AI-Chat-Token',forwarded)
            self.assertNotIn('Set-Cookie',headers)
        self.assertEqual(413,self.call('POST',path,'x'*32769,{'Content-Type':'application/json'})[0])
    def test_static_entrypoints_and_privacy(self):
        self.assertEqual(200,self.call('GET','/assets/js/payment-ai-tests.html')[0])
        root=Path(__file__).resolve().parents[1]
        html=(root/'index.html').read_text()
        for identifier in ('payment-ask-open','investigation-ask-open','payment-ask-close','payment-ask-panel','payment-ask-chat','payment-ask-feedback'):
            self.assertEqual(1,html.count('id="'+identifier+'"'))
        for path in (root/'assets/js/payment-ai').glob('*.js'):
            for banned in ('localStorage','sessionStorage','indexedDB','innerHTML','insertAdjacentHTML','http://127.0.0.1:8000','http://127.0.0.1:8082'):
                self.assertNotIn(banned,path.read_text(),path.name)
        app=(root/'assets/js/app.js').read_text()
        self.assertIn('paymentChatUI?.busy()',app)
        self.assertIn('onPaymentContextLeave',app)

if __name__=='__main__':unittest.main()
