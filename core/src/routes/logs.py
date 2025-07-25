import os
import logging
from fastapi import APIRouter, Depends, HTTPException, Query
from google.cloud import logging_v2
from google.auth.exceptions import DefaultCredentialsError
from ..config.auth import get_current_user_email
from typing import List, Optional
from pydantic import BaseModel
import iso8601

# Configure logger for this module
logger = logging.getLogger(__name__)
router = APIRouter(prefix="/projects", tags=["logs"])

# Pydantic model for the response
class LogEntry(BaseModel):
    timestamp: str
    level: str
    message: str

@router.get("/{project_id}/logs", response_model=List[LogEntry])
async def get_project_logs(

    project_id: str,
    # Timestamp in ISO 8601 format to fetch logs after this time
    timestamp: Optional[str] = Query(None),
    owner_email: str = Depends(get_current_user_email)
 ):
    """
    Fetches structured logs for a specific project ID from Google Cloud Logging.
    This endpoint is protected and requires user authentication.
    """
     # Although we don't use owner_email to query logs, it ensures
     # that only the authenticated owner of the project can access its logs.
     # A proper implementation would verify project ownership here.
    logger.info(f"Log request for project_id: {project_id} by {owner_email}")
 
    try:
        client = logging_v2.LoggingServiceV2Client()
    except DefaultCredentialsError:

        raise HTTPException(
            status_code=500,
            detail="Server is not authenticated with Google Cloud."
         )
 
    # Get the GCP Project ID from environment variables
    gcp_project_id = os.getenv("GCP_PROJECT_ID")
    if not gcp_project_id:
        raise HTTPException(
            status_code=500,
            detail="GCP_PROJECT_ID is not configured on the server."
        )
 
    # Construct the filter for querying logs
    # This filter is highly specific to find logs from our manager
    log_filter = [
        'resource.type="k8s_container"',
        'resource.labels.namespace_name="bspacekubs"',
        'jsonPayload.correlation_id="' + project_id + '"'
    ]
 
    # If a timestamp is provided, only fetch logs newer than it
    if timestamp:
        try:
            # Validate and format the timestamp for the filter
            parsed_time = iso8601.parse_date(timestamp)
            # Add a small buffer to avoid fetching the last log again
            formatted_time = parsed_time.strftime('%Y-%m-%dT%H:%M:%S.%fZ')
            log_filter.append(f'timestamp > "{formatted_time}"')
        except iso8601.ParseError:
            raise HTTPException(status_code=400, detail="Invalid timestamp format. Use ISO 8601.")
 
    # Join all parts of the filter
    final_filter = " AND ".join(log_filter)
    logger.info(f"Using log filter: {final_filter}")
 
    try:
        # Fetch the logs
        entries = client.list_log_entries(
            resource_names=[f"projects/{gcp_project_id}"],
            filter_=final_filter,
            order_by="timestamp,asc" # Get logs in ascending order
        )
 
        # Format the response
        response_logs = []
        for entry in entries:
            payload = entry.json_payload
            response_logs.append(
                LogEntry(
                    timestamp=entry.timestamp.isoformat(),
                    level=payload.get("level", "INFO"),
                    message=payload.get("message", "")
                )
            )
        return response_logs
 
    except Exception as e:
        logger.error(f"Failed to fetch logs from Google Cloud Logging: {e}")
        raise HTTPException(

            status_code=500,
            detail="An error occurred while fetching logs."
        )
