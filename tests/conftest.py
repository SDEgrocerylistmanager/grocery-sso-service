import time
from types import SimpleNamespace

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app
from app.token_validator import TokenValidator

ISSUER = "http://localhost:9000/application/o/grocery/"
CLIENT_ID = "grocery-sso"


def new_key():
    return rsa.generate_private_key(public_exponent=65537, key_size=2048)


# One key plays the role of Authentik's signing key
SIGNING_KEY = new_key()


class FakeJwkClient:
    """Stands in for PyJWKClient: always returns our test public key."""

    def get_signing_key_from_jwt(self, token):
        return SimpleNamespace(key=SIGNING_KEY.public_key())


@pytest.fixture
def settings():
    return Settings(
        issuer=ISSUER,
        client_id=CLIENT_ID,
        client_secret="test-secret",
        redirect_uri="http://localhost:8002/auth/callback",
        authorize_url="http://localhost:9000/application/o/authorize/",
        token_url="http://authentik-server:9000/application/o/token/",
        jwks_url="http://authentik-server:9000/application/o/grocery/jwks/",
    )


@pytest.fixture
def validator(settings):
    return TokenValidator(settings, jwk_client=FakeJwkClient())


@pytest.fixture
def make_token():
    def _make(key=None, algorithm="RS256", **overrides):
        now = int(time.time())
        claims = {
            "iss": ISSUER,
            "aud": CLIENT_ID,
            "sub": "6",
            "preferred_username": "akadmin",
            "email": "user@example.com",
            "iat": now,
            "exp": now + 3600,
        }
        claims.update(overrides)
        # A claim set to None means "leave it out"
        claims = {k: v for k, v in claims.items() if v is not None}
        return jwt.encode(claims, key or SIGNING_KEY, algorithm=algorithm)

    return _make


@pytest.fixture
def client(settings, validator):
    return TestClient(create_app(settings=settings, validator=validator))
