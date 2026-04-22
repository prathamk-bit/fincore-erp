"""
API routes for authentication and user management.

Endpoints:
    POST /api/auth/register  - Create a new user (admin only).
    POST /api/auth/login     - Authenticate and return a JWT token.
    GET  /api/auth/me        - Return the current authenticated user's info.
    GET  /api/auth/users     - List all users (admin only).
"""

from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from backend.auth.auth import (
    create_access_token,
    get_current_user,
    get_password_hash,
    role_required,
    verify_password,
)
from backend.models.database import get_db
from backend.models.user import User
from backend.schemas.user import LoginRequest, Token, UserCreate, UserResponse, UserUpdate

router = APIRouter(prefix="/api/auth", tags=["Authentication"])


# ---------------------------------------------------------------------------
# POST /register  (admin only)
# ---------------------------------------------------------------------------

@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def register(
    data: UserCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(role_required(["admin"])),
):
    """
    Create a new user account.

    Only administrators are allowed to register new users.
    """
    # Check for existing username
    existing_user = db.query(User).filter(User.username == data.username).first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Username '{data.username}' is already taken",
        )

    # Check for existing email
    existing_email = db.query(User).filter(User.email == data.email).first()
    if existing_email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Email '{data.email}' is already registered",
        )

    user = User(
        username=data.username,
        email=data.email,
        hashed_password=get_password_hash(data.password),
        role=data.role,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


# ---------------------------------------------------------------------------
# POST /login
# ---------------------------------------------------------------------------

@router.post("/login", response_model=Token)
def login(data: LoginRequest, db: Session = Depends(get_db)):
    """
    Authenticate a user and return a JWT access token.
    """
    user = db.query(User).filter(User.username == data.username).first()

    if not user or not verify_password(data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User account is inactive",
            headers={"WWW-Authenticate": "Bearer"},
        )

    access_token = create_access_token(username=user.username, role=user.role)
    return Token(access_token=access_token, token_type="bearer")


# ---------------------------------------------------------------------------
# GET /me
# ---------------------------------------------------------------------------

@router.get("/me", response_model=UserResponse)
def get_me(current_user: User = Depends(get_current_user)):
    """
    Return the profile of the currently authenticated user.
    """
    return current_user


# ---------------------------------------------------------------------------
# GET /users  (admin only)
# ---------------------------------------------------------------------------

@router.get("/users", response_model=List[UserResponse])
def list_users(
    db: Session = Depends(get_db),
    current_user: User = Depends(role_required(["admin"])),
):
    """
    List all user accounts.

    Only administrators can access this endpoint.
    """
    return db.query(User).order_by(User.id).all()


# ---------------------------------------------------------------------------
# PUT /users/{id}  (admin only)
# ---------------------------------------------------------------------------

@router.put("/users/{id}", response_model=UserResponse)
def update_user(
    id: int,
    data: UserUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(role_required(["admin"])),
):
    """
    Update an existing user account.

    Only administrators can update user accounts.
    """
    user = db.query(User).filter(User.id == id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User with id {id} not found",
        )

    # Update email if provided
    if data.email is not None and data.email != user.email:
        existing_email = db.query(User).filter(User.email == data.email, User.id != id).first()
        if existing_email:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Email '{data.email}' is already registered",
            )
        user.email = data.email

    # Update password if provided
    if data.password is not None:
        user.hashed_password = get_password_hash(data.password)

    # Update role if provided
    if data.role is not None:
        user.role = data.role

    # Update is_active if provided
    if data.is_active is not None:
        user.is_active = data.is_active

    db.commit()
    db.refresh(user)
    return user
