"""
JWT-based authentication and role-based access control for the ERP system.

Provides:
    - Password hashing / verification via passlib (bcrypt).
    - JWT access-token creation with embedded username, role, and expiry.
    - FastAPI dependencies for extracting the current user and enforcing roles.
"""

from datetime import datetime, timedelta, timezone
from typing import List, Optional
import os

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy.orm import Session

from backend.models.database import get_db
from backend.models.user import User

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

# Load secret key from environment variable, with fallback for development
SECRET_KEY = os.environ.get("ERP_JWT_SECRET_KEY", "erp-system-secret-key-2024-dev-only")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 480

# ---------------------------------------------------------------------------
# Password hashing
# ---------------------------------------------------------------------------

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Return True if *plain_password* matches *hashed_password*."""
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    """Return the bcrypt hash of *password*."""
    return pwd_context.hash(password)


# ---------------------------------------------------------------------------
# Token creation
# ---------------------------------------------------------------------------

def create_access_token(username: str, role: str, expires_delta: Optional[timedelta] = None) -> str:
    """
    Create a signed JWT containing the username (``sub``), role, and expiry.

    Args:
        username: The user's login name (stored in the ``sub`` claim).
        role: The user's role string (e.g. ``"admin"``).
        expires_delta: Optional custom lifetime; defaults to
            ``ACCESS_TOKEN_EXPIRE_MINUTES``.

    Returns:
        Encoded JWT string.
    """
    if expires_delta is None:
        expires_delta = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)

    expire = datetime.now(timezone.utc) + expires_delta

    to_encode = {
        "sub": username,
        "role": role,
        "exp": expire,
    }
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


# ---------------------------------------------------------------------------
# Current-user dependency
# ---------------------------------------------------------------------------

async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> User:
    """
    FastAPI dependency that extracts and validates the JWT from the
    ``Authorization`` header, then returns the corresponding ``User``
    record from the database.

    Raises:
        HTTPException 401: If the token is invalid, expired, or the user
            does not exist / is inactive.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: Optional[str] = payload.get("sub")
        if username is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception

    user = db.query(User).filter(User.username == username).first()

    if user is None:
        raise credentials_exception

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User account is inactive",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return user


# ---------------------------------------------------------------------------
# Role-based access control dependency
# ---------------------------------------------------------------------------

def role_required(allowed_roles: List[str]):
    """
    Return a FastAPI dependency that verifies the current user's role is
    in *allowed_roles*.

    Usage::

        @router.get("/admin-only")
        def admin_view(user: User = Depends(role_required(["admin"]))):
            ...

    Args:
        allowed_roles: A list of role strings that are permitted to access
            the endpoint.

    Raises:
        HTTPException 403: If the user's role is not in *allowed_roles*.
    """

    async def _role_checker(
        current_user: User = Depends(get_current_user),
    ) -> User:
        if current_user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have permission to access this resource",
            )
        return current_user

    return _role_checker
