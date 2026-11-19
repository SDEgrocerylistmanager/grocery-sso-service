from typing import Optional

from pydantic import BaseModel


class TokenResponse(BaseModel):
    access_token: str
    id_token: str
    token_type: str
    expires_in: int

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "access_token": "eyJhbGciOiJSUzI1NiIs...",
                    "id_token": "eyJhbGciOiJSUzI1NiIs...",
                    "token_type": "Bearer",
                    "expires_in": 3600,
                }
            ]
        }
    }


class UserInfo(BaseModel):
    sub: str
    preferred_username: Optional[str] = None
    email: Optional[str] = None
    exp: int

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "sub": "6",
                    "preferred_username": "akadmin",
                    "email": "user@example.com",
                    "exp": 1795104043,
                }
            ]
        }
    }


class ErrorResponse(BaseModel):
    detail: str
