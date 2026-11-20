"""Approval fixture contract regression; never contacts a real API/database."""
import ast,re,tempfile,unittest
from pathlib import Path
from unittest.mock import Mock
from container_e2e import Suite

class ApprovalContractTests(unittest.TestCase):
    def test_generated_approval_requests_use_valid_references_and_pending_merchants(self):
        with tempfile.TemporaryDirectory() as directory:
            folder=Path(directory);(folder/'secrets').mkdir()
            for name in ['admin_password','merchant_password']:(folder/'secrets'/name).write_text('synthetic-only')
            suite=object.__new__(Suite);suite.folder=folder;actors={};pending=set();approved=set();calls=[]
            def session(actor):
                client=Mock();actors[actor]=client
                def call(method,path,body=None,**kwargs):
                    calls.append((actor,method,path,body))
                    if path=='/api/v1/auth/register':
                        self.assertEqual(kwargs['expected'],(201,));pending.add(body['email']);return {'accountStatus':'PENDING_APPROVAL'}
                    if path.startswith('/api/v1/admin/merchants?'):
                        from urllib.parse import parse_qs,urlsplit
                        email=parse_qs(urlsplit(path).query)['search'][0];self.assertIn(email,pending);return {'items':[{'merchantId':email}]}
                    if path=='/api/v1/admin/merchant/approve':
                        self.assertEqual(actor,'ADMIN');self.assertEqual(method,'POST');self.assertIn(body['merchantId'],pending)
                        self.assertTrue(body['ownershipAttested']);self.assertRegex(body['reviewReference'],r'\A[A-Za-z0-9][A-Za-z0-9._/\-]{2,99}\Z')
                        approved.add(body['merchantId']);return {'status':'ACTIVE'}
                    if path=='/api/v1/merchant/profile':
                        email='merchant-'+actor[-1].lower()+'@e2e.example.test';self.assertIn(email,approved);return {'merchantId':email,'accountStatus':'ACTIVE'}
                    if path=='/api/v1/auth/refresh':return {'accessToken':'synthetic-only'}
                    return {}
                client.call.side_effect=call;return client
            suite.session=session;suite.authentication()
            approvals=[c for c in calls if c[2]=='/api/v1/admin/merchant/approve'];self.assertEqual(len(approvals),2)
            self.assertTrue(all(c[3]['reviewReference']=='CI-DISPOSABLE-FIXTURE-OWNERSHIP' for c in approvals))
            self.assertEqual(len(approved),2)
    def test_original_reference_violates_current_java_validation(self):
        source=(Path(__file__).resolve().parents[1]/'backend/src/main/java/com/paymesh/backend/security/accounts/MerchantAdministration.java').read_text()
        self.assertIn('reference.matches("[A-Za-z0-9][A-Za-z0-9._/\\\\-]{2,99}")',source)
        self.assertIsNone(re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._/\-]{2,99}','CI disposable fixture ownership'))
        self.assertIsNotNone(re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._/\-]{2,99}','CI-DISPOSABLE-FIXTURE-OWNERSHIP'))

if __name__=='__main__':unittest.main()
