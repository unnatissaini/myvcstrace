from fastapi import APIRouter, Request, Form, Depends, HTTPException, status
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from starlette.status import HTTP_303_SEE_OTHER
from server.db import get_db
from server.models import User, Repository, Log
from server.utils.token import create_access_token
from passlib.hash import bcrypt
from typing import List
from sqlalchemy.orm import Session
from server.schemas import LogOut
from sqlalchemy import or_, cast
from sqlalchemy.types import String

router = APIRouter()
templates = Jinja2Templates(directory="templates")

# 🔐 Change this to your secret password
SUPERADMIN_SECRET = "123"

# ----------------------------
# 🔐 SUPERADMIN LOGIN (password only)
# ----------------------------
@router.get("/superadmin-login", response_class=HTMLResponse)
async def superadmin_login_form(request: Request):
    return templates.TemplateResponse("superadmin_login.html", {"request": request})

@router.post("/superadmin-login", response_class=HTMLResponse)
async def superadmin_login(request: Request, password: str = Form(...)):
    if password == SUPERADMIN_SECRET:
        request.session["superadmin_authenticated"] = True
        return RedirectResponse(url="/superadmin", status_code=HTTP_303_SEE_OTHER)
    
    return templates.TemplateResponse("superadmin_login.html", {
        "request": request,
        "error": "Incorrect password"
    })

from fastapi import Query

@router.get("/api/superadmin/users")
def search_users(q: str = Query(..., min_length=1), db: Session = Depends(get_db)):
    query = db.query(User).filter(
        or_(
            User.username.ilike(f"%{q}%"),
            cast(User.id, String).ilike(f"%{q}%")
        )
    ).limit(10)
    return [{"id": user.id, "username": user.username} for user in query]


# ----------------------------
# ✅ SUPERADMIN AUTH DEPENDENCY
# ----------------------------


def require_superadmin(request: Request):
    if not request.session.get("superadmin_authenticated"):
        raise HTTPException(status_code=303, detail="Redirecting to /superadmin-login")
    return True


'''async def require_superadmin(request: Request):
    if request.cookies.get("superadmin_logged_in") != "true":
        return RedirectResponse(url="/superadmin-login", status_code=303)'''



# ----------------------------
# 📊 SUPERADMIN DASHBOARD UI ROUTES
# ----------------------------

@router.get("/superadmin", response_class=HTMLResponse)
async def superadmin_dashboard(request: Request, _=Depends(require_superadmin)):
    return templates.TemplateResponse("superadmin_dashboard.html", {"request": request})



@router.get("/superadmin/section/{section}", response_class=HTMLResponse)
async def load_section(section: str, request: Request, _: None = Depends(require_superadmin)):
    return templates.TemplateResponse(f"superadmin/section_{section}.html", {"request": request})


# ----------------------------
# 📦 API: USERS
# ----------------------------

@router.get("/api/superadmin/users-reset")
def get_all_users(db: Session = Depends(get_db), _: None = Depends(require_superadmin)):
    return db.query(User).order_by(User.id).all()


@router.delete("/api/superadmin/users/{user_id}")
def delete_user(user_id: int, db: Session = Depends(get_db), _: None = Depends(require_superadmin)):
    user = db.query(User).get(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    db.delete(user)
    db.commit()
    return {"message": "User deleted"}


# ----------------------------
# 📦 API: REPOSITORIES
# ----------------------------
@router.get("/api/superadmin/repositories")
def get_all_repositories(db: Session = Depends(get_db), _: None = Depends(require_superadmin)):
    repos = db.query(Repository).all()
    return [{
        "id": r.id,
        "name": r.name,
        "owner_username": r.owner.username if r.owner else "Unknown",
        "visibility": r.visibility
    } for r in repos]



@router.get("/superadmin/repo/{repo_id}/dashboard")
def superadmin_open_repo_dashboard(repo_id: int, request: Request):
    response = RedirectResponse(url=f"/repositories/{repo_id}/dashboard", status_code=HTTP_303_SEE_OTHER)
    response.set_cookie("superadmin_force_access", "true", httponly=True)
    return response


@router.delete("/api/superadmin/repositories/{repo_id}")
def delete_repo(repo_id: int, db: Session = Depends(get_db), _: None = Depends(require_superadmin)):
    repo = db.query(Repository).get(repo_id)
    if not repo:
        raise HTTPException(status_code=404, detail="Repository not found")
    db.delete(repo)
    db.commit()
    return {"message": "Repository deleted"}


@router.post("/api/superadmin/repositories/{repo_id}/toggle")
def toggle_visibility(repo_id: int, db: Session = Depends(get_db), _: None = Depends(require_superadmin)):
    repo = db.query(Repository).get(repo_id)
    if not repo:
        raise HTTPException(status_code=404, detail="Repository not found")
    repo.visibility = "private" if repo.visibility == "public" else "public"
    db.commit()
    return {"message": f"Visibility toggled to {repo.visibility}"}


# ----------------------------
# 📈 API: STATS & LOGS
# ----------------------------

@router.get("/api/superadmin/stats")
def get_stats(db: Session = Depends(get_db), _: None = Depends(require_superadmin)):
    return {
        "total_users": db.query(User).count(),
        "total_repos": db.query(Repository).count(),
        "public_repos": db.query(Repository).filter_by(visibility="public").count(),
        "private_repos": db.query(Repository).filter_by(visibility="private").count()
    }

@router.get("/api/superadmin/logs", response_model=List[LogOut])
def get_logs(db: Session = Depends(get_db)):
    logs = db.query(Log).order_by(Log.timestamp.desc()).limit(100).all()

    enriched_logs = []
    for log in logs:
        user = db.query(User).get(log.user_id)
        repo = db.query(Repository).get(log.repo_id)
        enriched_logs.append({
            "id": log.id,
            "user_id": log.user_id,
            "username": user.username if user else "Unknown",
            "repo_id": log.repo_id,
            "repo_name": repo.name if repo else "Unknown",
            "commit_id": log.commit_id,
            "action": log.action,
            "timestamp": log.timestamp
        })

    return enriched_logs

@router.get("/api/superadmin/users-list")
def get_users_list(db: Session = Depends(get_db)):
    users = db.query(User).order_by(User.username.asc()).all()
    return [{"id": u.id, "username": u.username} for u in users]

@router.get("/api/superadmin/repos-list")
def get_repos_list(db: Session = Depends(get_db)):
    repos = db.query(Repository).order_by(Repository.name.asc()).all()
    return [{"id": r.id, "name": r.name} for r in repos]

@router.get("/api/superadmin/logs/user/{user_id}")
def get_logs_by_user(user_id: int, db: Session = Depends(get_db)):
    logs = db.query(Log).filter(Log.user_id == user_id).order_by(Log.timestamp.desc()).all()
    enriched_logs = []
    for log in logs:
        enriched_logs.append({
            "id": log.id,
            "user_id": log.user_id,
            "username": log.user.username if log.user else "Unknown",
            "repo_id": log.repo_id,
            "repo_name": log.repo.name if log.repo else "Unknown",
            "commit_id": log.commit_id,
            "action": log.action,
            "timestamp": log.timestamp
        })
    return enriched_logs

@router.get("/api/superadmin/logs/repo/{repo_id}")
def get_logs_by_repo(repo_id: int, db: Session = Depends(get_db)):
    return db.query(Log).filter(Log.repo_id == repo_id).order_by(Log.timestamp.desc()).all()

@router.post("/api/superadmin/reset-password/{user_id}")
def reset_password(user_id: int, new_password: str = Form(...), db: Session = Depends(get_db), user=Depends(require_superadmin)):
    db_user = db.query(User).filter(User.id == user_id).first()
    if not db_user:
        raise HTTPException(status_code=404, detail="User not found")

    db_user.password_hash = bcrypt.hash(new_password)
    db.commit()
    return {"message": f"Password for '{db_user.username}' reset successfully"}

@router.get("/superadmin-logout")
def superadmin_logout(request: Request):
    response = RedirectResponse(url="/superadmin-login", status_code=303)
    response.delete_cookie("superadmin_logged_in")
    request.session.clear()
    return RedirectResponse(url="/superadmin-login", status_code=303)



@router.get("/api/superadmin/impersonate/{user_id}")
def impersonate_user(user_id: int, redirect_to: str = "dashboard", db: Session = Depends(get_db)):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    token = create_access_token(data={"sub": user.username})

    if redirect_to == "impersonated":
        response = RedirectResponse(url=f"/impersonated?token={token}", status_code=303)
    else:
        response = RedirectResponse(url="/dashboard", status_code=303)

    response.set_cookie(key="access_token", value=f"Bearer {token}", httponly=True)
    return response

'''@router.get("/impersonated", response_class=HTMLResponse)
def impersonated_entry(request: Request, token: str):
    response = RedirectResponse(url="/dashboard")
    response.set_cookie("access_token", token, httponly=True)
    return response'''
@router.get("/impersonated", response_class=HTMLResponse)
def impersonated_entry(token: str):
    html = f"""
    <script>
      localStorage.setItem("token", "Bearer {token}");
      window.location.href = "/dashboard";
    </script>
    """
    response = HTMLResponse(content=html)
    response.set_cookie("access_token", f"Bearer {token}", httponly=True)
    return response
