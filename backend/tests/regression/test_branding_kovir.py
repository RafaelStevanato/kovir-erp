from __future__ import annotations

import json

from fastapi.testclient import TestClient

from app.main import app
from tests.regression.auth_helpers import get_auth_context

client = TestClient(app)
LEGACY_BRANDING_TOKEN = "Flu" + "xor"


def _assert_no_legacy_branding(payload: object) -> None:
    serialized = json.dumps(payload, ensure_ascii=False)
    assert LEGACY_BRANDING_TOKEN not in serialized
    assert LEGACY_BRANDING_TOKEN.lower() not in serialized.lower()


def test_core_api_responses_use_kovir_branding() -> None:
    auth = get_auth_context(client)

    for path in (
        "/",
        "/system/money-rules",
        "/system/date-rules",
        "/system/id-rules",
        "/system/audit-rules",
        "/system/database-health",
    ):
        response = client.get(path, headers=auth.headers)
        assert response.status_code == 200, response.text
        _assert_no_legacy_branding(response.json())
