import json
import os
import subprocess
import sys

import pytest
from pydantic import ValidationError

from app.core.config import Settings


def test_legacy_integrations_cannot_be_enabled_in_release_environments():
    for environment in ("staging", "production"):
        with pytest.raises(ValidationError, match="Legacy intake integrations"):
            Settings(_env_file=None, app_env=environment, enable_legacy_integrations=True)


def test_default_application_has_internal_demand_and_no_legacy_route_registration():
    script = """
import json
from fastapi.testclient import TestClient
from app.main import app
client = TestClient(app)
paths = list(app.openapi()['paths'])
for path in (
    '/api/v1/employer-intake',
    '/api/v1/integrations/employer-portal/submissions',
    '/api/v1/integrations/hamis/events',
):
    assert client.get(path).status_code == 404
print(json.dumps(paths))
"""
    result = subprocess.run(
        [sys.executable, "-c", script],
        env={**os.environ, "APP_ENV": "test", "ENABLE_LEGACY_INTEGRATIONS": "false"},
        capture_output=True,
        text=True,
        check=True,
    )
    paths = json.loads(result.stdout)
    assert "/api/v1/participant-intake" in paths
    assert "/api/v1/organizations" in paths
    assert "/api/v1/vacancies" in paths
    assert not any(
        "employer-intake" in path or "employer-portal" in path or "/hamis/" in path
        for path in paths
    )
