from fastapi import APIRouter, Depends, UploadFile, File, Form, HTTPException ,Body
from sqlalchemy.orm import Session
from server.db import get_db
import shutil , zipfile, os , uuid ,hashlib 
from typing import List
from server.services.repository_service import create_commit_snapshot
from server.services.access_control import assign_admin_access , set_user_access_level
from server.models import Snapshot, Commit
from datetime import datetime, timedelta
from sqlalchemy.exc import IntegrityError
from server.models import Repository, Log, User, AccessControl
from server.dependencies import get_db, get_current_user, AccessControlInput
from server.services.access_control import get_user_access_level, has_write_access, get_user_repo_access, can_read_repo, can_write_repo
from server.schemas import DeleteRepoInput,DeleteFileInput , RepositoryUpdate ,LogOut ,UserOut , SetAccessLevelInput, Role
from server.constants.access_levels import ADMIN, WRITE
from server.dependencies import get_current_user
from server.models import AccessControl, Log
from pydantic import BaseModel
from uuid import uuid4
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
        visibility="private" if is_private else "public",
        description=description
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
        "description": repo.description,
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

@router.delete("/{repo_id}/file")
def delete_file(
    repo_id: int,
    payload: DeleteFileRequest = Body(...),
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
   
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
    
    now = datetime.now()
    threshold = now - timedelta(days=30)

    for root, files in os.walk(trash_dir):
        for filename in files:
            file_path = os.path.join(root, filename)
            try:
                file_mtime = datetime.fromtimestamp(os.path.getmtime(file_path))
                if file_mtime < threshold:
                    os.remove(file_path)
            except Exception as e:
                print(f"Failed to delete {file_path}: {e}")
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
from fastapi import Query

@router.post("/{repo_id}/restore_file")
def restore_file(
    repo_id: int,
    filename: str = Query(..., alias="filename"),
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    access = db.query(AccessControl).filter_by(user_id=current_user.id, repository_id=repo_id).first()
    if not access:
        raise HTTPException(status_code=403, detail="Permission denied")

    repo_path = f"D:/VCS_Storage/user_{current_user.id}/repo_{repo_id}"
    trash_path = os.path.join(repo_path, ".trash", filename)
    original_path = os.path.join(repo_path, filename)

    if not os.path.exists(trash_path):
        raise HTTPException(status_code=404, detail="File not found in trash")

    os.makedirs(os.path.dirname(original_path), exist_ok=True)
    shutil.move(trash_path, original_path)

    log = Log(
        user_id=current_user.id,
        repo_id=repo_id,
        action="restore_file",
        description=f"Restored file: {filename}",
        timestamp=datetime.utcnow()
    )
    db.add(log)
    db.commit()

    return {"detail": f"Restored: {filename}"}

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

    # Prevent the owner from changing their own access
    if access.user_id == current_user.id:
        raise HTTPException(status_code=400, detail="You cannot change your own access role")

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
    log = Log(
        user_id=current_user.id,
        repo_id=repo_id,
        action="update_access",
        description=f"Changed access of user {access.user_id} to role '{access.role}'",
        timestamp=datetime.utcnow()
    )
    db.add(log)

    db.commit()
    return {"detail": "Access updated successfully"}


@router.post("/{repo_id}/snapshot_repo")
def snapshot_whole_repository(
    repo_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    # Step 1: Verify access
    repo = db.query(Repository).filter_by(id=repo_id).first()
    if not repo:
        raise HTTPException(status_code=404, detail="Repository not found")

    access = db.query(AccessControl).filter_by(user_id=current_user.id, repository_id=repo_id).first()
    if not access or access.role != "admin":
        raise HTTPException(status_code=403, detail="Only admins can snapshot the full repo.")

    # Step 2: Define paths
    repo_path = f"D:/VCS_Storage/user_{current_user.id}/repo_{repo.id}"
    if not os.path.exists(repo_path):
        raise HTTPException(status_code=404, detail="Repository folder not found.")

    # Use Option 3: embed repo name and id in zip
    safe_repo_name = repo.name.replace(" ", "_").replace("/", "_")  # optional: sanitize
    snapshot_filename = f"{safe_repo_name}__{repo.id}__{uuid4().hex}.zip"
    zip_path = os.path.join(f"D:/VCS_Storage/user_{current_user.id}", snapshot_filename)

    # Step 3: Zip the repository
    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for root, _, files in os.walk(repo_path):
            for file in files:
                file_path = os.path.join(root, file)
                arcname = os.path.relpath(file_path, repo_path)
                zipf.write(file_path, arcname)

    # Step 4: Metadata
    content_hash = compute_file_hash(zip_path)
    size = os.path.getsize(zip_path)

    # Step 5: Save in DB
    snapshot = Snapshot(
        commit_id=None,
        file_path=zip_path,
        content_hash=content_hash,
        size=size,
        created_at=datetime.utcnow(),
        is_deleted=False,
        operation="repo_snapshot"
    )
    db.add(snapshot)
    db.commit()
    db.refresh(snapshot)

    return {
        "detail": "Snapshot created.",
        "snapshot_id": snapshot.id,
        "file_name": snapshot_filename,
        "repo": repo.name,
        "hash": snapshot.content_hash,
        "size": size
    }

@router.post("/{repo_id}/create_file")
def create_new_file(
    repo_id: int,
    filename: str = Form(...),
    content: str = Form(""),  # optional content
    db: Session = Depends(get_db),
    current_user: UserOut = Depends(get_current_user)
):    
    access = db.query(AccessControl).filter_by(user_id=current_user.id, repository_id=repo_id).first()
    if not access or access.role not in ("admin", "editor","collaborator"):
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
    log = Log(
        user_id=current_user.id,
        repo_id=repo_id,
        action="create_file",  # or "create_folder"
        description=f"Created file: {filename}",  # or folder
        timestamp=datetime.utcnow()
    )
    db.add(log)
    db.commit()

    return {"message": "File created", "filename": filename}

@router.post("/{repo_id}/create_folder")
def create_folder(
    repo_id: int,
    filename: str = Form(...),
    db: Session = Depends(get_db),
    current_user: UserOut = Depends(get_current_user)
):
    access = db.query(AccessControl).filter_by(user_id=current_user.id, repository_id=repo_id).first()
    if not access or access.role not in ("admin", "editor","collaborator"):
        raise HTTPException(status_code=403, detail="Permission denied")

    repo_folder = f"D:/VCS_Storage/user_{current_user.id}/repo_{repo_id}"
    folder_path = os.path.join(repo_folder, filename)
    os.makedirs(folder_path, exist_ok=True)
    log = Log(
        user_id=current_user.id,
        repo_id=repo_id,
        action="create_folder",  # or "create_folder"
        description=f"Created file: {filename}",  # or folder
        timestamp=datetime.utcnow()
    )
    db.add(log)
    db.commit()

    return {"message": "Folder created", "folder": filename}


def format_date(date: datetime) -> str:
    day = date.day
    suffix_str = suffix(day)
    formatted_date = date.strftime(f"%b %Y")  # Jan 2025
    return f"{day}{suffix_str} {formatted_date}"  # e.g., 1st Jan 2025

def suffix(day: int) -> str:
    if 11 <= day <= 13:
        return "th"
    return {1: "st", 2: "nd", 3: "rd"}.get(day % 10, "th")


@router.get("/public-repositories")
def get_public_repositories(db: Session = Depends(get_db)):
    public_repos = db.query(Repository).filter(Repository.visibility == "public").all()

    return [
        {
            "id": repo.id,
            "name": repo.name,
            "description": repo.description or "—",
            "owner": repo.owner.username,
            "created_at": format_date(repo.created_at), 
        }
        for repo in public_repos
    ]