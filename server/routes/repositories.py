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

@router.delete("/{repo_id}/file", status_code=204)
def delete_file_in_repo(
    repo_id: int,
    data: DeleteFileInput = Body(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):

    role = get_user_access_level(db, user_id=current_user.id, repo_id=repo_id)
    if not can_write_repo(role):
        raise HTTPException(status_code=403, detail=f"Insufficient permission to delete file. Role: {role}")

    if not os.path.exists(data.file_path):
        raise HTTPException(status_code=404, detail="File not found.")

    os.remove(data.file_path)

    log = Log(
        user_id=current_user.id,
        repo_id=repo_id,
        action="delete_file",
        description=f"Deleted file {data.file_path}",
        timestamp=datetime.utcnow()
    )
    db.add(log)
    db.commit()

    return {"detail": "File deleted successfully."}


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



from fastapi import Body

@router.post("/{repo_id}/merge_versions")
def merge_versions(
    repo_id: int,
    filename: str = Form(...),
    version1_path: str = Form(...),
    version2_path: str = Form(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    # ✅ Check admin access
    access = db.query(AccessControl).filter_by(user_id=current_user.id, repository_id=repo_id).first()
    if not access or access.role != "admin":
        raise HTTPException(status_code=403, detail="Only admins can merge versions.")

    # ✅ Ensure both files exist
    if not os.path.exists(version1_path) or not os.path.exists(version2_path):
        raise HTTPException(status_code=404, detail="One or both version files not found.")

    # ✅ Read both files
    with open(version1_path, "r", encoding="utf-8") as f1, open(version2_path, "r", encoding="utf-8") as f2:
        lines1 = f1.readlines()
        lines2 = f2.readlines()

    # ✅ Basic merge strategy: include all unique lines
    merged_lines = []
    max_len = max(len(lines1), len(lines2))
    for i in range(max_len):
        if i < len(lines1):
            merged_lines.append(lines1[i])
        if i < len(lines2) and lines2[i] != lines1[i] if i < len(lines1) else True:
            merged_lines.append(lines2[i])

    # ✅ Save merged version
    version_dir = f"D:/VCS_Storage/user_{current_user.id}/repo_{repo_id}/versions/{filename}"
    os.makedirs(version_dir, exist_ok=True)
    merged_filename = f"{uuid.uuid4()}_{filename}"
    merged_path = os.path.join(version_dir, merged_filename)

    with open(merged_path, "w", encoding="utf-8") as f:
        f.writelines(merged_lines)

    # ✅ Log the merge
    log = Log(
        user_id=current_user.id,
        repo_id=repo_id,
        action="merge_versions",
        description=f"Merged two versions of {filename}",
        timestamp=datetime.utcnow()
    )
    db.add(log)
    db.commit()

    return {
        "detail": "Files merged successfully.",
        "merged_version_path": merged_path
    }
@router.post("/{repo_id}/create_version")
def create_version(
    repo_id: int,
    filename: str = Form(...),
    source_path: str = Form(...),  # can be merged file or snapshot file
    db: Session = Depends(get_db),
    current_user: UserOut = Depends(get_current_user)
):
    # ✅ Check admin access
    access = db.query(AccessControl).filter_by(user_id=current_user.id, repository_id=repo_id).first()
    if not access or access.role != "admin":
        raise HTTPException(status_code=403, detail="Only admins can create official versions.")

    if not os.path.exists(source_path):
        raise HTTPException(status_code=404, detail="Source file not found.")

    # ✅ Determine version number
    version_dir = f"D:/VCS_Storage/user_{current_user.id}/repo_{repo_id}/versioned/{filename}"
    os.makedirs(version_dir, exist_ok=True)
    existing_versions = [f for f in os.listdir(version_dir) if f.startswith(filename)]
    version_number = len(existing_versions) + 1

    # ✅ Save approved version
    version_name = f"{filename}_v{version_number}"
    version_path = os.path.join(version_dir, version_name)
    shutil.copyfile(source_path, version_path)

    # ✅ Log the version creation
    log = Log(
        user_id=current_user.id,
        repo_id=repo_id,
        action="create_version",
        description=f"Created version {version_number} for {filename}",
        timestamp=datetime.utcnow()
    )
    db.add(log)
    db.commit()

    return {
        "detail": f"Version {version_number} created.",
        "version_path": version_path
    }


@router.post("/repositories/{repo_id}/merge_commits")
def merge_commits(
    repo_id: int,
    file_path: str,
    commit_ids: List[int],
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    # Access check
    access = db.query(AccessControl).filter_by(user_id=current_user.id, repository_id=repo_id).first()
    if not access:
        raise HTTPException(status_code=403, detail="Access denied")

    # Fetch commits
    commits = db.query(Commit).filter(Commit.id.in_(commit_ids), Commit.repo_id == repo_id).all()
    if len(commits) != len(commit_ids):
        raise HTTPException(status_code=404, detail="One or more commits not found")

    # Merge logic - here simple: concatenate content
    merged_content = "\n".join([commit.content for commit in commits])

    # Create new version file (save merged_content to disk if needed)
    version_path = save_merged_file_to_disk(merged_content, file_path)

    # Create new commit
    new_commit = Commit(
        repo_id=repo_id,
        author_id=current_user.id,
        file_path=file_path,
        message="Merged commits: " + ", ".join(map(str, commit_ids)),
        content=merged_content,
        version_path=version_path,
        status="merged"
    )
    db.add(new_commit)
    db.commit()
    db.refresh(new_commit)

    return {"commit_id": new_commit.id, "message": new_commit.message, "status": new_commit.status}

@router.post("/{repo_id}/merge")
def merge_commits(
    repo_id: int,
    data: dict = Body(...),
    db: Session = Depends(get_db),
    current_user: UserOut = Depends(get_current_user)
):
    file_name = data.get("file_name")
    commit_ids = data.get("commit_ids", [])
    target = data.get("target", "new")

    if not file_name or len(commit_ids) < 2:
        raise HTTPException(status_code=400, detail="Invalid merge request")

    # Check access
    access = db.query(AccessControl).filter_by(user_id=current_user.id, repository_id=repo_id).first()
    if not access or access.role not in ("admin", "editor"):
        raise HTTPException(status_code=403, detail="Permission denied")

    # Fetch commits
    commits = db.query(Commit).filter(Commit.id.in_(commit_ids), Commit.repo_id==repo_id, Commit.original_filename==file_name).all()
    if len(commits) != len(commit_ids):
        raise HTTPException(status_code=404, detail="One or more commits not found")

    # Merge contents (basic concat, can enhance later)
    merged_content = ""
    for c in commits:
        if c.content:
            merged_content += c.content + "\n"
        elif c.version_path and os.path.exists(c.version_path):
            with open(c.version_path, "r", encoding="utf-8") as f:
                merged_content += f.read() + "\n"

    repo_folder = f"D:/VCS_Storage/user_{current_user.id}/repo_{repo_id}"

    if target == "main":
        target_path = os.path.join(repo_folder, file_name)
    else:
        # Create a new merged file
        base_name, ext = os.path.splitext(file_name)
        new_file_name = f"{base_name}_merged_{datetime.utcnow().strftime('%Y%m%d%H%M%S')}{ext}"
        target_path = os.path.join(repo_folder, new_file_name)
        file_name = new_file_name  # update for commit

    os.makedirs(os.path.dirname(target_path), exist_ok=True)
    with open(target_path, "w", encoding="utf-8") as f:
        f.write(merged_content)

    # Save merge commit
    merge_commit = Commit(
        repo_id=repo_id,
        author_id=current_user.id,
        message=f"Merged commits {', '.join(map(str, commit_ids))}",
        parent_commit_id=commit_ids[-1],
        file_path=file_name,
        content=merged_content,
        status="merged"
    )
    db.add(merge_commit)
    db.commit()

    return {"message": f"Commits merged into {'main file' if target=='main' else file_name}"}
