"""Read-only password-change diagnosis, never a password reset or closeout certification.
Only password equality booleans escape memory; no hashes, credentials or raw archive rows.
"""
import hashlib
import json
import os
from pathlib import Path
import sys
from phase673_otp_ops import Ops, Stop, PG, ADMIN, MERCHANT, protected, hidden, identifier
from phase673_closeout import require, instant, copy_rows
from phase674_closeout import FinalAudit, ACTIVATION

FAILURE='otp-step17-verify-phase674-final-20261115T055205Z-0hvhy2md'
PASSWORD_EVENTS=('DISPOSABLE_MERCHANT_PASSWORD_RECOVERED','ADMIN_PASSWORD_CHANGED','LOCAL_DEMO_PASSWORD_RESET','ADMIN_PASSWORD_RECOVERED')
LIFECYCLE_EVENTS=('MERCHANT_APPROVE','MERCHANT_SUSPEND','MERCHANT_REACTIVATE','MERCHANT_REJECT')

def analyze(snapshot, baseline, targets, activated_at):
    current={u['user_id']:u for u in snapshot['app_users']};old={u['user_id']:u for u in baseline['app_users']}
    for label,name in (('admin',ADMIN),('merchant',MERCHANT)):
        uid=targets[label]
        require(uid in old and uid in current and old[uid]['login_normalized']==name and current[uid]['login_normalized']==name,'Disposable manifest/archive/current identity mismatch.')
    def roles(uid):return sorted(r['role_name'] for r in snapshot['user_roles'] if r['user_id']==uid)
    successful=[e for e in snapshot['audit'] if e['outcome']=='SUCCESS']
    rows=[];triggered=[];attention=[]
    for uid,u in sorted(current.items(),key=lambda x:x[1]['login_normalized']):
        before=old.get(uid);name=u['login_normalized'];disposable=uid in targets.values()
        classification='DISPOSABLE_MERCHANT' if uid==targets['merchant'] else 'DISPOSABLE_ADMIN' if uid==targets['admin'] else 'OPERATIONAL_OR_OTHER_NON_DESIGNATED'
        events=[];recent=[]
        for e in sorted(successful,key=lambda e:instant(e['occurred_at'])):
            if e['resource_type']!='ACCOUNT' or e['resource_id']!=uid or e['event_type'] not in PASSWORD_EVENTS:continue
            actor=current.get(e['actor_user_id']);source=e['metadata'].get('source')
            if e['actor_user_id'] is None and e['actor_identifier'] is None:
                actor_class='OFFLINE_OPERATOR' if source=='offline_operator_recovery' else 'LOCAL_DEMO_UNAUTHENTICATED' if source=='insecure_local_demo_on_screen_otp' else 'UNRESOLVED_UNAUTHENTICATED_SOURCE'
                actor_login=None
            else:
                valid=actor is not None and actor['login_normalized']==e['actor_identifier'] and roles(actor['user_id'])==['ADMIN']
                actor_class='AUTHENTICATED_ADMIN_SELF_RECORD' if valid and actor['user_id']==uid else 'AUTHENTICATED_ADMIN_RECORD' if valid else 'INCONSISTENT_ACTOR_RECORD'
                actor_login=actor['login_normalized'] if actor else 'UNRESOLVED_ACTOR'
            after=instant(e['occurred_at'])>=instant(activated_at)
            safe=dict(eventType=e['event_type'],occurredAt=e['occurred_at'],afterActivation=after,actorClassification=actor_class,actorLogin=actor_login)
            events.append(safe)
            if after:recent.append(safe)
        pw=[e for e in recent if e['eventType']=='ADMIN_PASSWORD_CHANGED']
        if pw and name!=ADMIN:triggered.append(name)
        changed=None if before is None else u['password_hash']!=before['password_hash']
        expected=[e for e in recent if (classification=='DISPOSABLE_MERCHANT' and e['eventType']=='DISPOSABLE_MERCHANT_PASSWORD_RECOVERED' and e['actorClassification']=='OFFLINE_OPERATOR') or
                  (classification=='DISPOSABLE_ADMIN' and e['eventType']=='ADMIN_PASSWORD_CHANGED' and e['actorClassification']=='AUTHENTICATED_ADMIN_SELF_RECORD')]
        if changed is None:explanation='NO_ACTIVATION_BASELINE_FOR_NEW_ACCOUNT'
        elif changed and disposable and len(expected)==1 and len(recent)==1:explanation='MATCHES_DOCUMENTED_DISPOSABLE_ACTIVITY_AND_AUDIT'
        elif changed:explanation='UNEXPLAINED_OR_NOT_AUTHORIZED_BY_DOCUMENTED_SCOPE';attention.append(name)
        elif pw and name!=ADMIN:explanation='UNEXPECTED_OPERATIONAL_PASSWORD_CHANGE_AUDIT_WITHOUT_NET_HASH_CHANGE';attention.append(name)
        else:explanation='NO_NET_PASSWORD_HASH_CHANGE'
        mids={m['merchant_id'] for m in snapshot['merchant_memberships'] if m['user_id']==uid}
        activity=[dict(eventType=e['event_type'],occurredAt=e['occurred_at']) for e in successful if e['resource_type']=='MERCHANT' and e['resource_id'] in mids and e['event_type'] in LIFECYCLE_EVENTS and instant(e['occurred_at'])>=instant(activated_at)]
        rows.append(dict(login=name,classification=classification,classificationSource='Exact protected disposable manifest UUID + archive/current normalized login' if disposable else 'Not an explicitly designated disposable identity',
            status=u['account_status'],enabled=u['enabled'],roles=roles(uid),passwordHashChanged='NOT_COMPARABLE_NEW_ACCOUNT' if changed is None else 'YES' if changed else 'NO',
            previousAuthorizationVersion=None if before is None else before['authorization_version'],currentAuthorizationVersion=u['authorization_version'],
            previousUpdatedAt=None if before is None else before['updated_at'],currentUpdatedAt=u['updated_at'],
            passwordAuditEvents=events,lifecycleAuditEvents=activity,explanation=explanation))
    missing=[u['login_normalized'] for uid,u in old.items() if uid not in current]
    require(not missing,'An activation-baseline account is missing; stop for investigation.')
    return dict(accounts=rows,accountsMatchingExactVerifierFailure=triggered,accountsRequiringOperatorExplanation=sorted(set(attention+triggered)),
                result='DIAGNOSIS_REQUIRES_OPERATOR_REVIEW' if attention or triggered else 'DIAGNOSIS_COMPLETE_NOT_CLOSEOUT_CERTIFICATION',
                limits=['Audit actor fields are persisted evidence, not a new authentication test.',
                        'BCrypt hash inequality does not prove that plaintext differs; rehashing can also change stored bytes.',
                        'Approval/suspension/reactivation increment authorization versions without changing passwords.',
                        'Logout-all may increment versions without a password audit; no cause is invented for additional increments.',
                        'Phase673 historical evidence limitations remain unchanged.'])

class Diagnosis(FinalAudit):
    def __init__(self):
        Ops.__init__(self,'diagnose-phase674-password-mismatch')
        self.report=self.repo/'frontend/PHASE-6.7.4-ADMIN-DASHBOARD-MERCHANT-MANAGEMENT-REPORT.md'
    def account_archive(self,snapshot):
        backup=self.activation['backup'];path=protected(backup['path']);directory=protected(self.private/'backups',0o700)
        require(path.resolve().is_relative_to(directory.resolve()),'Archive is outside protected demo backups.')
        require(hashlib.sha256(path.read_bytes()).hexdigest()==backup['sha256'],'Original activation archive checksum mismatch.')
        self.command([PG/'pg_restore','--list',path]);result={}
        # Extract only whitelisted data into memory. Never run archive SQL or restore a database.
        for table in ('app_users','user_roles'):
            columns,rows=copy_rows(self.command([PG/'pg_restore','--data-only','--table='+table,'--file=-',path])+'\n',table)
            types={r['column_name']:r['data_type'] for r in snapshot['types'] if r['table_name']==table}
            require(set(columns)==set(types),'Account archive/current columns differ.')
            result[table]=[{k:(None if v is None else v=='t' if types[k]=='boolean' else int(v) if types[k] in ('bigint','integer','smallint') else v) for k,v in row.items()} for row in rows]
        return result
    def run(self):
        self.activation=json.loads(protected(self.private/ACTIVATION/'evidence.json').read_text())
        require(self.activation.get('success') is True and self.activation.get('mode')=='activate-phase674' and self.activation.get('recoveryEnabled') is False,'Authentic successful OTP-disabled V11 activation evidence required.')
        targets=json.loads(protected(self.manifest).read_text());targets={k:identifier(targets[k]) for k in ('admin','merchant')}
        require(targets['admin']!=targets['merchant'],'Disposable target identities must differ.')
        failed=json.loads(protected(self.private/FAILURE/'evidence.json').read_text())
        require(failed.get('mode')=='verify-phase674-final' and failed.get('success') is False,'Authentic failed closeout evidence required.')
        self.evidence['failedAuditEvidence']=str(self.private/FAILURE/'evidence.json')
        self.index_before=hashlib.sha256((self.repo/'.git/index').read_bytes()).hexdigest();self.staged_before=self.command(['/usr/bin/git','-C',self.repo,'diff','--cached','--binary'])
        self.services={}
        service_specs=[('java',18080,self.repo/'backend','java'),('frontend',5500,self.repo,'python'),('ai',8000,self.repo/'ai-service','python'),('llm',8082,Path.home()/'Developer/paymesh-tools/llama.cpp','llm')]
        for k,p,c,t in service_specs:self.services[k]=self.service(p,c,t)
        self.launch() # V11-aware argv/artifact inspection only, never activation/restart.
        require(self.flags.get('paymesh.demo.password-recovery.enabled')=='false','OTP must remain disabled.')
        require(self.services['java']['pid']==str(self.activation['newJavaPid']) and self.services['frontend']['pid']==str(self.activation['newFrontendPid']),'Java/frontend identity differs from activation; review restart evidence.')
        for k in ('ai','llm'):require(self.services[k]==self.activation['beforeServices'][k],'Preserved Python/LLM service identity differs.')
        for name in ('psql','pg_restore'):require(' 16.' in self.command([PG/name,'--version']),'PostgreSQL16 tools required.')
        self.db_password=hidden('Existing paymesh_demo_user database password (hidden): ');require(bool(self.db_password),'Empty database credential.')
        self.stage='read-only-diagnostic-identity'
        require(self.sql("SELECT current_database(),current_user,host(inet_server_addr()),inet_server_port(),current_setting('transaction_read_only')")=='paymesh_demo|paymesh_demo_user|127.0.0.1|5432|on','Read-only demo target verification failed.')
        require(self.sql("SELECT string_agg(version,',' ORDER BY installed_rank)||'|'||bool_and(success)::text FROM public.flyway_schema_history WHERE version IS NOT NULL")=='1,2,3,4,5,6,7,8,9,10,11|true','Require successful V1–V11 only.')
        require(self.http_json('proxy:/api/v1/auth/password/capabilities')==(200,{'localDemoEnabled':False}),'OTP capability must remain disabled.')
        self.stage='read-only-password-comparison';s=self.snapshot()
        require(not any(e['enabled'] for e in s['eligibility']),'Recovery eligibility must stay disabled.')
        baseline=self.account_archive(s);summary=analyze(s,baseline,targets,self.activation['startedAt'])
        for k,p,c,t in service_specs:require(self.service(p,c,t)==self.services[k],'Service identity changed during diagnosis.')
        self.evidence.update(diagnosis=summary,result=summary['result'],activationEvidence=str(self.private/ACTIVATION/'evidence.json'),archiveChecksumVerified=True,archiveRestored=False)
        self.stage='diagnostic-complete-not-certification'
        for row in summary['accounts']:
            print(row['login']+': '+row['classification']+'; hash changed='+row['passwordHashChanged']+'; version '+str(row['previousAuthorizationVersion'])+' -> '+str(row['currentAuthorizationVersion'])+'; '+row['status']+'; roles='+','.join(row['roles']))
            print('  Classification source: '+row['classificationSource'])
            print('  '+row['explanation']+'; updated '+str(row['previousUpdatedAt'])+' -> '+str(row['currentUpdatedAt']))
            for event in row['passwordAuditEvents']:
                print('  '+event['eventType']+' '+event['occurredAt']+(' [AFTER_ACTIVATION]' if event['afterActivation'] else ' [HISTORICAL]')+'; actor='+str(event['actorLogin'] or event['actorClassification'])+'; '+event['actorClassification'])
            for event in row['lifecycleAuditEvents']:print('  Version-changing lifecycle event (not a password change): '+event['eventType']+' '+event['occurredAt'])
        print('Exact verifier-condition account(s): '+(', '.join(summary['accountsMatchingExactVerifierFailure']) or 'NONE IN CURRENT SNAPSHOT'))
        print(summary['result'])
    def closeout(self,success):
        self.evidence.update(success=success,stage=self.stage)
        if hasattr(self,'index_before'):
            self.evidence['indexPreserved']=hashlib.sha256((self.repo/'.git/index').read_bytes()).hexdigest()==self.index_before
            self.evidence['stagedPreserved']=self.command(['/usr/bin/git','-C',self.repo,'diff','--cached','--binary'])==self.staged_before
        self.private_json(self.run_dir/'evidence.json',self.evidence);self.db_password=None
        with self.report.open('a') as out:out.write('\n## Operator password-mismatch diagnosis\n\n'+('Read-only diagnosis completed; NOT closeout certification.' if success else 'Diagnosis stopped safely; no changes permitted automatically.')+' Private evidence: `'+str(self.run_dir/'evidence.json')+'`.\n')
        print(('Diagnostic evidence recorded.' if success else 'Stopped safely; review private evidence.')+' Evidence: '+str(self.run_dir/'evidence.json'))

def main():
    os.umask(0o077);op=None
    if len(sys.argv)!=1 or not sys.stdin.isatty() or not sys.stdout.isatty():print('Use the interactive diagnostic wrapper without arguments.',file=sys.stderr);return 1
    try:
        op=Diagnosis();op.run();op.closeout(True)
        return 2 if op.evidence['diagnosis']['accountsRequiringOperatorExplanation'] else 0
    except Stop as e:print(str(e),file=sys.stderr)
    except (Exception,KeyboardInterrupt):print('Read-only diagnosis failed; inspect protected evidence, never raw secrets.',file=sys.stderr)
    if op:
        try:op.closeout(False)
        except Exception:print('Private diagnostic evidence could not be completed; no automatic retry.',file=sys.stderr)
    return 1
if __name__=='__main__':sys.exit(main())
