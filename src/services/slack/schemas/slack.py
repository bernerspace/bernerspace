from typing import Dict, Optional, Any
from dataclasses import dataclass

@dataclass
class SlackResponse:
    """Standard response wrapper for Slack API calls"""
    ok: bool
    data: Dict[str, Any]
    error: Optional[str] = None
    warning: Optional[str] = None