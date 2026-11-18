import unittest
from pathlib import Path
import test_admin_proxy as helper
from dev_server import FRONTEND_ROUTES,allowed

class AdminAIUITests(unittest.TestCase):
    setUpClass=classmethod(helper.AdminProxyTests.setUpClass.__func__)
    tearDownClass=classmethod(helper.AdminProxyTests.tearDownClass.__func__)
    call=helper.AdminProxyTests.call
    def test_exact_static_route_and_api_methods(self):
        self.assertIn('/admin/ai',FRONTEND_ROUTES)
        for path in ('/admin/ai','/assets/js/admin-ai-tests.html'):
            status,body,headers=self.call('GET',path)
            self.assertEqual(200,status)
            self.assertIn('no-store',headers['Cache-Control'])
            self.assertIn('Content-Security-Policy',headers)
        self.assertTrue(allowed('POST','/api/v1/admin/ai/chat'))
        for method,path in (('GET','/api/v1/admin/ai/chat'),('POST','/api/v1/admin/ai/chat?role=ADMIN'),('POST','/api/v1/chat'),('GET','/api/v1/admin/ai/secrets')):
            self.assertFalse(allowed(method,path))
    def test_private_state_and_shared_safe_rendering(self):
        root=Path(__file__).resolve().parents[1]/'assets/js'
        for folder in ('admin-ai','chat'):
            for path in (root/folder).glob('*.js'):
                source=path.read_text()
                for banned in ('localStorage','sessionStorage','indexedDB','innerHTML','insertAdjacentHTML','http://127.0.0.1:8000','http://127.0.0.1:8082'):
                    self.assertNotIn(banned,source,path.name)
        source=(root/'chat/presentation.js').read_text()
        for attribute in ('aria-live','aria-busy','role'):
            self.assertIn(attribute,source)
        self.assertIn('adminChat?.busy()', (root/'portals/view.js').read_text())

if __name__=='__main__':unittest.main()
