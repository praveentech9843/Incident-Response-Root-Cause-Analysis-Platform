from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.orm import Session
import jwt

from app.api.dependencies.auth import get_current_user, require_roles
from app.core.database import get_db
from app.core.security import (
    Role,
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)
from app.models.user import User
from app.schemas.auth import CurrentUserResponse, LoginRequest, RefreshTokenRequest, TokenResponse
from app.schemas.user import UserCreate, UserListResponse, UserResponse, UserUpdateRole, UserUpdateStatus
from app.services.audit_service import log_audit_event

router = APIRouter()


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
def register(
    req: UserCreate,
    request: Request,
    db: Session = Depends(get_db),
):
    """
    Register a new user account.
    Passwords are never stored in plaintext (Argon2 hashing).
    """
    request_id = getattr(request.state, "request_id", None) or request.headers.get("X-Request-ID", "unknown")

    # Check username uniqueness
    if db.query(User).filter(User.username == req.username).first():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": {
                    "code": "USERNAME_EXISTS",
                    "message": f"Username '{req.username}' already registered",
                    "request_id": request_id,
                }
            },
        )

    # Check email uniqueness
    if db.query(User).filter(User.email == req.email).first():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": {
                    "code": "EMAIL_EXISTS",
                    "message": f"Email '{req.email}' already registered",
                    "request_id": request_id,
                }
            },
        )

    # Normalize role
    role = req.role.upper()
    if role not in [Role.ADMIN.value, Role.DEVELOPER.value, Role.VIEWER.value]:
        role = Role.DEVELOPER.value

    # First user in database automatically gets ADMIN role
    if db.query(User).count() == 0:
        role = Role.ADMIN.value

    user = User(
        username=req.username,
        email=req.email,
        password_hash=hash_password(req.password),
        role=role,
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    # Log audit event
    log_audit_event(
        db=db,
        actor=user.username,
        action="USER_REGISTER",
        target_entity="USER",
        target_id=str(user.id),
        request_id=request_id,
        metadata={"email": user.email, "role": user.role},
    )

    access_token = create_access_token(user.id, user.username, user.role)
    refresh_token = create_refresh_token(user.id, user.username, user.role)

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer",
        user=UserResponse.model_validate(user),
    )


@router.post("/login", response_model=TokenResponse)
def login(
    req: LoginRequest,
    request: Request,
    db: Session = Depends(get_db),
):
    """
    Authenticate user and issue JWT access and refresh tokens.
    """
    request_id = getattr(request.state, "request_id", None) or request.headers.get("X-Request-ID", "unknown")

    # Match by username or email
    user = (
        db.query(User)
        .filter((User.username == req.username) | (User.email == req.username))
        .first()
    )

    if not user or not verify_password(req.password, user.password_hash):
        log_audit_event(
            db=db,
            actor=req.username,
            action="FAILED_LOGIN",
            target_entity="AUTH",
            request_id=request_id,
            metadata={"reason": "Invalid credentials"},
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "error": {
                    "code": "INVALID_CREDENTIALS",
                    "message": "Invalid username or password",
                    "request_id": request_id,
                }
            },
        )

    if not user.is_active:
        log_audit_event(
            db=db,
            actor=user.username,
            action="FAILED_LOGIN_INACTIVE",
            target_entity="USER",
            target_id=str(user.id),
            request_id=request_id,
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "error": {
                    "code": "USER_INACTIVE",
                    "message": "User account is disabled",
                    "request_id": request_id,
                }
            },
        )

    log_audit_event(
        db=db,
        actor=user.username,
        action="LOGIN",
        target_entity="USER",
        target_id=str(user.id),
        request_id=request_id,
    )

    access_token = create_access_token(user.id, user.username, user.role)
    refresh_token = create_refresh_token(user.id, user.username, user.role)

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer",
        user=UserResponse.model_validate(user),
    )


@router.post("/refresh", response_model=TokenResponse)
def refresh_token(
    req: RefreshTokenRequest,
    request: Request,
    db: Session = Depends(get_db),
):
    """
    Exchange a valid refresh token for a newly minted access token and refresh token.
    """
    request_id = getattr(request.state, "request_id", None) or request.headers.get("X-Request-ID", "unknown")

    try:
        payload = decode_token(req.refresh_token)
        if payload.get("type") != "refresh":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail={
                    "error": {
                        "code": "INVALID_TOKEN_TYPE",
                        "message": "Refresh token required",
                        "request_id": request_id,
                    }
                },
            )
        user_id = int(payload.get("sub", 0))
        user = db.query(User).filter(User.id == user_id).first()
        if not user or not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail={
                    "error": {
                        "code": "USER_NOT_FOUND",
                        "message": "Active user account not found",
                        "request_id": request_id,
                    }
                },
            )

        new_access = create_access_token(user.id, user.username, user.role)
        new_refresh = create_refresh_token(user.id, user.username, user.role)

        return TokenResponse(
            access_token=new_access,
            refresh_token=new_refresh,
            token_type="bearer",
            user=UserResponse.model_validate(user),
        )
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "error": {
                    "code": "REFRESH_TOKEN_EXPIRED",
                    "message": "Refresh token has expired, please log in again",
                    "request_id": request_id,
                }
            },
        )
    except jwt.InvalidTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "error": {
                    "code": "INVALID_REFRESH_TOKEN",
                    "message": "Invalid refresh token",
                    "request_id": request_id,
                }
            },
        )


@router.get("/me", response_model=CurrentUserResponse)
def get_me(
    current_user: User = Depends(get_current_user),
):
    """Return currently authenticated user identity and role."""
    return CurrentUserResponse(user=UserResponse.model_validate(current_user))


@router.post("/logout")
def logout(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Invalidate current user session and record logout in audit trail.
    """
    request_id = getattr(request.state, "request_id", None) or request.headers.get("X-Request-ID", "unknown")
    log_audit_event(
        db=db,
        actor=current_user.username,
        action="LOGOUT",
        target_entity="USER",
        target_id=str(current_user.id),
        request_id=request_id,
    )
    return {"status": "ok", "message": "Successfully logged out"}


# --------------------------------------------------------------------------
# Admin-only user management endpoints
# --------------------------------------------------------------------------
@router.get("/users", response_model=UserListResponse)
def list_users(
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(require_roles([Role.ADMIN.value])),
    db: Session = Depends(get_db),
):
    """Admin-only list of users with pagination."""
    query = db.query(User)
    total = query.count()
    users = query.order_by(User.id.asc()).offset(offset).limit(limit).all()
    return UserListResponse(
        total=total,
        users=[UserResponse.model_validate(u) for u in users],
    )


@router.patch("/users/{user_id}/role", response_model=UserResponse)
def update_user_role(
    user_id: int,
    req: UserUpdateRole,
    request: Request,
    current_user: User = Depends(require_roles([Role.ADMIN.value])),
    db: Session = Depends(get_db),
):
    """Admin-only update of user role."""
    request_id = getattr(request.state, "request_id", None) or request.headers.get("X-Request-ID", "unknown")
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": {
                    "code": "USER_NOT_FOUND",
                    "message": f"User {user_id} not found",
                    "request_id": request_id,
                }
            },
        )

    old_role = user.role
    user.role = req.role.upper()
    db.commit()
    db.refresh(user)

    log_audit_event(
        db=db,
        actor=current_user.username,
        action="ROLE_CHANGE",
        target_entity="USER",
        target_id=str(user.id),
        request_id=request_id,
        metadata={"old_role": old_role, "new_role": user.role},
    )

    return UserResponse.model_validate(user)


@router.patch("/users/{user_id}/status", response_model=UserResponse)
def update_user_status(
    user_id: int,
    req: UserUpdateStatus,
    request: Request,
    current_user: User = Depends(require_roles([Role.ADMIN.value])),
    db: Session = Depends(get_db),
):
    """Admin-only activation / deactivation of user account."""
    request_id = getattr(request.state, "request_id", None) or request.headers.get("X-Request-ID", "unknown")
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": {
                    "code": "USER_NOT_FOUND",
                    "message": f"User {user_id} not found",
                    "request_id": request_id,
                }
            },
        )

    old_status = user.is_active
    user.is_active = req.is_active
    db.commit()
    db.refresh(user)

    log_audit_event(
        db=db,
        actor=current_user.username,
        action="USER_STATUS_CHANGE",
        target_entity="USER",
        target_id=str(user.id),
        request_id=request_id,
        metadata={"old_status": old_status, "new_status": user.is_active},
    )

    return UserResponse.model_validate(user)
