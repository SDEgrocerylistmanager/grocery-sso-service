import os
from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class Settings:
    # Expected "iss" claim in the tokens (the public Authentik URL)
    issuer: str
    client_id: str
    client_secret: str
    redirect_uri: str
    # Browser-facing URL: the user is redirected here to log in
    authorize_url: str
    # Server-to-server URLs: inside Docker these point to authentik-server
    token_url: str
    jwks_url: str
    # Where to send the user after login; if None the callback returns JSON
    frontend_url: Optional[str] = None


def load_settings() -> Settings:
    # The client secret has no default: fail fast if it is missing
    secret = os.environ.get("OIDC_CLIENT_SECRET")
    if not secret:
        raise RuntimeError("OIDC_CLIENT_SECRET is not set")

    base = os.environ.get("OIDC_BASE_URL", "http://localhost:9000")
    return Settings(
        issuer=os.environ.get("OIDC_ISSUER", f"{base}/application/o/grocery/"),
        client_id=os.environ.get("OIDC_CLIENT_ID", "grocery-sso"),
        client_secret=secret,
        redirect_uri=os.environ.get(
            "OIDC_REDIRECT_URI", "http://localhost:8002/auth/callback"
        ),
        authorize_url=os.environ.get(
            "OIDC_AUTHORIZE_URL", f"{base}/application/o/authorize/"
        ),
        token_url=os.environ.get("OIDC_TOKEN_URL", f"{base}/application/o/token/"),
        jwks_url=os.environ.get(
            "OIDC_JWKS_URL", f"{base}/application/o/grocery/jwks/"
        ),
        frontend_url=os.environ.get("FRONTEND_URL") or None,
    )
