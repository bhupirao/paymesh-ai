import unittest
from review_publication import review,KEY_MARKER
class ReviewTests(unittest.TestCase):
    def helper(self):
        return KEY_MARKER+b' generateKeyPair() Base64.getMimeEncoder getPrivate().getEncoded()'
    def test_reviewed_dynamic_helper(self):
        issues,known=review('backend/src/test/java/com/paymesh/backend/security/accounts/SessionRecoveryIntegrationTest.java',self.helper())
        self.assertEqual(issues,[]);self.assertEqual(known,['DYNAMIC_TEST_KEY_DELIMITER'])
    def test_unknown_marker_is_not_suppressed(self):
        issues,known=review('unknown.java',self.helper())
        self.assertIn('PRIVATE_KEY_PATTERN',issues);self.assertFalse(known)
    def test_payload_not_hidden_by_generated_helper(self):
        issues,known=review('backend/src/test/java/com/paymesh/backend/security/accounts/SessionRecoveryIntegrationTest.java',self.helper()+b'MII'+b'A'*70)
        self.assertIn('ENCODED_KEY_OR_CERTIFICATE_REVIEW',issues);self.assertIn('PRIVATE_KEY_PATTERN',issues);self.assertFalse(known)
    def test_delimiter_only_fixture(self):
        issues,known=review('deploy/test_container_preparation.py',b"b'"+KEY_MARKER+b"'")
        self.assertEqual(issues,[]);self.assertEqual(known,['SCANNER_DELIMITER_ONLY_FIXTURE'])
    def test_literal_jwt_not_ignored_in_tests(self):
        issues,_=review('tests/fixture.py',b'eyJ'+b'a'*12+b'.'+b'b'*24+b'.'+b'c'*24)
        self.assertIn('LITERAL_JWT_REVIEW',issues)
    def test_local_configuration_flagged(self):
        issues,_=review('.aws/config',b'demo')
        self.assertIn('LOCAL_CONFIGURATION',issues)
if __name__=='__main__':unittest.main()
