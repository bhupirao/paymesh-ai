import unittest
from pathlib import Path
import phase681_analytics_deployment as d
class AnalyticsDeploymentTests(unittest.TestCase):
    def test_new_evidence_prefix_preserves_original_deployment_records(self):
        s=Path(d.__file__).read_text();self.assertIn("super().__init__('redeploy-phase681-analytics')",s);self.assertIn('REDEPLOY_PHASE681_ANALYTICS_OTP_DISABLED',s);self.assertIn('DashboardAnalytics.class',s)
    def test_v11_no_new_migration_and_backup_before_stop(self):
        s=Path(d.__file__).read_text();self.assertIn('1,2,3,4,5,6,7,8,9,10,11|true',s);self.assertLess(s.index('self.backup()'),s.index('self.restart(False)'));self.assertIn('[6,4,4,2,6,4]',s);self.assertIn('self.unchanged_other_services()',s)
if __name__=='__main__':unittest.main()
