"""Private container entry: secret file to process environment, never argv/logs."""
import os
from pathlib import Path

def main():
    token = Path('/run/secrets/ai_token').read_text().strip()
    import re
    if not re.fullmatch(r'[A-Za-z0-9_-]{64,128}', token):
        raise SystemExit('Invalid container service credential')
    os.environ['PAYMESH_AI_CHAT_SERVICE_TOKEN'] = token
    os.execvp('python', ['python', '-m', 'uvicorn', 'app.main:app', '--host', '127.0.0.1', '--port', '8000', '--no-access-log'])

if __name__ == '__main__':
    main()
