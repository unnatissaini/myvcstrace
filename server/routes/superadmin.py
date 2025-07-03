from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from server.dependencies import get_current_user
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from server.db import get_db
from server.models import Commit, User, Repository , Snapshot
from passlib.context import CryptContext
from server.schemas import RepositoryCreate
from server.utils.token import create_access_token  # function to generate JWT
from fastapi.responses import JSONResponse
from passlib.hash import bcrypt
from fastapi import  FastAPI, Request, Form, Depends, status , HTTPException , APIRouter
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware
from server.dependencies import get_current_user , RepositoryAccessOut
from sqlalchemy.orm import Session
import hashlib
from server.models import Log
import os
import uuid
import traceback
from typing import List
from server.models import AccessControl
from pydantic import BaseModel
from server.services.access_control import get_user_access_level
from datetime import datetime
from server.utils.diff_utils import apply_diff
router = APIRouter()
templates = Jinja2Templates(directory="templates")
def require_superadmin(current_user: User = Depends(get_current_user)):
    if current_user.username != "superadmin":
        raise HTTPException(status_code=403, detail="Superadmin access required")
    return current_user

@router.get("/superadmin", response_class=HTMLResponse)
async def superadmin_dashboard(request: Request, user=Depends(require_superadmin)):
    return templates.TemplateResponse("superadmin_dashboard.html", {"request": request})

@router.get("/superadmin/section/{section}", response_class=HTMLResponse)
async def load_section(section: str, request: Request, user=Depends(require_superadmin)):
    return templates.TemplateResponse(f"superadmin/section_{section}.html", {"request": request})

@router.get("/api/superadmin/users")
def get_all_users(db: Session = Depends(get_db), user=Depends(require_superadmin)):
    return db.query(User).all()

@router.delete("/api/superadmin/users/{user_id}")
def delete_user(user_id: int, db: Session = Depends(get_db), user=Depends(require_superadmin)):
    db_user = db.query(User).get(user_id)
    if db_user:
        db.delete(db_user)
        db.commit()
        return {"message": "User deleted"}
    raise HTTPException(status_code=404, detail="User not found")
@router.get("/api/superadmin/stats")
def get_stats(db: Session = Depends(get_db)):
    return {
        "total_users": db.query(User).count(),
        "total_repos": db.query(Repository).count(),
        "public_repos": db.query(Repository).filter_by(visibility="public").count(),
        "private_repos": db.query(Repository).filter_by(visibility="private").count()
    }

@router.get("/api/superadmin/repositories")
def get_all_repositories(db: Session = Depends(get_db)):
    return [{
        "id": r.id,
        "name": r.name,
        "owner_username": r.owner.username,
        "visibility": r.visibility
    } for r in db.query(Repository).all()]

@router.delete("/api/superadmin/repositories/{repo_id}")
def delete_repo(repo_id: int, db: Session = Depends(get_db)):
    repo = db.query(Repository).get(repo_id)
    if repo:
        db.delete(repo)
        db.commit()
        return {"message": "Deleted"}
    raise HTTPException(status_code=404)

@router.post("/api/superadmin/repositories/{repo_id}/toggle")
def toggle_visibility(repo_id: int, db: Session = Depends(get_db)):
    repo = db.query(Repository).get(repo_id)
    if repo:
        repo.visibility = "private" if repo.visibility == "public" else "public"
        db.commit()
        return {"message": "Toggled"}
    raise HTTPException(status_code=404)

@router.get("/api/superadmin/logs")
def get_logs(db: Session = Depends(get_db)):
    return db.query(Log).order_by(Log.timestamp.desc()).limit(100).all()
