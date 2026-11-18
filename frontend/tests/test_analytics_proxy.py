import unittest
from dev_server import allowed
from admin_proxy import allowed_admin
from merchant_proxy import allowed_merchant
class AnalyticsProxyTests(unittest.TestCase):
    def test_exact_read_only_analytics_routes(self):
        for role in ('merchant','admin'):
            self.assertTrue(allowed('GET','/api/v1/'+role+'/analytics?currency=INR&from=2026-01-01T00%3A00%3A00Z&to=2026-01-02T00%3A00%3A00Z'))
            self.assertFalse(allowed('POST','/api/v1/'+role+'/analytics'))
    def test_no_merchant_identity_selection_or_duplicate_query(self):
        self.assertFalse(allowed_merchant('GET','/api/v1/merchant/analytics?merchantId=OTHER'));self.assertFalse(allowed_admin('GET','/api/v1/admin/analytics?size=100'));self.assertFalse(allowed_admin('GET','/api/v1/admin/analytics?currency=INR&currency=USD'));self.assertTrue(allowed_admin('GET','/api/v1/admin/analytics?merchantId=KNOWN'))
if __name__=='__main__':unittest.main()
