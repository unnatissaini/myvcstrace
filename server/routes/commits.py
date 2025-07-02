from fastapi import APIRouter, Form, Depends, HTTPException
from sqlalchemy.orm import Session
from datetime import datetime
import os
import uuid
import pathlib
from server.models import Log, FileVersion, MergeHistory
from server.models import Commit, Snapshot, AccessControl
from server.db import get_db
from server.dependencies import get_current_user
from server.schemas import UserOut
from server.routes.repositories import compute_file_hash

router = APIRouter(prefix="/repositories", tags=["Commits"])
import re

def strip_version_suffix(filename):
    # e.g., a_v1.docs → a.docs
    base, ext = os.path.splitext(filename)
    base = re.sub(r'_v\d+$', '', base)
    return base + ext

@router.post("/{repo_id}/commit")
def create_commit(
    repo_id: int,
    message: str = Form(...),
    filename: str = Form(...),
    content: str = Form(...),
    db: Session = Depends(get_db),
    current_user: UserOut = Depends(get_current_user)
):
    # ✅ 1. Access check
    access = db.query(AccessControl).filter_by(
        user_id=current_user.id,
        repository_id=repo_id
    ).first()
    if not access or access.role not in ("admin", "editor"):
        raise HTTPException(status_code=403, detail="Permission denied")

    # ✅ 2. Normalize the filename
    safe_rel_path = pathlib.Path(filename).as_posix().lstrip("/\\")
    base_name = os.path.splitext(os.path.basename(safe_rel_path))[0]

    # ✅ 3. Commit folder structure: proposed_commits/folder/file/
    commit_folder = os.path.join(
        f"D:/VCS_Storage/user_{current_user.id}/repo_{repo_id}/proposed_commits",
        os.path.dirname(safe_rel_path),
        base_name
    )
    unique_commit_filename = f"{uuid.uuid4()}.txt"
    snapshot_path = os.path.join(commit_folder, unique_commit_filename)

    # ✅ 4. Ensure directory exists
    os.makedirs(os.path.dirname(snapshot_path), exist_ok=True)

    # ✅ 5. Write file content
    with open(snapshot_path, "w", encoding="utf-8") as f:
        f.write(content)

    # ✅ 6. Store commit metadata
    commit = Commit(
        repo_id=repo_id,
        author_id=current_user.id,
        message=message,
        original_filename=safe_rel_path,
        versioned_filename=None,
        snapshot_path=snapshot_path,
        status="proposed"
    )
    db.add(commit)
    db.commit()
    db.refresh(commit)

    return {
        "commit_id": commit.id,
        "message": f"Commit proposed for {safe_rel_path}",
        "snapshot_file": snapshot_path
    }

@router.post("/{repo_id}/revert/{commit_id}")
def revert_commit(
    repo_id: int,
    commit_id: int,
    db: Session = Depends(get_db),
    current_user: UserOut = Depends(get_current_user)
):
    # ✅ 1. Access Control
    access = db.query(AccessControl).filter_by(
        user_id=current_user.id,
        repository_id=repo_id
    ).first()
    if not access or access.role not in ("admin", "editor"):
        raise HTTPException(status_code=403, detail="Permission denied")

    # ✅ 2. Fetch the commit
    commit = db.query(Commit).filter_by(id=commit_id, repo_id=repo_id).first()
    if not commit:
        raise HTTPException(status_code=404, detail="Commit not found")

    # ✅ 3. Read from snapshot
    if not commit.snapshot_path or not os.path.exists(commit.snapshot_path):
        raise HTTPException(status_code=404, detail="Snapshot file missing")

    with open(commit.snapshot_path, "r", encoding="utf-8") as f:
        content_to_restore = f.read()

    # ✅ 4. Restore to original file path
    repo_folder = f"D:/VCS_Storage/user_{current_user.id}/repo_{repo_id}"
    original_path = os.path.join(repo_folder, commit.original_filename)
    os.makedirs(os.path.dirname(original_path), exist_ok=True)

    with open(original_path, "w", encoding="utf-8") as f:
        f.write(content_to_restore)

    # ✅ 5. Update status of the commit to "proposed" again
    commit.status = "proposed"
    db.commit()

    # ✅ 6. Log the revert action (optional)
    log = Log(
        user_id=current_user.id,
        repo_id=repo_id,
        commit_id=commit.id,
        action="revert",
        description=f"Reverted {commit.original_filename} to commit {commit.id}",
        timestamp=datetime.utcnow()
    )
    db.add(log)
    db.commit()

    return {"message": f"File reverted to commit {commit.id}", "filename": commit.original_filename}

@router.post("/{repo_id}/merge/{commit_id}")
def merge_commit_with_file(
    repo_id: int,
    commit_id: int,
    db: Session = Depends(get_db),
    current_user: UserOut = Depends(get_current_user)
):


    # 1. Check access (admin only)
    access = db.query(AccessControl).filter_by(user_id=current_user.id, repository_id=repo_id).first()
    if not access or access.role != "admin":
        raise HTTPException(status_code=403, detail="Only admins can merge commits")

    # 2. Fetch commit
    commit = db.query(Commit).filter_by(id=commit_id, repo_id=repo_id).first()
    if not commit:
        raise HTTPException(status_code=404, detail="Commit not found")
    if commit.status == "merged":
        raise HTTPException(status_code=400, detail="Commit already merged")

    if commit.original_filename and commit.original_filename.startswith("versions/"):
        commit.original_filename = commit.original_filename[len("versions/"):]
    base_name = strip_version_suffix(commit.original_filename or commit.versioned_filename)

    file_version = db.query(FileVersion).filter_by(
        repo_id=repo_id, original_filename=base_name
    ).first()


    if not file_version:
        file_version = FileVersion(
            repo_id=repo_id,
            original_filename=commit.original_filename,
            latest_version=1
        )
        db.add(file_version)
        db.commit()
        db.refresh(file_version)
    else:
        file_version.latest_version += 1
        db.commit()

    # 4. Generate versioned filename
    version_number = file_version.latest_version
    clean_name = strip_version_suffix(commit.original_filename or commit.versioned_filename)
    name, ext = os.path.splitext(clean_name)
    versioned_filename = f"{name}_v{version_number}{ext}"


    # 5. Define file path
    version_path = f"D:/VCS_Storage/user_{current_user.id}/repo_{repo_id}/versions/{versioned_filename}"
    os.makedirs(os.path.dirname(version_path), exist_ok=True)

    # 6. Write merged content to version file
    with open(version_path, "w", encoding="utf-8") as f:
        with open(commit.snapshot_path, "r", encoding="utf-8") as source:
            content = source.read()
            f.write(content)

    # 7. Update original commit
    commit.status = "merged"
    db.commit()

    # 8. Create new merged commit
    merged_commit = Commit(
        repo_id=repo_id,
        author_id=current_user.id,
        message=f"Merged commit {commit.id} into version {versioned_filename}",
        parent_commit_id=commit.id,
        original_filename=commit.original_filename,
        versioned_filename=versioned_filename,
        snapshot_path=version_path,
        status="merged"
    )
    db.add(merged_commit)
    db.commit()
    db.refresh(merged_commit)

    # 9. Record merge history (optional)
    merge_record = MergeHistory(
        repo_id=repo_id,
        base_commit_id=None,
        merged_commit_id=commit.id,
        result_commit_id=merged_commit.id,
        result_filename=versioned_filename,
        merged_by=current_user.id
    )
    db.add(merge_record)
    db.commit()

    return {"message": f"Commit merged as {versioned_filename}", "commit_id": merged_commit.id}
