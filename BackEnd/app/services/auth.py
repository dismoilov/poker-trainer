"""Auth service — user creation, login."""

from sqlalchemy.orm import Session
from app.models import UserModel
from app.security import hash_password, verify_password, create_access_token


def get_user_by_username(db: Session, username: str) -> UserModel | None:
    return db.query(UserModel).filter(UserModel.username == username).first()


def create_user(db: Session, username: str, password: str, is_admin: bool = False) -> UserModel:
    user = UserModel(
        username=username,
        password_hash=hash_password(password),
        is_active=True,
        is_admin=is_admin,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def authenticate(db: Session, username: str, password: str) -> tuple[UserModel, str] | None:
    """Return (user, token) or None if auth fails."""
    user = get_user_by_username(db, username)
    if not user or not verify_password(password, user.password_hash):
        return None
    token = create_access_token(user.id, user.username)
    return user, token
