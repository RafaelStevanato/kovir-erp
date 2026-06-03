from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app
from app.modules.security.service import INTERNAL_APP_VIEWS, V1_APP_VIEWS
from tests.regression.auth_helpers import get_auth_context

client = TestClient(app)


def test_login_exposes_only_v1_views_by_default() -> None:
    auth = get_auth_context(client)

    response = client.get("/auth/me", headers=auth.headers)

    assert response.status_code == 200, response.text
    allowed_views = set(response.json()["data"]["allowed_views"])
    assert set(V1_APP_VIEWS).issubset(allowed_views)
    assert allowed_views.isdisjoint(INTERNAL_APP_VIEWS)


def test_allowed_views_catalog_hides_internal_modules_by_default() -> None:
    auth = get_auth_context(client)

    response = client.get("/security/allowed-views", headers=auth.headers)

    assert response.status_code == 200, response.text
    catalog_views = {item["view"] for item in response.json()["data"]}
    assert set(V1_APP_VIEWS).issubset(catalog_views)
    assert catalog_views.isdisjoint(INTERNAL_APP_VIEWS)


def test_internal_routes_are_not_exposed_by_default() -> None:
    auth = get_auth_context(client)
    internal_paths = [
        "/bi/rules",
        "/marketplaces/rules",
        "/mercado-pago/rules",
        "/technical-regression/rules",
        "/stress-tests/rules",
        "/demo/safety-rules",
    ]

    for path in internal_paths:
        response = client.get(path, headers=auth.headers)
        assert response.status_code == 404, path
        assert response.json()["detail"] == "Modulo interno indisponivel."
