"""Read-only diagnosis; not a closeout pass or an authentication/recovery experiment.
Only two fixed disposable identities are queried. No passwords, tokens or digests selected.
"""
from datetime import datetime, timezone, timedelta
import json
import hashlib
import re
import os
from pathlib import Path
import sys
from phase673_otp_ops import Ops, Stop, PG, ADMIN, MERCHANT, protected, hidden, identifier, literal
from phase673_closeout import require, instant


def micros(delta):
    return delta.days*86400000000 + delta.seconds*1000000 + delta.microseconds


def analyze(account, sessions, audits, observed):
    now = instant(observed)
    events = sorted(audits, key=lambda e:instant(e['occurred_at']))
    safe = {'authorizationVersion':account['authorization_version'], 'enabled':account['enabled'],
            'accountStatus':account['account_status'], 'roles':account['roles'],
            'accountCreatedAt':account['created_at'],
            'earliestPossibleCleanupAtMinimumConfiguredLifetime':(instant(account['created_at'])+timedelta(seconds=900+86400)).isoformat(),
            'minimumLifetimeCleanupCouldHaveBecomeEligible':now > instant(account['created_at'])+timedelta(seconds=900+86400),
            'successfulResetCount':len(events), 'resetAuditTimestamps':[e['occurred_at'] for e in events],
            'retainedFamilyCount':len(sessions), 'revocationReason':'Not recorded in auth_sessions',
            'actualJwtAcceptanceTested':False, 'deletedFamilyHistoryAvailable':False}
    if len(events) != 1:
        safe['interpretation'] = 'NO_SINGLE_RESET_BOUNDARY: inspect audit history; no historical revocation certification.'
        return safe
    when = instant(events[0]['occurred_at'])
    require(when <= now, 'Reset audit is later than database observation; investigate clocks.')
    roles = ','.join(sorted(account['roles']))
    rows = []
    for index, session in enumerate(sorted(sessions,key=lambda s:instant(s['created_at'])),1):
        created = instant(session['created_at'])
        revoked = instant(session['revoked_at']) if session['revoked_at'] is not None else None
        absolute, idle = instant(session['absolute_expires_at']), instant(session['idle_expires_at'])
        temporal = 'BEFORE' if created < when else ('AFTER' if created > when else 'EQUAL_BOUNDARY')
        lower = session['authorization_version'] < account['authorization_version']
        eligible = (account['enabled'] and bool(account['roles']) and revoked is None and absolute > now and idle > now
                    and session['authorization_version']==account['authorization_version']
                    and session['account_status']==account['account_status'] and session['roles_snapshot']==roles)
        rows.append({'familyOrdinal':index, 'createdAt':session['created_at'], 'authorizationVersion':session['authorization_version'],
                     'relativeToResetAudit':temporal, 'lowerThanCurrentVersion':lower, 'revokedAt':session['revoked_at'],
                     'revocationMinusResetMicroseconds':micros(revoked-when) if revoked is not None else None,
                     'revokedByResetAuditTime':revoked is not None and revoked<=when,
                     'absoluteExpiresAt':session['absolute_expires_at'], 'idleExpiresAt':session['idle_expires_at'],
                     'expiredNow':absolute<=now or idle<=now,
                     'eligibleForCurrentCleanup':absolute < now - timedelta(days=1),
                     'passesCurrentFamilyAccountChecks':eligible})
    before = [s for s in rows if s['relativeToResetAudit']=='BEFORE']
    lower = [s for s in rows if s['lowerThanCurrentVersion']]
    safe.update({'families':rows, 'createdBeforeReset':len(before),
                 'createdAtResetBoundary':sum(s['relativeToResetAudit']=='EQUAL_BOUNDARY' for s in rows),
                 'createdAfterReset':sum(s['relativeToResetAudit']=='AFTER' for s in rows),
                 'revokedBeforeOrAtReset':sum(s['revokedByResetAuditTime'] for s in rows),
                 'unrevokedPreResetFamilies':sum(s['revokedAt'] is None for s in before),
                 'revokedAfterResetPreFamilies':sum(s['revokedAt'] is not None and not s['revokedByResetAuditTime'] for s in before),
                 'currentEligiblePreResetFamilies':sum(s['passesCurrentFamilyAccountChecks'] for s in before),
                 'currentEligibleBoundaryFamilies':sum(s['passesCurrentFamilyAccountChecks'] for s in rows if s['relativeToResetAudit']=='EQUAL_BOUNDARY'),
                 'originalPredicateLowerVersionCount':len(lower),
                 'originalPredicateUnrevokedCount':sum(s['revokedAt'] is None for s in lower),
                 'originalPredicateRevokedAfterResetCount':sum(s['revokedAt'] is not None and not s['revokedByResetAuditTime'] for s in lower),
                 'originalPredicateIncludesPostResetFamilies':sum(s['relativeToResetAudit']=='AFTER' for s in lower),
                 'originalSessionPredicatePasses':bool(lower) and all(s['revokedByResetAuditTime'] for s in lower),
                 'rowStateProvesRetainedPreResetRevocation':bool(before) and all(s['revokedByResetAuditTime'] for s in before)})
    if not before:
        safe['interpretation']='MISSING_PRE_RESET_ROWS: absent, never created or cleaned up cannot be distinguished from retained rows alone.'
    elif safe['unrevokedPreResetFamilies']:
        safe['interpretation']='UNREVOKED_PRE_RESET_ROWS: investigate trigger/revocation behavior even if version/expiry currently blocks access.'
    elif safe['revokedAfterResetPreFamilies'] or safe['createdAtResetBoundary']:
        safe['interpretation']='ORDERING_OR_PRECISION_REVIEW: do not infer reset-time revocation or waive timestamp assertions.'
    else:
        safe['interpretation']='RETAINED_PRE_RESET_ROWS_REVOKED: timestamps support retained-row revocation; not a replay/token test.'
    return safe


class Diagnosis(Ops):
    def __init__(self):
        super().__init__('diagnose-session-revocation')

    def sql(self, query, write=False):
        require(not write, 'Diagnostic SQL writes are forbidden.')
        return super().sql("BEGIN ISOLATION LEVEL REPEATABLE READ READ ONLY; SET LOCAL timezone='UTC'; SET LOCAL statement_timeout='20s'; " + query + '; COMMIT;',write=False)

    def snapshot(self, targets):
        admin, merchant = identifier(targets['admin']), identifier(targets['merchant'])
        cte = "WITH targets AS (SELECT CASE WHEN u.login_normalized="+literal(ADMIN)+" THEN 'admin' ELSE 'merchant' END AS label,u.user_id,u.enabled,u.account_status,u.authorization_version,u.created_at,(SELECT COALESCE(json_agg(role_name ORDER BY role_name),'[]'::json) FROM public.user_roles r WHERE r.user_id=u.user_id) AS roles FROM public.app_users u WHERE (u.user_id="+literal(admin)+"::uuid AND u.login_normalized="+literal(ADMIN)+") OR (u.user_id="+literal(merchant)+"::uuid AND u.login_normalized="+literal(MERCHANT)+")) "
        queries = {
            'accounts':'SELECT label,enabled,account_status,authorization_version,roles,created_at FROM targets',
            'sessions':'SELECT t.label,s.authorization_version,s.account_status,s.roles_snapshot,s.created_at,s.absolute_expires_at,s.idle_expires_at,s.revoked_at FROM public.auth_sessions s JOIN targets t ON t.user_id=s.user_id',
            'audits':"SELECT t.label,e.occurred_at,(e.actor_user_id IS NULL AND e.actor_identifier IS NULL) AS anonymous_actor,e.metadata->>'source' AS source FROM public.security_audit_events e JOIN targets t ON e.resource_id=t.user_id::text WHERE e.event_type='LOCAL_DEMO_PASSWORD_RESET' AND e.resource_type='ACCOUNT' AND e.outcome='SUCCESS'",
            'challengeMetadata':'SELECT t.label,c.authorization_version,c.created_at,c.expires_at,c.consumed_at FROM public.password_recovery_challenges c JOIN targets t ON c.user_id=t.user_id',
            'triggers':"SELECT t.tgname AS name,t.tgenabled AS enabled,p.proname AS function_name,p.prosrc AS function_body FROM pg_trigger t JOIN pg_class r ON r.oid=t.tgrelid JOIN pg_namespace n ON n.oid=r.relnamespace JOIN pg_proc p ON p.oid=t.tgfoid WHERE n.nspname='public' AND r.relname='app_users' AND t.tgname='auth_account_security_change' AND NOT t.tgisinternal",
            'timestampPrecision':"SELECT table_name,column_name,datetime_precision FROM information_schema.columns WHERE table_schema='public' AND ((table_name='auth_sessions' AND column_name IN ('created_at','revoked_at','absolute_expires_at','idle_expires_at')) OR (table_name='security_audit_events' AND column_name='occurred_at'))"}
        fields=["'transactionStartedAt',CURRENT_TIMESTAMP", "'observedAt',clock_timestamp()", "'replicationRole',current_setting('session_replication_role')"]
        for key,query in queries.items():
            fields.append("'"+key+"',COALESCE((SELECT json_agg(row_to_json(x)) FROM ("+query+") x),'[]'::json)")
        return json.loads(self.sql(cte+'SELECT json_build_object('+','.join(fields)+')'))

    def run(self):
        self.stage='diagnostic-preflight'
        targets=json.loads(protected(self.manifest).read_text())
        require(identifier(targets['admin'])!=identifier(targets['merchant']), 'Dedicated targets must be distinct.')
        for key,port,cwd,kind in [('java',18080,self.repo/'backend','java'),('frontend',5500,self.repo,'python'),('ai',8000,self.repo/'ai-service','python'),('llm',8082,Path.home()/'Developer/paymesh-tools/llama.cpp','llm')]:
            if not hasattr(self,'services'):self.services={}
            self.services[key]=self.service(port,cwd,kind)
        self.launch()  # Private argv validation only; no restart or config changes.
        self.index_before=self.command(['/usr/bin/shasum','-a','256',self.repo/'.git/index']).split()[0]
        self.staged_before=self.command(['/usr/bin/git','-C',self.repo,'diff','--cached','--binary'])
        require(' 16.' in self.command([PG/'psql','--version']), 'PostgreSQL16 tools required.')
        self.db_password=hidden('Existing paymesh_demo_user database password (hidden): ')
        require(bool(self.db_password), 'Empty database credential.')
        self.stage='read-only-database-identity'
        require(self.sql("SELECT current_database(),current_user,host(inet_server_addr()),inet_server_port(),current_setting('transaction_read_only')")== 'paymesh_demo|paymesh_demo_user|127.0.0.1|5432|on', 'Read-only demo database identity mismatch.')
        require(self.sql("SELECT count(*) FROM public.flyway_schema_history WHERE version='10' AND success")=='1', 'Successful V10 migration is required.')
        self.stage='read-only-session-diagnosis'
        local_before=datetime.now(timezone.utc).isoformat()
        snapshot=self.snapshot(targets)
        local_after=datetime.now(timezone.utc).isoformat()
        require(sorted(a['label'] for a in snapshot['accounts'])==['admin','merchant'], 'Dedicated account UUID/name association mismatch.')
        results={}
        for account in snapshot['accounts']:
            label=account['label']
            events=[e for e in snapshot['audits'] if e['label']==label]
            require(all(e['anonymous_actor'] and e['source']=='insecure_local_demo_on_screen_otp' for e in events), 'Reset audit source/actor metadata differs from actual recovery contract.')
            results[label]=analyze(account,[s for s in snapshot['sessions'] if s['label']==label],events,snapshot['observedAt'])
            results[label]['retainedChallengeMetadata']=[{k:v for k,v in row.items() if k!='label'} for row in snapshot['challengeMetadata'] if row['label']==label]
        source=(self.repo/'backend/src/main/resources/db/migration/V10__persistent_sessions_and_local_demo_recovery.sql').read_text()
        expected_body=re.search(r'CREATE FUNCTION revoke_auth_state_for_account_change\(\).*?AS \$\$(.*?)\$\$;',source,re.S).group(1)
        trigger_metadata=[{k:v for k,v in row.items() if k!='function_body'} | {'bodyMatchesReviewedV10':row['function_body']==expected_body} for row in snapshot['triggers']]
        self.evidence['diagnosis']={'accounts':results, 'databaseTransactionStartedAt':snapshot['transactionStartedAt'],
                                   'databaseObservedAt':snapshot['observedAt'], 'operatorClockBeforeQuery':local_before,
                                   'operatorClockAfterQuery':local_after, 'timestampPrecision':snapshot['timestampPrecision'],
                                   'triggerMetadata':trigger_metadata,
                                   'expectedTriggerPresentEnabledAndMatchesV10':len(trigger_metadata)==1 and trigger_metadata[0]['enabled'] in ('O','A') and trigger_metadata[0]['function_name']=='revoke_auth_state_for_account_change' and trigger_metadata[0]['bodyMatchesReviewedV10'],
                                   'configuredRecoveryEnabledFlag':self.flags.get('paymesh.demo.password-recovery.enabled'),
                                   'diagnosticConnectionReplicationRole':snapshot['replicationRole'],
                                   'cleanupPolicy':'On new session creation: at most100 families with absolute_expires_at < AuthenticationClock.now minus24h; no deletion audit/tombstone.',
                                   'legacyJwtLimit':'No-sid JWTs are not inventoried in auth_sessions; changed authorization_version rejects old-version tokens. No token was requested or tested.'}
        self.unchanged_other_services()
        require(self.service(18080,self.repo/'backend','java')==self.services['java'],'Java identity changed during diagnosis.')
        print(json.dumps(self.evidence['diagnosis'],indent=2))  # Only explicitly selected sanitized metadata.
        self.evidence['result']='Read-only diagnosis captured; NOT a successful closeout or proof of historical cleanup.'
        self.stage='diagnosis-captured-not-certified'
        print('Diagnosis captured. No session, password, OTP or service mutation performed. Closeout remains blocked.')

    def closeout(self, success):
        self.evidence.update({'captureSucceeded':success, 'stage':self.stage, 'closeoutCertified':False})
        if hasattr(self,'index_before'):
            self.evidence['indexPreserved']=hashlib.sha256((self.repo/'.git/index').read_bytes()).hexdigest()==self.index_before
            self.evidence['stagedPreserved']=self.command(['/usr/bin/git','-C',self.repo,'diff','--cached','--binary'])==self.staged_before
        path=self.run_dir/'evidence.json'
        self.private_json(path,self.evidence)
        with self.report.open('a') as out:
            out.write('\n## Operator session-revocation diagnostic evidence\n\n')
            out.write('Diagnostic capture '+('completed' if success else 'failed')+'; **not closeout certification**. Stage '+self.stage+'. Protected evidence: `'+str(path)+'`. No password/session/OTP/service mutation performed.\n')
        self.db_password=None
        print(('Diagnostic evidence saved.' if success else 'Diagnosis stopped safely.')+' Evidence: '+str(path))


def main():
    os.umask(0o077)
    if len(sys.argv)!=1 or not sys.stdin.isatty() or not sys.stdout.isatty():
        print('Operator-only diagnostic; no arguments, pipes or credentials in commands.',file=sys.stderr);return 1
    operation=None
    try:
        operation=Diagnosis();operation.run();operation.closeout(True);return 0
    except Stop as error:print(str(error),file=sys.stderr)
    except (Exception,KeyboardInterrupt):print('Diagnostic failed/interrupted; no raw exceptions or credentials displayed.',file=sys.stderr)
    if operation:
        try:operation.closeout(False)
        except Exception:print('Could not record protected diagnostic evidence.',file=sys.stderr)
    return 1

if __name__=='__main__':sys.exit(main())
