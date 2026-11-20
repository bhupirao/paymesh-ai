"""Offline policy tests of the parsed image workflow; no Docker or network calls."""
import json
from pathlib import Path
import subprocess
import unittest
ROOT=Path(__file__).resolve().parents[1]

def input_value(value,publish):
    if value=='${{ inputs.publish_images }}':return publish
    if value=='${{ !inputs.publish_images }}':return not publish
    if value=="${{ inputs.publish_images && 'mode=min' || 'false' }}":return 'mode=min' if publish else False
    if value in ('false','true'):return value=='true'
    return value

class ImageWorkflowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # The existing local offline YAML tool; GitHub's ubuntu-24.04 runner has Ruby.
        raw=subprocess.check_output(['ruby','-rjson','-ryaml','-e','puts JSON.generate(YAML.load_file(ARGV[0]))',str(ROOT/'.github/workflows/container-images.yml')])
        cls.workflow=json.loads(raw);cls.job=cls.workflow['jobs']['images']
        cls.steps=cls.job['steps'];cls.build=next(s for s in cls.steps if s.get('uses','').startswith('docker/build-push-action@'))
    def test_build_only_exporter_contract_all_components(self):
        for component in self.job['strategy']['matrix']['image']:
            with self.subTest(component=component):
                values={k:input_value(v,False) for k,v in self.build['with'].items()}
                self.assertEqual(values['platforms'],'linux/amd64')
                self.assertIs(values['load'],True)
                self.assertIs(values['push'],False)
                self.assertIs(values['provenance'],False)
                self.assertIs(values['sbom'],False)
                self.assertNotIn('attests',values)
                self.assertNotIn('outputs',values) # no conflicting extra exporter
    def test_publishing_retains_registry_provenance_without_local_load(self):
        values={k:input_value(v,True) for k,v in self.build['with'].items()}
        self.assertIs(values['load'],False);self.assertIs(values['push'],True)
        self.assertEqual(values['provenance'],'mode=min')
    def test_no_component_dropped(self):self.assertEqual(self.job['strategy']['matrix']['image'],['java','python','frontend','llama'])
    def test_no_registry_auth_for_build_only(self):
        login=next(s for s in self.steps if s.get('uses','').startswith('docker/login-action@'))
        self.assertEqual(login['if'],'inputs.publish_images')
    def test_manual_publish_defaults_off(self):
        event=self.workflow.get('on',self.workflow.get('true'))
        inputs=event['workflow_dispatch']['inputs']
        self.assertIs(inputs['publish_images']['default'],False)
        self.assertIs(inputs['disposable_e2e_verified']['default'],False)
        self.assertEqual(set(event),{'workflow_dispatch'})
    def test_capacity_and_authorization_gates_unchanged(self):
        self.assertEqual(self.workflow['permissions'],{'contents':'read','actions':'read'})
        self.assertEqual(self.job['strategy']['max-parallel'],1)
        self.assertIn('dockerhub-publication',self.job['environment'])
        gate=next(s['run'] for s in self.workflow['jobs']['validate']['steps'] if s.get('name')=='Validate destinations and publishing gate')
        self.assertIn("os.environ['PUBLISH'] != 'true' or os.environ['E2E'] == 'true'",gate)
    def test_current_node24_actions(self):
        actions=[s.get('uses') for j in self.workflow['jobs'].values() for s in j['steps'] if s.get('uses')]
        self.assertEqual(set(actions),{'actions/checkout@v6','docker/setup-buildx-action@v4','docker/login-action@v4','docker/build-push-action@v7'})
    def test_loaded_image_architecture_verified_on_runner(self):
        step=next(s for s in self.steps if s.get('name')=='Verify locally loaded image architecture')
        self.assertEqual(step['if'],'${{ !inputs.publish_images }}')
        self.assertIn('docker image inspect',step['run']);self.assertIn('amd64',step['run'])
if __name__=='__main__':unittest.main()
