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
from typing import List
from server.models import AccessControl
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
from pydantic import BaseModel
from server.services.access_control import get_user_access_level
from datetime import datetime
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
    repos = db.query(Repository).filter_by(owner_id=current_user.id).all()
    logs = db.query(Log).filter_by(user_id=current_user.id).order_by(Log.timestamp.desc()).limit(5).all()

    return {
        "user": {"id": current_user.id, "username": current_user.username},
        "repos": [{"id": r.id, "name": r.name} for r in repos],
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
    access = db.query(AccessControl).filter_by(user_id=current_user.id, repository_id=repo_id).first()
    if not access:
        raise HTTPException(status_code=403, detail="No access to this repository.")

    repo_path = f"D:/VCS_Storage/user_{current_user.id}/repo_{repo_id}"
    if not os.path.exists(repo_path):
        return []

    tree = list_dir_recursive(repo_path)
    #print("\n\n=== TREE OUTPUT ===")
    #print(tree)
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
    if not access or access.role not in ("admin", "editor"):
        raise HTTPException(status_code=403, detail="Permission denied")

    file_path = f"D:/VCS_Storage/user_{current_user.id}/repo_{repo_id}/{name}"
    os.makedirs(os.path.dirname(file_path), exist_ok=True)

    with open(file_path, "w", encoding="utf-8") as f:
        f.write(content)

    return {"message": "File created", "filename": name}


from server.utils.file_parser import extract_text_from_file  # <- add this

@router.get("/repositories/{repo_id}/file")
def get_file_content(
    repo_id: int,
    name: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    # Check access permission
    access = db.query(AccessControl).filter_by(user_id=current_user.id, repository_id=repo_id).first()
    if not access:
        raise HTTPException(status_code=403, detail="No access to this repository.")

    # Full file path
    file_path = f"D:/VCS_Storage/user_{current_user.id}/repo_{repo_id}/{name}"
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="File not found.")

    # Try extracting content based on file extension
    try:
        ext = os.path.splitext(name)[1].lower()
        if ext in [".doc", ".docx", ".pdf"]:
            content = extract_text_from_file(file_path)
        else:
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error reading file: {str(e)}")

    return {"filename": name, "content": content}


@router.get("/repositories/{repo_id}/dashboard", response_class=HTMLResponse)
def repo_dashboard(repo_id: int, request: Request, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    # Step 1: Check if repository exists
    repo = db.query(Repository).filter(Repository.id == repo_id).first()
    if not repo:
        raise HTTPException(status_code=404, detail="Repository not found")

    # Step 2: Role-based access control
    if repo.owner_id != current_user.id:
        access = db.query(AccessControl).filter_by(repository_id=repo_id, user_id=current_user.id).first()
        if not access or access.role not in ("viewer", "editor", "admin"):
            raise HTTPException(status_code=403, detail="Access denied to repository")
        role = access.role
    else:
        role = "owner"

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

from fastapi import Form
from fastapi.responses import RedirectResponse

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

from sqlalchemy import func, or_


@router.get("/repositories/{repo_id}/file_commits")
def get_file_commits(
    repo_id: int,
    file_path: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    # 1. Check access
    access = db.query(AccessControl).filter_by(user_id=current_user.id, repository_id=repo_id).first()
    if not access:
        raise HTTPException(status_code=403, detail="Access denied")

    # 2. Fetch commits for the given file
    commits = (
        db.query(Commit, User.username)
        .join(User, Commit.author_id == User.id)
        .filter(Commit.repo_id == repo_id)
        .filter(Commit.original_filename == file_path)  # ✔️ match based on original filename
        .order_by(Commit.timestamp.desc())
        .all()
    )

    # 3. Format response
    result = []
    for commit, username in commits:
        result.append({
            "commit_id": commit.id,
            "author": username,
            "message": commit.message,
            "timestamp": commit.timestamp,
            "status": commit.status,
            "version_file": commit.versioned_filename or "",  # merged file name or empty for proposed
            "snapshot_path": commit.snapshot_path  # optional: for loading content
        })

    return result



@router.get("/repositories/{repo_id}/role")
def get_user_role(
    repo_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    role = get_user_access_level(db, user_id=current_user.id, repo_id=repo_id)
    if not role:
        raise HTTPException(status_code=403, detail="No access to this repository.")
    
    return {"role": role}



from pydantic import BaseModel

class FileEditRequest(BaseModel):
    filename: str
    content: str
    is_binary: bool = False
import base64

@router.put("/repositories/{repo_id}/edit_file")
def edit_file(
    repo_id: int,
    edit: FileEditRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    access = db.query(AccessControl).filter_by(user_id=current_user.id, repository_id=repo_id).first()
    if not access or access.role not in ("admin", "editor", "collaborator"):
        raise HTTPException(status_code=403, detail="Permission denied")

    file_path = os.path.join(f"D:/VCS_Storage/user_{current_user.id}/repo_{repo_id}", edit.filename)
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="File not found")

    try:
        if edit.is_binary:
            # Decode from base64 and write as binary
            decoded_data = base64.b64decode(edit.content)
            with open(file_path, "wb") as f:
                f.write(decoded_data)
        else:
            # Write plain text
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(edit.content)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Write failed: {e}")

    # Log it
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



@router.post("/repositories/{repo_id}/merge_commit_with_original")
def merge_commit_with_original(
    repo_id: int,
    commit_id: int = Form(...),
    filename: str = Form(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    access = db.query(AccessControl).filter_by(user_id=current_user.id, repository_id=repo_id).first()
    if not access or access.role != "admin":
        raise HTTPException(status_code=403, detail="Only admins can merge commit with original")

    commit = db.query(Commit).filter_by(id=commit_id, repo_id=repo_id).first()
    if not commit or not commit.snapshot_path:
        raise HTTPException(status_code=404, detail="Commit or snapshot not found")

    repo_folder = f"D:/VCS_Storage/user_{current_user.id}/repo_{repo_id}"
    original_path = os.path.join(repo_folder, filename)

    if not os.path.exists(original_path):
        raise HTTPException(status_code=404, detail="Original file not found")

    with open(commit.snapshot_path, "r", encoding="utf-8") as f1, open(original_path, "r", encoding="utf-8") as f2:
        lines1 = f1.readlines()
        lines2 = f2.readlines()

    merged_lines = list(dict.fromkeys(lines1 + lines2))

    version_dir = os.path.join(repo_folder, "versions", filename)
    os.makedirs(version_dir, exist_ok=True)
    version_file = f"{filename}_v{uuid.uuid4().hex[:6]}.txt"
    version_path = os.path.join(version_dir, version_file)

    with open(version_path, "w", encoding="utf-8") as f:
        f.writelines(merged_lines)

    db.add(Log(
        user_id=current_user.id,
        repo_id=repo_id,
        action="merge_commit_original",
        description=f"Merged commit {commit_id} with original {filename}",
        timestamp=datetime.utcnow()
    ))
    db.commit()

    return {"detail": "Merged successfully", "version_path": version_path}


@router.get("/repositories/{repo_id}/versions")
def list_versions(repo_id: int, filename: str, current_user: User = Depends(get_current_user)):
    version_dir = f"D:/VCS_Storage/user_{current_user.id}/repo_{repo_id}/versions/{filename}"
    if not os.path.exists(version_dir):
        return []
    files = os.listdir(version_dir)
    return [{"version_file": f, "path": os.path.join(version_dir, f)} for f in files]

@router.get("/repositories/{repo_id}/commit_file")
def get_commit_file(repo_id: int, commit_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    # Fetch the commit
    commit = db.query(Commit).filter_by(id=commit_id, repo_id=repo_id).first()
    if not commit:
        raise HTTPException(status_code=404, detail="Commit not found")

    # If it's a merged commit with versioned file (final content)
    if commit.snapshot_path:
        try:
            with open(commit.snapshot_path, "r") as f:
                content = f.read()
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Error reading file: {e}")
    else:
        # It's a proposed commit — find its Snapshot
        snapshot = db.query(Snapshot).filter_by(commit_id=commit.id).first()
        if not snapshot:
            raise HTTPException(status_code=404, detail="Snapshot not found")
        try:
            with open(snapshot.content_path, "r") as f:
                content = f.read()
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Error reading snapshot: {e}")

    return {
        "content": content,
        "status": commit.status,
        "author": commit.author.username,
        "message": commit.message,
        "timestamp": commit.timestamp
    }

