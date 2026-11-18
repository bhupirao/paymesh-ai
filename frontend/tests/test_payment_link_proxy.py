import unittest
from merchant_proxy import allowed_merchant,SPA
class PaymentLinkProxyTests(unittest.TestCase):
 def test_exact_routes(self):
  root='/api/v1/merchant/payment-links';ident='b5a18fe4-38a9-4fc3-87a7-e8a09fe9aa11'
  for method,path in [('POST',root),('GET',root),('GET',root+'?page=0&size=5&status=ACTIVE&currency=INR'),('GET',root+'/'+ident),('POST',root+'/'+ident+'/cancel')]:self.assertTrue(allowed_merchant(method,path),(method,path))
 def test_boundaries(self):
  root='/api/v1/merchant/payment-links'
  for path in [root+'?merchantId=x',root+'?size=51',root+'?page=-1',root+'?page=0&page=1',root+'?status=SUCCESS',root+'?search=%0a',root+'?search=%ZZ',root+'/../profile',root+'?currency=EUR'] :self.assertFalse(allowed_merchant('GET',path),path)
  for path in [root+'?x=1',root+'/bogus',root+'/b5a18fe4-38a9-4fc3-87a7-e8a09fe9aa11']:self.assertFalse(allowed_merchant('POST',path),path)
 def test_spa(self):
  self.assertIn('/merchant/payment-links',SPA);self.assertIn('/merchant/payment-links/create',SPA)
