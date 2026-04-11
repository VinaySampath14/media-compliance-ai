import operator
from typing import Annotated, List, Dict, Optional, Any, TypedDict


# Defines the shape of a single compliance violation
class ComplianceIssue(TypedDict):
    category: str            # e.g. "Misleading Claims", "FTC Disclosure"
    description: str         # what exactly is the violation
    severity: str            # "CRITICAL" or "WARNING"
    timestamp: Optional[str] # where in the video it happens, e.g. "00:32"


# The shared whiteboard — all nodes read from and write to this
class VideoAuditState(TypedDict):

    # --- Input ---
    video_url: str           # YouTube URL provided by user
    video_id: str            # short tracking ID e.g. "vid_ce6c43bb"

    # --- Set by Indexer Node ---
    local_file_path: Optional[str]   # temp path where video is downloaded
    video_metadata: Dict[str, Any]   # e.g. {"duration": 120, "platform": "youtube"}
    transcript: Optional[str]        # full speech-to-text from Azure Video Indexer
    ocr_text: List[str]              # list of on-screen text detected

    # --- Set by Auditor Node ---
    # Annotated with operator.add so nodes APPEND to the list, not overwrite it
    compliance_results: Annotated[List[ComplianceIssue], operator.add]

    # --- Final Output ---
    final_status: str        # "PASS" or "FAIL"
    final_report: str        # AI-generated markdown summary

    # --- System ---
    # Same append behavior — multiple nodes can log errors without overwriting
    errors: Annotated[List[str], operator.add]
