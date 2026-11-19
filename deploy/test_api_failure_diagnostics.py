"""Offline request metadata tests: synthetic responses only, no live services."""
import io,json,subprocess,unittest,urllib.error
from email.message import Message
from pathlib import Path
from unittest.mock import Mock,MagicMock
import container_e2e as e

class ApiFailureTests(unittest.TestCase):
    def session(self,status=200,body=None,cookie=False):
        session=e.Session('ADMIN');headers=Message()
        if cookie:headers['Set-Cookie']='pm_refresh=SYNTHETIC_SECRET; Path=/api/v1/auth; HttpOnly; SameSite=Strict'
        raw=json.dumps(body or {}).encode()
        if status>=400:session.client.open=Mock(side_effect=urllib.error.HTTPError(e.BASE, status,'omitted',headers,io.BytesIO(raw)))
        else:
            response=Mock(status=status,headers=headers);response.read.return_value=raw
            session.client.open=MagicMock();session.client.open.return_value.__enter__.return_value=response
        return session
    def test_wrong_login_status_records_exact_request_and_fixed_error(self):
        s=self.session(401,{'message':'Authentication failed'})
        with self.assertRaisesRegex(e.Failure,'UNEXPECTED_HTTP_STATUS_401'):s.login('private-login','private-password')
        self.assertEqual(s.last_request['endpoint'],'/api/v1/auth/login');self.assertEqual(s.last_request['actualStatus'],401)
        self.assertEqual(s.last_request['expectedStatuses'],[200]);self.assertEqual(s.last_request['responseErrorCode'],'AUTHENTICATION_FAILED')
        self.assertEqual(s.last_request['actor'],'ADMIN');self.assertFalse(s.last_request['bearerAttached']);s.client.open.assert_called_once()
        self.assertNotIn('private-',json.dumps(s.last_request))
    def test_unknown_error_values_and_field_names_never_retained(self):
        s=self.session(403,{'message':'SYNTHETIC_SECRET','SYNTHETIC_SECRET':'private'})
        with self.assertRaises(e.Failure):s.call('GET','/api/v1/admin/profile')
        self.assertNotIn('SYNTHETIC_SECRET',json.dumps(s.last_request));self.assertEqual(s.last_request['responseErrorCode'],'UNRECOGNIZED_ERROR_TEXT_OMITTED')
    def test_missing_login_token_retains_safe_shape(self):
        s=self.session(body={'roles':['SYNTHETIC_SECRET']})
        with self.assertRaisesRegex(e.Failure,'LOGIN_TOKEN_MISSING'):s.login('private','private')
        self.assertFalse(s.last_request['accessTokenPresent']);self.assertEqual(s.last_request['responseFields'],['roles'])
    def test_missing_cookie_retains_only_boolean_header_and_jar_state(self):
        s=self.session(body={'accessToken':'SYNTHETIC_SECRET'},cookie=True)
        with self.assertRaisesRegex(e.Failure,'HTTPONLY_REFRESH_COOKIE_MISSING'):s.login('private','private')
        self.assertTrue(s.last_request['refreshCookieHeaderPresent']);self.assertTrue(s.last_request['refreshCookieHeaderHttpOnly']);self.assertFalse(s.last_request['refreshCookieStored'])
        self.assertNotIn('SYNTHETIC_SECRET',json.dumps(s.last_request))
    def test_unknown_paths_queries_and_checkout_tokens_omitted(self):
        self.assertEqual(e.safe_endpoint('/api/v1/admin/merchants?search=private@example.invalid'),'/api/v1/admin/merchants')
        self.assertEqual(e.safe_endpoint('/api/v1/checkout/'+'a'*43+'/pay'),'/api/v1/checkout/{checkoutToken}/pay')
        self.assertEqual(e.safe_endpoint('/api/v1/payments/11111111-1111-1111-1111-111111111111'),'/api/v1/payments/{resourceId}')
        self.assertEqual(e.safe_endpoint('/api/v1/private-value'),'UNRECOGNIZED_ROUTE_OMITTED')
    def test_non_json_and_non_object_never_retained(self):
        self.assertEqual(e.response_metadata(b'PRIVATE',502)['responseShape'],'NON_JSON')
        self.assertEqual(e.response_metadata(b'["PRIVATE"]',200)['responseShape'],'NON_OBJECT')
    def test_observer_receives_snapshot_and_stage_resets_it(self):
        suite=object.__new__(e.Suite);suite.passed=[];suite.last_request={'old':True}
        suite.check('synthetic',lambda:self.assertIsNone(suite.last_request))
        s=self.session();s.observer=suite.observe_request;s.call('GET','/api/v1/admin/profile');s.last_request['actor']='changed'
        self.assertEqual(suite.last_request['actor'],'ADMIN')
    def test_invalid_actor_rejected(self):
        with self.assertRaises(e.Failure):e.Session('private-data')
    def test_failure_artifact_is_narrow_and_precedes_cleanup(self):
        root=Path(__file__).resolve().parents[1]
        steps=json.loads(subprocess.check_output(['ruby','-rjson','-ryaml','-e','puts JSON.generate(YAML.load_file(ARGV[0]))',str(root/'.github/workflows/container-e2e.yml')]))['jobs']['e2e']['steps']
        api=next(s for s in steps if s.get('id')=='api_e2e');upload=next(s for s in steps if s.get('name')=='Retain sanitized API failure metadata');cleanup=next(s for s in steps if s.get('name','').startswith('Stop only'))
        self.assertLess(steps.index(api),steps.index(upload));self.assertLess(steps.index(upload),steps.index(cleanup))
        self.assertEqual(upload['if'],"${{ failure() && steps.api_e2e.outcome == 'failure' }}")
        self.assertEqual(upload['with']['path'],'${{ env.E2E_DIR }}/sanitized-e2e.json');self.assertEqual(upload['with']['retention-days'],3)

if __name__=='__main__':unittest.main()
