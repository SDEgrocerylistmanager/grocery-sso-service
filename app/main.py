import base64
import hashlib
import secrets
from typing import Optional
from urllib.parse import urlencode

import httpx
from fastapi import Depends, FastAPI, HTTPException, Query, Request
from fastapi.responses import RedirectResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.config import Settings, load_settings
from app.schemas import ErrorResponse, TokenResponse, UserInfo
from app.state_store import StateStore
from app.token_validator import InvalidToken, KeysUnavailable, TokenValidator

# auto_error=False lets us answer 401 (not 403) when the header is missing
bearer_scheme = HTTPBearer(auto_error=False)


def _unauthorized(message: str) -> HTTPException:
    return HTTPException(
        status_code=401,
        detail=message,
        headers={"WWW-Authenticate": "Bearer"},
    )


def create_app(
    settings: Optional[Settings] = None,
    validator: Optional[TokenValidator] = None,
    http_client: Optional[httpx.Client] = None,
) -> FastAPI:
    # Dependencies can be injected, which keeps the tests independent from Authentik
    settings = settings or load_settings()
    validator = validator or TokenValidator(settings)
    http_client = http_client or httpx.Client(timeout=10)
    states = StateStore()

    app = FastAPI(
        title="Grocery SSO Service",
        version="1.0.0",
        description="Process-centric service handling the OAuth 2.0 / OIDC "
        "login flow with Authentik and JWT validation.",
    )

    @app.get("/health", tags=["system"], summary="Liveness probe")
    def health():
        return {"status": "ok"}

    @app.get(
        "/auth/login",
        tags=["auth"],
        summary="Start the login: redirect the browser to Authentik",
        status_code=307,
        responses={307: {"description": "Redirect to the Authentik login page"}},
    )
    def login():
        # state protects against CSRF, PKCE protects the authorization code
        state = secrets.token_urlsafe(32)
        verifier = secrets.token_urlsafe(64)
        challenge = (
            base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest())
            .rstrip(b"=")
            .decode()
        )
        states.save(state, verifier)
        query = urlencode(
            {
                "response_type": "code",
                "client_id": settings.client_id,
                "redirect_uri": settings.redirect_uri,
                "scope": "openid profile email",
                "state": state,
                "code_challenge": challenge,
                "code_challenge_method": "S256",
            }
        )
        return RedirectResponse(f"{settings.authorize_url}?{query}", status_code=307)

    @app.get(
        "/auth/callback",
        tags=["auth"],
        summary="Receive the authorization code and exchange it for tokens",
        response_model=TokenResponse,
        responses={
            302: {
                "description": "If FRONTEND_URL is set: redirect to the frontend "
                "with access_token, id_token, token_type and expires_in in the URL fragment"
            },
            400: {"model": ErrorResponse, "description": "Invalid state or login error"},
            502: {"model": ErrorResponse, "description": "Authentik rejected the exchange"},
        },
    )
    def callback(
        code: Optional[str] = Query(None),
        state: Optional[str] = Query(None),
        error: Optional[str] = Query(None),
    ):
        if error:
            raise HTTPException(status_code=400, detail=f"Login failed: {error}")
        # The state must be one we issued, and it can be used only once
        verifier = states.pop(state) if state else None
        if not code or verifier is None:
            raise HTTPException(status_code=400, detail="Invalid or expired state")

        try:
            response = http_client.post(
                settings.token_url,
                data={
                    "grant_type": "authorization_code",
                    "code": code,
                    "redirect_uri": settings.redirect_uri,
                    "client_id": settings.client_id,
                    "client_secret": settings.client_secret,
                    "code_verifier": verifier,
                },
            )
        except httpx.HTTPError:
            raise HTTPException(status_code=502, detail="Authentik is unreachable")
        if response.status_code != 200:
            raise HTTPException(status_code=502, detail="Code exchange rejected")

        tokens = response.json()
        # Never hand out an id_token we did not verify ourselves
        try:
            validator.validate(tokens["id_token"])
        except KeyError:
            raise HTTPException(status_code=502, detail="Missing id_token")
        except InvalidToken:
            raise HTTPException(status_code=502, detail="Invalid id_token")
        except KeysUnavailable:
            raise HTTPException(status_code=502, detail="Signing keys unavailable")

        result = TokenResponse(
            access_token=tokens["access_token"],
            id_token=tokens["id_token"],
            token_type=tokens.get("token_type", "Bearer"),
            expires_in=tokens.get("expires_in", 0),
        )
        if settings.frontend_url:
            # Tokens go in the URL fragment: browsers never send it to servers
            # or write it in logs. The frontend reads it and keeps it in memory.
            fragment = urlencode(result.model_dump())
            return RedirectResponse(
                f"{settings.frontend_url}#{fragment}", status_code=302
            )
        return result

    @app.get(
        "/auth/verify",
        tags=["auth"],
        summary="Validate a Bearer JWT and return the user identity",
        response_model=UserInfo,
        responses={
            401: {"model": ErrorResponse, "description": "Missing or invalid token"},
            503: {"model": ErrorResponse, "description": "Signing keys unavailable"},
        },
    )
    def verify(
        credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
    ):
        if credentials is None:
            raise _unauthorized("Missing bearer token")
        try:
            claims = validator.validate(credentials.credentials)
        except InvalidToken:
            raise _unauthorized("Invalid or expired token")
        except KeysUnavailable:
            raise HTTPException(status_code=503, detail="Signing keys unavailable")
        return UserInfo(
            sub=str(claims["sub"]),
            preferred_username=claims.get("preferred_username"),
            email=claims.get("email"),
            exp=claims["exp"],
        )

    return app
