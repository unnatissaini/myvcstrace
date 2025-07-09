from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from server.db import get_db
from server.models import Commit, User, Repository , Snapshot, AccessControl, Log
from passlib.context import CryptContext
from server.schemas import RepositoryCreate, UserOut
from server.utils.token import create_access_token  # function to generate JWT
from fastapi.responses import JSONResponse , RedirectResponse , FileResponse
from passlib.hash import bcrypt
from fastapi import  FastAPI, Request, Form, Depends, status , HTTPException , APIRouter
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware
from server.dependencies import get_current_user , RepositoryAccessOut, get_current_user_optional
from sqlalchemy.orm import Session
import os, mimetypes
from typing import List, Optional
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
from pydantic import BaseModel
from server.services.access_control import get_user_access_level
from datetime import datetime
from server.utils.diff_utils import apply_diff
from starlette.status import HTTP_303_SEE_OTHER
from fastapi import APIRouter, Depends, HTTPException
from datetime import datetime
from server.utils.file_parser import extract_text_from_file  # <- add this
from server.utils.file_parser import extract_text_from_file  # <- add this
from sqlalchemy import or_


class NewFile(BaseModel):
    name: str
    content: str = ""

router = APIRouter()
templates = Jinja2Templates(directory="templates")
router.mount("/static", StaticFiles(directory="static"), name="static")

# Show login form
@router.get("/", response_class=HTMLResponse)
def login_form(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})
@router.get("/login", response_class=HTMLResponse)
def login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})

@router.post("/login")
def login(
    username: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db)
):
    user = db.query(User).filter(User.username == username).first()
    if not user or not bcrypt.verify(password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    
    token = create_access_token(data={"sub": user.username})

    return JSONResponse({"access_token": token, "token_type": "bearer"})

# Logout
@router.get("/logout")
def logout(request: Request):
    request.session.clear()
    return RedirectResponse("/login", status_code=302)


@router.get("/dashboard", response_class=HTMLResponse)
def dashboard_page(request: Request):
    return templates.TemplateResponse("dashboard.html", {"request": request})

@router.get("/dashboard", response_class=HTMLResponse)
def dashboard(request: Request, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    repos = db.query(Repository).filter(
        (Repository.owner_id == current_user.id) |
        (Repository.is_public == True)
    ).all()
    return templates.TemplateResponse("dashboard.html", {
        "request": request,
        "repositories": repos,
        "user": current_user
    })

@router.get("/api/dashboard-data")
def dashboard_data(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    def format_date_with_suffix(dt: datetime):
        if not dt:
            return ""
        day = dt.day
        suffix = "th" if 11 <= day <= 13 else {1: "st", 2: "nd", 3: "rd"}.get(day % 10, "th")
        return f"{day}{suffix} {dt.strftime('%b %Y')}"  # Use on Windows

    repos = db.query(Repository).filter_by(owner_id=current_user.id).all()
    logs = db.query(Log).filter_by(user_id=current_user.id).order_by(Log.timestamp.desc()).limit(5).all()

    return {
        "user": {"id": current_user.id, "username": current_user.username},
        "repos": [{
            "id": r.id,
            "name": r.name,
            "visibility": r.visibility,
            "created_at": format_date_with_suffix(r.created_at),
            "description": r.description
        } for r in repos],
        "logs": [{"timestamp": str(l.timestamp), "action": l.action, "repo_id": l.repo_id} for l in logs]
    }


def list_dir_recursive(base_path, rel_path=""):
    items = []
    full_path = os.path.join(base_path, rel_path)

    for entry in os.listdir(full_path):
        entry_path = os.path.join(full_path, entry)
        relative_entry_path = os.path.join(rel_path, entry).replace("\\", "/")

        if os.path.isdir(entry_path):
            items.append({
                "name": entry,
                "type": "folder",
                "path": relative_entry_path,
                "children": list_dir_recursive(base_path, relative_entry_path)
            })
        else:
            items.append({
                "name": entry,
                "type": "file",
                "path": relative_entry_path
            })

    return items
@router.get("/repositories/{repo_id}/files")
def get_file_tree(
    repo_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    # Get the repository
    repo = db.query(Repository).filter(Repository.id == repo_id).first()
    if not repo:
        raise HTTPException(status_code=404, detail="Repository not found")

    # If user is owner
    if repo.owner_id == current_user.id:
        owner_id = current_user.id

    # If repo is private
    elif repo.visibility == "private":
        access = db.query(AccessControl).filter_by(user_id=current_user.id, repository_id=repo_id).first()
        if not access or access.role not in ("viewer", "editor", "admin", "collaborator"):
            raise HTTPException(status_code=403, detail="Access denied to private repository")
        owner_id = repo.owner_id  # use actual owner path for file access

    # If repo is public and user is not owner
    else:
        owner_id = repo.owner_id  # public repo is viewable

    # Construct correct file path
    repo_path = f"D:/VCS_Storage/user_{owner_id}/repo_{repo_id}"
    if not os.path.exists(repo_path):
        return []

    tree = list_dir_recursive(repo_path)
    return tree

@router.post("/repositories/{repo_id}/files")
def create_new_file(
    repo_id: int,
    payload: NewFile,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    name = payload.get("name")
    content = payload.get("content", "")

    if not name:
        raise HTTPException(status_code=400, detail="Filename is required")

    # Check access
    access = db.query(AccessControl).filter_by(user_id=current_user.id, repository_id=repo_id).first()
    if not access or access.role not in ("admin", "editor","collaborator"):
        raise HTTPException(status_code=403, detail="Permission denied")

    file_path = f"D:/VCS_Storage/user_{current_user.id}/repo_{repo_id}/{name}"
    os.makedirs(os.path.dirname(file_path), exist_ok=True)

    with open(file_path, "w", encoding="utf-8") as f:
        f.write(content)

    return {"message": "File created", "filename": name}



@router.get("/repositories/{repo_id}/file")
def get_file_content(
    repo_id: int,
    name: str,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user_optional)
):
    repo = db.query(Repository).filter(Repository.id == repo_id).first()
    if not repo:
        raise HTTPException(status_code=404, detail="Repository not found")

    # 🔐 Access logic
    if repo.visibility == "private":
        if not current_user:
            raise HTTPException(status_code=401, detail="Login required for private repository")
        if repo.owner_id != current_user.id:
            access = db.query(AccessControl).filter_by(
                user_id=current_user.id,
                repository_id=repo_id
            ).first()
            if not access:
                raise HTTPException(status_code=403, detail="No access to this private repository")

    # 📁 File path
    file_path = f"D:/VCS_Storage/user_{repo.owner_id}/repo_{repo_id}/{name}"
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="File not found.")

    # 📄 Determine content type
    mime_type, _ = mimetypes.guess_type(file_path)
    ext = os.path.splitext(name)[1].lower()

    if ext in [".pdf", ".doc", ".docx"]:
        try:
            content = extract_text_from_file(file_path)
            return {"filename": name, "content": content}
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to extract content: {str(e)}")

    if mime_type and not mime_type.startswith("text"):
        return FileResponse(file_path, media_type=mime_type, filename=os.path.basename(name))

    try:
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()
        return {"filename": name, "content": content}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error reading text file: {str(e)}")



@router.get("/repositories/{repo_id}/dashboard", response_class=HTMLResponse)
def repo_dashboard(repo_id: int, request: Request, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    # Step 1: Check if repository exists
    repo = db.query(Repository).filter(Repository.id == repo_id).first()
    if not repo:
        raise HTTPException(status_code=404, detail="Repository not found")

    # Step 2: Role-based access control
    if repo.visibility == "private":
        if repo.owner_id != current_user.id:
            access = db.query(AccessControl).filter_by(repository_id=repo_id, user_id=current_user.id).first()
            if not access or access.role not in ("viewer", "editor", "admin", "collaborator"):
                raise HTTPException(status_code=403, detail="Access denied to private repository")
            role = access.role
        else:
            role = "owner"
    else:
        # Public repository: anyone can view
        if repo.owner_id == current_user.id:
            role = "owner"
        else:
            access = db.query(AccessControl).filter_by(repository_id=repo_id, user_id=current_user.id).first()
            role = access.role if access else "guest"  # guest for public view-only access


    # Step 3: Load files (excluding merged commits — handled in file list JS)
    repo_path = f"D:/VCS_Storage/user_{current_user.id}/repo_{repo_id}"
    files = []
    if os.path.exists(repo_path):
        files = [f for f in os.listdir(repo_path) if os.path.isfile(os.path.join(repo_path, f))]

    # Step 4: Render dashboard
    return templates.TemplateResponse("repo_dashboard.html", {
        "request": request,
        "repo_id": repo.id,
        "repo_name": repo.name,
        "user_id": current_user.id,
        "repositories": [repo],
        "files": files,
        "role": role  # Optional: use in frontend to conditionally show buttons
    })


@router.post("/repositories/{repo_id}/open", response_class=RedirectResponse)
def open_repo_dashboard(repo_id: int, token: str = Form(...)):
    response = RedirectResponse(url=f"/repositories/{repo_id}/dashboard", status_code=302)
    response.set_cookie(key="Authorization", value=f"Bearer {token}", httponly=True)
    return response


@router.get("/accessible-repositories", response_model=List[RepositoryAccessOut])
async def get_accessible_repositories(
    current_user: User = Depends(get_current_user), 
    db: Session = Depends(get_db)
):
    query = (
        db.query(Repository, AccessControl.role)
        .join(AccessControl, AccessControl.repository_id == Repository.id)
        .filter(
            AccessControl.user_id == current_user.id,
            Repository.owner_id != current_user.id   
        )
    )

    results = query.all()

    # Sort by role and visibility
    role_priority = {"admin": 1, "collaborator": 2, "editor": 2, "viewer": 3}
    visibility_priority = {"private": 1, "public": 2}
    
    sorted_results = sorted(
        results,
        key=lambda x: (
            role_priority.get(x[1], 99),
            visibility_priority.get(x[0].visibility, 99)
        )
    )

    return [
        {
            "id": repo.id,
            "name": repo.name,
            "owner": repo.owner.username,
            "visibility": repo.visibility,
            "role": role
        }
        for repo, role in sorted_results
    ]


def build_commit_tree(commits):
    tree = {}
    lookup = {c["id"]: c for c in commits}
    for commit in commits:
        parent_id = commit.get("parent_commit_id")
        if parent_id and parent_id in lookup:
            lookup[parent_id].setdefault("children", []).append(commit)
        else:
            tree[commit["id"]] = commit
    return list(tree.values())


@router.get("/repositories/{repo_id}/file_commits")
def get_file_commits(
    repo_id: int,
    file_path: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    # 1. Access check
    access = db.query(AccessControl).filter_by(user_id=current_user.id, repository_id=repo_id).first()
    if not access:
        raise HTTPException(status_code=403, detail="Access denied")

    # 2. Fetch commits for file or its versions
    raw_commits = (
        db.query(Commit, User.username)
        .join(User, Commit.author_id == User.id)
        .filter(Commit.repo_id == repo_id)
        .filter(
            or_(
                Commit.original_filename == file_path,
                Commit.versioned_filename.like(f"{file_path}%")
            )
        )
        .order_by(Commit.timestamp.asc())
        .all()
    )

    # 3. Format commits for tree
    commits = []
    for commit, username in raw_commits:
        commits.append({
            "id": commit.id,
            "author": username,
            "message": commit.message,
            "timestamp": str(commit.timestamp),
            "status": commit.status,
            "parent_commit_id": commit.parent_commit_id,
            "version_file": commit.versioned_filename or "",
            "snapshot_path": commit.snapshot_path
        })

    # 4. Return tree structure
    return build_commit_tree(commits)


@router.get("/repositories/{repo_id}/role")
def get_user_role(
    repo_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    # Fetch the repository
    repo = db.query(Repository).filter(Repository.id == repo_id).first()
    if not repo:
        raise HTTPException(status_code=404, detail="Repository not found")

    # If user is the owner
    if repo.owner_id == current_user.id:
        return {"role": "owner"}

    # If repo is private, check access
    if repo.visibility == "private":
        access = db.query(AccessControl).filter_by(repository_id=repo_id, user_id=current_user.id).first()
        if not access or access.role not in ("viewer", "editor", "admin", "collaborator"):
            raise HTTPException(status_code=403, detail="No access to this private repository.")
        return {"role": access.role}

    # If public and not owner, check if access is defined; else default to guest
    access = db.query(AccessControl).filter_by(repository_id=repo_id, user_id=current_user.id).first()
    if access:
        return {"role": access.role}
    
    return {"role": "guest"}  # default role for public repo with no access assigned






class FileEditRequest(BaseModel):
    filename: str
    content: str
    is_binary: bool = False

@router.put("/repositories/{repo_id}/edit_file")
def edit_file(
    repo_id: int,
    edit: FileEditRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    # ✅ Access control
    access = db.query(AccessControl).filter_by(
        user_id=current_user.id,
        repository_id=repo_id
    ).first()
    if not access or access.role not in ("admin", "editor", "collaborator"):
        raise HTTPException(status_code=403, detail="Permission denied")

    # ✅ Full file path
    file_path = os.path.join(
        f"D:/VCS_Storage/user_{current_user.id}/repo_{repo_id}",
        edit.filename
    )

    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="File not found")

    try:
        # ✅ Save plain text for all file types (binary handled via commit upload if needed)
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(edit.content)

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Write failed: {e}")

    # ✅ Log the edit
    log = Log(
        user_id=current_user.id,
        repo_id=repo_id,
        action="edit_file",
        description=f"Edited file {edit.filename}",
        timestamp=datetime.utcnow()
    )
    db.add(log)
    db.commit()

    return {"detail": f"File '{edit.filename}' saved successfully."}


@router.get("/repositories/{repo_id}/versions")
def list_versions(repo_id: int, filename: str, current_user: User = Depends(get_current_user)):
    version_dir = f"D:/VCS_Storage/user_{current_user.id}/repo_{repo_id}/versions/{filename}"
    if not os.path.exists(version_dir):
        return []
    files = os.listdir(version_dir)
    return [{"version_file": f, "path": os.path.join(version_dir, f)} for f in files]

@router.get("/repositories/{repo_id}/commit_file")
def get_commit_content(
    repo_id: int,
    commit_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    access = db.query(AccessControl).filter_by(user_id=current_user.id, repository_id=repo_id).first()
    if not access:
        raise HTTPException(status_code=403, detail="Access denied")

    commit = db.query(Commit).filter_by(id=commit_id, repo_id=repo_id).first()
    if not commit:
        raise HTTPException(status_code=404, detail="Commit not found")

    if commit.diff_text:
        content = apply_diff("", commit.diff_text)
    elif commit.snapshot_path and os.path.exists(commit.snapshot_path):
        with open(commit.snapshot_path, "r", encoding="utf-8") as f:
            content = f.read()
    else:
        raise HTTPException(status_code=404, detail="No content available")

    return {"content": content}

@router.get("/repositories/{repo_id}/stats")
def get_repo_stats(repo_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):

    repo_dir = f"D:/VCS_Storage/user_{current_user.id}/repo_{repo_id}"
    if not os.path.exists(repo_dir):
        raise HTTPException(status_code=404, detail="Repository not found")

    total_size = 0
    file_count = 0
    for root, dirs, files in os.walk(repo_dir):
        for file in files:
            file_path = os.path.join(root, file)
            if os.path.isfile(file_path):
                file_count += 1
                total_size += os.path.getsize(file_path)

    size_mb = total_size / (1024 * 1024)
    # Estimate time: assume 50ms per file + 1ms per KB (just a rough model)
    estimated_time_sec = round((file_count * 0.05 + total_size / 1024 / 1000), 2)

    return {
        "file_count": file_count,
        "total_size_mb": round(size_mb, 2),
        "estimated_time_sec": estimated_time_sec
    }

class VisibilityUpdate(BaseModel):
    new_visibility: str


@router.patch("/repositories/{repo_id}/toggle-visibility")
def toggle_visibility(
    repo_id: int,
    update: VisibilityUpdate,   # ✅ use Pydantic model
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    repo = db.query(Repository).filter(Repository.id == repo_id).first()
    if not repo:
        raise HTTPException(status_code=404, detail="Repository not found")

    if repo.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not allowed to change visibility")

    if update.new_visibility not in ["public", "private"]:
        raise HTTPException(status_code=400, detail="Invalid visibility option")

    repo.visibility = update.new_visibility
    db.commit()
    return {"detail": f"Visibility set to {repo.visibility}"}
@router.get("/users/{user_id}/log")
def get_user_log(user_id: int, db: Session = Depends(get_db)):
    logs = (
        db.query(Log, User.username)
        .join(User, Log.user_id == User.id)
        .filter(Log.user_id == user_id)
        .order_by(Log.timestamp.desc())
        .limit(50)
        .all()
    )

    return [
        {
            "timestamp": log.timestamp,
            "action": log.action,
            "repo_id": log.repo_id,
            "user_id": log.user_id,
            "username": username,
        }
        for log, username in logs
    ]
