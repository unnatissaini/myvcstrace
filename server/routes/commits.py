from fastapi import APIRouter, Form, Depends, HTTPException
from sqlalchemy.orm import Session
from datetime import datetime
import os
import uuid
import pathlib
from server.models import Log, FileVersion, MergeHistory, User ,Commit, Snapshot, AccessControl
from server.db import get_db
from server.dependencies import get_current_user
from server.schemas import UserOut
from server.routes.repositories import compute_file_hash
from fpdf import FPDF
from server.utils.diff_utils import generate_diff
from docx import Document

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

    # ✅ 2. Normalize path
    safe_rel_path = pathlib.Path(filename).as_posix().lstrip("/\\")
    if not safe_rel_path.endswith(".txt"):
        safe_rel_path = os.path.splitext(safe_rel_path)[0] + ".txt"

    full_path = os.path.join(f"D:/VCS_Storage/user_{current_user.id}/repo_{repo_id}", safe_rel_path)
    ext = ".txt"


    # ✅ 3. If it's a text file, generate diff
    if ext == ".txt":
        original = ""
        if os.path.exists(full_path):
            with open(full_path, "r", encoding="utf-8") as f:
                original = f.read()

        diff = generate_diff(original, content)

        commit = Commit(
            repo_id=repo_id,
            author_id=current_user.id,
            message=message,
            original_filename=safe_rel_path,
            versioned_filename=None,
            snapshot_path=None,
            diff_text=diff,
            status="proposed"
        )
        db.add(commit)
        db.commit()
        db.refresh(commit)

        return {
            "commit_id": commit.id,
            "message": f"Text commit created with diff for {safe_rel_path}",
            "type": "diff"
        }

    # ✅ 4. If it's a non-text file (e.g., PDF, DOCX), store full snapshot
    else:
        commit_folder = os.path.join(
            f"D:/VCS_Storage/user_{current_user.id}/repo_{repo_id}/proposed_commits",
            os.path.dirname(safe_rel_path),
            os.path.splitext(os.path.basename(safe_rel_path))[0]
        )
        os.makedirs(commit_folder, exist_ok=True)

        ext = os.path.splitext(safe_rel_path)[1]
        unique_filename = f"{uuid.uuid4()}{ext}"
        snapshot_path = os.path.join(commit_folder, unique_filename)

        # Save content to snapshot
        try:
            with open(snapshot_path, "w", encoding="utf-8") as f:
                f.write(content)
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to save snapshot: {e}")

        commit = Commit(
            repo_id=repo_id,
            author_id=current_user.id,
            message=message,
            original_filename=safe_rel_path,
            versioned_filename=None,
            snapshot_path=snapshot_path,
            diff_text=None,
            status="proposed"
        )
        db.add(commit)
        db.commit()
        db.refresh(commit)

        return {
            "commit_id": commit.id,
            "message": f"Binary commit stored with snapshot for {safe_rel_path}",
            "snapshot_file": snapshot_path,
            "type": "snapshot"
        }
@router.post("/{repo_id}/revert/{commit_id}")
def revert_commit(
    repo_id: int,
    commit_id: int,
    db: Session = Depends(get_db),
    current_user: UserOut = Depends(get_current_user)
):
    access = db.query(AccessControl).filter_by(user_id=current_user.id, repository_id=repo_id).first()
    if not access or access.role not in ("admin", "editor"):
        raise HTTPException(status_code=403, detail="Permission denied")

    commit = db.query(Commit).filter_by(id=commit_id, repo_id=repo_id).first()
    if not commit:
        raise HTTPException(status_code=404, detail="Commit not found")

    # ✅ Undo merge
    if commit.status == "merged":
        version_path = os.path.join(
            f"D:/VCS_Storage/user_{current_user.id}/repo_{repo_id}/versions",
            commit.versioned_filename
        )
        if os.path.exists(version_path):
            os.remove(version_path)

        commit.status = "proposed"
        commit.versioned_filename = None
        db.commit()

        db.add(Log(
            user_id=current_user.id,
            repo_id=repo_id,
            commit_id=commit.id,
            action="revert",
            description=f"Undo merge of commit #{commit.id}",
            timestamp=datetime.utcnow()
        ))
        db.commit()

        return {"message": f"Merged version reverted. Commit #{commit.id} is now proposed again."}

    # ✅ Restore deleted file
    original_path = os.path.join(
        f"D:/VCS_Storage/user_{current_user.id}/repo_{repo_id}",
        commit.original_filename
    )

    if os.path.exists(original_path):
        raise HTTPException(status_code=400, detail="File already exists")

    content = ""
    if commit.diff_text:
        content = apply_diff("", commit.diff_text)
    elif commit.snapshot_path and os.path.exists(commit.snapshot_path):
        with open(commit.snapshot_path, "r", encoding="utf-8") as f:
            content = f.read()
    else:
        raise HTTPException(status_code=404, detail="No diff/snapshot to restore")

    os.makedirs(os.path.dirname(original_path), exist_ok=True)
    with open(original_path, "w", encoding="utf-8") as f:
        f.write(content)

    db.add(Log(
        user_id=current_user.id,
        repo_id=repo_id,
        commit_id=commit.id,
        action="revert",
        description=f"Restored deleted file from commit #{commit.id}",
        timestamp=datetime.utcnow()
    ))
    db.commit()

    return {"message": f"File restored from commit {commit.id}"}

from fastapi.responses import FileResponse
import os
import re

import os
import re

def get_next_flat_version_filename(folder: str, filename: str) -> str:
    """
    Extracts base from given filename and finds next flat version filename.
    Handles both commit merges and version-version merges.
    """
    name, ext = os.path.splitext(os.path.basename(filename))
    base = re.sub(r"_v\d+$", "", name)

    pattern = re.compile(rf"^{re.escape(base)}_v(\d+){re.escape(ext)}$")
    max_version = 0

    for f in os.listdir(folder):
        match = pattern.match(f)
        if match:
            max_version = max(max_version, int(match.group(1)))

    return f"{base}_v{max_version + 1}{ext}"


from fastapi import Body
from typing import List, Optional


@router.post("/{repo_id}/merge")
def merge_multiple_commits_or_versions(
    repo_id: int,
    file_name: Optional[str] = Body(None),
    commit_ids: List[int] = Body(...),
    db: Session = Depends(get_db),
    current_user: UserOut = Depends(get_current_user)
):
    # ✅ Access check
    access = db.query(AccessControl).filter_by(
        user_id=current_user.id,
        repository_id=repo_id
    ).first()
    if not access or access.role != "admin":
        raise HTTPException(status_code=403, detail="Only admins can merge.")

    if len(commit_ids) < 2:
        raise HTTPException(status_code=400, detail="At least 2 commits required to merge.")

    commits = db.query(Commit).filter(Commit.id.in_(commit_ids)).all()

    if len(commits) != len(commit_ids):
        raise HTTPException(status_code=404, detail="Some commits not found.")

    # ✅ All commits must be from the same file lineage
    filenames = {strip_version_suffix(c.original_filename or c.versioned_filename) for c in commits}
    if len(filenames) != 1:
        raise HTTPException(status_code=400, detail="Commits must belong to the same original file.")

    # ✅ Combine content from all commits (you can choose smarter merge logic)
    merged_content = ""
    from server.utils.diff_utils import apply_diff

    repo_root = f"D:/VCS_Storage/user_{current_user.id}/repo_{repo_id}"

    for commit in commits:
        content = ""
        if commit.diff_text:
            original_path = os.path.join(repo_root, commit.original_filename)
            base_content = ""
            if os.path.exists(original_path):
                with open(original_path, "r", encoding="utf-8") as f:
                    base_content = f.read()
            content = apply_diff(base_content, commit.diff_text)

        elif commit.snapshot_path and os.path.exists(commit.snapshot_path):
            with open(commit.snapshot_path, "r", encoding="utf-8") as f:
                content = f.read()
        else:
            raise HTTPException(status_code=404, detail=f"No valid snapshot or diff for commit {commit.id}")

        merged_content += f"\n\n# Commit {commit.id}\n{content.strip()}\n"


    # ✅ Save merged content to new version file
    repo_folder = f"D:/VCS_Storage/user_{current_user.id}/repo_{repo_id}/versions"
    os.makedirs(repo_folder, exist_ok=True)

    base_filename = commits[0].original_filename or commits[0].versioned_filename
    versioned_filename = get_next_flat_version_filename(repo_folder, base_filename)
    version_path = os.path.join(repo_folder, versioned_filename)

    with open(version_path, "w", encoding="utf-8") as out:
        out.write(merged_content)

    # ✅ Register merged commit
    merged_commit = Commit(
        repo_id=repo_id,
        author_id=current_user.id,
        message=f"Merged commits {', '.join(map(str, commit_ids))}",
        original_filename=base_filename,
        versioned_filename=versioned_filename,
        snapshot_path=version_path,
        status="merged"
    )
    db.add(merged_commit)
    db.commit()
    db.refresh(merged_commit)

    # ✅ Update all merged commits’ status
    for c in commits:
        c.status = "merged"
    db.commit()

    # ✅ Log
    log = Log(
        user_id=current_user.id,
        repo_id=repo_id,
        commit_id=merged_commit.id,
        action="merge",
        description=f"Merged commits {commit_ids} into {versioned_filename}",
        timestamp=datetime.utcnow()
    )
    db.add(log)
    db.commit()
    merged_content = merged_content.strip()

    return {
        "message": f"Merged into {versioned_filename}",
        "versioned_filename": versioned_filename,
        "commit_id": merged_commit.id
    }

from server.utils.diff_utils import apply_diff

@router.post("/{repo_id}/merge/{commit_id}")
def merge_commit(
    repo_id: int,
    commit_id: int,
    db: Session = Depends(get_db),
    current_user: UserOut = Depends(get_current_user)
):
    # ✅ Access check
    access = db.query(AccessControl).filter_by(user_id=current_user.id, repository_id=repo_id).first()
    if not access or access.role != "admin":
        raise HTTPException(status_code=403, detail="Only admins can merge commits.")

    # ✅ Fetch commit
    commit = db.query(Commit).filter_by(id=commit_id, repo_id=repo_id).first()
    if not commit or commit.status != "proposed":
        raise HTTPException(status_code=404, detail="Commit not found or already merged")

    # ✅ Get original path
    base_filename = commit.original_filename
    if not base_filename:
        raise HTTPException(status_code=400, detail="Original filename missing")

    version_dir = f"D:/VCS_Storage/user_{current_user.id}/repo_{repo_id}/versions"
    os.makedirs(version_dir, exist_ok=True)
    repo_root = f"D:/VCS_Storage/user_{current_user.id}/repo_{repo_id}"
    # ✅ Prepare merged content
    content = ""
    if commit.diff_text:
        original_path = os.path.join(repo_root, commit.original_filename)
        base_content = ""
        if os.path.exists(original_path):
            with open(original_path, "r", encoding="utf-8") as f:
                base_content = f.read()
        content = apply_diff(base_content, commit.diff_text)

    elif commit.snapshot_path and os.path.exists(commit.snapshot_path):
        with open(commit.snapshot_path, "r", encoding="utf-8") as f:
            content = f.read()
    else:
        raise HTTPException(status_code=400, detail="No valid snapshot or diff to merge.")

    # ✅ Save new version
    versioned_filename = get_next_flat_version_filename(version_dir, base_filename)
    version_path = os.path.join(version_dir, versioned_filename)

    with open(version_path, "w", encoding="utf-8") as f:
        f.write(content)

    # ✅ Overwrite file in working directory
    original_path = os.path.join(f"D:/VCS_Storage/user_{current_user.id}/repo_{repo_id}", base_filename)
    os.makedirs(os.path.dirname(original_path), exist_ok=True)
    with open(original_path, "w", encoding="utf-8") as f:
        f.write(content)

    # ✅ Mark commit as merged
    commit.status = "merged"
    commit.versioned_filename = versioned_filename
    db.commit()

    # ✅ Log
    log = Log(
        user_id=current_user.id,
        repo_id=repo_id,
        commit_id=commit.id,
        action="merge",
        description=f"Merged commit {commit.id} into {versioned_filename}",
        timestamp=datetime.utcnow()
    )
    db.add(log)
    db.commit()

    return {"message": f"Commit merged as {versioned_filename}", "version_file": versioned_filename}
from server.utils.diff_utils import apply_diff

@router.get("/{repo_id}/commit_preview/{commit_id}")
def preview_commit(
    repo_id: int,
    commit_id: int,
    db: Session = Depends(get_db),
    current_user: UserOut = Depends(get_current_user)
):
    commit = db.query(Commit).filter_by(id=commit_id, repo_id=repo_id).first()
    if not commit:
        raise HTTPException(status_code=404, detail="Commit not found")

    base_path = f"D:/VCS_Storage/user_{current_user.id}/repo_{repo_id}"
    full_path = os.path.join(base_path, commit.original_filename)

    # 🧠 1. Reconstruct content
    if commit.diff_text:
        base_content = ""
        if os.path.exists(full_path):
            with open(full_path, "r", encoding="utf-8") as f:
                base_content = f.read()

        try:
            content = apply_diff(base_content, commit.diff_text)
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Diff application failed: {e}")
    elif commit.snapshot_path and os.path.exists(commit.snapshot_path):
        with open(commit.snapshot_path, "r", encoding="utf-8") as f:
            content = f.read()
    else:
        raise HTTPException(status_code=404, detail="Nothing to preview")

    return {"content": content, "filename": commit.original_filename}

@router.get("/repositories/{repo_id}/file_merge_info")
def get_file_merge_info(
    repo_id: int,
    file_name: str,
    db: Session = Depends(get_db),
    current_user: UserOut = Depends(get_current_user)
):
    # Access check
    access = db.query(AccessControl).filter_by(user_id=current_user.id, repository_id=repo_id).first()
    if not access:
        raise HTTPException(status_code=403, detail="Access denied")

    # Find the commit that produced this versioned file
    result_commit = (
        db.query(Commit)
        .filter_by(repo_id=repo_id, versioned_filename=file_name, status="merged")
        .first()
    )
    if not result_commit:
        return {"is_merged": False}

    # Check MergeHistory entry
    merge = db.query(MergeHistory).filter_by(
        repo_id=repo_id,
        result_commit_id=result_commit.id
    ).first()

    if not merge:
        return {"is_merged": False}

    return {
        "is_merged": True,
        "commit_id": result_commit.id,
        "sources": [
            f"Commit #{merge.base_commit_id}",
            f"Commit #{merge.merged_commit_id}"
        ]
    }

@router.get("/{repo_id}/download_version")
def download_version(
    repo_id: int,
    file: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    access = db.query(AccessControl).filter_by(user_id=current_user.id, repository_id=repo_id).first()
    if not access:
        raise HTTPException(status_code=403, detail="Permission denied")

    path = f"D:/VCS_Storage/user_{current_user.id}/repo_{repo_id}/versions/{file}"
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail="File not found")

    return FileResponse(path, filename=file)

@router.get("/{repo_id}/edit_file_text")
def convert_to_editable_text(
    repo_id: int,
    name: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    access = db.query(AccessControl).filter_by(user_id=current_user.id, repository_id=repo_id).first()
    if not access or access.role not in ("admin", "editor", "collaborator"):
        raise HTTPException(status_code=403, detail="Permission denied")

    file_path = os.path.join(f"D:/VCS_Storage/user_{current_user.id}/repo_{repo_id}", name)
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="Original file not found")

    from server.utils.file_parser import extract_text_from_file

    # Generate .txt version
    text_version_path = os.path.splitext(file_path)[0] + ".txt"
    try:
        content = extract_text_from_file(file_path)

        # Save the extracted text to .txt file
        with open(text_version_path, "w", encoding="utf-8") as f:
            f.write(content)

        rel_txt_path = os.path.relpath(text_version_path, f"D:/VCS_Storage/user_{current_user.id}/repo_{repo_id}")
        return {
            "message": "Editable text file created",
            "editable_path": rel_txt_path,
            "content": content
        }
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Failed to extract and save text: {str(e)}")

@router.get("/{repo_id}/convert_version")
def convert_versioned_file(
    repo_id: int,
    filename: str,
    target_format: str,
    db: Session = Depends(get_db),
    current_user: UserOut = Depends(get_current_user)
):
    # ✅ 1. Access check
    access = db.query(AccessControl).filter_by(
        user_id=current_user.id, repository_id=repo_id
    ).first()
    if not access:
        raise HTTPException(status_code=403, detail="Permission denied")

    # ✅ 2. Ensure the file exists
    repo_folder = f"D:/VCS_Storage/user_{current_user.id}/repo_{repo_id}/versions"
    file_path = os.path.join(repo_folder, filename)

    if not os.path.isfile(file_path):
        raise HTTPException(status_code=404, detail="Source .txt file not found")

    # ✅ 3. Must be a .txt file
    if not filename.lower().endswith(".txt"):
        raise HTTPException(status_code=400, detail="Only .txt files can be converted")

    # ✅ 4. Read file content
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to read file: {str(e)}")

    # ✅ 5. Build target path
    base_name, _ = os.path.splitext(filename)
    target_format = target_format.lower()
    if target_format not in ["docx", "pdf"]:
        raise HTTPException(status_code=400, detail="Unsupported target format")

    out_path = os.path.join(repo_folder, f"{base_name}.{target_format}")

    # ✅ 6. Convert
    try:
        if target_format == "docx":
            doc = Document()
            for line in content.splitlines():
                doc.add_paragraph(line)
            doc.save(out_path)

        elif target_format == "pdf":
            pdf = FPDF()
            pdf.add_page()
            pdf.set_auto_page_break(auto=True, margin=15)
            pdf.set_font("Arial", size=12)
            for line in content.splitlines():
                pdf.multi_cell(0, 10, txt=line)
            pdf.output(out_path)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Conversion failed: {str(e)}")

    # ✅ 7. Return the converted file
    media_type = "application/pdf" if target_format == "pdf" else "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    return FileResponse(out_path, media_type=media_type, filename=os.path.basename(out_path))

@router.get("/{repo_id}/version_files")
def list_version_files(
    repo_id: int,
    current_user: User = Depends(get_current_user)
):
    version_dir = f"D:/VCS_Storage/user_{current_user.id}/repo_{repo_id}/versions"
    if not os.path.exists(version_dir):
        return []

    return [f for f in os.listdir(version_dir) if f.endswith(".txt")]

@router.post("/{repo_id}/merge_versions")
def merge_versions(
    repo_id: int,
    payload: dict,
    db: Session = Depends(get_db),
    current_user: UserOut = Depends(get_current_user)
):
    from fastapi.responses import FileResponse

    version_files = payload.get("version_files")
    if not version_files or len(version_files) != 2:
        raise HTTPException(status_code=400, detail="Exactly 2 version files must be selected")

    # Access check
    access = db.query(AccessControl).filter_by(user_id=current_user.id, repository_id=repo_id).first()
    if not access or access.role not in ("admin", "editor"):
        raise HTTPException(status_code=403, detail="Permission denied")

    version_dir = f"D:/VCS_Storage/user_{current_user.id}/repo_{repo_id}/versions"
    paths = [os.path.join(version_dir, f) for f in version_files]

    for path in paths:
        if not os.path.exists(path):
            raise HTTPException(status_code=404, detail=f"Version file '{path}' not found")

    # Read content from both files
    content = ""
    try:
        for path in paths:
            with open(path, "r", encoding="utf-8") as f:
                content += f.read() + "\n"
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error reading version files: {e}")

    # Determine base name and extension
    merged_filename = get_next_flat_version_filename(version_dir, version_files[0])

    merged_path = os.path.join(version_dir, merged_filename)
    with open(merged_path, "w", encoding="utf-8") as f:
        f.write(content.strip())

    return {"message": f"Versions merged into {merged_filename}", "versioned_filename": merged_filename}
