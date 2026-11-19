import jwt
from jwt import PyJWKClient

from app.config import Settings


class InvalidToken(Exception):
    """The token is malformed, expired, badly signed or not meant for us."""


class KeysUnavailable(Exception):
    """The signing keys could not be fetched from Authentik."""


class TokenValidator:
    def __init__(self, settings: Settings, jwk_client=None):
        self._settings = settings
        # PyJWKClient downloads the public keys and caches them
        self._jwk_client = jwk_client or PyJWKClient(settings.jwks_url)

    def validate(self, token: str) -> dict:
        try:
            key = self._jwk_client.get_signing_key_from_jwt(token).key
            return jwt.decode(
                token,
                key,
                # Only RS256: never trust the algorithm declared in the token
                algorithms=["RS256"],
                audience=self._settings.client_id,
                issuer=self._settings.issuer,
                # Reject tokens that lack any of these claims
                options={"require": ["exp", "iss", "aud", "sub"]},
            )
        except jwt.PyJWKClientConnectionError as exc:
            raise KeysUnavailable(str(exc)) from exc
        except jwt.PyJWTError as exc:
            raise InvalidToken(str(exc)) from exc
