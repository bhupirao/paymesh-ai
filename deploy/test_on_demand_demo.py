"""Offline only: no Docker, tunnel, external network or service mutations."""
import hashlib
from email.message import Message
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock,patch
import demo_edge as edge
import on_demand_demo as demo
from container_e2e import Failure

ROOT=Path(__file__).resolve().parent.parent

def headers(**values):
    result=Message()
    for name,value in values.items():result[name.replace('_','-')]=value
    return result

def base():return headers(Host='quiet-demo.trycloudflare.com',Origin='https://quiet-demo.trycloudflare.com')

class EdgeTests(unittest.TestCase):
    def request(self,h=None,method='POST',path='/api/v1/auth/login'):
        return edge.request_headers(h or base(),method,path,'quiet-demo.trycloudflare.com')
    def test_exact_origin_mapping(self):
        result=self.request();self.assertEqual(result['Host'],'127.0.0.1:15500');self.assertEqual(result['Origin'],'http://127.0.0.1:15500')
    def test_wrong_host(self):
        with self.assertRaises(edge.Denied):self.request(headers(Host='evil.test'))
    def test_duplicate_host(self):
        h=base();h['Host']='quiet-demo.trycloudflare.com'
        with self.assertRaises(edge.Denied):self.request(h)
    def test_cross_origin(self):
        h=base();h.replace_header('Origin','https://evil.test')
        with self.assertRaises(edge.Denied):self.request(h)
    def test_missing_post_origin(self):
        with self.assertRaises(edge.Denied):self.request(headers(Host='quiet-demo.trycloudflare.com'))
    def test_duplicate_origin(self):
        h=base();h['Origin']='https://quiet-demo.trycloudflare.com'
        with self.assertRaises(edge.Denied):self.request(h)
    def test_safe_navigation_without_origin(self):
        self.request(headers(Host='quiet-demo.trycloudflare.com'),method='GET')
    def test_forwarded_rejected(self):
        for name,value in [('Forwarded','for=127.0.0.1'),('X-Forwarded-Proto','http'),('X-Forwarded-Host','evil.test'),('X-Forwarded-For','1.2.3.4, 5.6.7.8'),('X-Original-Host','evil.test')]:
            with self.subTest(name=name):
                h=base();h[name]=value
                with self.assertRaises(edge.Denied):self.request(h)
    def test_canonical_forwarding_stripped(self):
        h=base();h['X-Forwarded-Proto']='https';h['X-Forwarded-For']='192.0.2.1'
        self.assertFalse(any('forwarded' in k.lower() for k in self.request(h)))
    def test_duplicate_forwarding_rejected(self):
        h=base();h['X-Forwarded-Proto']='https';h['X-Forwarded-Proto']='https'
        with self.assertRaises(edge.Denied):self.request(h)
    def test_auth_csrf_not_fabricated(self):
        h=base();h['Authorization']='Bearer synthetic';h['X-PayMesh-CSRF']='1'
        result=self.request(h);self.assertEqual(result['Authorization'],'Bearer synthetic');self.assertEqual(result['X-PayMesh-CSRF'],'1')
        self.assertNotIn('X-PayMesh-CSRF',self.request())
    def test_provider_credentials_not_forwarded(self):
        h=base();h['Cf-Access-Jwt-Assertion']='synthetic';h['Cookie']='CF_Authorization=synthetic; pm_refresh='+'a'*43
        result=self.request(h);self.assertEqual(result['Cookie'],'pm_refresh='+'a'*43);self.assertNotIn('Cf-Access-Jwt-Assertion',result)
    def test_cookie_security_and_clearing(self):
        for token in ('a'*43,''):
            value=edge.secure_cookie('pm_refresh='+token+'; Path=/api/v1/auth; HttpOnly; SameSite=Strict; Max-Age=0')
            for attribute in ('Secure','HttpOnly','SameSite=Strict','Path=/api/v1/auth','Max-Age=0'):self.assertIn(attribute,value)
    def test_cookie_weakening_rejected(self):
        for raw in ('pm_refresh=abc; Path=/; HttpOnly; SameSite=Strict','pm_refresh='+'a'*43+'; Path=/api/v1/auth; SameSite=Strict','pm_refresh='+'a'*43+'; Path=/api/v1/auth; HttpOnly; SameSite=None','pm_refresh='+'a'*43+'; Path=/api/v1/auth; HttpOnly; SameSite=Strict; Domain=evil.test'):
            with self.assertRaises(edge.Denied):edge.secure_cookie(raw)
    def test_no_open_redirect_targets(self):
        for path in ('//evil.test','http://evil.test','/\\evil.test','/x\r\nHost:evil.test'):
            with self.assertRaises(edge.Denied):self.request(path=path)
    def test_request_smuggling_headers(self):
        for name in ('Transfer-Encoding','Upgrade','Proxy-Authorization'):
            h=base();h[name]='synthetic'
            with self.assertRaises(edge.Denied):self.request(h)
    def test_public_url_restriction(self):
        self.assertEqual(edge.public_host('https://quiet-demo.trycloudflare.com'),'quiet-demo.trycloudflare.com')
        for url in ('http://quiet-demo.trycloudflare.com','https://evil.test','https://quiet-demo.trycloudflare.com:443','https://quiet-demo.trycloudflare.com/','https://user@quiet-demo.trycloudflare.com'):
            with self.assertRaises(edge.Denied):edge.public_host(url)

class LifecycleTests(unittest.TestCase):
    def report(self):
        return dict(success=True,modelInferenceVerified=True,publishedImagesOnly=True,retries=0,infrastructureError=False,tests=[dict(code=c,status='passed',chromiumLaunchStatus='SUCCEEDED') for c in demo.TESTS],steps=[dict(code=c,passed=True) for c in demo.STAGES])
    def test_real_browser_gate(self):demo.browser_gate(self.report())
    def test_fallback_or_skipped_rejected(self):
        for field,value in [('modelInferenceVerified',False),('success',False),('retries',1),('publishedImagesOnly',False)]:
            report=self.report();report[field]=value
            with self.assertRaises(Failure):demo.browser_gate(report)
        report=self.report();report['tests'][0]['status']='skipped'
        with self.assertRaises(Failure):demo.browser_gate(report)
    def test_all_ten_stages_required(self):
        report=self.report();report['steps'].pop()
        with self.assertRaises(Failure):demo.browser_gate(report)
    def test_exact_otp_challenge(self):
        self.assertTrue(demo.challenge('https://login.trycloudflare.com/authorize',302))
        for url in ('https://evil.test/authorize','http://login.trycloudflare.com/authorize','https://login.trycloudflare.com/other'):
            self.assertFalse(demo.challenge(url,302))
        self.assertFalse(demo.challenge('https://login.trycloudflare.com/authorize',200))
    def test_owned_child_termination(self):
        child=Mock();child.poll.side_effect=[None,0];demo.terminate(child);child.terminate.assert_called_once();child.wait.assert_called_once()
    def test_never_signal_exited_child(self):
        child=Mock();child.poll.return_value=0;demo.terminate(child);child.terminate.assert_not_called()
    def test_interrupted_cleanup_not_verified(self):
        with tempfile.TemporaryDirectory() as d:
            folder=Path(d);self.assertTrue(demo.closed(folder))
            (folder/'demo-processes.json').write_text('{"pids":[]}')
            self.assertFalse(demo.closed(folder))
            (folder/'public-access-closed.json').write_text('{"success":true}')
            self.assertTrue(demo.closed(folder))
    def test_interrupted_process_creation_blocks_cleanup(self):
        with tempfile.TemporaryDirectory() as d:
            folder=Path(d);(folder/'public-access-starting.json').write_text('{}')
            self.assertFalse(demo.closed(folder))
    def test_live_process_prevents_cleanup(self):
        with tempfile.TemporaryDirectory() as d:
            folder=Path(d);(folder/'demo-processes.json').write_text('{"pids":[1]}');(folder/'public-access-closed.json').write_text('{}')
            with patch.object(Path,'exists',return_value=True):self.assertFalse(demo.closed(folder))
    def test_public_close_before_container_cleanup(self):
        source=(ROOT/'deploy/on_demand_demo.py').read_text()
        self.assertLess(source.index("require(closed(suite.folder)"),source.index('return cleanup_project('))
        self.assertLess(source.index('terminate(child) # Public'),source.index("private_json(folder/'public-access-closed.json'"))
        self.assertIn('time.monotonic()>=self.server.deadline',(ROOT/'deploy/demo_edge.py').read_text())
    def test_demo_lock_and_unchanged_backend(self):
        lock=demo.lock();self.assertEqual(lock['platform'],'linux/amd64');self.assertEqual(len(lock['images']),4)
    def test_alternate_cleanup_requires_review_validator(self):
        source=(ROOT/'deploy/release_artifact_e2e.py').read_text()
        self.assertIn("'deploy/compose.demo.yaml'",source);self.assertIn("compose_file == COMPOSE or validate_config is not None",source)

class ConfigurationTests(unittest.TestCase):
    def test_workflow_security(self):
        s=(ROOT/'.github/workflows/on-demand-demo.yml').read_text()
        for value in ('workflow_dispatch:','contents: read','timeout-minutes: 55','cancel-in-progress: false','environment: demo-preview',"E2E_VERIFY_QWEN: 'true'",'--no-build','--pull never','npm test','always()','DEMO_ALLOWED_EMAIL'):
            self.assertIn(value,s)
        for value in ('pull_request:','push:','schedule:','docker/login-action','build-push-action','DOCKERHUB_TOKEN','secrets: inherit'):
            self.assertNotIn(value,s)
        self.assertLess(s.index('npm test'),s.index('OTP-protected HTTPS'))
        self.assertLess(s.index('OTP-protected HTTPS'),s.index('remove only owned'))
    def test_allowlisted_actions(self):
        import re
        refs=re.findall(r'uses: (\S+)',(ROOT/'.github/workflows/on-demand-demo.yml').read_text())
        self.assertEqual(set(refs),{'actions/checkout@d23441a48e516b6c34aea4fa41551a30e30af803','actions/upload-artifact@cf430e030ddbb5b0abf93d22962f4752f3646cd9'})
    def test_no_raw_artifacts(self):
        s=(ROOT/'.github/workflows/on-demand-demo.yml').read_text().split('path: |')[1]
        for forbidden in ('private-tunnel','secrets/','.env','trace','screenshot','*.log'):self.assertNotIn(forbidden,s)
    def test_compose_no_external_volumes_or_public_ports(self):
        s=(ROOT/'deploy/compose.demo.yaml').read_text()
        self.assertNotIn('build:',s);self.assertNotIn('external:',s)
        self.assertEqual(s.count("ports: ['127.0.0.1:15500:15500']"),1)
        self.assertEqual(s.count('network_mode: service:java'),3)
        self.assertIn('container_pgdata:',s)
    def test_swagger_integrity_and_disabled_operations(self):
        folder=ROOT/'deploy/swagger-ui';m=json.loads((folder/'manifest.json').read_text())
        self.assertEqual(m['version'],'5.35.1')
        for name,digest in m['files'].items():self.assertEqual(hashlib.sha256((folder/name).read_bytes()).hexdigest(),digest)
        s=(folder/'docs.js').read_text()
        for value in ('supportedSubmitMethods:[]','tryItOutEnabled:false','persistAuthorization:false','validatorUrl:null'):self.assertIn(value,s)
    def test_openapi_matches_controller_routes(self):
        spec=json.loads((ROOT/'backend/openapi/paymesh-demo.json').read_text());base=ROOT/'backend/src/main/java/com/paymesh/backend/security/auth'
        for path in spec['paths']:
            if path.startswith('/api/v1/auth/'):
                suffix=path.removeprefix('/api/v1/auth')
                file='AuthController.java' if suffix=='/login' else 'SessionController.java'
                source=(base/file).read_text()
                self.assertIn('@RequestMapping("/api/v1/auth")',source);self.assertIn('@PostMapping("'+suffix+'")',source)
        source=(ROOT/'backend/src/main/java/com/paymesh/backend/controller/PaymentController.java').read_text()
        self.assertIn('@RequestMapping("/api/v1/payments")',source);self.assertIn('@GetMapping("/health")',source);self.assertIn('@RequestHeader("Idempotency-Key")',source)
    def test_no_unsupported_cli_fallback(self):
        s=(ROOT/'deploy/on_demand_demo.py').read_text()
        self.assertIn("'--allowed-mail',email",s);self.assertIn("b'--allowed-mail' in result.stdout",s)
        self.assertIn("require(challenge(location,status),'OTP_ACCESS_GATE_UNVERIFIED')",s)
        self.assertLess(s.index("require(challenge(location,status)"),s.index('server.active=True'))


class HandlerSimulationTests(unittest.TestCase):
    def handler(self,active=True,deadline=None):
        import io,time,types
        h=edge.Handler.__new__(edge.Handler)
        h.command='GET';h.path='/merchant/login';h.headers=base();h.rfile=io.BytesIO()
        h.server=types.SimpleNamespace(active=active,deadline=deadline or time.monotonic()+60,host='quiet-demo.trycloudflare.com')
        h.send_safe=Mock();return h
    def test_expiration_blocks_before_upstream(self):
        import time
        h=self.handler(deadline=time.monotonic()-1)
        with patch.object(edge.http.client,'HTTPConnection') as upstream:h.handle_demo();upstream.assert_not_called()
        self.assertEqual(h.send_safe.call_args.args[0],410)
    def test_locked_gate_blocks_before_upstream(self):
        h=self.handler(active=False)
        with patch.object(edge.http.client,'HTTPConnection') as upstream:h.handle_demo();upstream.assert_not_called()
        self.assertEqual(h.send_safe.call_args.args[0],410)
    def test_wrong_origin_blocks_before_upstream(self):
        h=self.handler();h.headers.replace_header('Origin','https://evil.test')
        with patch.object(edge.http.client,'HTTPConnection') as upstream:h.handle_demo();upstream.assert_not_called()
        self.assertEqual(h.send_safe.call_args.args[0],403)
    def test_approved_post_preserves_csrf_and_bearer(self):
        h=self.handler();h.command='POST';h.path='/api/v1/auth/refresh';h.headers['X-PayMesh-CSRF']='1'
        with patch.object(edge.http.client,'HTTPConnection') as constructor:
            child=constructor.return_value;response=child.getresponse.return_value
            response.read.return_value=b'{}';response.status=200;response.getheaders.return_value=[];response.getheader.return_value='application/json'
            h.handle_demo()
            sent=child.request.call_args.kwargs['headers']
            self.assertEqual(sent['X-PayMesh-CSRF'],'1');self.assertEqual(sent['Origin'],'http://127.0.0.1:15500')
            child.close.assert_called_once()
    def test_weak_upstream_cookie_rejected(self):
        h=self.handler()
        with patch.object(edge.http.client,'HTTPConnection') as constructor:
            response=constructor.return_value.getresponse.return_value
            response.read.return_value=b'{}';response.getheaders.return_value=[('Set-Cookie','pm_refresh=bad')]
            h.handle_demo()
        self.assertEqual(h.send_safe.call_args.args[0],403)
    def test_static_docs_not_a_proxy(self):
        h=self.handler();h.path='/docs/../../secrets'
        with patch.object(edge.http.client,'HTTPConnection') as upstream:h.handle_demo();upstream.assert_not_called()
        self.assertEqual(h.send_safe.call_args.args[0],403)

class MoreSecurityTests(unittest.TestCase):
    def test_exact_recipient_only(self):
        self.assertTrue(demo.allowed_email('operator@example.test'))
        for email in ('*@example.test','operator@example.test,other@example.test','Display <operator@example.test>','operator@example.test\n',r'operator\name@example.test','@example.test','a'*255+'@example.test'):
            self.assertFalse(demo.allowed_email(email))
    def test_malformed_broker_port_fails_closed(self):
        self.assertFalse(demo.challenge('https://login.trycloudflare.com:invalid/authorize',302))
    def test_raw_edge_exception_not_reported(self):
        h=HandlerSimulationTests().handler()
        with patch.object(edge.http.client,'HTTPConnection',side_effect=RuntimeError('SECRET_CANARY_URL_TOKEN')):
            h.handle_demo()
        self.assertEqual(h.send_safe.call_args.args,(502,b'Demo temporarily unavailable'))
    def test_internal_csrf_authorization_unchanged(self):
        source=(ROOT/'frontend/dev_server.py').read_text()
        self.assertIn("self.headers.get('X-PayMesh-Checkout' if path.startswith('/api/v1/checkout/') else 'X-PayMesh-CSRF') != '1'",source)
        controller=(ROOT/'backend/src/main/java/com/paymesh/backend/security/auth/SessionController.java').read_text()
        self.assertIn('if(!browser.allowed(request))return result(403',controller)


class LiveEntryTests(unittest.TestCase):
    def test_live_entry_is_validated_and_never_a_checkout_url(self):
        source=(ROOT/'deploy/on_demand_demo.py').read_text()
        self.assertIn("print('DEMO_AUTHENTICATED_ENTRY='+url+'/_demo/start',flush=True)",source)
        self.assertLess(source.index('server.host=public_host(url)'),source.index("print('DEMO_AUTHENTICATED_ENTRY='"))
        self.assertLess(source.index("require(challenge(location,status)"),source.index("print('DEMO_AUTHENTICATED_ENTRY='"))
        for line in source.splitlines():
            if 'print(' in line:
                self.assertNotIn('password',line)
                self.assertNotIn('email',line)
                self.assertNotIn('credentials',line)
    def test_summary_does_not_promise_live_availability(self):
        docs=(ROOT/'deploy/ON-DEMAND-DEMO.md').read_text()
        self.assertIn('step summary only after the step finishes',docs)
        self.assertIn('Session closed.',(ROOT/'deploy/on_demand_demo.py').read_text())



class ServeDiagnosticTests(unittest.TestCase):
    def test_guard_failure_is_allowlisted_not_raw(self):
        self.assertEqual(demo.error_code(Failure('DEMO_TUNNEL_EXITED')),'DEMO_TUNNEL_EXITED')
        self.assertEqual(demo.error_code(Failure('SECRET_CANARY_RAW_URL')),'UNCLASSIFIED_SERVE_ERROR')
        self.assertEqual(demo.error_code(Failure(['SECRET_CANARY'])),'UNCLASSIFIED_SERVE_ERROR')
    def test_os_and_network_error_messages_not_emitted(self):
        import urllib.error
        for error in (PermissionError(13,'SECRET_CANARY'),urllib.error.URLError('https://secret.invalid/token'),RuntimeError('SECRET_CANARY')):
            trace=demo.ServeTrace();trace.at('OTP_PROBE');trace.capture(error)
            raw=json.dumps(trace.failure)
            self.assertNotIn('SECRET_CANARY',raw);self.assertNotIn('https://',raw);self.assertNotIn('secret.invalid',raw)
            self.assertEqual(trace.failure['operationCode'],'OTP_PROBE')
    def test_natural_exit_recorded_before_shutdown(self):
        trace=demo.ServeTrace();trace.child=Mock();trace.child.poll.return_value=7;trace.at('TUNNEL_STARTUP_WAIT')
        trace.capture(Failure('DEMO_TUNNEL_EXITED'))
        trace.child.poll.return_value=-15;trace.at('PUBLIC_ACCESS_SHUTDOWN');trace.capture(RuntimeError('secret'))
        self.assertEqual(trace.failure['tunnelExitCodeAtFailure'],7)
        self.assertEqual(trace.failure['operationCode'],'TUNNEL_STARTUP_WAIT')
    def test_otp_probe_records_only_status_and_boolean(self):
        trace=demo.ServeTrace();trace.probe_status=503;trace.challenge_match=False;trace.at('OTP_CHALLENGE_VALIDATION')
        trace.capture(Failure('OTP_ACCESS_GATE_UNVERIFIED'))
        self.assertEqual(trace.failure['otpProbeHttpStatus'],503);self.assertFalse(trace.failure['otpChallengeMatched'])
        self.assertFalse(trace.failure['accessOpened'])
    def test_bounded_private_output_classification(self):
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/'private-tunnel.log'
            path.write_bytes(b'flag provided but not defined: SECRET_CANARY https://secret.invalid/token\n'+b'x'*262144)
            trace=demo.ServeTrace();trace.log=path;trace.capture(Failure('DEMO_TUNNEL_EXITED'))
            self.assertEqual(trace.failure['tunnelOutputCategory'],'CLI_ARGUMENT_REJECTED')
            self.assertNotIn('SECRET_CANARY',json.dumps(trace.failure))
    def test_unknown_provider_output_remains_unknown(self):
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/'private-tunnel.log';path.write_text('SECRET_CANARY unknown condition')
            trace=demo.ServeTrace();trace.log=path;trace.capture(RuntimeError('SECRET_CANARY'))
            self.assertEqual(trace.failure['tunnelOutputCategory'],'UNCLASSIFIED_OR_NO_TUNNEL_OUTPUT')
            self.assertEqual(trace.failure['failureCode'],'UNCLASSIFIED_SERVE_ERROR')
    def test_unknown_exception_type_is_not_a_dynamic_output_channel(self):
        error=type('SECRET_CANARY_EXCEPTION',(Exception,),{})('SECRET_CANARY')
        trace=demo.ServeTrace();trace.capture(error)
        self.assertEqual(trace.failure['exceptionType'],'UNCLASSIFIED_EXCEPTION')
    def test_artifact_and_stdout_both_sanitized(self):
        import contextlib,io
        with tempfile.TemporaryDirectory() as d:
            trace=demo.ServeTrace();trace.capture(RuntimeError('SECRET_CANARY'))
            output=io.StringIO()
            with contextlib.redirect_stdout(output):trace.emit(Path(d))
            path=Path(d)/'sanitized-demo-serve.json';self.assertEqual(path.stat().st_mode&0o777,0o600)
            self.assertNotIn('SECRET_CANARY',path.read_text()+output.getvalue())
            value=json.loads(output.getvalue().split('=',1)[1]);self.assertEqual(value,json.loads(path.read_text()))
    def test_artifact_path_added_without_private_logs(self):
        source=(ROOT/'.github/workflows/on-demand-demo.yml').read_text()
        paths=source.split('path: |',1)[1]
        self.assertIn('sanitized-demo-serve.json',paths);self.assertNotIn('private-tunnel.log',paths)
    def test_failed_spawn_is_captured_without_starting_any_process(self):
        from types import SimpleNamespace
        import contextlib,io
        with tempfile.TemporaryDirectory() as d:
            folder=Path(d);root=folder/'source';(root/'deploy').mkdir(parents=True)
            (folder/'secrets').mkdir()
            for n in ('admin_password','merchant_password'):(folder/'secrets'/n).write_text('SECRET_CANARY_PASSWORD')
            (folder/'sanitized-browser.json').write_text(json.dumps(LifecycleTests().report()))
            (folder/'sanitized-browser-final.json').write_text('{"success":true}')
            import time
            (folder/'demo-created.json').write_text(json.dumps({'created':time.time()}))
            (folder/'cloudflared').write_bytes(b'OFFLINE_NON_EXECUTABLE_FIXTURE')
            (root/'deploy/cloudflared-demo.json').write_text(json.dumps({'sha256':hashlib.sha256((folder/'cloudflared').read_bytes()).hexdigest()}))
            output=io.StringIO()
            environment={'DEMO_ALLOWED_EMAIL':'operator@example.test','DEMO_MINUTES':'5','GITHUB_STEP_SUMMARY':str(folder/'summary')}
            with patch.object(demo,'ROOT',root),patch.dict(demo.os.environ,environment),patch.object(demo,'Edge') as edge_mock,patch.object(demo.threading,'Thread'),patch.object(demo.signal,'signal'),patch.object(demo.subprocess,'run',return_value=SimpleNamespace(returncode=0,stdout=b'--allowed-mail')),patch.object(demo.subprocess,'Popen',side_effect=PermissionError(13,'SECRET_CANARY')),contextlib.redirect_stdout(output):
                with self.assertRaises(PermissionError):demo.serve(SimpleNamespace(folder=folder))
                self.assertFalse(edge_mock.return_value.active)
            evidence=json.loads((folder/'sanitized-demo-serve.json').read_text())
            self.assertEqual(evidence['operationCode'],'TUNNEL_SPAWN')
            self.assertEqual(evidence['exceptionType'],'PermissionError');self.assertEqual(evidence['osErrorNumber'],13)
            self.assertEqual(evidence['tunnelProcessState'],'NOT_STARTED');self.assertFalse(evidence['accessOpened'])
            self.assertTrue(json.loads((folder/'public-access-closed.json').read_text())['success'])
            self.assertNotIn('SECRET_CANARY',output.getvalue()+json.dumps(evidence))

if __name__=='__main__':unittest.main()
