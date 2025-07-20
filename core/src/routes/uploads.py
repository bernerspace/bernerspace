from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from fastapi.responses import StreamingResponse
from google.cloud import storage
from beanie import PydanticObjectId
from ..models.projects import Project, Version, UploadResponse
from ..config.auth import get_current_user_email
from ..config.config import settings
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

router = APIRouter(prefix="/projects", tags=["uploads"])

@router.post("/{project_id}/upload", response_model=UploadResponse)
async def upload_tar(
    project_id: str,
    file: UploadFile = File(...),
    env_vars: str = Form(...),
    current_path: str = Form(...),
    language: str = Form(...),
    has_dockerfile: bool = Form(False),
    owner_email: str = Depends(get_current_user_email)
):
    logger.info(f"Starting upload for project_id: {project_id}")
    gcs_client = storage.Client()
    try:
        logger.info(f"Attempting to access bucket: {settings.GCP_BUCKET}")
        bucket = gcs_client.bucket(settings.GCP_BUCKET)
    except Exception as e:
        logger.error(f"GCS bucket error: {e}")
        raise HTTPException(status_code=500, detail=f"GCS bucket misconfigured: {e}")


    # Validate project
    try:
        pid = PydanticObjectId(project_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid project ID")
    proj = await Project.get(pid)
    if not proj or proj.owner_email != owner_email:
        raise HTTPException(status_code=404, detail="Project not found")

    # Compute next version
    count = await Version.find({"project_id": pid}).count()
    version = count + 1

    # Upload to GCS
    filename = f"{proj.name}/v{version}/{file.filename}"
    blob = bucket.blob(filename)
    content = await file.read()
    blob.upload_from_string(content)
    size = len(content)

    # Persist metadata
    metadata = Version(
        project_id=pid,
        project_name=proj.name, 
        version=version,
        filename=file.filename,
        gcs_path=filename,
        size=size,
        current_path=current_path,
        language=language,
        has_dockerfile=has_dockerfile,
        env_vars=__import__('json').loads(env_vars)
    )
    await metadata.insert()

    return UploadResponse(
        project_id=project_id,
        project_name=proj.name,
        version=version,
        success=True,
        filename=file.filename,
        gcs_path=filename,
        size=size,
        current_path=current_path,
        language=language,
        has_dockerfile=has_dockerfile
    )

@router.get("/{project_id}/download/{version}")
async def download_tar(
    project_id: str,
    version: int,
    owner_email: str = Depends(get_current_user_email)
):
    # Initialize GCS client and bucket
    gcs_client = storage.Client()
    try:
        bucket = gcs_client.bucket(settings.GCP_BUCKET)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"GCS bucket misconfigured: {e}")

    try:
        pid = PydanticObjectId(project_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid project ID")
    ver = await Version.find_one({"project_id": pid, "version": version})
    if not ver:
        raise HTTPException(status_code=404, detail="Version not found")

    blob = bucket.blob(ver.gcs_path)
    content = blob.download_as_bytes()
    return StreamingResponse(
        iter([content]),
        media_type="application/x-tar",
        headers={
            "Content-Disposition": f"attachment; filename={ver.filename}",
            "X-Project-Id": str(ver.project_id),
            "X-Project-Name": getattr(ver, "project_name", ""),  # <-- Use getattr for safety
            "X-Version": str(ver.version),
            "X-Filename": ver.filename,
            "X-GCS-Path": ver.gcs_path,
            "X-Size": str(ver.size),
            "X-Current-Path": ver.current_path,
            "X-Language": ver.language,
            "X-Has-Dockerfile": str(ver.has_dockerfile),
            "X-Uploaded-At": str(ver.uploaded_at)
        }
    )