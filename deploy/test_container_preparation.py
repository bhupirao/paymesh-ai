import importlib.util
import sys
import unittest
from email.message import Message
from pathlib import Path
from unittest.mock import patch
HERE=Path(__file__).resolve().parent
sys.path[:0]=[str(HERE),str(HERE.parent/'frontend')]
from frontend_entry import ContainerHandler
from check_publication import findings
class PreparationTests(unittest.TestCase):
    def handler(self,origin=None):
        obj=object.__new__(ContainerHandler);obj.headers=Message()
        if origin:obj.headers['Origin']=origin
        obj.error=lambda code,text:code
        return obj
    def test_origin_fixed_translation(self):
        obj=self.handler('http://127.0.0.1:15500')
        with patch('frontend_entry.Handler.proxy',lambda s,p,n:s.headers['Origin']):
            self.assertEqual(obj.proxy('/api/v1/auth/login',0),'http://127.0.0.1:5500')
        self.assertEqual(obj.headers['Origin'],'http://127.0.0.1:15500')
    def test_hostile_origin_not_forwarded(self):
        with patch('frontend_entry.Handler.proxy') as proxy:
            self.assertEqual(self.handler('https://evil.example').proxy('/api/v1/auth/login',0),403);proxy.assert_not_called()
    def test_duplicate_origin_rejected(self):
        obj=self.handler('http://127.0.0.1:15500');obj.headers['Origin']='http://127.0.0.1:15500'
        self.assertEqual(obj.proxy('/api/v1/auth/login',0),403)
    def test_no_origin_not_invented(self):
        with patch('frontend_entry.Handler.proxy',lambda s,p,n:s.headers.get('Origin')):
            self.assertIsNone(self.handler().proxy('/api/v1/auth/refresh',0))
    def test_exception_restores_origin(self):
        obj=self.handler('http://127.0.0.1:15500')
        with patch('frontend_entry.Handler.proxy',side_effect=RuntimeError):
            with self.assertRaises(RuntimeError):obj.proxy('/api/v1/auth/login',0)
        self.assertEqual(obj.headers['Origin'],'http://127.0.0.1:15500')
    def test_no_access_logging(self):self.assertIsNone(self.handler().log_message('private-url'))
    def test_model_excluded(self):self.assertIn('PRIVATE_OR_LARGE_ARTIFACT',findings(Path('model.gguf'),b''))
    def test_large_file(self):self.assertIn('OVER_10_MIB',findings(Path('large'),b'x'*(10*1024*1024+1)))
    def test_private_key(self):self.assertIn('PRIVATE_KEY_PATTERN',findings(Path('file'),b'-----BEGIN PRIVATE KEY-----'))
    def test_env(self):self.assertIn('ENVIRONMENT_FILE',findings(Path('.env.local'),b''))
    def test_generated(self):self.assertIn('GENERATED_DIRECTORY',findings(Path('app/.venv/lib.py'),b''))
    def test_example_allowed(self):self.assertFalse(findings(Path('.env.example'),b'KEY=replace_me'))
if __name__=='__main__':unittest.main()
