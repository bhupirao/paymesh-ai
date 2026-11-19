"""Real disposable-container API E2E. Inert on import; no host DB/service paths.
Outputs fixed check names and counts, never payloads, tokens, SQL or raw logs.
"""
from decimal import Decimal
from http.cookiejar import CookieJar
import json,os,re,subprocess,sys,urllib.request,urllib.error,urllib.parse,uuid
from pathlib import Path
from ci_fixture_setup import runner_project
BASE='http://127.0.0.1:15500'
SAFE_ACTORS={'UNSPECIFIED','ADMIN','MERCHANT_A','MERCHANT_B','ANONYMOUS','PUBLIC_CHECKOUT'}
SAFE_RESPONSE_FIELDS={'accessToken','tokenType','expiresAt','expiresIn','roles','accountStatus','status','message','code','error','merchantId','items','total','conversation','turn','turns'}
SAFE_ERRORS={
    'Authentication failed':'AUTHENTICATION_FAILED',
    'Request denied':'REQUEST_DENIED',
    'Access denied':'ACCESS_DENIED',
    'Invalid session cookie':'INVALID_SESSION_COOKIE',
    'Payment service unavailable':'UPSTREAM_UNAVAILABLE',
    'Check registration fields and password requirements.':'REGISTRATION_INVALID',
    'Registration could not be completed. Sign in or use different details.':'REGISTRATION_CONFLICT',
    'Access denied. Check current authorization or current password.':'ACCESS_DENIED',
    'Unauthorized':'UNAUTHORIZED','Forbidden':'FORBIDDEN','Bad Request':'BAD_REQUEST',
}

def safe_endpoint(path):
    path=path.split('?',1)[0]
    if re.fullmatch(r'/api/v1/auth/(login|register|refresh|logout|logout-all)',path):return path
    if re.fullmatch(r'/api/v1/(admin|merchant)/(profile|dashboard|merchants|merchant/approve|payments|refunds)',path):return path
    if path in ('/','/merchant/ai','/admin/ai'):return path
    if re.fullmatch(r'/api/v1/checkout/[A-Za-z0-9_-]{43}(?:/(status|pay))?',path):return re.sub(r'(?<=checkout/)[A-Za-z0-9_-]{43}','{checkoutToken}',path)
    if re.fullmatch(r'/api/v1/(?:payments|admin/payments|merchant/payment-links|(?:merchant|admin)/ai/conversations)(?:/[0-9a-f-]{36})?(?:/(?:process|refund|refunds|cancel|messages|rename|delete|ai/chat))?',path):return re.sub(r'[0-9a-f-]{36}','{resourceId}',path)
    if path in ('/api/v1/merchant/ai/chat','/api/v1/admin/ai/chat'):return path
    return 'UNRECOGNIZED_ROUTE_OMITTED'

def response_metadata(raw,status):
    try:value=json.loads(raw)
    except (ValueError,UnicodeError):return {'responseShape':'NON_JSON','responseErrorCode':'NON_JSON_ERROR' if status>=400 else None}
    if not isinstance(value,dict):return {'responseShape':'NON_OBJECT','responseErrorCode':None}
    error=None
    if status>=400:
        error=next((SAFE_ERRORS[value[k]] for k in ('message','error','detail') if isinstance(value.get(k),str) and value[k] in SAFE_ERRORS),'UNRECOGNIZED_ERROR_TEXT_OMITTED')
    return {'responseShape':'OBJECT','responseFields':sorted(SAFE_RESPONSE_FIELDS.intersection(value)),'accessTokenPresent':isinstance(value.get('accessToken'),str) and bool(value['accessToken']),'responseErrorCode':error}

class Failure(Exception):pass

def require(ok,code):
    if not ok:raise Failure(code)

def money(value):return Decimal(str(value))

class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self,*args,**kwargs):return None

class Session:
    def __init__(self,actor='UNSPECIFIED',observer=None):
        require(actor in SAFE_ACTORS,'INVALID_DIAGNOSTIC_ACTOR');self.actor=actor;self.observer=observer;self.last_request=None
        self.cookies=CookieJar();self.client=urllib.request.build_opener(urllib.request.ProxyHandler({}),NoRedirect(),urllib.request.HTTPCookieProcessor(self.cookies));self.token=None
    def record(self):
        if self.observer:self.observer(dict(self.last_request))
    def call(self,method,path,body=None,expected=(200,),key=None):
        require(path.startswith('/api/v1/') or path in ('/','/merchant/ai','/admin/ai'),'FIXED_API_PATH_REQUIRED')
        headers={'Accept':'application/json','Origin':BASE}
        if body is not None:headers['Content-Type']='application/json'
        if key:headers['Idempotency-Key']=key
        if self.token and not path.startswith(('/api/v1/auth/','/api/v1/checkout/')):headers['Authorization']='Bearer '+self.token
        if path.startswith('/api/v1/auth/'):headers['X-PayMesh-CSRF']='1'
        if path.startswith('/api/v1/checkout/'):headers['X-PayMesh-Checkout']='1'
        self.last_request={'actor':self.actor,'method':method,'endpoint':safe_endpoint(path),'expectedStatuses':list(expected),'actualStatus':None,'bearerAttached':'Authorization' in headers};self.record()
        req=urllib.request.Request(BASE+path,data=None if body is None else json.dumps(body).encode(),headers=headers,method=method)
        try:
            with self.client.open(req,timeout=55) as response:status=response.status;raw=response.read(524289);response_headers=response.headers
        except urllib.error.HTTPError as error:status=error.code;raw=error.read(524289);response_headers=error.headers
        self.last_request.update(actualStatus=status)
        if len(raw)<=524288:self.last_request.update(response_metadata(raw,status))
        cookie_headers=response_headers.get_all('Set-Cookie',[]) if response_headers is not None else []
        self.last_request.update(refreshCookieHeaderPresent=any(h.startswith('pm_refresh=') for h in cookie_headers),refreshCookieHeaderHttpOnly=any(h.startswith('pm_refresh=') and '; httponly' in h.lower() for h in cookie_headers));self.record()
        require(status in expected,'UNEXPECTED_HTTP_STATUS_'+str(status));require(len(raw)<=524288,'RESPONSE_TOO_LARGE')
        if path in ('/','/merchant/ai','/admin/ai'):return None
        return json.loads(raw,parse_float=Decimal) if raw else None
    def login(self,login,password):
        result=self.call('POST','/api/v1/auth/login',{'login':login,'password':password})
        self.last_request.update(refreshCookieStored=any(c.name=='pm_refresh' for c in self.cookies),refreshCookieStoredHttpOnly=any(c.name=='pm_refresh' and c.has_nonstandard_attr('HttpOnly') for c in self.cookies));self.record()
        require(isinstance(result.get('accessToken'),str),'LOGIN_TOKEN_MISSING');self.token=result['accessToken']
        require(any(c.name=='pm_refresh' and c.has_nonstandard_attr('HttpOnly') for c in self.cookies),'HTTPONLY_REFRESH_COOKIE_MISSING')
        return result

class Suite:
    def __init__(self):
        self.project=runner_project();self.folder=Path(os.environ['RUNNER_TEMP']).resolve()/self.project
        require(os.environ.get('E2E_PROJECT')==self.project,'PROJECT_MISMATCH')
        self.compose=['docker','compose','--project-name',self.project,'--env-file',str(self.folder/'container.env'),'-f','deploy/compose.yaml'];self.passed=[];self.stage='preflight';self.last_request=None;self.verify_qwen=os.environ.get('E2E_VERIFY_QWEN')=='true'
    def observe_request(self,record):self.last_request=record
    def session(self,actor):return Session(actor,self.observe_request)
    def command(self,args,data=None):
        r=subprocess.run(args,input=data,capture_output=True,timeout=45)
        require(r.returncode==0,'CONTAINER_OPERATION_FAILED');return r.stdout
    def sql(self,text):
        return self.command(self.compose+['exec','-T','postgres','psql','-X','-U','paymesh_container_user','-d','paymesh_container','-Atq','-v','ON_ERROR_STOP=1'],text.encode()).decode().strip()
    def check(self,name,operation):
        self.stage=name;self.last_request=None;operation();self.passed.append(name);print(name+': PASS')
    def identity(self):
        ids=self.command(self.compose+['ps','-q']).decode().split();require(len(ids)==5,'FIVE_CONTAINERS_REQUIRED')
        states=json.loads(self.command(['docker','inspect',*ids]));db=None
        for c in states:
            require(c['Config']['Labels'].get('com.docker.compose.project')==self.project,'FOREIGN_CONTAINER')
            require(c['State'].get('Health',{}).get('Status')=='healthy','UNHEALTHY_CONTAINER')
            if c['Config']['Labels'].get('com.docker.compose.service')=='postgres':db=c
            if c['Config']['Labels'].get('com.docker.compose.service')=='java':
                bindings=c['HostConfig']['PortBindings'];require(set(bindings)=={'15500/tcp'} and bindings['15500/tcp']==[{'HostIp':'127.0.0.1','HostPort':'15500'}],'PRIVATE_PORT_EXPOSURE')
        require(db is not None,'DATABASE_CONTAINER_REQUIRED')
        mounts=[m for m in db['Mounts'] if m['Destination']=='/var/lib/postgresql/data']
        require(len(mounts)==1 and mounts[0]['Type']=='volume' and mounts[0]['Name']==self.project+'_container_pgdata','FRESH_NAMED_VOLUME_REQUIRED')
        self.image_ids={c['Config']['Labels']['com.docker.compose.service']:c['Image'] for c in states}
    def seed(self):
        # The only SQL fixture write is a bootstrap Admin in the guarded EMPTY
        # runner database. Merchants and financial data are created through APIs.
        pw=(self.folder/'secrets/admin_password').read_text();require(bool(re.fullmatch('[A-Za-z0-9_-]{20,72}',pw)),'FIXTURE_PASSWORD_FORMAT')
        self.sql("""BEGIN;
DO $$ BEGIN IF current_database()<>'paymesh_container' OR current_user<>'paymesh_container_user' OR current_setting('data_directory')<>'/var/lib/postgresql/data' OR (SELECT count(*) FROM flyway_schema_history WHERE success AND version IN ('1','2','3','4','5','6','7','8','9','10','11','12','13','14'))<>14 OR EXISTS(SELECT 1 FROM app_users) OR EXISTS(SELECT 1 FROM payments) OR EXISTS(SELECT 1 FROM refunds) OR EXISTS(SELECT 1 FROM payment_links) OR EXISTS(SELECT 1 FROM ai_conversations) THEN RAISE EXCEPTION 'CI_EMPTY_DATABASE_REQUIRED'; END IF; END $$;
CREATE EXTENSION IF NOT EXISTS pgcrypto;
INSERT INTO app_users(user_id,login_normalized,password_hash,enabled,authorization_version,account_status) VALUES ('11111111-1111-4111-8111-111111111111','ci-admin@e2e.example.test',crypt('"""+pw+"""',gen_salt('bf',12)),true,1,'ACTIVE');
INSERT INTO user_roles(user_id,role_name) VALUES ('11111111-1111-4111-8111-111111111111','ADMIN');
COMMIT;""")
    def authentication(self):
        self.admin=self.session('ADMIN');self.admin.login('ci-admin@e2e.example.test',(self.folder/'secrets/admin_password').read_text())
        self.admin.call('GET','/api/v1/admin/profile');self.admin.call('GET','/api/v1/merchant/dashboard',expected=(403,))
        anonymous=self.session('ANONYMOUS');anonymous.call('GET','/merchant/ai');anonymous.call('GET','/admin/ai');anonymous.call('GET','/api/v1/merchant/dashboard',expected=(401,403))
        self.merchants=[];password=(self.folder/'secrets/merchant_password').read_text()
        for letter in ('a','b'):
            login='merchant-'+letter+'@e2e.example.test'
            result=anonymous.call('POST','/api/v1/auth/register',{'firstName':'CI','lastName':letter,'businessName':'Disposable '+letter,'email':login,'mobile':'+12025550101','businessType':'COMPANY','country':'US','password':password,'confirmPassword':password,'terms':True},expected=(201,))
            require(result['accountStatus']=='PENDING_APPROVAL','REGISTRATION_STATUS')
            rows=self.admin.call('GET','/api/v1/admin/merchants?search='+urllib.parse.quote(login)+'&size=5')['items'];require(len(rows)==1,'MERCHANT_LOOKUP')
            mid=rows[0]['merchantId'];self.admin.call('POST','/api/v1/admin/merchant/approve',{'merchantId':mid,'reviewReference':'CI disposable fixture ownership','ownershipAttested':True})
            session=self.session('MERCHANT_'+letter.upper());session.login(login,password);profile=session.call('GET','/api/v1/merchant/profile');require(profile['merchantId']==mid and profile['accountStatus']=='ACTIVE','MERCHANT_PROFILE')
            session.call('GET','/api/v1/admin/profile',expected=(403,));self.merchants.append((session,mid))
        self.a,self.mid=self.merchants[0];self.b,_=self.merchants[1]
        refreshed=self.a.call('POST','/api/v1/auth/refresh',{});self.a.token=refreshed['accessToken']
    def payment(self):
        body={'merchantId':self.mid,'amount':'13.25','currency':'INR','customerId':'synthetic-ci-customer','paymentMethod':'UPI'};key=str(uuid.uuid4())
        created=self.a.call('POST','/api/v1/payments',body,expected=(201,),key=key);self.payment_id=created['paymentId'];require(created['status']=='CREATED' and money(created['amount'])==Decimal('13.25'),'PAYMENT_CREATED')
        replay=self.a.call('POST','/api/v1/payments',body,key=key);require(replay['paymentId']==self.payment_id,'PAYMENT_IDEMPOTENCY')
        self.b.call('GET','/api/v1/payments/'+self.payment_id,expected=(403,404))
        done=self.a.call('POST','/api/v1/payments/'+self.payment_id+'/process');require(done['status']=='SUCCESS','PAYMENT_SUCCESS')
        self.admin.call('GET','/api/v1/admin/payments/'+self.payment_id)
    def checkout(self):
        link=self.a.call('POST','/api/v1/merchant/payment-links',{'amount':'25.00','currency':'USD','paymentMethod':'CARD','customerReference':'synthetic-order','description':'Disposable checkout fixture','expiryHours':24},expected=(201,),key=str(uuid.uuid4()))
        path=link['checkoutPath'];require(bool(re.fullmatch(r'/checkout/[A-Za-z0-9_-]{43}',path)),'CHECKOUT_PATH')
        api='/api/v1'+path;customer=self.session('PUBLIC_CHECKOUT');view=customer.call('GET',api)
        require(view['checkoutStatus']=='ACTIVE' and money(view['amount'])==Decimal('25.00') and view['currency']=='USD','PUBLIC_CHECKOUT_READ')
        require(not {'paymentId','merchantId','email','userId'}.intersection(view),'PUBLIC_RESPONSE_PRIVACY')
        paid=customer.call('POST',api+'/pay',{'confirmed':True},key=str(uuid.uuid4()));require(paid['checkoutStatus']=='PAID' and paid['paymentStatus']=='SUCCESS','CHECKOUT_SUCCESS')
        again=customer.call('GET',api+'/status');require(again['checkoutStatus']=='PAID' and again['receiptReference'],'PAID_RECEIPT')
        customer.call('POST',api+'/pay',{'confirmed':True},expected=(409,),key=str(uuid.uuid4()))
        owned=self.a.call('GET','/api/v1/merchant/payment-links/'+link['linkId']);require(owned['status']=='PAID' and owned['paymentId'],'OWNED_PAID_LINK')
        self.b.call('GET','/api/v1/merchant/payment-links/'+link['linkId'],expected=(403,404))
    def refunds(self):
        for amount in ('3.25','10.00'):
            r=self.a.call('POST','/api/v1/payments/'+self.payment_id+'/refund',{'amount':amount},expected=(201,),key=str(uuid.uuid4()));require(r['status']=='SUCCESS' and money(r['amount'])==Decimal(amount),'REFUND_RECORDED')
        payment=self.a.call('GET','/api/v1/payments/'+self.payment_id);require(payment['status']=='REFUNDED','FULL_REFUND_STATUS')
        history=self.a.call('GET','/api/v1/payments/'+self.payment_id+'/refunds');require(sum((money(r['amount']) for r in history),Decimal('0'))==Decimal('13.25'),'EXACT_REFUND_TOTAL')
        self.b.call('GET','/api/v1/payments/'+self.payment_id+'/refunds',expected=(403,404))
    def ai_and_conversations(self):
        for session,portal in ((self.a,'merchant'),(self.admin,'admin')):
            result=session.call('POST','/api/v1/'+portal+'/ai/chat',{'question':'What is idempotency?','history':[]})
            require(result['intent']=='KNOWLEDGE' and result['generationStatus']==('SUCCEEDED' if self.verify_qwen else 'NOT_ATTEMPTED') and result['analysisMode']==('RAG_LLM' if self.verify_qwen else 'RAG_ASSISTED') and result['knowledgeReferences'],'PRIVATE_AUTH_RAG_CHAT')
        base='/api/v1/merchant/ai/conversations';created=self.a.call('POST',base,{'requestId':str(uuid.uuid4()),'title':'Disposable API E2E','context':None},expected=(200,201));c=created['conversation'];cid=c['conversationId']
        self.b.call('GET',base+'/'+cid,expected=(404,));self.admin.call('GET','/api/v1/admin/ai/conversations/'+cid,expected=(404,))
        turn=self.a.call('POST',base+'/'+cid+'/messages',{'requestId':str(uuid.uuid4()),'expectedVersion':c['version'],'question':'What is idempotency?'})
        require(turn['status']=='COMPLETED' and turn['turn']['response']['generationStatus']==('SUCCEEDED' if self.verify_qwen else 'NOT_ATTEMPTED'),'SAVED_GENERATION_STATUS')
        saved=self.a.call('GET',base+'/'+cid+'/messages?page=0&size=5');require(saved['total']==1 and len(saved['turns'])==1,'SAVED_HISTORY')
        renamed=self.a.call('POST',base+'/'+cid+'/rename',{'expectedVersion':saved['conversation']['version'],'title':'Renamed disposable E2E'})['conversation'];require(renamed['title']=='Renamed disposable E2E','RENAME_PERSISTED')
        self.a.call('POST',base+'/'+cid+'/delete',{'expectedVersion':renamed['version']});self.a.call('GET',base+'/'+cid,expected=(404,))
    def final_state(self):
        counts=json.loads(self.sql("SELECT json_build_object('users',(SELECT count(*) FROM app_users),'payments',(SELECT count(*) FROM payments),'refunds',(SELECT count(*) FROM refunds),'links',(SELECT count(*) FROM payment_links),'attempts',(SELECT count(*) FROM checkout_attempts),'conversations',(SELECT count(*) FROM ai_conversations));"))
        require(counts=={'users':3,'payments':2,'refunds':2,'links':1,'attempts':1,'conversations':0},'FINAL_FIXTURE_COUNTS')
        self.a.call('POST','/api/v1/auth/logout',{});self.a.call('POST','/api/v1/auth/refresh',{},expected=(401,))
        self.counts=counts
    def run(self):
        self.folder.mkdir(mode=0o700,exist_ok=True)
        try:
            for name,operation in [('container_identity_health',self.identity),('empty_database_seed',self.seed),('authentication_and_roles',self.authentication),('payments_and_idempotency',self.payment),('public_checkout',self.checkout),('partial_full_refunds',self.refunds),('private_ai_and_saved_history',self.ai_and_conversations),('final_counts_and_logout',self.final_state)]:self.check(name,operation)
            result={'success':True,'checksPassed':self.passed,'project':self.project,'sourceCommit':os.environ.get('GITHUB_SHA'),'imageIds':self.image_ids,'counts':self.counts,'modelInferenceRequested':self.verify_qwen,'modelInferenceVerified':self.verify_qwen,'nativeBrowserTested':False,'localMacServicesAccessed':False,'dockerHubPublished':False}
        except Exception as error:
            code=str(error) if isinstance(error,Failure) else 'UNEXPECTED_RUNNER_OR_PROTOCOL_ERROR'
            if not re.fullmatch('[A-Z0-9_]{1,80}',code):code='UNCLASSIFIED_FAILURE'
            result={'success':False,'failureCode':code,'lastRequest':self.last_request,'failedStage':self.stage,'checksPassed':self.passed,'modelInferenceRequested':self.verify_qwen,'modelInferenceVerified':False,'dockerHubPublished':False}
        if not result['success']:print('E2E_FAILURE_DIAGNOSTIC='+json.dumps({'failureCode':result['failureCode'],'lastRequest':result['lastRequest']},sort_keys=True))
        path=self.folder/'sanitized-e2e.json';path.write_text(json.dumps(result,indent=2));path.chmod(0o600)
        print('DISPOSABLE_CONTAINER_API_E2E_PASS' if result['success'] else 'DISPOSABLE_CONTAINER_API_E2E_FAILED_STAGE='+self.stage)
        return 0 if result['success'] else 1
if __name__=='__main__':
    try:raise SystemExit(Suite().run())
    except Exception:print('E2E_RUNNER_GUARD_FAILED');raise SystemExit(1)
