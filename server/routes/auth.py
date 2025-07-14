from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from server.db import get_db
from server.services.auth_service import register_user, login_user
from pydantic import BaseModel
import os

router = APIRouter(prefix="/auth", tags=["auth"])

class RegisterRequest(BaseModel):
    username: str
    #email: str
    password: str

class LoginRequest(BaseModel):
    username: str
    password: str

@router.post("/register")
def register(req: RegisterRequest, db: Session = Depends(get_db)):
    user = register_user(db, req.username, req.password)

    # ✅ Create folder for the user after registration
    user_dir = f"D:/VCS_Storage/user_{user.id}"
    os.makedirs(user_dir, exist_ok=True)

    return {"message": "User registered successfully", "user_id": user.id}
    #return register_user(db, req.username, req.password)


@router.post("/login")
def login(req: LoginRequest, db: Session = Depends(get_db)):
    return login_user(db, req.username, req.password)
