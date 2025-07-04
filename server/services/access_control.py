from server.models import AccessControl , User
from server.constants.access_levels import READ, WRITE, ADMIN
from sqlalchemy.orm import Session
from typing import Optional
from server.utils.role_mapper import ROLE_TO_ACCESS
from server.models import Repository
from fastapi import HTTPException
from server.schemas import Role


def get_user_repo_access(db: Session, user_id: int, repo_id: int) -> Optional[str]:
    access = db.query(AccessControl).filter_by(user_id=user_id, repository_id=repo_id).first()
    return access.role if access else None

def can_read_repo(repo: Repository, role: Optional[str]) -> bool:
    if repo.visibility == "public":
        return True
    return role in [ "viewer", "editor", "admin","collaborator"]

def can_write_repo(role: Optional[str]) -> bool:
    return role in ["editor", "admin","collaborator"]

def is_admin_repo(role: Optional[str]) -> bool:
    return role == "admin"

def has_read_access(level: str) -> bool:
    return level in [READ, WRITE, ADMIN]

def has_write_access(level: str) -> bool:
    return level in [WRITE, ADMIN]

def has_admin_access(level: str) -> bool:
    return level == ADMIN

def get_user_access_level(db: Session, user_id: int, repo_id: int) -> Optional[str]:
    access = db.query(AccessControl).filter_by(user_id=user_id, repository_id=repo_id).first()
    return access.role if access else None

def assign_admin_access(db: Session, user_id: int, repository_id: int):
    access_entry = AccessControl(
        user_id=user_id,
        repository_id=repository_id,
        role=ADMIN  
    )
    db.add(access_entry)
    db.commit()
    db.refresh(access_entry)
    return access_entry


def assign_access_by_user_role(db: Session, user: User, repository_id: int):
    access_level = ROLE_TO_ACCESS[user.role]
    access = db.query(AccessControl).filter_by(user_id=user.id, repository_id=repository_id).first()
    if access:
        access.role = access_level
    else:
        access = AccessControl(user_id=user.id, repository_id=repository_id, role=access_level)
        db.add(access)
    db.commit()
    return access


def set_user_access_level(db: Session, user_id: int, repository_id: int, role: str):
    # Validate role using the Role enum
    try:
        role_enum = Role(role)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid role '{role}'. Valid roles: {[r.value for r in Role]}")

    # Check if access entry already exists
    access = db.query(AccessControl).filter_by(user_id=user_id, repository_id=repository_id).first()
    if access:
        access.role = role_enum.value  
    else:
        access = AccessControl(user_id=user_id, repository_id=repository_id, role=role_enum.value)
        db.add(access)

    db.commit()
    db.refresh(access)
    return access

