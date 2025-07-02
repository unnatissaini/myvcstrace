from fastapi import APIRouter, Depends, UploadFile, File, Form, HTTPException ,Body
from sqlalchemy.orm import Session
from server.db import get_db
import shutil
import os
from typing import List
from server.services.repository_service import create_commit_snapshot
from server.services.access_control import assign_admin_access , set_user_access_level
from server.models import Snapshot, Commit
import hashlib
from datetime import datetime
from sqlalchemy.exc import IntegrityError
from server.models import Repository, Log, User, AccessControl
from server.dependencies import get_db, get_current_user, AccessControlInput
from server.services.access_control import get_user_access_level, has_write_access, get_user_repo_access, can_read_repo, can_write_repo
from server.schemas import DeleteRepoInput,DeleteFileInput , RepositoryUpdate ,LogOut ,UserOut , SetAccessLevelInput
from server.constants.access_levels import ADMIN, WRITE
from server.schemas import Role
import uuid
import zipfile
from server.dependencies import get_current_user
from server.db import get_db
from server.models import AccessControl, Log
from pydantic import BaseModel
import os
from datetime import datetime
router = APIRouter(
    prefix="/repositories",
    tags=["repositories"]
)
def get_repository(repo_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    repo = db.query(Repository).filter_by(id=repo_id).first()
    if not repo:
        raise HTTPException(status_code=404, detail="Repository not found")

    role = get_user_repo_access(db, current_user.id, repo_id)

    if can_read_repo(repo, role):
        return repo

   


def compute_file_hash(file_path: str) -> str:
    hasher = hashlib.sha256()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


@router.post("/create")
def create_repository(
    name: str = Form(...),
    description: str = Form(""),
    is_private: bool = Form(False),
    file: UploadFile | None = File(None),  
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # Create repository DB entry
    repo = Repository(
        name=name,
        owner_id=current_user.id,
        visibility="private" if is_private else "public"
    )
    db.add(repo)
    db.commit()
    db.refresh(repo)

    # Assign admin access
    assign_admin_access(db, user_id=current_user.id, repository_id=repo.id)

    file_path = None

    # If file is uploaded, save it
    if file:
        upload_dir = f"D:/VCS_Storage/user_{current_user.id}/repo_{repo.id}"
        os.makedirs(upload_dir, exist_ok=True)
        file_path = os.path.join(upload_dir, file.filename)
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
    else:
        # ✅ Still create the directory even if no file uploaded
        upload_dir = f"D:/VCS_Storage/user_{current_user.id}/repo_{repo.id}"
        os.makedirs(upload_dir, exist_ok=True)
        file_path = None
    # Log creation
    log_entry = Log(
        user_id=current_user.id,
        repo_id=repo.id,
        action="create_repo",
        description=f"Repository '{repo.name}' created."
    )
    db.add(log_entry)
    db.commit()

    return {
        "repo_id": repo.id,
        "repo_name": repo.name,
        "file_uploaded": file.filename if file else None,
        "saved_to": file_path if file else "No file uploaded"
    }
@router.post("/{repo_id}/upload")
def upload_file_to_repo(
    repo_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user)
):
    # Check access control
    access = db.query(AccessControl).filter_by(user_id=current_user.id, repository_id=repo_id).first()
    if not access or not can_write_repo(access.role):
        raise HTTPException(status_code=403, detail="You do not have permission to upload to this repository.")

    # Proceed with upload
    upload_dir = f"D:/VCS_Storage/user_{current_user.id}/repo_{repo_id}"
    os.makedirs(upload_dir, exist_ok=True)

    file_path = os.path.join(upload_dir, file.filename)
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    log_entry = Log(
        user_id=current_user.id,
        repo_id=repo_id,
        action="upload_file",
        description=f"Uploaded file '{file.filename}' to path '{file_path}'"
    )
    db.add(log_entry)
    db.commit()

    return {
        "repo_id": repo_id,
        "file_uploaded": file.filename,
        "saved_to": file_path
    }


@router.get("/{repo_id}/log")
def get_logs(repo: Repository = Depends(get_repository), db: Session = Depends(get_db)):
    logs = db.query(Log).filter_by(repo_id=repo.id).all()
    return logs



@router.get("/users/{user_id}/log", response_model=List[LogOut])
def get_user_log(user_id: int, db: Session = Depends(get_db)):
    logs = db.query(Log).filter(Log.user_id == user_id).order_by(Log.timestamp.desc()).all()
    return logs


@router.put("/{repo_id}")
def update_repository(
    repo_id: int,
    repo_update: RepositoryUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    repo = db.query(Repository).filter(Repository.id == repo_id).first()
    if not repo:
        raise HTTPException(status_code=404, detail="Repository not found")

    access_level = get_user_access_level(db, current_user.id, repo_id)
    if not has_write_access(access_level):
        raise HTTPException(status_code=403, detail="Write access required")

    repo.name = repo_update.name or repo.name
    repo.description = repo_update.description or repo.description
    repo.is_public = repo_update.is_public if repo_update.is_public is not None else repo.is_public

    db.commit()
    db.refresh(repo)
    log_entry = Log(
    user_id=current_user.id,
    repo_id=repo.id,
    action="update_repo",
    details=f"Updated repository: name='{repo.name}', description='{repo.description}', is_public={repo.is_public}"
    )
    db.add(log_entry)
    db.commit()

    return {"message": "Repository updated", "repository": repo}

@router.delete("/{repo_id}")
def delete_repository(
    repo_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # Check if user is admin of the repo
    access = db.query(AccessControl).filter_by(
        user_id=current_user.id,
        repository_id=repo_id
    ).first()

    if not access or access.role != "admin":
        raise HTTPException(status_code=403, detail="Only admin can delete this repository.")

    repo = db.query(Repository).filter_by(id=repo_id).first()
    if not repo:
        raise HTTPException(status_code=404, detail="Repository not found.")
    log = Log(
        user_id=current_user.id,
        action="delete",
        repo_id=repo_id,
        description=f"Repository '{repo.name}' deleted by user '{current_user.username}'"
    )
    db.add(log)
    db.commit()
    # Delete local folder
    repo_path = f"D:/VCS_Storage/user_{current_user.id}/repo_{repo.id}"
    if os.path.exists(repo_path):
        shutil.rmtree(repo_path)

    db.delete(repo)
    db.commit()

    
    

    return {"detail": f"Repository '{repo.name}' deleted successfully."}



class DeleteFileRequest(BaseModel):
    file_path: str  # relative path from repo root
import shutil

@router.delete("/{repo_id}/file")
def delete_file(
    repo_id: int,
    payload: DeleteFileRequest = Body(...),
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    # Access check (same as before)
    access = db.query(AccessControl).filter_by(
        user_id=current_user.id,
        repository_id=repo_id
    ).first()
    if not access or access.role not in ("admin", "editor", "collaborator"):
        raise HTTPException(status_code=403, detail="No permission to delete file.")

    # Paths
    repo_path = f"D:/VCS_Storage/user_{current_user.id}/repo_{repo_id}"
    file_path = os.path.join(repo_path, payload.file_path)
    trash_dir = os.path.join(repo_path, ".trash")
    trashed_path = os.path.join(trash_dir, payload.file_path)

    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="File not found.")

    try:
        os.makedirs(os.path.dirname(trashed_path), exist_ok=True)
        shutil.move(file_path, trashed_path)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to move to trash: {e}")

    # Log the deletion
    log = Log(
        user_id=current_user.id,
        repo_id=repo_id,
        action="delete_file",
        description=f"Moved to trash: {payload.file_path}",
        timestamp=datetime.utcnow()
    )
    db.add(log)
    db.commit()

    return {"detail": f"File moved to trash: {payload.file_path}"}
@router.post("/{repo_id}/restore_file")
def restore_file(
    repo_id: int,
    payload: DeleteFileRequest = Body(...),
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    access = db.query(AccessControl).filter_by(user_id=current_user.id, repository_id=repo_id).first()
    if not access:
        raise HTTPException(status_code=403, detail="Permission denied")

    repo_path = f"D:/VCS_Storage/user_{current_user.id}/repo_{repo_id}"
    trash_path = os.path.join(repo_path, ".trash", payload.file_path)
    original_path = os.path.join(repo_path, payload.file_path)

    if not os.path.exists(trash_path):
        raise HTTPException(status_code=404, detail="File not found in trash")

    os.makedirs(os.path.dirname(original_path), exist_ok=True)
    shutil.move(trash_path, original_path)

    log = Log(
        user_id=current_user.id,
        repo_id=repo_id,
        action="restore_file",
        description=f"Restored file: {payload.file_path}",
        timestamp=datetime.utcnow()
    )
    db.add(log)
    db.commit()

    return {"detail": f"Restored: {payload.file_path}"}

@router.get("/{repo_id}/trash_files")
def list_trashed_files(
    repo_id: int,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    access = db.query(AccessControl).filter_by(user_id=current_user.id, repository_id=repo_id).first()
    if not access:
        raise HTTPException(status_code=403, detail="Access denied")

    trash_dir = f"D:/VCS_Storage/user_{current_user.id}/repo_{repo_id}/.trash"
    if not os.path.exists(trash_dir):
        return []

    files = []
    for root, _, filenames in os.walk(trash_dir):
        for name in filenames:
            full_path = os.path.join(root, name)
            rel_path = os.path.relpath(full_path, trash_dir)
            files.append(rel_path.replace("\\", "/"))

    return files

@router.put("/{repo_id}/visibility")
def change_visibility(repo_id: int, visibility: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    if visibility not in ["public", "private"]:
        raise HTTPException(status_code=400, detail="Invalid visibility option")

    access = db.query(AccessControl).filter_by(user_id=current_user.id, repository_id=repo_id).first()
    if not access or access.role != "admin":
        raise HTTPException(status_code=403, detail="Only admin can change visibility")

    repo = db.query(Repository).filter_by(id=repo_id).first()
    if not repo:
        raise HTTPException(status_code=404, detail="Repository not found")

    repo.visibility = visibility
    db.commit()
    return {"detail": f"Visibility changed to {visibility}"}

@router.post("/{repo_id}/access-control")
def update_access_control(
    repo_id: int,
    access: AccessControlInput,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    # Only the repository owner can assign access
    repo = db.query(Repository).filter(Repository.id == repo_id).first()
    if not repo:
        raise HTTPException(status_code=404, detail="Repository not found")

    if repo.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Only the owner can grant access")

    # Check if access already exists
    existing = db.query(AccessControl).filter_by(
        repository_id=repo_id,
        user_id=access.user_id
    ).first()

    if existing:
        existing.role = access.role
    else:
        db.add(AccessControl(
            repository_id=repo_id,
            user_id=access.user_id,
            role=access.role
        ))

    db.commit()
    return {"detail": "Access updated successfully"}


@router.post("/{repo_id}/snapshot_repo")
def snapshot_whole_repository(
    repo_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    # Step 1: Permission check
    access = db.query(AccessControl).filter_by(user_id=current_user.id, repository_id=repo_id).first()
    if not access or access.role != "admin":
        raise HTTPException(status_code=403, detail="Only admins can snapshot the full repo.")

    # Step 2: Define source and zip file path
    repo_folder = f"D:/VCS_Storage/user_{current_user.id}"
    if not os.path.exists(repo_folder):
        raise HTTPException(status_code=404, detail="Repository folder not found.")

    snapshot_filename = f"{uuid.uuid4()}_full_repo_snapshot.zip"
    zip_path = os.path.join(repo_folder, snapshot_filename)

    # Step 3: Create zip of the whole repository
    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for root, _, files in os.walk(repo_folder):
            for file in files:
                if file != snapshot_filename:  # Avoid zipping itself
                    file_path = os.path.join(root, file)
                    arcname = os.path.relpath(file_path, repo_folder)
                    zipf.write(file_path, arcname)

    # Step 4: Compute file hash and size
    content_hash = compute_file_hash(zip_path)
    file_size = os.path.getsize(zip_path)

    # Step 5: Save snapshot entry
    snapshot = Snapshot(
        commit_id=None,  # No specific commit
        file_path=zip_path,
        content_hash=content_hash,
        size=file_size,
        created_at=datetime.utcnow(),
        is_deleted=False,
        operation="add"
    )
    db.add(snapshot)
    db.commit()
    db.refresh(snapshot)

    return {
        "detail": "Repository snapshot created.",
        "snapshot_id": snapshot.id,
        "file": snapshot.file_path,
        "hash": snapshot.content_hash,
        "size": snapshot.size
    }

from fastapi import Form

@router.post("/{repo_id}/create_file")
def create_new_file(
    repo_id: int,
    filename: str = Form(...),
    content: str = Form(""),  # optional content
    db: Session = Depends(get_db),
    current_user: UserOut = Depends(get_current_user)
):    
    access = db.query(AccessControl).filter_by(user_id=current_user.id, repository_id=repo_id).first()
    if not access or access.role not in ("admin", "editor"):
        raise HTTPException(status_code=403, detail="Permission denied")

    repo_folder = f"D:/VCS_Storage/user_{current_user.id}/repo_{repo_id}"
    os.makedirs(repo_folder, exist_ok=True)
    file_path = os.path.join(repo_folder, filename)

    # Check for existing file
    if os.path.exists(file_path):
        raise HTTPException(status_code=409, detail="File already exists")

    # Write content
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(content or "")

    return {"message": "File created", "filename": filename}

@router.post("/{repo_id}/create_folder")
def create_folder(
    repo_id: int,
    filename: str = Form(...),
    db: Session = Depends(get_db),
    current_user: UserOut = Depends(get_current_user)
):
    access = db.query(AccessControl).filter_by(user_id=current_user.id, repository_id=repo_id).first()
    if not access or access.role not in ("admin", "editor"):
        raise HTTPException(status_code=403, detail="Permission denied")

    repo_folder = f"D:/VCS_Storage/user_{current_user.id}/repo_{repo_id}"
    folder_path = os.path.join(repo_folder, filename)
    os.makedirs(folder_path, exist_ok=True)

    return {"message": "Folder created", "folder": filename}

