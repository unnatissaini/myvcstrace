from fastapi.security import OAuth2PasswordBearer
from fastapi import Depends, HTTPException
from jose import JWTError
from server.models import User
from server.db import get_db
from sqlalchemy.orm import Session
from server.utils.token import decode_token
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="login")

def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)) -> User:
    try:
        payload = decode_token(token)
        username = payload.get("sub")
        if not username:
            raise HTTPException(status_code=401, detail="Invalid token")
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")
    
    user = db.query(User).filter(User.username == username).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user

from pydantic import BaseModel

class AccessControlInput(BaseModel):
    user_id: int
    role: str

class RepositoryAccessOut(BaseModel):
    id: int
    name: str
    owner: str
    visibility: str
    role: str

    class Config:
        orm_mode = True
