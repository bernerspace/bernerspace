from typing import List
from fastapi import APIRouter, Depends, HTTPException
from beanie import PydanticObjectId
from src.models.projects import Project, Version, CreateProjectRequest, ProjectResponse
from src.config.auth import get_current_user_email

router = APIRouter(prefix="/projects", tags=["projects"])

@router.post("/", response_model=ProjectResponse)
async def create_project(
    req: CreateProjectRequest,
    owner_email: str = Depends(get_current_user_email)
):
    existing = await Project.find_one({"name": req.name, "owner_email": owner_email})
    if existing:
        raise HTTPException(status_code=400, detail="Project name already exists")
    proj = Project(name=req.name, owner_email=owner_email)
    await proj.insert()
    return ProjectResponse(
        id=str(proj.id),
        name=proj.name,
        owner_email=proj.owner_email,
        created_at=proj.created_at,
        versions=[]
    )

@router.get("/{project_id}", response_model=ProjectResponse)
async def get_project(
    project_id: str,
    owner_email: str = Depends(get_current_user_email)
):
    try:
        pid = PydanticObjectId(project_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid project ID")
    proj = await Project.get(pid)
    if not proj or proj.owner_email != owner_email:
        raise HTTPException(status_code=404, detail="Project not found")
    vers = (
        await Version.find({"project_id": pid}).sort("version").to_list()
    )
    versions_data = [{
        "version": v.version,
        "filename": v.filename,
        "gcs_path": v.gcs_path,
        "size": v.size,
        "current_path": v.current_path,
        "language": v.language,
        "has_dockerfile": v.has_dockerfile,
        "env_vars": v.env_vars,
        "uploaded_at": v.uploaded_at
    } for v in vers]
    return ProjectResponse(
        id=str(proj.id),
        name=proj.name,
        owner_email=proj.owner_email,
        created_at=proj.created_at,
        versions=versions_data
    )


@router.get("/", response_model=List[ProjectResponse])
async def list_projects(owner_email: str = Depends(get_current_user_email)):
    projects = await Project.find({"owner_email": owner_email}).to_list()
    result = []
    for proj in projects:
        vers = await Version.find({"project_id": proj.id}).sort("version").to_list()
        versions_data = [{
            "version": v.version,
            "filename": v.filename,
            "gcs_path": v.gcs_path,
            "size": v.size,
            "current_path": v.current_path,
            "language": v.language,
            "has_dockerfile": v.has_dockerfile,
            "env_vars": v.env_vars,
            "uploaded_at": v.uploaded_at
        } for v in vers]
        result.append(ProjectResponse(
            id=str(proj.id),
            name=proj.name,
            owner_email=proj.owner_email,
            created_at=proj.created_at,
            versions=versions_data
        ))
    return result