from fastapi.security import OAuth2PasswordBearer
from fastapi import Depends, HTTPException ,Request
from jose import JWTError
from server.models import User
from server.db import get_db
from sqlalchemy.orm import Session
from server.utils.token import decode_token,SECRET_KEY, ALGORITHM
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="login")
from jose import JWTError, jwt
from pydantic import BaseModel
'''def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)) -> User:
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
    return user'''
def get_current_user_optional(
    request: Request,
    db: Session = Depends(get_db)
):
    token = request.cookies.get("access_token")
    if not token or not token.startswith("Bearer "):
        return None
    
    try:
        payload = jwt.decode(token[7:], SECRET_KEY, algorithms=[ALGORITHM])
        username = payload.get("sub")
        if not username:
            return None
        return db.query(User).filter_by(username=username).first()
    except JWTError:
        return None

def get_current_user(request: Request, db: Session = Depends(get_db)):
    token = None

    # Try to get token from Authorization header
    auth_header = request.headers.get("Authorization")
    if auth_header and auth_header.startswith("Bearer "):
        token = auth_header.split("Bearer ")[1]
    
    # If not found, fallback to cookie
    if not token:
        token = request.cookies.get("access_token")
        if token and token.startswith("Bearer "):
            token = token[7:]

    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")

    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username = payload.get("sub")
        if username is None:
            raise HTTPException(status_code=401, detail="Invalid token payload")
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")

    user = db.query(User).filter(User.username == username).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    return user



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
