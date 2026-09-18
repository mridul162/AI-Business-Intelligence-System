from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request, status

from api.security.authentication import AuthenticationService
from api.security.errors import AuthenticationError
from api.security.schemas import LoginRequest, TokenResponse

router = APIRouter(prefix="/auth", tags=["authentication"])


@router.post("/token", response_model=TokenResponse)
def issue_token(request: Request, credentials: LoginRequest) -> TokenResponse:
    service: AuthenticationService = request.app.state.auth_service
    try:
        user = service.authenticate(credentials.email, credentials.password)
    except AuthenticationError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials.",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc

    token = request.app.state.token_service.create_access_token(
        user,
        request.app.state.jwt_expire_minutes,
    )
    return TokenResponse(access_token=token)