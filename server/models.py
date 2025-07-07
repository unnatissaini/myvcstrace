from sqlalchemy.orm import relationship
from datetime import datetime
from server.db import Base
from sqlalchemy import Column, Integer, String, ForeignKey, Text, DateTime, Enum, Boolean
from sqlalchemy.orm import relationship, backref
from datetime import datetime
from sqlalchemy import UniqueConstraint
from enum import Enum
from sqlalchemy import Text
from sqlalchemy import BigInteger

class User(Base):
    __tablename__ = 'users'
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True)
    password_hash = Column(String)

    repos = relationship("Repository", back_populates="owner")
    access_controls = relationship("AccessControl", back_populates="user", cascade="all, delete-orphan")
    logs = relationship("Log", back_populates="user", cascade="all, delete-orphan")

class Repository(Base):
    __tablename__ = 'repositories'
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True)
    owner_id = Column(Integer, ForeignKey("users.id"))
    visibility = Column(String, default="private")
    owner = relationship("User", back_populates="repos")
    commits = relationship("Commit", back_populates="repository")
    access_controls = relationship("AccessControl", back_populates="repository", cascade="all, delete-orphan")
    created_at = Column(DateTime, default=datetime.utcnow)
    description = Column(Text)

class Commit(Base):
    __tablename__ = "commits"

    id = Column(Integer, primary_key=True, index=True)
    repo_id = Column(Integer, ForeignKey("repositories.id", ondelete="CASCADE"))
    author_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"))
    parent_commit_id = Column(Integer, ForeignKey("commits.id", ondelete="SET NULL"))

    message = Column(Text, nullable=False)
    original_filename = Column(String, nullable=False)      # e.g. "main.py"
    versioned_filename = Column(String, nullable=True)     # e.g. "main_v2.py"
    snapshot_path = Column(String, nullable=True)          # e.g. "/snapshots/main_v2.py"

    status = Column(String, default="proposed")             # 'proposed', 'merged'
    timestamp = Column(DateTime, default=datetime.utcnow)


    diff_text = Column(Text, nullable=True)  # new column to store unified diff

    # Relationships
    repository = relationship("Repository", back_populates="commits")
    author = relationship("User")
    parent = relationship("Commit", remote_side=[id], backref="children")
    snapshot = relationship("Snapshot", back_populates="commit", uselist=False)


class AccessControl(Base):
    __tablename__ = "access_control"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"))
    repository_id = Column(Integer, ForeignKey("repositories.id", ondelete="CASCADE"))
    role = Column(String, nullable=False)  # e.g., "read", "write", "admin"

    user = relationship("User", back_populates="access_controls")
    repository = relationship("Repository", back_populates="access_controls")

class Log(Base):
    __tablename__ = "log"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    repo_id = Column(Integer, ForeignKey("repositories.id", ondelete="SET NULL"), nullable=True)  
    commit_id = Column(Integer, ForeignKey("commits.id"), nullable=True)
    action = Column(String, nullable=False)
    timestamp = Column(DateTime, default=datetime.utcnow)
    description = Column(Text)

    user = relationship("User", back_populates="logs")
    repo = relationship("Repository", backref="logs")

class Snapshot(Base):
    __tablename__ = "snapshot"

    id = Column(Integer, primary_key=True, index=True)
    commit_id = Column(Integer, ForeignKey("commits.id", ondelete="CASCADE"))
    file_path = Column(String, nullable=False)      
    content_hash = Column(String, nullable=False)      
    size = Column(BigInteger)
    created_at = Column(DateTime, default=datetime.utcnow)
    is_deleted = Column(Boolean, default=False)    
    operation = Column(String, nullable=False, default="add")  # "add", "modify", "delete"

    commit = relationship("Commit", back_populates="snapshot")

class FileVersion(Base):
    __tablename__ = "file_versions"

    id = Column(Integer, primary_key=True)
    repo_id = Column(Integer, ForeignKey("repositories.id", ondelete="CASCADE"))
    original_filename = Column(String, nullable=False)
    latest_version = Column(Integer, default=1)

    __table_args__ = (
        UniqueConstraint('repo_id', 'original_filename', name='uix_repo_file'),
    )
class MergeHistory(Base):
    __tablename__ = "merge_history"

    id = Column(Integer, primary_key=True)
    repo_id = Column(Integer, ForeignKey("repositories.id", ondelete="CASCADE"))
    base_commit_id = Column(Integer, ForeignKey("commits.id", ondelete="SET NULL"))
    merged_commit_id = Column(Integer, ForeignKey("commits.id", ondelete="SET NULL"))
    result_commit_id = Column(Integer, ForeignKey("commits.id", ondelete="SET NULL"))

    result_filename = Column(String, nullable=False)
    merged_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"))
    timestamp = Column(DateTime, default=datetime.utcnow)

    base_commit = relationship("Commit", foreign_keys=[base_commit_id])
    merged_commit = relationship("Commit", foreign_keys=[merged_commit_id])
    result_commit = relationship("Commit", foreign_keys=[result_commit_id])

class FileVersionHistory(Base):
    __tablename__ = "file_version_history"

    id = Column(Integer, primary_key=True)
    repo_id = Column(Integer, ForeignKey("repositories.id", ondelete="CASCADE"))
    original_filename = Column(String, nullable=False)
    version_no = Column(Integer, nullable=False)
    commit_id = Column(Integer, ForeignKey("commits.id", ondelete="SET NULL"))
    versioned_filename = Column(String, nullable=False)
    snapshot_path = Column(String, nullable=False)
    merged_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"))
    timestamp = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint('repo_id', 'original_filename', 'version_no', name='uix_repo_file_version'),
    )

    commit = relationship("Commit")
    merged_by_user = relationship("User", foreign_keys=[merged_by])
