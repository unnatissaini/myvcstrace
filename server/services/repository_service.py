from server.models import Commit, Snapshot, Log
from datetime import datetime
import hashlib
import os

from server.models import AccessControl
from server.constants.access_levels import ADMIN
from sqlalchemy.orm import Session

def assign_admin_access(db: Session, user_id: int, repository_id: int):
    access = AccessControl(
        user_id=user_id,
        repository_id=repository_id,
        access_level=ADMIN
    )
    db.add(access)
    db.commit()
import shutil
import uuid

def create_commit_snapshot(db, repo_id, user_id, message, file_path):
    # Step 1: Create a snapshots folder inside the repo if it doesn't exist
    snapshot_dir = os.path.join(os.path.dirname(file_path), "snapshots")
    os.makedirs(snapshot_dir, exist_ok=True)

    # Step 2: Generate a unique snapshot filename
    original_filename = os.path.basename(file_path)
    unique_name = f"{uuid.uuid4().hex}_{original_filename}"
    snapshot_path = os.path.join(snapshot_dir, unique_name)

    # Step 3: Copy original file to snapshot path
    shutil.copy(file_path, snapshot_path)

    # Step 4: Compute file hash
    with open(snapshot_path, "rb") as f:
        content = f.read()
    content_hash = hashlib.sha256(content).hexdigest()

    # Step 5: Save commit entry
    commit = Commit(
        repo_id=repo_id,
        author_id=user_id,
        message=message,
        snapshot_path=snapshot_path
    )
    db.add(commit)
    db.commit()
    db.refresh(commit)

    # Step 6: Save snapshot entry
    snapshot = Snapshot(
        commit_id=commit.id,
        file_path=snapshot_path,
        content_hash=content_hash,
        size=len(content)
    )
    db.add(snapshot)
    db.commit()
    log_entry = Log(
    user_id=user_id,
    repo_id=repo_id,
    action="commit",
    description=f"Committed file(s) with message: {message}"
    )
    db.add(log_entry)
    db.commit()


    return commit
