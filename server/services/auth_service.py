from sqlalchemy.orm import Session
from server.utils.hasher import hash_password, verify_password
from server.utils.token import create_access_token
from server.models import User
from fastapi import HTTPException, status

def register_user(db: Session, username: str, password: str):
    if db.query(User).filter(User.username == username).first():
        raise HTTPException(status_code=400, detail="Username already exists.")
    new_user = User(username=username, password_hash=hash_password(password))
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    #return {"id": new_user.id, "username": new_user.username}
    return new_user

def login_user(db: Session, username: str, password: str):
    user = db.query(User).filter(User.username == username).first()
    if not user or not verify_password(password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    token = create_access_token({"sub": user.username})
    return {"access_token": token, "token_type": "bearer"}
