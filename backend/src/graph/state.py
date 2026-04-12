import operator
from typing import Annotated, List, Dict, Optional, Any, TypedDict


# Defines the shape of a single compliance violation
class ComplianceIssue(TypedDict):
    category: str            # e.g. "Misleading Claims", "FTC Disclosure"
    description: str         # what exactly is the violation
    severity: str            # "CRITICAL", "WARNING", or "REVIEW NEEDED"
    timestamp: Optional[str] # where in the video it happens, e.g. "00:32"
    confidence: float        # 0.0–1.0 — how certain GPT-4 is about this violation


# The shared whiteboard — all nodes read from and write to this
class VideoAuditState(TypedDict):

    # --- Input ---
    video_url: str           # YouTube URL provided by user
    video_id: str            # short tracking ID e.g. "vid_ce6c43bb"

    # --- Set by Indexer Node ---
    local_file_path: Optional[str]        # temp path where video is downloaded
    video_metadata: Dict[str, Any]        # e.g. {"duration": 120, "platform": "youtube"}
    transcript: Optional[str]             # full transcript with [HH:MM:SS] prefixes
    transcript_segments: List[Dict[str, Any]]  # [{text, timestamp}] per segment
    ocr_text: List[str]                   # list of on-screen text detected

    # --- Set by Auditor Node ---
    # Annotated with operator.add so nodes APPEND to the list, not overwrite it
    compliance_results: Annotated[List[ComplianceIssue], operator.add]

    # --- Final Output ---
    final_status: str        # "PASS", "REVIEW", or "FAIL"
    final_report: str        # AI-generated markdown summary

    # --- System ---
    # Same append behavior — multiple nodes can log errors without overwriting
    errors: Annotated[List[str], operator.add]
