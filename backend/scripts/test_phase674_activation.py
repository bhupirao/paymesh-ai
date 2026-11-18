"""No live services/DB; verify operator gate ordering and read-only integrity collection."""
import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock,patch
import phase674_activation as a

class ActivationTests(unittest.TestCase):
    def test_integrity_uses_only_read_queries_and_no_password_hashes(self):
        obj=object.__new__(a.Activation);obj.sql=Mock(return_value='test-only-records')
        values=obj.integrity();self.assertEqual(13,len(values))
        for call in obj.sql.call_args_list:
            self.assertTrue(call.args[0].startswith('SELECT '));self.assertNotIn('password_hash',call.args[0]);self.assertFalse(call.kwargs)
    def test_no_live_operation_before_target_history_otp_counts_and_confirmation(self):
        for broken in ('target','history','otp','counts','confirmation'):
            with tempfile.TemporaryDirectory() as tmp:
                obj=object.__new__(a.Activation);obj.repo=Path(tmp);obj.private=Path(tmp);obj.evidence={};(obj.repo/'.git').mkdir();(obj.repo/'.git/index').write_bytes(b'fixture')
                obj.env={key:'test-only' for key in ('PAYMESH_JWT_ISSUER','PAYMESH_JWT_AUDIENCE','PAYMESH_RAZORPAY_WEBHOOK_SECRET','PAYMESH_STRIPE_WEBHOOK_SECRET','PAYMESH_SETTLEMENT_ADMIN_TOKEN')}
                obj.service=Mock(return_value={'pid':'1','start':'fixture'});obj.launch=Mock(side_effect=lambda:setattr(obj,'flags',{'paymesh.demo.password-recovery.enabled':'false'}))
                obj.command=Mock(side_effect=lambda args,**kwargs:'PostgreSQL 16.3' if '--version' in args else 'fixture')
                def sql(query):
                    if 'current_database()' in query:return 'wrong' if broken=='target' else 'paymesh_demo|paymesh_demo_user|127.0.0.1|5432'
                    if 'string_agg(version' in query:return 'wrong' if broken=='history' else '1,2,3,4,5,6,7,8,9,10|true'
                    return '0'
                obj.sql=Mock(side_effect=sql);obj.http_json=Mock(return_value=(200,{'localDemoEnabled':broken=='otp'}));obj.counts=Mock(return_value=[0]*6 if broken=='counts' else [6,4,4,2,6,4]);obj.integrity=Mock(return_value={});obj.backup=Mock();obj.restart=Mock()
                with patch.object(a,'protected',side_effect=lambda path,*args:path),patch.object(a,'hidden',return_value='test-only-password'),patch('builtins.input',return_value='NO_APPROVAL'):
                    with self.assertRaises(a.Stop):obj.run()
                obj.backup.assert_not_called();obj.restart.assert_not_called()
    def test_new_artifact_requires_v11_while_old_recovery_guard_is_unchanged(self):
        source=Path(a.__file__).read_text();self.assertIn('set(range(1, 12))',source);self.assertIn('V11__merchant_administration.sql',source)
        old=Path(a.__file__).with_name('phase673_otp_ops.py').read_text();self.assertIn('set(range(1, 11))',old)
        self.assertNotIn('flyway.clean',source);self.assertNotIn('flyway.repair',source);self.assertNotIn('paymesh_db',source)

if __name__=='__main__':unittest.main()
