"""Build an allowlisted static Pages artifact; never reads runtime configuration.
The demo spec and Swagger assets are inputs only and remain byte-for-byte intact.
"""
import argparse
import copy
import hashlib
import json
from pathlib import Path
import re
import shutil

ROOT=Path(__file__).resolve().parent.parent
SPEC='backend/openapi/paymesh-demo.json'
SCHEMA_SHA='2385f5bbb8c37878daae73baeabe7f34b2f022a4a8c049329ee61f71796f039c'
PATHS={'/api/v1/auth/login':'post','/api/v1/auth/refresh':'post',
       '/api/v1/auth/logout':'post','/api/v1/auth/logout-all':'post',
       '/api/v1/payments/health':'get','/api/v1/payments':'post'}

def require(ok,code):
    if not ok:raise ValueError(code)

def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()

def record_fields(source,name):
    match=re.search(r'\brecord\s+'+name+r'\s*\((.*?)\)\s*\{',source,re.S)
    require(match is not None,'JAVA_RECORD_NOT_FOUND')
    text=re.sub(r'@\w+(?:\([^)]*\))?','',match.group(1))
    return {name:kind for kind,name in re.findall(r'\b(String|BigDecimal|UUID|Instant|long)\s+(\w+)',text)}

def source_contracts(root):
    auth=root/'backend/src/main/java/com/paymesh/backend/security/auth'
    login=(auth/'AuthController.java').read_text();session=(auth/'SessionController.java').read_text()
    require('@RequestMapping("/api/v1/auth")' in login and '@PostMapping("/login")' in login,'LOGIN_ROUTE_CHANGED')
    fields={name:kind for kind,name in re.findall(r'public\s+(String|char\[\]|Boolean)\s+(\w+)',login)}
    require(fields=={'login':'String','password':'char[]','rememberMe':'Boolean'},'LOGIN_FIELDS_CHANGED')
    require('@NotBlank @Size(max = 255)' in login and '@NotNull @Size(max = 72)' in login,'LOGIN_VALIDATION_CHANGED')
    for suffix in ('refresh','logout','logout-all'):require('@PostMapping("/'+suffix+'")' in session,'SESSION_ROUTE_CHANGED')
    require('Map.of("status",code,"message",message)' in session,'SESSION_RESPONSE_CHANGED')
    token=(auth/'JwtTokenService.java').read_text()
    require(record_fields(token,'TokenResponse')=={'accessToken':'String','tokenType':'String','expiresIn':'long','expiresAt':'Instant','login':'String'},'TOKEN_FIELDS_CHANGED')
    dto=root/'backend/src/main/java/com/paymesh/backend/dto'
    request_source=(dto/'PaymentRequest.java').read_text()
    require('@DecimalMin(value = "0.01"' in request_source and '@Digits(integer = 12, fraction = 2)' in request_source,'PAYMENT_VALIDATION_CHANGED')
    require(record_fields(request_source,'PaymentRequest')=={'merchantId':'String','amount':'BigDecimal','currency':'String','customerId':'String','paymentMethod':'String'},'PAYMENT_REQUEST_CHANGED')
    require(record_fields((dto/'PaymentResponse.java').read_text(),'PaymentResponse')=={'paymentId':'UUID','merchantId':'String','amount':'BigDecimal','currency':'String','customerId':'String','paymentMethod':'String','status':'String','createdAt':'Instant'},'PAYMENT_RESPONSE_CHANGED')
    controller=(root/'backend/src/main/java/com/paymesh/backend/controller/PaymentController.java').read_text()
    for marker in ('@RequestMapping("/api/v1/payments")','@GetMapping("/health")','@PostMapping\n','@RequestHeader("Idempotency-Key")','HttpStatus.CREATED','HttpStatus.OK','"status", "RUNNING"'):
        require(marker in controller,'PAYMENT_ROUTE_OR_RESPONSE_CHANGED')
    policy=(auth/'AuthBrowserPolicy.java').read_text()
    for marker in ('COOKIE="pm_refresh"','getHeader("X-PayMesh-CSRF")','"1"','httpOnly(true)','sameSite("Strict")','path("/api/v1/auth")'):
        require(marker in policy,'BROWSER_POLICY_CHANGED')


def validate_spec(spec):
    require(spec.get('openapi')=='3.0.3' and spec.get('info',{}).get('version')=='1.0.1','OPENAPI_HEADER_INVALID')
    require(set(spec.get('paths',{}))==set(PATHS),'OPENAPI_SCOPE_CHANGED')
    for path,method in PATHS.items():
        operation=spec['paths'][path]
        require(set(operation)=={method},'OPENAPI_METHOD_CHANGED')
        require(type(operation[method].get('responses')) is dict and bool(operation[method]['responses']),'OPENAPI_RESPONSES_REQUIRED')
        require(all(re.fullmatch('[1-5][0-9][0-9]',code) for code in operation[method]['responses']),'OPENAPI_STATUS_INVALID')
    def walk(node):
        if isinstance(node,dict):
            if '$ref' in node:
                ref=node['$ref'];require(type(ref) is str and ref.startswith('#/'),'REMOTE_REFERENCE_FORBIDDEN')
                target=spec
                try:
                    for part in ref[2:].split('/'):target=target[part.replace('~1','/').replace('~0','~')]
                except (KeyError,TypeError):raise ValueError('UNRESOLVED_OPENAPI_REFERENCE') from None
            for key,value in node.items():
                require(key not in ('example','examples','externalValue','callbacks','webhooks'),'EXAMPLES_OR_EXTERNAL_OPERATIONS_FORBIDDEN')
                walk(value)
        elif isinstance(node,list):
            for child in node:walk(child)
    walk(spec)


def formal_validate(root,spec):
    # Lazy import: existing deployment workflows require no new dependency.
    from jsonschema import Draft4Validator
    schema=root/'deploy/openapi-3.0-schema.json'
    require(digest(schema)==SCHEMA_SHA,'OFFICIAL_OPENAPI_SCHEMA_MISMATCH')
    value=json.loads(schema.read_text());Draft4Validator.check_schema(value)
    require(not list(Draft4Validator(value).iter_errors(spec)),'OFFICIAL_OPENAPI_VALIDATION_FAILED')


def presentation_spec(root):
    source_contracts(root)
    spec=copy.deepcopy(json.loads((root/SPEC).read_text()));validate_spec(spec)
    spec['info'].update(title='PayMesh AI — REST API Documentation',description='Read-only, source-checked subset. No live backend is hosted on this site. All payment gateways are simulated. Authentication, browser sessions and payment creation are covered here; other APIs are documented in the repository source reference.')
    spec['tags']=[{'name':'Authentication','description':'Shared Merchant/Admin identity. Sign-in issues a JWT; permissions are enforced separately.'},
        {'name':'Browser sessions','description':'Cookie-backed refresh rotation and revocation, protected by exact Origin and X-PayMesh-CSRF.'},
        {'name':'Payments','description':'Simulated payments. Creation requires a bearer token plus role, account and merchant-scope authorization.'}]
    schemas={
        'LoginRequest':{'type':'object','required':['login','password'],'properties':{'login':{'type':'string','minLength':1,'maxLength':255},'password':{'type':'string','format':'password','maxLength':72,'writeOnly':True},'rememberMe':{'type':'boolean','default':False}}},
        'TokenResponse':{'type':'object','properties':{'accessToken':{'type':'string','readOnly':True,'description':'RS256 access token. No real token is provided by this documentation.'},'tokenType':{'type':'string','enum':['Bearer']},'expiresIn':{'type':'integer','format':'int64','description':'Access-token lifetime in seconds (900 in the implementation).'},'expiresAt':{'type':'string','format':'date-time'},'login':{'type':'string'}}},
        'SessionResult':{'type':'object','properties':{'status':{'type':'integer'},'message':{'type':'string'}}},
        'PaymentRequest':{'type':'object','required':['merchantId','amount','currency','customerId','paymentMethod'],'properties':{'merchantId':{'type':'string','minLength':1,'description':'Must be within the authenticated actor’s authorized scope.'},'amount':{'type':'number','minimum':0.01,'multipleOf':0.01,'description':'Java BigDecimal; at most 12 integer digits and two fractional digits.'},'currency':{'type':'string','minLength':1},'customerId':{'type':'string','minLength':1},'paymentMethod':{'type':'string','minLength':1}}},
        'PaymentResponse':{'type':'object','properties':{'paymentId':{'type':'string','format':'uuid'},'merchantId':{'type':'string'},'amount':{'type':'number','description':'Exact decimal monetary value in the payment currency.'},'currency':{'type':'string'},'customerId':{'type':'string'},'paymentMethod':{'type':'string'},'status':{'type':'string'},'createdAt':{'type':'string','format':'date-time'}}},
        'PaymentHealth':{'type':'object','properties':{'service':{'type':'string'},'status':{'type':'string','enum':['RUNNING']}}}
    }
    spec['components']['schemas']=schemas
    spec['components']['securitySchemes']['refreshCookie']={'type':'apiKey','in':'cookie','name':'pm_refresh','description':'Opaque browser refresh cookie; HttpOnly, SameSite=Strict, auth-path scoped. Secure on HTTPS deployments. Never enter a cookie on this static site.'}
    def content(schema):return {'application/json':{'schema':{'$ref':'#/components/schemas/'+schema}}}
    identifiers=['signIn','refreshSession','logoutSession','logoutAllSessions','paymentHealth','createPayment']
    for identifier,(path,method) in zip(identifiers,PATHS.items()):
        op=spec['paths'][path][method];op['operationId']=identifier
        op['tags']=['Authentication' if path.endswith('/login') else 'Browser sessions' if '/auth/' in path else 'Payments']
        op['description']='Read-only reference: execution is disabled. Error-body structure can vary by validation/controller/security layer; no universal error schema is claimed.'
    login=spec['paths']['/api/v1/auth/login']['post'];login['requestBody']={'required':True,'content':content('LoginRequest')};login['responses']['200']['content']=content('TokenResponse')
    login['description']+=' For browser requests, the configured Origin and X-PayMesh-CSRF: 1 are required; a refresh cookie is issued. Nonbrowser sign-in returns a bearer token without creating a browser session.'
    for suffix in ('refresh','logout','logout-all'):
        op=spec['paths']['/api/v1/auth/'+suffix]['post']
        op['parameters']=[{'name':'Origin','in':'header','required':True,'schema':{'type':'string'},'description':'Exact configured application Origin; this documentation hostname is not a live API origin.'},{'name':'X-PayMesh-CSRF','in':'header','required':True,'schema':{'type':'string','enum':['1']}}]
        op['responses']['200']['content']=content('TokenResponse' if suffix=='refresh' else 'SessionResult')
        op['description']+=' Refresh rotates the existing browser session; logout revokes the current session; logout-all revokes all sessions for the account. Browser cookie values are never supplied here.'
        if suffix!='logout':op['security']=[{'refreshCookie':[]}]
    pay=spec['paths']['/api/v1/payments']['post'];pay['requestBody']={'required':True,'content':content('PaymentRequest')}
    pay['description']+=' Merchant and Admin roles are accepted at the route, then current account/role state and merchant access are rechecked. A new request returns 201; an authorized idempotent replay returns 200. This operation creates a payment record; it does not claim to process or settle real funds.'
    for code in ('200','201'):pay['responses'][code]['content']=content('PaymentResponse')
    spec['paths']['/api/v1/payments/health']['get']['responses']['200']['content']=content('PaymentHealth')
    spec['paths']['/api/v1/payments/health']['get']['description']+=' Static payment-service availability response, not a full database/model readiness guarantee.'
    validate_spec(spec)
    return spec


def build(output,root=ROOT,formal=False):
    root=Path(root);output=Path(output)
    require(not output.exists() and not output.is_symlink(),'OUTPUT_MUST_BE_NEW')
    spec=presentation_spec(root)
    if formal:
        formal_validate(root,json.loads((root/SPEC).read_text()));formal_validate(root,spec)
    vendor=root/'deploy/swagger-ui';manifest=json.loads((vendor/'manifest.json').read_text())
    require(manifest['package']=='swagger-ui-dist' and manifest['version']=='5.35.1','SWAGGER_VERSION_MISMATCH')
    for name,value in manifest['files'].items():require(digest(vendor/name)==value,'SWAGGER_INTEGRITY_MISMATCH')
    output.mkdir(parents=True,exist_ok=False);(output/'assets').mkdir()
    for name in ('index.html','site.css','site.js'):shutil.copyfile(root/'docs/api'/name,output/name)
    for src,dst in [('swagger-ui-bundle.js','swagger-ui-bundle.js'),('swagger-ui.css','swagger-ui.css'),('LICENSE','LICENSE.txt'),('NOTICE','NOTICE.txt')]:shutil.copyfile(vendor/src,output/'assets'/dst)
    (output/'openapi.json').write_text(json.dumps(spec,indent=2,ensure_ascii=False)+'\n')
    (output/'.nojekyll').write_text('')
    (output/'build-info.json').write_text(json.dumps({'sourceOpenApiSha256':digest(root/SPEC),'publishedSpecSha256':digest(output/'openapi.json'),'swaggerUiVersion':manifest['version'],'operations':len(PATHS),'readOnly':True},indent=2)+'\n')
    require({p.relative_to(output).as_posix() for p in output.rglob('*') if p.is_file()}=={'index.html','site.css','site.js','openapi.json','build-info.json','.nojekyll','assets/swagger-ui-bundle.js','assets/swagger-ui.css','assets/LICENSE.txt','assets/NOTICE.txt'},'STATIC_ARTIFACT_SCOPE_MISMATCH')
    print('STATIC_API_DOCS_VALIDATED_AND_BUILT')
    return spec

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--output',required=True);parser.add_argument('--formal',action='store_true');args=parser.parse_args()
    build(args.output,formal=args.formal)
