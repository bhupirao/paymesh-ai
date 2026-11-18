"""Mock-only closeout checks: never instantiate Ops or use a live DB/HTTP service."""
import copy
from datetime import datetime
from decimal import Decimal
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch
import uuid
import phase673_closeout as c


def fixture():
    root, admin, merchant = [str(uuid.uuid4()) for _ in range(3)]
    users = [dict(user_id=id, login_normalized=name, enabled=True, account_status=status, authorization_version=1,
                  created_at='2026-11-14T10:00:00Z', password_hash='test-only-never-output-hash')
             for id,name,status in ((root,c.REVIEWER,'ACTIVE'),(admin,c.ADMIN,'ACTIVE'),(merchant,c.MERCHANT,'PENDING_APPROVAL'))]
    state = dict(admin=admin,merchant=merchant,reviewer=dict(id=root,version=1),reference='test-review')
    data = dict(app_users=users, user_roles=[dict(user_id=u['user_id'],role_name='MERCHANT' if u['user_id']==merchant else 'ADMIN') for u in users],
                merchant_registrations=[dict(user_id=merchant,merchant_id='TEST_ONLY',email=c.MERCHANT)],
                merchants=[dict(merchant_id='TEST_ONLY',active=False,verified=False,verified_by=None,verified_at=None)],
                merchant_memberships=[dict(user_id=merchant,merchant_id='TEST_ONLY',active=False,granted_by=None)],
                eligibility=[dict(user_id=id,portal=portal,enabled=True,designated_by=root,review_reference='test-review') for id,portal in ((admin,'ADMIN'),(merchant,'MERCHANT'))],
                sessions=[],challenges=[],grants=[],audit=[],collectedAt='2026-11-15T01:00:00Z')
    data['audit'].append(dict(event_type='ACCOUNT_CREATED',outcome='SUCCESS',resource_id=admin,resource_type='ACCOUNT',actor_user_id=root,actor_identifier=c.REVIEWER,metadata=dict(role='ADMIN'),occurred_at='2026-11-14T10:00:00Z'))
    for id,portal in ((admin,'ADMIN'),(merchant,'MERCHANT')):
        data['audit'].append(dict(event_type='LOCAL_DEMO_PASSWORD_RESET',outcome='SUCCESS',resource_id=id,resource_type='ACCOUNT',actor_user_id=None,actor_identifier=None,metadata=dict(source='insecure_local_demo_on_screen_otp'),occurred_at='2026-11-14T12:00:01Z'))
        data['sessions'] += [dict(user_id=id,authorization_version=0,created_at='2026-11-14T11:00:00Z',revoked_at='2026-11-14T12:00:00Z'),dict(user_id=id,authorization_version=1,created_at='2026-11-14T12:01:00Z',revoked_at=None)]
        challenge=str(uuid.uuid4())
        data['challenges'].append(dict(challenge_id=challenge,user_id=id,portal=portal,authorization_version=0,consumed_at='2026-11-14T12:00:00Z'))
        data['grants'].append(dict(challenge_id=challenge,consumed_at='2026-11-14T12:00:00Z'))
    for row in data['sessions']:
        row.update(account_status='PENDING_APPROVAL' if row['user_id']==merchant else 'ACTIVE',roles_snapshot='MERCHANT' if row['user_id']==merchant else 'ADMIN',absolute_expires_at='2026-12-15T00:00:00Z',idle_expires_at='2026-12-15T00:00:00Z')
    return data,state


class CloseoutTests(unittest.TestCase):
    def test_read_only_transactions_and_write_rejection(self):
        obj=object.__new__(c.Closeout)
        with patch.object(c.Ops,'sql',return_value='ok') as base:
            self.assertEqual('ok',obj.sql('SELECT 1'))
            text=base.call_args.args[0]
            self.assertTrue(text.startswith('BEGIN ISOLATION LEVEL REPEATABLE READ READ ONLY;'))
            self.assertTrue(text.endswith('; COMMIT;')); self.assertFalse(base.call_args.kwargs['write'])
            with self.assertRaises(c.Stop): obj.sql('UPDATE anything',write=True)
            self.assertEqual(1,base.call_count)

    def test_snapshot_has_no_otp_refresh_or_reset_digests(self):
        obj=object.__new__(c.Closeout);obj.sql=Mock(return_value='{}');obj.snapshot()
        query=obj.sql.call_args.args[0]
        for forbidden in ('otp_digest','token_digest','auth_refresh_tokens','pg_read_file'):
            self.assertNotIn(forbidden,query)
        self.assertIn('public.auth_sessions',query);self.assertIn('public.security_audit_events',query)

    def test_correct_pre_audit_allows_current_unrevoked_signins(self):
        data,targets=fixture(); result=c.audit_accounts(data,targets,True)
        self.assertEqual(1,result['admin']['priorFamiliesRevoked']); self.assertEqual(1,result['merchant']['postResetFamilies'])

    def test_post_requires_disabled_scope_and_all_consumed(self):
        data,targets=fixture()
        for e in data['eligibility']:e['enabled']=False
        c.audit_accounts(data,targets,False)
        data['grants'][0]['consumed_at']=None
        with self.assertRaises(c.Stop):c.audit_accounts(data,targets,False)

    def test_extra_missing_resets_and_operational_reset_fail(self):
        for change in ('extra','missing','operational'):
            data,targets=fixture()
            if change=='extra':data['audit'].append(copy.deepcopy(data['audit'][1]))
            if change=='missing':data['audit'].pop()
            if change=='operational':
                row=copy.deepcopy(data['audit'][1]);row['resource_id']=targets['reviewer']['id'];data['audit'].append(row)
            with self.assertRaises(c.Stop):c.audit_accounts(data,targets,True)

    def test_actor_source_timestamp_and_versions_fail_closed(self):
        for key,value in [('actor_user_id',str(uuid.uuid4())),('metadata',{'source':'wrong'}),('occurred_at','2099-01-01T00:00:00Z')]:
            data,targets=fixture();data['audit'][1][key]=value
            with self.assertRaises(c.Stop):c.audit_accounts(data,targets,True)
        data,targets=fixture();data['app_users'][1]['authorization_version']=2
        with self.assertRaises(c.Stop):c.audit_accounts(data,targets,True)

    def test_wrong_admin_creation_actor_is_rejected(self):
        data,targets=fixture();data['audit'][0]['actor_user_id']=targets['admin']
        with self.assertRaises(c.Stop):c.audit_accounts(data,targets,True)

    def test_prior_family_not_revoked_is_rejected(self):
        data,targets=fixture();data['sessions'][0]['revoked_at']=None
        with self.assertRaises(c.Stop):c.audit_accounts(data,targets,True)

    def test_wrong_roles_pending_activation_and_broad_eligibility_rejected(self):
        for change in ('role','membership','registry','eligibility'):
            data,targets=fixture()
            if change=='role':data['user_roles'][1]['role_name']='MERCHANT'
            if change=='membership':data['merchant_memberships'][0]['active']=True
            if change=='registry':data['merchants'][0]['verified']=True
            if change=='eligibility':data['eligibility'].append(dict(user_id=targets['reviewer']['id'],portal='ADMIN',enabled=True))
            with self.assertRaises(c.Stop):c.audit_accounts(data,targets,True)

    def test_copy_null_escapes_empty_unicode_and_malformed(self):
        text='COPY public.payments (id, detail, other) FROM stdin;\n1\tline\\nwith\\tunicode-é\\\\end\t\\N\n\\.\n'
        cols,rows=c.copy_rows(text,'payments');self.assertEqual(['id','detail','other'],cols)
        self.assertEqual('line\nwith\tunicode-é\\end',rows[0]['detail']);self.assertIsNone(rows[0]['other'])
        self.assertEqual([],c.copy_rows('COPY public.payments (id) FROM stdin;\n\\.\n','payments')[1])
        for text in ('missing','COPY public.payments (id, x) FROM stdin;\n1\n\\.\n'):
            with self.assertRaises(c.Stop):c.copy_rows(text,'payments')

    def test_exact_amounts_and_timestamp_normalization_and_row_changes(self):
        types={'amount':'numeric','at':'timestamp with time zone','ok':'boolean'};cols=list(types)
        old=[dict(amount='999999999999.99',at='2026-11-14 15:30:00+05:30',ok='t')]
        live=[dict(amount=Decimal('999999999999.99'),at='2026-11-14T10:00:00+00:00',ok=True)]
        self.assertEqual(c.row_counts(old,cols,types),c.row_counts(live,cols,types))
        live[0]['amount']=Decimal('999999999999.98')
        self.assertNotEqual(c.row_counts(old,cols,types),c.row_counts(live,cols,types))

    def test_pre_post_fingerprints_preserve_password_without_storing_hash(self):
        obj=object.__new__(c.Closeout); obj.phase='pre'; obj.services={k:dict(pid='1',start='test') for k in ('frontend','ai','llm')};obj.flags={'paymesh.sessions.origin':'http://127.0.0.1:5500'};obj.evidence={}
        snapshot={t:[] for t in c.ACCOUNTS+c.FINANCIAL};snapshot['collectedAt']='2026-11-15T01:00:00Z'
        snapshot['app_users']=[dict(password_hash='test-only-new-private-hash')]
        with tempfile.TemporaryDirectory() as tmp:
            obj.baseline_file=Path(tmp)/'pre.json'
            def save(path,data):
                path.write_text(json.dumps(data));path.chmod(0o600)
            obj.private_json=save;obj.compare_pre_post(snapshot)
            self.assertNotIn('test-only-new-private-hash',obj.baseline_file.read_text())
            obj.phase='post';obj.compare_pre_post(snapshot)
            snapshot['app_users'][0]['password_hash']='changed'
            with self.assertRaises(c.Stop):obj.compare_pre_post(snapshot)

    def test_backup_row_comparison_rejects_same_count_financial_changes_and_bad_checksum(self):
        import hashlib
        obj=object.__new__(c.Closeout);obj.evidence={}
        snapshot={t:[{'id':'test-id','amount':Decimal('25.00')}] for t in c.FINANCIAL+c.ACCOUNTS}
        snapshot['types']=[dict(table_name=t,column_name=col,data_type=kind) for t in c.FINANCIAL+c.ACCOUNTS for col,kind in (('id','text'),('amount','numeric'))]
        def command(args):
            if '--list' in args:return 'mock archive list'
            table=next(a.split('=',1)[1] for a in args if str(a).startswith('--table='))
            return 'COPY public.'+table+' (id, amount) FROM stdin;\ntest-id\t25.00\n\\.\n'
        obj.command=Mock(side_effect=command)
        with tempfile.TemporaryDirectory() as tmp:
            obj.private=Path(tmp);folder=obj.private/'backups';folder.mkdir(mode=0o700)
            path=folder/'test.dump';path.write_bytes(b'mock custom-format archive');path.chmod(0o600)
            obj.activation={'backup':{'path':str(path),'sha256':hashlib.sha256(path.read_bytes()).hexdigest()}}
            obj.compare_backup(snapshot)
            self.assertTrue(obj.evidence['financialRowComparison']['matched'])
            snapshot['payments'][0]['amount']=Decimal('24.99')
            with self.assertRaises(c.Stop):obj.compare_backup(snapshot)
            obj.activation['backup']['sha256']='invalid';obj.command.reset_mock()
            with self.assertRaises(c.Stop):obj.compare_backup(snapshot)
            obj.command.assert_not_called()

    def test_verifier_source_has_no_mutation_or_recovery_http_operations(self):
        import ast
        tree=ast.parse(Path(c.__file__).read_text())
        forbidden={'restart','eligibility','backup','reviewer','create_admin','prepare_accounts'}
        for node in ast.walk(tree):
            if isinstance(node,ast.Call) and isinstance(node.func,ast.Attribute):
                self.assertNotIn(node.func.attr,forbidden)
                if node.func.attr=='http_json':
                    self.assertEqual(1,len(node.args));self.assertEqual([],node.keywords)
        self.assertNotIn('/api/v1/auth/password/reset',Path(c.__file__).read_text())

    def test_missing_post_baseline_fails_without_writing(self):
        obj=object.__new__(c.Closeout);obj.phase='post';obj.flags={};obj.evidence={};obj.private_json=Mock()
        snapshot={t:[] for t in c.ACCOUNTS+c.FINANCIAL}
        with tempfile.TemporaryDirectory() as tmp:
            obj.baseline_file=Path(tmp)/'missing.json'
            with self.assertRaises(c.Stop):obj.compare_pre_post(snapshot)
        obj.private_json.assert_not_called()

if __name__=='__main__':unittest.main()
