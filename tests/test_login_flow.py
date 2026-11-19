from urllib.parse import parse_qs, urlparse

import httpx
from fastapi.testclient import TestClient

from app.main import create_app


def start_login(client):
    """Call /auth/login and return the state sent to Authentik."""
    response = client.get("/auth/login", follow_redirects=False)
    assert response.status_code == 307
    return response, parse_qs(urlparse(response.headers["location"]).query)


def client_with_token_endpoint(settings, validator, handler):
    # MockTransport replaces the real HTTP call to Authentik's token endpoint
    http = httpx.Client(transport=httpx.MockTransport(handler))
    return TestClient(
        create_app(settings=settings, validator=validator, http_client=http)
    )


def test_login_redirects_to_authentik(client, settings):
    response, query = start_login(client)
    assert response.headers["location"].startswith(settings.authorize_url)
    assert query["client_id"] == [settings.client_id]
    assert query["redirect_uri"] == [settings.redirect_uri]
    assert query["scope"] == ["openid profile email"]
    assert query["code_challenge_method"] == ["S256"]
    assert "state" in query and "code_challenge" in query


def test_callback_rejects_unknown_state(client):
    response = client.get("/auth/callback", params={"code": "abc", "state": "forged"})
    assert response.status_code == 400


def test_callback_rejects_missing_code(client):
    _, query = start_login(client)
    response = client.get("/auth/callback", params={"state": query["state"][0]})
    assert response.status_code == 400


def test_callback_reports_login_error(client):
    response = client.get("/auth/callback", params={"error": "access_denied"})
    assert response.status_code == 400


def test_callback_success_returns_tokens(settings, validator, make_token):
    id_token = make_token()
    seen = {}

    def handler(request):
        seen["body"] = parse_qs(request.content.decode())
        return httpx.Response(
            200,
            json={
                "access_token": "access-123",
                "id_token": id_token,
                "token_type": "Bearer",
                "expires_in": 3600,
            },
        )

    client = client_with_token_endpoint(settings, validator, handler)
    _, query = start_login(client)
    response = client.get(
        "/auth/callback", params={"code": "abc", "state": query["state"][0]}
    )

    assert response.status_code == 200
    assert response.json()["access_token"] == "access-123"
    # The server-side exchange must carry the secret and the PKCE verifier
    assert seen["body"]["client_secret"] == ["test-secret"]
    assert "code_verifier" in seen["body"]


def test_callback_redirects_to_frontend_with_tokens_in_fragment(
    settings, validator, make_token
):
    from dataclasses import replace

    id_token = make_token()

    def handler(request):
        return httpx.Response(
            200,
            json={"access_token": "access-123", "id_token": id_token, "token_type": "Bearer", "expires_in": 3600},
        )

    with_frontend = replace(settings, frontend_url="http://localhost:3000/")
    client = client_with_token_endpoint(with_frontend, validator, handler)
    _, query = start_login(client)
    response = client.get(
        "/auth/callback",
        params={"code": "abc", "state": query["state"][0]},
        follow_redirects=False,
    )

    assert response.status_code == 302
    location = urlparse(response.headers["location"])
    assert location.netloc == "localhost:3000"
    # Tokens are in the fragment, never in the query string
    assert location.query == ""
    fragment = parse_qs(location.fragment)
    assert fragment["access_token"] == ["access-123"]
    assert fragment["id_token"] == [id_token]
    assert fragment["expires_in"] == ["3600"]


def test_state_can_be_used_only_once(settings, validator, make_token):
    id_token = make_token()

    def handler(request):
        return httpx.Response(
            200,
            json={"access_token": "a", "id_token": id_token, "token_type": "Bearer", "expires_in": 1},
        )

    client = client_with_token_endpoint(settings, validator, handler)
    _, query = start_login(client)
    params = {"code": "abc", "state": query["state"][0]}
    assert client.get("/auth/callback", params=params).status_code == 200
    assert client.get("/auth/callback", params=params).status_code == 400


def test_callback_fails_if_authentik_rejects_code(settings, validator):
    client = client_with_token_endpoint(
        settings, validator, lambda request: httpx.Response(400, json={"error": "invalid_grant"})
    )
    _, query = start_login(client)
    response = client.get(
        "/auth/callback", params={"code": "bad", "state": query["state"][0]}
    )
    assert response.status_code == 502


def test_callback_rejects_forged_id_token(settings, validator, make_token):
    from tests.conftest import new_key

    forged = make_token(key=new_key())
    client = client_with_token_endpoint(
        settings,
        validator,
        lambda request: httpx.Response(
            200,
            json={"access_token": "a", "id_token": forged, "token_type": "Bearer", "expires_in": 1},
        ),
    )
    _, query = start_login(client)
    response = client.get(
        "/auth/callback", params={"code": "abc", "state": query["state"][0]}
    )
    assert response.status_code == 502
