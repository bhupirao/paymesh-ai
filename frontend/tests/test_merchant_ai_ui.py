import unittest
from pathlib import Path
import test_admin_proxy as helper
from dev_server import FRONTEND_ROUTES,allowed

class MerchantAIUITests(unittest.TestCase):
    setUpClass=classmethod(helper.AdminProxyTests.setUpClass.__func__)
    tearDownClass=classmethod(helper.AdminProxyTests.tearDownClass.__func__)
    call=helper.AdminProxyTests.call
    def test_direct_route_and_mocked_test_page(self):
        self.assertIn('/merchant/ai',FRONTEND_ROUTES)
        for path in ('/merchant/ai','/assets/js/merchant-ai-tests.html'):
            status,body,headers=self.call('GET',path)
            self.assertEqual(200,status)
            self.assertIn('no-store',headers['Cache-Control'])
            self.assertIn('Content-Security-Policy',headers)
        self.assertFalse(allowed('GET','/api/v1/merchant/ai/chat'))
        self.assertFalse(allowed('POST','/api/v1/chat'))
    def test_private_modules_no_storage_or_untrusted_html(self):
        root=Path(__file__).resolve().parents[1]/'assets/js/merchant-ai'
        for p in [*root.glob('*.js'),*(root.parent/'chat').glob('*.js')]:
            source=p.read_text()
            for banned in ('localStorage','sessionStorage','indexedDB','innerHTML','insertAdjacentHTML','http://127.0.0.1:8000','http://127.0.0.1:8082'):
                self.assertNotIn(banned,source,p.name)
        self.assertIn('mountConversation',(root/'view.js').read_text())
        view=(root.parent/'chat/presentation.js').read_text()
        self.assertIn("'role','status'",view)
        self.assertIn("'aria-live','polite'",view)
        self.assertIn("'aria-busy'",view)

if __name__=='__main__':unittest.main()
