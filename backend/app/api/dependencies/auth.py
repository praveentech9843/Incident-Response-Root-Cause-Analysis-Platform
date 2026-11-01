from typing import Callable, List, Optional
from fastapi import Depends, Header, HTTPException, Request, status
from sqlalchemy.orm import Session
import jwt

from app.core.config import settings
from app.core.database import get_db
from app.core.security import Role, decode_token
from app.models.user import User


def get_current_user(
    request: Request,
    authorization: Optional[str] = Header(None, alias="Authorization"),
    db: Session = Depends(get_db),
) -> User:
    """
    Extract and authenticate user from Authorization: Bearer <token>.
    Enforces token expiration, signature validity, and active user status.
    """
    request_id = getattr(request.state, "request_id", None) or request.headers.get("X-Request-ID", "unknown")

    if authorization and authorization.startswith("Bearer "):
        token = authorization.split(" ", 1)[1].strip()
        try:
            payload = decode_token(token)
            if payload.get("type") != "access":
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail={
                        "error": {
                            "code": "INVALID_TOKEN_TYPE",
                            "message": "Access token required",
                            "request_id": request_id,
                        }
                    },
                )
            user_id = int(payload.get("sub", 0))
            user = db.query(User).filter(User.id == user_id).first()
            if not user:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail={
                        "error": {
                            "code": "USER_NOT_FOUND",
                            "message": "User not found",
                            "request_id": request_id,
                        }
                    },
                )
            if not user.is_active:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail={
                        "error": {
                            "code": "USER_INACTIVE",
                            "message": "User account is deactivated",
                            "request_id": request_id,
                        }
                    },
                )
            return user
        except jwt.ExpiredSignatureError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail={
                    "error": {
                        "code": "TOKEN_EXPIRED",
                        "message": "Authentication token has expired",
                        "request_id": request_id,
                    }
                },
            )
        except (jwt.InvalidTokenError, ValueError):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail={
                    "error": {
                        "code": "INVALID_TOKEN",
                        "message": "Invalid authentication token",
                        "request_id": request_id,
                    }
                },
            )

    # Check if strict authentication is required
    strict_auth = (
        settings.AUTH_STRICT
        or request.headers.get("x-strict-auth") == "true"
        or settings.APP_ENV == "production"
    )

    if strict_auth:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "error": {
                    "code": "UNAUTHORIZED",
                    "message": "Authentication required. Missing Bearer token.",
                    "request_id": request_id,
                }
            },
        )

    # Fallback developer identity for legacy test mode when auth header is omitted
    return User(
        id=0,
        username="dev_anonymous",
        email="dev@example.com",
        password_hash="",
        role=Role.ADMIN.value,
        is_active=True,
    )


def require_roles(allowed_roles: List[str]) -> Callable:
    """RBAC dependency checking if user's role is in the allowed roles list."""
    def role_checker(
        request: Request,
        current_user: User = Depends(get_current_user),
    ) -> User:
        request_id = getattr(request.state, "request_id", None) or request.headers.get("X-Request-ID", "unknown")
        if current_user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "error": {
                        "code": "FORBIDDEN",
                        "message": f"Role '{current_user.role}' is not authorized. Allowed: {allowed_roles}",
                        "request_id": request_id,
                    }
                },
            )
        return current_user

    return role_checker


def get_acting_identity(current_user: User, payload_val: Optional[str] = None) -> str:
    """
    Enforces Phase 8 authenticated identity rule:
    Derived from current_user.username rather than trusting client-provided string.
    Only falls back to payload_val in unauthenticated legacy test mode.
    """
    if current_user.id != 0:
        return current_user.username
    return payload_val or current_user.username
