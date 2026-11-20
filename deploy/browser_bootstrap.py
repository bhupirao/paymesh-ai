"""Hosted-runner browser fixture bootstrap only. Never calls login/chat APIs."""
import json
import os
from pathlib import Path
import sys
from container_e2e import require
from release_artifact_e2e import ReleaseSuite


def main(action):
    suite = ReleaseSuite()  # Reuses the published-image and hosted-runner guards.
    if action == 'seed':
        suite.check('browser_image_identity', suite.identity)
        suite.check('browser_empty_database_seed', suite.seed)
        report = {'success': True, 'publishedImagesVerified': True, 'freshV14Verified': True,
                  'adminBootstrapOnly': True, 'applicationImagesBuilt': False}
        with os.fdopen(os.open(suite.folder/'sanitized-browser-bootstrap.json', os.O_CREAT | os.O_EXCL | os.O_WRONLY | os.O_NOFOLLOW, 0o600), 'w') as output:
            output.write(json.dumps(report, indent=2)+'\n')
        print('BROWSER_ADMIN_BOOTSTRAP_ONLY_PASS')
        return 0
    if action == 'final':
        counts = json.loads(suite.sql("SELECT json_build_object('users',(SELECT count(*) FROM app_users),'payments',(SELECT count(*) FROM payments),'refunds',(SELECT count(*) FROM refunds),'links',(SELECT count(*) FROM payment_links),'attempts',(SELECT count(*) FROM checkout_attempts),'conversations',(SELECT count(*) FROM ai_conversations));"))
        require(counts == {'users': 3, 'payments': 2, 'refunds': 2, 'links': 1, 'attempts': 1, 'conversations': 0}, 'BROWSER_FINAL_FIXTURE_COUNTS')
        with os.fdopen(os.open(suite.folder/'sanitized-browser-final.json', os.O_CREAT | os.O_EXCL | os.O_WRONLY | os.O_NOFOLLOW, 0o600), 'w') as output:
            output.write(json.dumps({'success': True, 'counts': counts}, indent=2)+'\n')
        print('BROWSER_FINAL_FIXTURE_COUNTS_PASS')
        return 0
    require(False, 'UNKNOWN_BROWSER_BOOTSTRAP_ACTION')


if __name__ == '__main__':
    try:
        raise SystemExit(main(sys.argv[1] if len(sys.argv) == 2 else ''))
    except Exception:
        print('BROWSER_BOOTSTRAP_OR_FINAL_CHECK_FAILED_NO_RAW_OUTPUT')
        raise SystemExit(1)
