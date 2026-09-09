from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from pydantic import BaseModel

from config import get_settings


security = HTTPBearer(auto_error=False)


class TokenRequest(BaseModel):
    client_id: str
    client_secret: str


class ClientProfile(BaseModel):
    client_id: str
    scopes: list[str]


def _create_access_token(client_id: str, scopes: list[str]) -> str:
    settings = get_settings()

    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(seconds=settings.jwt_expire_seconds)

    payload = {
        "sub": client_id,
        "scopes": scopes,
        "exp": int(expires_at.timestamp()),
    }

    return jwt.encode(
        payload,
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
    )


def authenticate_client(
    client_id: str,
    client_secret: str,
) -> ClientProfile | None:
    settings = get_settings()

    if (
        client_id != settings.auth_client_id
        or client_secret != settings.auth_client_secret
    ):
        return None

    return ClientProfile(
        client_id=client_id,
        scopes=["query", "ingest", "admin"],
    )


async def get_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
) -> ClientProfile:
    # These endpoints must remain reachable without a bearer token.
    # /auth/token is required to obtain the bearer token in the first place.
    if request.url.path in {"/health", "/metrics", "/auth/token"}:
        return ClientProfile(
            client_id="public",
            scopes=[],
        )

    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )

    settings = get_settings()

    try:
        payload: dict[str, Any] = jwt.decode(
            credentials.credentials,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm],
        )

        client_id = payload.get("sub")
        scopes = payload.get("scopes")

        if not isinstance(client_id, str) or not isinstance(scopes, list):
            raise JWTError("Invalid token payload")

        if not all(isinstance(scope, str) for scope in scopes):
            raise JWTError("Invalid scopes")

    except JWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc

    return ClientProfile(
        client_id=client_id,
        scopes=scopes,
    )


def require_scope(scope: str):
    async def scope_dependency(
        current_user: ClientProfile = Depends(get_current_user),
    ) -> ClientProfile:
        if scope not in current_user.scopes:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Missing required scope: {scope}",
            )

        return current_user

    return scope_dependency
