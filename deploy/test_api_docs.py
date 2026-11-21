"""Offline static-site tests. No browser, backend, Docker or network required."""
import copy
import hashlib
from html.parser import HTMLParser
import json
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import unittest
from urllib.parse import urljoin,urlsplit
import build_api_docs as docs
ROOT=Path(__file__).resolve().parent.parent

class Links(HTMLParser):
    def __init__(self):super().__init__();self.links=[];self.ids=[];self.forms=0
    def handle_starttag(self,tag,attrs):
        a=dict(attrs)
        if 'id' in a:self.ids.append(a['id'])
        if tag=='form':self.forms+=1
        for key in ('href','src'):
            if key in a:self.links.append((tag,a[key]))

def yaml(path):
    raw=subprocess.check_output(['ruby','-rjson','-ryaml','-e','puts JSON.generate(YAML.load_file(ARGV[0]))',str(path)])
    return json.loads(raw)

class ApiDocsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp=tempfile.TemporaryDirectory();cls.output=Path(cls.temp.name)/'site';cls.spec=docs.build(cls.output)
        cls.html=(cls.output/'index.html').read_text();cls.links=Links();cls.links.feed(cls.html)
    @classmethod
    def tearDownClass(cls):cls.temp.cleanup()
    def test_input_json_scope_valid(self):docs.validate_spec(json.loads((ROOT/docs.SPEC).read_text()))
    def test_java_contracts_are_checked(self):docs.source_contracts(ROOT)
    def test_exact_original_paths_preserved(self):
        self.assertEqual(set(self.spec['paths']),set(json.loads((ROOT/docs.SPEC).read_text())['paths']))
        self.assertEqual(len(self.spec['paths']),6)
    def test_request_and_response_shapes(self):
        s=self.spec['components']['schemas'];self.assertEqual(set(s['LoginRequest']['properties']),{'login','password','rememberMe'})
        self.assertEqual(set(s['TokenResponse']['properties']),{'accessToken','tokenType','expiresIn','expiresAt','login'})
        self.assertEqual(set(s['PaymentRequest']['properties']),{'merchantId','amount','currency','customerId','paymentMethod'})
        self.assertEqual(set(s['PaymentResponse']['properties']),{'paymentId','merchantId','amount','currency','customerId','paymentMethod','status','createdAt'})
        self.assertNotIn('examples',json.dumps(self.spec))
    def test_schema_refs_resolve(self):docs.validate_spec(self.spec)
    def test_remote_reference_rejected(self):
        value=copy.deepcopy(self.spec);value['components']['schemas']['bad']={'$ref':'https://example.invalid/schema'}
        with self.assertRaisesRegex(ValueError,'REMOTE_REFERENCE'):docs.validate_spec(value)
    def test_missing_reference_rejected(self):
        value=copy.deepcopy(self.spec);value['components']['schemas']['bad']={'$ref':'#/components/schemas/Missing'}
        with self.assertRaisesRegex(ValueError,'UNRESOLVED'):docs.validate_spec(value)
    def test_extra_endpoints_rejected(self):
        value=copy.deepcopy(self.spec);value['paths']['/api/v1/invented']={'get':{'responses':{'200':{'description':'bad'}}}}
        with self.assertRaisesRegex(ValueError,'SCOPE'):docs.validate_spec(value)
    def test_unknown_methods_rejected(self):
        value=copy.deepcopy(self.spec);value['paths']['/api/v1/payments']['delete']={}
        with self.assertRaisesRegex(ValueError,'METHOD'):docs.validate_spec(value)
    def test_examples_rejected_to_avoid_sensitive_fixtures(self):
        value=copy.deepcopy(self.spec);value['info']['example']='SYNTHETIC_CANARY'
        with self.assertRaisesRegex(ValueError,'EXAMPLES'):docs.validate_spec(value)
    def test_tag_groups_are_present(self):
        self.assertEqual({t['name'] for t in self.spec['tags']},{'Authentication','Browser sessions','Payments'})
        self.assertTrue(all(op['tags'] for item in self.spec['paths'].values() for op in item.values()))
    def test_browser_and_payment_security_documented(self):
        self.assertEqual(self.spec['paths']['/api/v1/payments']['post']['security'],[{'bearerAuth':[]}])
        self.assertEqual(self.spec['components']['securitySchemes']['refreshCookie']['name'],'pm_refresh')
        self.assertIn('X-PayMesh-CSRF',json.dumps(self.spec))
    def test_local_assets_and_links_exist_at_pages_subpath(self):
        for tag,url in self.links.links:
            if url.startswith('https://'):
                self.assertEqual(tag,'a');self.assertEqual(urlsplit(url).hostname,'github.com');continue
            if url.startswith('#'):
                self.assertIn(url[1:],self.links.ids);continue
            self.assertFalse(url.startswith('/'))
            resolved=urlsplit(urljoin('https://bhupirao.github.io/paymesh-ai/',url)).path
            self.assertTrue(resolved.startswith('/paymesh-ai/'))
            if url!='./':self.assertTrue((self.output/url.removeprefix('./')).is_file(),url)
    def test_no_cdn_or_inline_script(self):
        self.assertNotIn('cdn.',self.html);self.assertNotRegex(self.html,r'<script(?![^>]*src=)[^>]*>')
        self.assertNotRegex(self.html,r'\son\w+\s*=')
    def test_explicit_read_only_notice(self):
        self.assertIn('Documentation only.',self.html);self.assertIn('backend is not permanently hosted',self.html)
        self.assertIn('not included in this specification',self.html);self.assertIn('No token entry',self.html)
    def test_accessible_navigation_and_mobile_layout(self):
        self.assertEqual(self.links.forms,0);self.assertEqual(len(self.links.ids),len(set(self.links.ids)))
        self.assertIn('class="skip-link"',self.html);self.assertIn('aria-label="Primary navigation"',self.html)
        self.assertIn('width=device-width',self.html);self.assertIn('max-width:520px',(self.output/'site.css').read_text())
    def test_csp_restricts_execution_and_network(self):
        for rule in ("default-src 'none'","script-src 'self'","connect-src 'self'","form-action 'none'"):self.assertIn(rule,self.html)
        self.assertNotIn("script-src 'self' 'unsafe-inline'",self.html)
    def test_no_runtime_or_private_artifacts(self):
        files=[p.relative_to(self.output).as_posix() for p in self.output.rglob('*') if p.is_file()]
        self.assertEqual(len(files),10)
        self.assertFalse(any(name.endswith(('.env','.dump','.gguf','.pem','.py')) for name in files))
        for name in ('index.html','openapi.json','site.js','build-info.json'):
            text=(self.output/name).read_text();self.assertNotRegex(text,r'gh[pousr]_[A-Za-z0-9]{30,}|eyJ[A-Za-z0-9_-]{25,}\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+')
    def test_license_and_notice_preserved(self):
        for original,new in [('LICENSE','LICENSE.txt'),('NOTICE','NOTICE.txt')]:self.assertEqual((ROOT/'deploy/swagger-ui'/original).read_bytes(),(self.output/'assets'/new).read_bytes())
    def test_asset_integrity_and_metadata(self):
        manifest=json.loads((ROOT/'deploy/swagger-ui/manifest.json').read_text())
        for name in ('swagger-ui-bundle.js','swagger-ui.css'):self.assertEqual(docs.digest(self.output/'assets'/name),manifest['files'][name])
        info=json.loads((self.output/'build-info.json').read_text());self.assertTrue(info['readOnly']);self.assertEqual(info['operations'],6)
        self.assertEqual(info['sourceOpenApiSha256'],docs.digest(ROOT/docs.SPEC))
    def test_existing_output_is_never_overwritten(self):
        with self.assertRaisesRegex(ValueError,'OUTPUT_MUST_BE_NEW'):docs.build(self.output)
    def test_official_schema_is_pinned(self):
        manifest=json.loads((ROOT/'deploy/openapi-schema-manifest.json').read_text());self.assertEqual(manifest['sha256'],docs.SCHEMA_SHA)
        self.assertEqual(docs.digest(ROOT/'deploy/openapi-3.0-schema.json'),docs.SCHEMA_SHA)
        self.assertIn('Apache License',(ROOT/'deploy/openapi-schema-LICENSE').read_text())
    def test_source_fields_drift_fails_closed(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);folder=root/'backend/src/main/java/com/paymesh/backend/security/auth';folder.mkdir(parents=True)
            for name in ('AuthController.java','SessionController.java'):(folder/name).write_bytes((ROOT/'backend/src/main/java/com/paymesh/backend/security/auth'/name).read_bytes())
            p=folder/'AuthController.java';p.write_text(p.read_text().replace('String login;','String renamed;'))
            with self.assertRaisesRegex(ValueError,'LOGIN_FIELDS_CHANGED'):docs.source_contracts(root)
    def test_readme_link_is_marked_pending(self):
        text=(ROOT/'README.md').read_text();self.assertIn('API documentation — deployment pending',text);self.assertIn('https://bhupirao.github.io/paymesh-ai/',text)
    def test_workflow_manual_only_and_least_privilege(self):
        model=yaml(ROOT/'.github/workflows/api-docs-pages.yml');self.assertEqual(model.get('on',model.get('true')),{'workflow_dispatch':None})
        self.assertEqual(model['permissions'],{'contents':'read'});self.assertFalse(model['concurrency']['cancel-in-progress'])
        build=model['jobs']['build'];deploy=model['jobs']['deploy']
        self.assertEqual(build['permissions'],{'contents':'read','pages':'read'})
        self.assertEqual(deploy['permissions'],{'pages':'write','id-token':'write'});self.assertEqual(deploy['needs'],'build');self.assertEqual(deploy['environment']['name'],'github-pages')
    def test_workflow_pins_and_artifact_scope(self):
        text=(ROOT/'.github/workflows/api-docs-pages.yml').read_text();pins=json.loads((ROOT/'deploy/pages-action-pins.json').read_text())
        refs=re.findall(r'uses: (\S+)',text);self.assertEqual(len(refs),4)
        for ref in refs:self.assertRegex(ref,r'^[A-Za-z0-9_-]+/[A-Za-z0-9_-]+@[a-f0-9]{40}$')
        for name,sha in pins['direct'].items():self.assertIn(name+'@'+sha,refs)
        self.assertIn('enablement: false',text);self.assertIn('--formal',text);self.assertIn('--require-hashes',text)
        self.assertIn('path: ${{ runner.temp }}/paymesh-api-site',text)
        self.assertNotIn('secrets.',text);self.assertNotIn('docker',text.lower());self.assertNotIn('cloudflared',text)
    def test_build_dependencies_exact_and_hashed(self):
        text=(ROOT/'deploy/requirements-pages.txt').read_text()
        self.assertEqual(len(re.findall(r'^\S+==[0-9.]+',text,re.M)),6)
        self.assertEqual(len(re.findall(r'^\S+==[0-9.]+ \\\n\s+--hash=sha256:[a-f0-9]{64}',text,re.M)),6)

if __name__=='__main__':unittest.main()
