"""Fresh forward-release Python launch specification. No action on import."""
from pathlib import Path
from phase673_otp_ops import Stop

def python_spec(release, saved, sink, enabled):
    release=Path(release)
    if saved.argv[1:]!=('-m','uvicorn','app.main:app','--host','127.0.0.1','--port','8000','--no-access-log'):
        raise Stop('Python command differs from reviewed launch.')
    if any(saved.environment.get(k) for k in ('PYTHONPATH','PYTHONHOME')):
        raise Stop('Unexpected Python import override.')
    env=dict(saved.environment)
    executable=str(release/'python/.venv/bin/python')
    env.update(PYTHONDONTWRITEBYTECODE='1',__PYVENV_LAUNCHER__=executable,
               PAYMESH_AI_CHAT_API_ENABLED='true' if enabled else 'false',
               PAYMESH_AI_CHAT_VALIDATION_DIAGNOSTICS_FILE=str(sink))
    return [executable,*saved.argv[1:]],release/'python',env
