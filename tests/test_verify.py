import time

import jwt

from tests.conftest import new_key


def auth(token):
    return {"Authorization": f"Bearer {token}"}


def test_valid_token_returns_identity(client, make_token):
    response = client.get("/auth/verify", headers=auth(make_token()))
    assert response.status_code == 200
    body = response.json()
    assert body["sub"] == "6"
    assert body["preferred_username"] == "akadmin"
    assert body["email"] == "user@example.com"


def test_missing_header_is_401(client):
    response = client.get("/auth/verify")
    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"


def test_garbage_token_is_401(client):
    assert client.get("/auth/verify", headers=auth("not-a-jwt")).status_code == 401


def test_expired_token_is_401(client, make_token):
    token = make_token(exp=int(time.time()) - 10)
    assert client.get("/auth/verify", headers=auth(token)).status_code == 401


def test_wrong_signature_is_401(client, make_token):
    # Signed with a key that is not Authentik's
    token = make_token(key=new_key())
    assert client.get("/auth/verify", headers=auth(token)).status_code == 401


def test_wrong_audience_is_401(client, make_token):
    token = make_token(aud="another-client")
    assert client.get("/auth/verify", headers=auth(token)).status_code == 401


def test_wrong_issuer_is_401(client, make_token):
    token = make_token(iss="http://evil.example/")
    assert client.get("/auth/verify", headers=auth(token)).status_code == 401


def test_missing_sub_is_401(client, make_token):
    token = make_token(sub=None)
    assert client.get("/auth/verify", headers=auth(token)).status_code == 401


def test_unsigned_token_is_401(client):
    # alg "none" must never be accepted
    token = jwt.encode(
        {"sub": "6", "iss": "x", "aud": "grocery-sso", "exp": int(time.time()) + 60},
        key=None,
        algorithm="none",
    )
    assert client.get("/auth/verify", headers=auth(token)).status_code == 401


def test_hs256_token_is_401(client, make_token):
    # Algorithm-confusion attempt: HMAC token signed with a made-up secret
    token = make_token(key="a-very-long-shared-secret-for-testing-0123456789", algorithm="HS256")
    assert client.get("/auth/verify", headers=auth(token)).status_code == 401


def test_health(client):
    assert client.get("/health").json() == {"status": "ok"}
