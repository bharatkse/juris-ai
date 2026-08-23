"""
Authentication.
"""

from __future__ import annotations

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.dependencies.user import get_user_repository
from src.db.session import get_db_session
from src.repositories.user import UserRepository
from src.security.jwt import decode_token, get_subject, is_token_type
from src.security.password import PasswordService
from src.services.auth import AuthenticationService

oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl="/auth/login",
)


async def get_current_user(
    token: str = Depends(oauth2_scheme),
    user_repository: UserRepository = Depends(
        get_user_repository,
    ),
):
    """
    Resolve the currently authenticated user from the access token.
    """

    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={
            "WWW-Authenticate": "Bearer",
        },
    )

    try:
        payload = decode_token(token)

        if not is_token_type(
            payload,
            "access",
        ):
            raise credentials_exception

        user_id = get_subject(payload)

        if not user_id:
            raise credentials_exception

    except JWTError:
        raise credentials_exception from None

    user = await user_repository.get(
        user_id,
    )

    if user is None:
        raise credentials_exception

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is inactive",
        )

    return user


def get_password_service() -> PasswordService:
    """
    Create a password service.
    """

    return PasswordService()


def get_authentication_service(
    db: AsyncSession = Depends(get_db_session),
    password_service=Depends(
        get_password_service,
    ),
) -> AuthenticationService:
    """
    Build authentication service.
    """

    user_repository = UserRepository(
        session=db,
    )

    return AuthenticationService(
        password_service=password_service,
        user_repository=user_repository,
    )
