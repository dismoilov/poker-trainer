"""Auth API routes."""

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db import get_db
from app.schemas import LoginRequest, LoginResponse, UserInfo
from app.security import get_current_user, hash_password, verify_password
from app.models import UserModel
from app.services.auth import authenticate

router = APIRouter(prefix="/api/auth", tags=["auth"])


class ChangePasswordRequest(BaseModel):
    currentPassword: str
    newPassword: str


@router.post("/login", response_model=LoginResponse)
def login(req: LoginRequest, db: Session = Depends(get_db)):
    result = authenticate(db, req.username, req.password)
    if not result:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
        )
    user, token = result
    return LoginResponse(
        accessToken=token,
        user=UserInfo(id=user.id, username=user.username),
    )


@router.get("/me", response_model=UserInfo)
def get_me(user: UserModel = Depends(get_current_user)):
    return UserInfo(id=user.id, username=user.username)


@router.post("/password")
def change_password(
    req: ChangePasswordRequest,
    user: UserModel = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not verify_password(req.currentPassword, user.password_hash):
        raise HTTPException(status_code=400, detail="Неверный текущий пароль")
    user.password_hash = hash_password(req.newPassword)
    db.commit()
    return {"ok": True}
