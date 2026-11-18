"""Sanitized fixture tests only: no DB/service operation and no bearer/token material."""
import ast
import copy
from pathlib import Path
import unittest
from unittest.mock import Mock, patch
import phase673_session_diagnosis as d

RESET='2026-11-14T12:00:00.123456Z'
NOW='2026-11-14T13:00:00Z'


def account(version=1):
    return dict(enabled=True,account_status='ACTIVE',authorization_version=version,roles=['ADMIN'],created_at='2026-11-14T10:00:00Z')


def session(created='2026-11-14T11:00:00Z',version=0,revoked='2026-11-14T12:00:00Z'):
    return dict(created_at=created,authorization_version=version,account_status='ACTIVE',roles_snapshot='ADMIN',
                absolute_expires_at='2026-11-15T01:00:00Z',idle_expires_at='2026-11-14T20:00:00Z',revoked_at=revoked)


def report(rows,version=1):
    return d.analyze(account(version),rows,[dict(occurred_at=RESET)],NOW)


class SessionDiagnosisTests(unittest.TestCase):
    def test_revoked_old_and_valid_new_session_are_separate(self):
        r=report([session(),session(created='2026-11-14T12:05:00Z',version=1,revoked=None)])
        self.assertTrue(r['originalSessionPredicatePasses']);self.assertTrue(r['rowStateProvesRetainedPreResetRevocation'])
        self.assertEqual(1,r['createdBeforeReset']);self.assertEqual(1,r['createdAfterReset'])
        self.assertTrue(r['families'][1]['passesCurrentFamilyAccountChecks']);self.assertEqual(0,r['unrevokedPreResetFamilies'])

    def test_missing_rows_never_prove_historical_revocation_or_cleanup(self):
        for rows in ([],[session(created='2026-11-14T12:05:00Z',version=1,revoked=None)]):
            r=report(rows);self.assertFalse(r['originalSessionPredicatePasses']);self.assertFalse(r['rowStateProvesRetainedPreResetRevocation'])
            self.assertTrue(r['interpretation'].startswith('MISSING_PRE_RESET_ROWS'))
            self.assertFalse(r['deletedFamilyHistoryAvailable']);self.assertFalse(r['minimumLifetimeCleanupCouldHaveBecomeEligible'])

    def test_later_logout_all_can_make_lower_version_post_reset_row_fail_old_predicate(self):
        r=report([session(),session(created='2026-11-14T12:05:00Z',version=1,revoked='2026-11-14T12:10:00Z')],version=2)
        self.assertFalse(r['originalSessionPredicatePasses']);self.assertTrue(r['rowStateProvesRetainedPreResetRevocation'])
        self.assertEqual(1,r['originalPredicateIncludesPostResetFamilies']);self.assertEqual(1,r['originalPredicateRevokedAfterResetCount'])

    def test_unrevoked_pre_reset_version_mismatch_remains_anomaly_but_cannot_use_family(self):
        r=report([session(revoked=None)])
        self.assertEqual(1,r['unrevokedPreResetFamilies']);self.assertEqual(0,r['currentEligiblePreResetFamilies'])
        self.assertFalse(r['rowStateProvesRetainedPreResetRevocation']);self.assertTrue(r['interpretation'].startswith('UNREVOKED'))

    def test_current_eligible_pre_reset_family_is_explicit_red_flag(self):
        r=report([session(version=1,revoked=None)])
        self.assertEqual(1,r['currentEligiblePreResetFamilies']);self.assertFalse(r['actualJwtAcceptanceTested'])

    def test_microsecond_boundaries_are_not_waived(self):
        for value,passed,delta in [('2026-11-14T12:00:00.123455Z',True,-1),(RESET,True,0),('2026-11-14T12:00:00.123457Z',False,1)]:
            r=report([session(revoked=value)])
            self.assertEqual(passed,r['originalSessionPredicatePasses']);self.assertEqual(delta,r['families'][0]['revocationMinusResetMicroseconds'])
        r=report([session(created=RESET,version=1,revoked=None)])
        self.assertEqual(1,r['createdAtResetBoundary']);self.assertEqual(0,r['createdBeforeReset'])
        self.assertEqual(1,r['currentEligibleBoundaryFamilies']);self.assertFalse(r['rowStateProvesRetainedPreResetRevocation'])

    def test_expiry_and_cleanup_use_strict_actual_boundaries(self):
        row=session(version=1,revoked=None);row['absolute_expires_at']='2026-11-13T13:00:00Z';r=report([row])
        self.assertTrue(r['families'][0]['expiredNow']);self.assertFalse(r['families'][0]['eligibleForCurrentCleanup'])
        row['absolute_expires_at']='2026-11-13T12:59:59.999999Z';self.assertTrue(report([row])['families'][0]['eligibleForCurrentCleanup'])
        row['absolute_expires_at']=NOW;r=report([row]);self.assertEqual(0,r['currentEligiblePreResetFamilies'])

    def test_disabled_status_roles_and_idle_expiry_deny_family(self):
        for change in ('disabled','status','roles','idle'):
            a=account();row=session(version=1,revoked=None)
            if change=='disabled':a['enabled']=False
            if change=='status':row['account_status']='PENDING_APPROVAL'
            if change=='roles':row['roles_snapshot']='MERCHANT'
            if change=='idle':row['idle_expires_at']=NOW
            r=d.analyze(a,[row],[dict(occurred_at=RESET)],NOW)
            self.assertEqual(0,r['currentEligiblePreResetFamilies'])

    def test_no_reset_or_multiple_resets_are_evidence_limits(self):
        for events in ([],[dict(occurred_at=RESET),dict(occurred_at='2026-11-14T12:10:00Z')]):
            r=d.analyze(account(),[session()],events,NOW)
            self.assertTrue(r['interpretation'].startswith('NO_SINGLE_RESET_BOUNDARY'))
            self.assertNotIn('originalSessionPredicatePasses',r)

    def test_readonly_queries_and_explicit_dedicated_scope_no_credentials(self):
        obj=object.__new__(d.Diagnosis)
        with patch.object(d.Ops,'sql',return_value='ok') as base:
            self.assertEqual('ok',obj.sql('SELECT 1'));self.assertIn('REPEATABLE READ READ ONLY',base.call_args.args[0])
            with self.assertRaises(d.Stop):obj.sql('anything',write=True)
        obj.sql=Mock(return_value='{}');obj.snapshot(dict(admin='11111111-1111-4111-8111-111111111111',merchant='22222222-2222-4222-8222-222222222222'))
        query=obj.sql.call_args.args[0]
        self.assertIn(d.ADMIN,query);self.assertIn(d.MERCHANT,query)
        for forbidden in ('password_hash','otp_digest','token_digest','auth_refresh_tokens','payments','refunds','SELECT *'):
            self.assertNotIn(forbidden,query)
        self.assertIn('JOIN targets',query)

    def test_no_mutation_or_http_calls_in_diagnostic(self):
        tree=ast.parse(Path(d.__file__).read_text())
        forbidden={'restart','eligibility','reviewer','create_admin','prepare_accounts','http_json','snapshot_all','backup','refresh','logout'}
        for node in ast.walk(tree):
            if isinstance(node,ast.Call) and isinstance(node.func,ast.Attribute):self.assertNotIn(node.func.attr,forbidden)

if __name__=='__main__':unittest.main()
