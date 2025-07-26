import os
import logging
from fastapi import APIRouter, Depends, HTTPException, Query
from google.cloud import logging_v2
from google.auth.exceptions import DefaultCredentialsError
from ..config.auth import get_current_user_email
from typing import List, Optional
from pydantic import BaseModel
import iso8601

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/projects", tags=["logs"])

class LogEntry(BaseModel):
    timestamp: str
    level: str
    message: str

@router.get("/{project_id}/logs", response_model=List[LogEntry])
async def get_project_logs(
    project_id: str,
    timestamp: Optional[str] = Query(None),
    owner_email: str = Depends(get_current_user_email)
):
    logger.info(f"Log request for project_id: {project_id} by {owner_email}")

    try:
        client = logging_v2.Client()
    except DefaultCredentialsError:
        raise HTTPException(
            status_code=500,
            detail="Server is not authenticated with Google Cloud."
        )

    gcp_project_id = os.getenv("GCP_PROJECT_ID")
    if not gcp_project_id:
        raise HTTPException(
            status_code=500,
            detail="GCP_PROJECT_ID is not configured on the server."
        )

    log_filter = [
        'resource.type="k8s_container"',
        'resource.labels.namespace_name="bspacekubs"',
        'jsonPayload.correlation_id="' + project_id + '"'
    ]

    if timestamp:
        try:
            parsed_time = iso8601.parse_date(timestamp)
            formatted_time = parsed_time.strftime('%Y-%m-%dT%H:%M:%S.%fZ')
            log_filter.append(f'timestamp > "{formatted_time}"')
        except iso8601.ParseError:
            raise HTTPException(status_code=400, detail="Invalid timestamp format. Use ISO 8601.")

    final_filter = " AND ".join(log_filter)
    logger.info(f"Using log filter: {final_filter}")

    try:
        entries = client.list_entries(
            resource_names=[f"projects/{gcp_project_id}"],
            filter_=final_filter,
            order_by="timestamp"
        )

        response_logs = []
        for entry in entries:
            payload = entry.payload
            if isinstance(payload, dict):
                response_logs.append(
                    LogEntry(
                        timestamp=entry.timestamp.isoformat(),
                        level=payload.get("level", "INFO"),
                        message=payload.get("message", "")
                    )
                )
        return response_logs

    except Exception as e:
        logger.exception("An error occurred while fetching logs from Google Cloud Logging: %s", e)
        raise HTTPException(
            status_code=500,
            detail="An error occurred while fetching logs."
        )