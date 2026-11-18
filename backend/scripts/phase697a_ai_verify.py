"""Future operator probes/config staging only. No database, financial tools or automatic retries."""
import base64,json,os,re,sys,uuid,urllib.request,urllib.error
from http.cookies import SimpleCookie
from pathlib import Path
from phase673_otp_ops import Ops,Stop,hidden

ORIGIN='http://127.0.0.1:5500'
PORTS={'java':18080,'frontend':5500,'python':8000,'llm':8082}
PHRASES={'health':'VERIFY_PHASE697_HEALTH_ONLY','internal':'VERIFY_PHASE697_PRIVATE_MODEL_INFERENCE','internal-diagnostic':'VERIFY_PHASE697_SINGLE_CORRELATED_DIAGNOSTIC','merchant':'VERIFY_PHASE697_AUTHORIZED_CHAT_AND_TEMP_CONVERSATION','admin':'VERIFY_PHASE697_AUTHORIZED_CHAT_AND_TEMP_CONVERSATION','stage-enable':'STAGE_PHASE697_AI_ENABLE_CONFIG_ONLY','stage-disable':'STAGE_PHASE697_AI_DISABLE_CONFIG_ONLY'}
MODES={'DETERMINISTIC':{'DISABLED','NOT_ATTEMPTED','NO_RELEVANT_CONTEXT','RETRIEVAL_UNAVAILABLE'},'RAG_ASSISTED':{'NOT_ATTEMPTED','TIMEOUT','UNAVAILABLE','INVALID_RESPONSE','VALIDATION_FAILED','CONTEXT_LIMIT','DISABLED'},'RAG_LLM':{'SUCCEEDED'}}

def safe_generation(body):
    mode,status=body.get('analysisMode'),body.get('generationStatus')
    if status not in MODES.get(mode,set()):raise Stop('Invalid generation mode/status; no inference certification.')
    knowledge=body.get('knowledgeReferences',[])
    if not isinstance(knowledge,list) or len(knowledge)>5 or (mode in ('RAG_LLM','RAG_ASSISTED') and not knowledge) or (mode=='DETERMINISTIC' and knowledge):raise Stop('Generation citations are missing or inconsistent.')
    return {'analysisMode':mode,'generationStatus':status,'actualInferenceProven':mode=='RAG_LLM' and status=='SUCCEEDED','knowledgeCount':len(body.get('knowledgeReferences',[])),'moneyFactCount':len(body.get('moneyFacts',[]))}

class Verification(Ops):
    def __init__(self,mode):
        super().__init__('phase697a-'+mode);self.mode=mode;self.token=None;self.cookie=None
    def services_checked(self):
        self.services={}
        for key,port,cwd,kind in [('java',18080,self.repo/'backend','java'),('frontend',5500,self.repo,'python'),('ai',8000,self.repo/'ai-service','python'),('llm',8082,Path.home()/'Developer/paymesh-tools/llama.cpp','llm')]:self.services[key]=self.service(port,cwd,kind)
        self.evidence['services']=self.services
    def call(self,service,path,body=None,token=None,key=None,cookie=None):
        # Deliberately no caller-controlled origin, proxy, redirects or arbitrary public path.
        allowed=service=='java' and path=='/actuator/health/readiness' or service=='python' and path in ('/health','/api/v1/chat') or service=='llm' and path=='/health'
        if service=='frontend':
            allowed=path in ('/merchant/ai','/admin/ai','/api/v1/auth/login','/api/v1/auth/logout','/api/v1/auth/password/capabilities','/api/v1/payments/health') or bool(re.fullmatch(r'/api/v1/(merchant|admin)/ai/chat',path)) or bool(re.fullmatch(r'/api/v1/payments/[a-f0-9-]{36}/ai/chat',path)) or bool(re.fullmatch(r'/api/v1/(merchant|admin)/ai/conversations(?:/[a-f0-9-]{36}(?:/(?:messages|rename|delete|requests/[a-f0-9-]{36}))?)?',path))
        if not allowed:raise Stop('Probe target is not allowlisted.')
        headers={'Accept':'application/json'}
        if token:
            if service!='frontend':raise Stop('Browser bearer destination denied.')
            headers['Authorization']='Bearer '+token
        if key:
            if service!='python' or path!='/api/v1/chat':raise Stop('Internal credential destination denied.')
            headers['X-PayMesh-AI-Chat-Token']=key
        if cookie:
            if service!='frontend' or path!='/api/v1/auth/logout':raise Stop('Session cookie destination denied.')
            headers['Cookie']=cookie
        if path in ('/api/v1/auth/login','/api/v1/auth/logout'):headers.update(Origin=ORIGIN,**{'X-PayMesh-CSRF':'1'})
        data=None if body is None else json.dumps(body,separators=(',',':')).encode()
        if data is not None:
            if len(data)>32768:raise Stop('Probe request exceeds limit.')
            headers['Content-Type']='application/json'
        request=urllib.request.Request('http://127.0.0.1:'+str(PORTS[service])+path,data=data,headers=headers)
        try:
            with self.http.open(request,timeout=45) as r:
                raw=r.read(524289)
                if len(raw)>524288:raise Stop('Probe response exceeds limit.')
                if path in ('/merchant/ai','/admin/ai'):return r.status,{},None
                return r.status,json.loads(raw),r.headers.get('Set-Cookie')
        except urllib.error.HTTPError as e:
            status=e.code;e.close();return status,{},None
        except Stop:raise
        except Exception:raise Stop('HTTP outcome unknown; do not retry automatically. Reconcile using private request identifiers.') from None
    def expect(self,status,expected):
        if status!=expected:raise Stop('Unexpected HTTP status; verification stopped without retry.')
    def stage_config(self,enable):
        # New bundle only; never overwrite existing config or restart anything.
        if input('Attest private loopback with no public tunnel; type NO_PUBLIC_PROXY_OR_TUNNEL: ').strip()!='NO_PUBLIC_PROXY_OR_TUNNEL':raise Stop('Private attestation missing.')
        key=hidden('Existing/private operator-supplied shared service token (hidden,64–128 URL-safe characters): ') if enable else ''
        try:
            if enable and not re.fullmatch('[A-Za-z0-9_-]{64,128}',key):raise Stop('Invalid service token format.')
            java=self.run_dir/'java-chat.properties';python=self.run_dir/'python-chat.env'
            with java.open('x') as f:
                os.chmod(java,0o600);f.write('paymesh.ai.chat.enabled='+str(enable).lower()+'\n')
                if enable:f.write('paymesh.ai.chat.service-token='+key+'\n')
                f.write('paymesh.demo.password-recovery.enabled=false\n')
            with python.open('x') as f:
                os.chmod(python,0o600);f.write('PAYMESH_AI_CHAT_API_ENABLED='+str(enable).lower()+'\nPAYMESH_AI_CHAT_SERVICE_TOKEN='+key+'\n')
            self.evidence.update(configStagedOnly=True,enabledAfterReviewedRestarts=enable,javaConfig=str(java),pythonConfig=str(python),serviceRestartsPerformed=False)
        finally:key=''
        print('CONFIG_STAGED_ONLY; services unchanged; review protected evidence for bundle paths.')
    def health(self):
        for service,path in [('java','/actuator/health/readiness'),('python','/health'),('llm','/health'),('frontend','/api/v1/payments/health'),('frontend','/merchant/ai'),('frontend','/admin/ai')]:
            status,body,_=self.call(service,path);self.expect(status,200)
            if service in ('java','python') and body.get('status')!='UP':raise Stop('Service is not ready.')
        status,body,_=self.call('frontend','/api/v1/auth/password/capabilities');self.expect(status,200)
        if body.get('localDemoEnabled') is not False:raise Stop('OTP must remain disabled.')
        self.evidence['healthOnlyNotInference']=True;print('HEALTH_PASS; MODEL_INFERENCE_NOT_VERIFIED')
    def internal(self,correlation_id=None,key_override=None):
        key=key_override if key_override is not None else hidden('Protected matching Java/Python chat service token (hidden): ')
        try:
            if not re.fullmatch('[A-Za-z0-9_-]{64,128}',key):raise Stop('Invalid service credential format.')
            correlation_id=str(uuid.uuid4()) if correlation_id is None else correlation_id
            from phase697a_diagnostic import correlation
            if not correlation(correlation_id):raise Stop('Invalid diagnostic request identity.')
            body={'correlationId':correlation_id,'callerRole':'ADMIN','question':'Explain idempotency and duplicate payment prevention.','history':[]}
            wrong=('A' if key[0]!='A' else 'B')+key[1:]
            self.expect(self.call('python','/api/v1/chat',body,key=wrong)[0],401)
            status,result,_=self.call('python','/api/v1/chat',body,key=key);self.expect(status,200)
            if result.get('correlationId')!=body['correlationId']:raise Stop('Internal correlation mismatch.')
            self.evidence['internalAuthenticationVerified']=True;self.evidence['generation']=safe_generation(result)
            if not self.evidence['generation']['actualInferenceProven']:raise Stop('Fallback observed; actual model inference remains unverified.')
            print('PRIVATE_AUTH_AND_RAG_LLM_SUCCEEDED; no raw prompt/answer retained')
        finally:key=''
    def authenticated(self,role):
        login=hidden('Existing authorized '+role+' login (hidden): ');password=hidden('Password (hidden): ')
        try:status,result,cookie=self.call('frontend','/api/v1/auth/login',{'login':login,'password':password,'rememberMe':False})
        finally:login=password=''
        self.expect(status,200)
        parsed=SimpleCookie();parsed.load(cookie or '');refresh=parsed.get('pm_refresh')
        if refresh and re.fullmatch('[A-Za-z0-9_-]{43}',refresh.value):self.cookie='pm_refresh='+refresh.value
        if not self.cookie or result.get('tokenType')!='Bearer':raise Stop('Supported session login contract unavailable.')
        self.token=result.get('accessToken','')
        try:
            payload=self.token.split('.')[1];claims=json.loads(base64.urlsafe_b64decode(payload+'='*(-len(payload)%4)))
            if claims.get('roles')!=[role.upper()] or claims.get('account_status')!='ACTIVE':raise ValueError()
        except Exception:raise Stop('Expected enabled ACTIVE single-role identity required.') from None
        # A backend rejection, not a model-generated ownership assertion.
        opposite='admin' if role=='merchant' else 'merchant'
        self.expect(self.call('frontend','/api/v1/'+opposite+'/ai/chat',{'question':'What is idempotency?'},token=self.token)[0],403)
        ctx={'statistics':{}}
        mid=hidden('Authorized Merchant ID (Admin only; blank platform): ') if role=='admin' else ''
        if mid:
            if not re.fullmatch('[A-Za-z0-9][A-Za-z0-9._:-]{0,99}',mid):raise Stop('Invalid Merchant selector.')
            ctx['merchantId']=mid
        payment=hidden('Known authorized payment UUID (blank overview): ')
        if payment:
            try:
                if str(uuid.UUID(payment))!=payment:raise ValueError()
            except Exception:raise Stop('Canonical payment UUID required.') from None
            ctx.pop('statistics');ctx['paymentId']=payment
        question="What is this payment's recorded status?" if payment else 'Summarize payment statistics'
        endpoint='/api/v1/'+role+'/ai/chat'
        body={'question':question,'history':[],'context':ctx}
        status,result,_=self.call('frontend',endpoint,body,token=self.token);self.expect(status,200)
        self.evidence['statelessGeneration']=safe_generation(result)
        if payment:
            status,result,_=self.call('frontend','/api/v1/payments/'+payment+'/ai/chat',{'question':question,'history':[]},token=self.token);self.expect(status,200);self.evidence['paymentAskGeneration']=safe_generation(result)
        base='/api/v1/'+role+'/ai/conversations'
        status,result,_=self.call('frontend',base,{'requestId':str(uuid.uuid4()),'context':ctx,'title':'Integration verification temporary conversation'},token=self.token);self.expect(status,201)
        c=result['conversation'];cid=c['conversationId'];version=c['version'];self.evidence['createdConversationId']=cid
        request_id=str(uuid.uuid4());send={'requestId':request_id,'expectedVersion':version,'question':question};self.evidence['lastRequestId']=request_id
        status,done,_=self.call('frontend',base+'/'+cid+'/messages',send,token=self.token);self.expect(status,200)
        if done.get('status')!='COMPLETED':raise Stop('Request remains unresolved; use original identity for authorized reconciliation.')
        self.evidence['savedGeneration']=safe_generation(done['turn']['response'])
        status,replay,_=self.call('frontend',base+'/'+cid+'/messages',send,token=self.token);self.expect(status,200)
        if replay.get('turn')!=done.get('turn'):raise Stop('Durable request replay differs.')
        version=done['conversation']['version'];request_id=str(uuid.uuid4());self.evidence['lastRequestId']=request_id
        status,second,_=self.call('frontend',base+'/'+cid+'/messages',{'requestId':request_id,'expectedVersion':version,'question':'What about the gateway?' if payment else 'What is idempotency?'},token=self.token);self.expect(status,200)
        status,restored,_=self.call('frontend',base+'/'+cid+'/messages',token=self.token);self.expect(status,200)
        if restored.get('total')!=2 or len(restored.get('turns',[]))!=2:raise Stop('Completed turn restoration differs.')
        version=second['conversation']['version']
        status,renamed,_=self.call('frontend',base+'/'+cid+'/rename',{'expectedVersion':version,'title':'Integration verification renamed'},token=self.token);self.expect(status,200)
        status,deleted,_=self.call('frontend',base+'/'+cid+'/delete',{'expectedVersion':renamed['conversation']['version']},token=self.token);self.expect(status,200)
        if deleted.get('deleted') is not True:raise Stop('Deletion is unconfirmed.')
        self.expect(self.call('frontend',base+'/'+cid,token=self.token)[0],404)
        self.evidence.update(temporaryConversationDeleted=True,completedTurnsRestored=2,requestReplayVerified=True,wrongRoleDenied=True)
        if not self.evidence['savedGeneration']['actualInferenceProven']:raise Stop('Persistence verified but saved answer used fallback; model integration remains unverified.')
        print('AUTHORIZED_CHAT_PERSISTENCE_REPLAY_RENAME_DELETE_PASS; browser/isolation/race checks remain separate')
    def run(self):
        self.services_checked()
        if input('Type '+PHRASES[self.mode]+': ').strip()!=PHRASES[self.mode]:raise Stop('Verification/config staging not confirmed.')
        if self.mode.startswith('stage-'):self.stage_config(self.mode=='stage-enable')
        elif self.mode=='health':self.health()
        elif self.mode=='internal':self.internal()
        elif self.mode=='internal-diagnostic':
            from phase697a_diagnostic import run
            run(self)
        else:self.authenticated(self.mode)
    def closeout(self,success):
        if self.cookie:
            try:
                self.expect(self.call('frontend','/api/v1/auth/logout',{},cookie=self.cookie)[0],200);self.evidence['verificationSessionLogoutConfirmed']=True
            except Exception:self.evidence['verificationSessionLogoutConfirmed']=False;print('Session logout unconfirmed; do not claim cleanup succeeded.',file=sys.stderr)
        self.token=self.cookie=None
        self.evidence['success']=success;self.private_json(self.run_dir/'evidence.json',self.evidence)
        print('Protected sanitized evidence: '+str(self.run_dir/'evidence.json'))

def main():
    os.umask(0o077);op=None
    if len(sys.argv)!=2 or sys.argv[1] not in PHRASES or not sys.stdin.isatty() or not sys.stdout.isatty():print('Interactive wrapper and one documented mode required.');return 1
    try:op=Verification(sys.argv[1]);op.run();op.closeout(True);return 0
    except Stop as e:print(str(e),file=sys.stderr)
    except (Exception,KeyboardInterrupt):print('Verification/config staging failed; no automatic retry, restore or restart.',file=sys.stderr)
    if op:
        try:op.closeout(False)
        except Exception:print('Private evidence unavailable.',file=sys.stderr)
    return 1
if __name__=='__main__':sys.exit(main())
