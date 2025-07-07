from pydantic import BaseModel
from enum import Enum
from typing import Optional


class FileEditRequest(BaseModel):
    filename: str
    content: str  # Base64-encoded string for binary, plain text for text files
    is_binary: bool = False

class UserOut(BaseModel):
    id: int
    username: str

    class Config:
        from_attributes = True  # For SQLAlchemy compatibility (Pydantic v2+)

class RepositoryCreate(BaseModel):
    name: str

from datetime import datetime

class LogOut(BaseModel):
    id: int
    user_id: int
    repo_id: int
    commit_id: Optional[int]
    action: str
    username: str
    repo_name: str
    timestamp: datetime

    class Config:
        from_attributes = True

from typing import Optional

class RepositoryUpdate(BaseModel):
    name: Optional[str]
    description: Optional[str]
    is_public: Optional[bool]

class DeleteRepoInput(BaseModel):
    file_path: str

class DeleteFileInput(BaseModel):
    file_path: str

class Role(str, Enum):
    ADMIN = "admin"
    EDITOR = "editor"
    VIEWER = "viewer"
class SetAccessLevelInput(BaseModel):
    user_id: int
    role: Role