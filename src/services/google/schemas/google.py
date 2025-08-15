from typing import Dict, Any
from pydantic import BaseModel, Field

class GoogleToolCall(BaseModel):
    """
    Represents a tool call for the Google service.
    """
    tool_name: str = Field(..., description="The name of the tool to call.")
    parameters: Dict[str, Any] = Field(default_factory=dict, description="The parameters for the tool call.")
