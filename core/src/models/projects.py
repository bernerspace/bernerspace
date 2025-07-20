from beanie import Document, PydanticObjectId
from pydantic import BaseModel, Field
from datetime import datetime
from typing import Dict, Optional

class Project(Document):
    name: str
    owner_email: str
    created_at: datetime = Field(default_factory=datetime.utcnow)

    class Settings:
        name = "projects"

class Version(Document):
    project_id: PydanticObjectId
    version: int
    filename: str
    gcs_path: str
    size: int
    current_path: str
    language: str
    has_dockerfile: bool
    env_vars: Dict[str, str]
    uploaded_at: datetime = Field(default_factory=datetime.utcnow)

    class Settings:
        name = "versions"

# Pydantic request/response models
class CreateProjectRequest(BaseModel):
    name: str

class ProjectResponse(BaseModel):
    id: str
    name: str
    owner_email: str
    created_at: datetime
    versions: list[dict]

class UploadResponse(BaseModel):
    project_id: str
    project_name: Optional[str] = None
    version: int
    success: bool
    filename: str
    gcs_path: str
    size: int
    current_path: str
    language: str
    has_dockerfile: bool
