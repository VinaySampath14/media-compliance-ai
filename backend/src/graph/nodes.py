import logging
from typing import Dict, Any

from backend.src.graph.state import VideoAuditState

logger = logging.getLogger("media-compliance-ai")


# --- NODE 1: INDEXER ---
def index_video_node(state: VideoAuditState) -> Dict[str, Any]:
    """
    Downloads video, sends to Azure Video Indexer, extracts transcript + OCR.
    Currently returns hardcoded data — real Azure calls added in Phase 3.
    """
    video_url = state.get("video_url")
    logger.info(f"[Indexer] Processing: {video_url}")

    # --- HARDCODED FOR NOW ---
    # Real version will: download with yt-dlp → upload to Azure VI → poll → extract
    return {
        "transcript": "This product guarantees you will lose 10 pounds in 7 days or your money back. Results are absolutely guaranteed.",
        "ocr_text": ["GUARANTEED RESULTS", "100% MONEY BACK"],
        "video_metadata": {
            "duration": 45,
            "platform": "youtube"
        }
    }


# --- NODE 2: AUDITOR ---
def audit_content_node(state: VideoAuditState) -> Dict[str, Any]:
    """
    Queries Azure AI Search for compliance rules, sends to GPT-4, returns violations.
    Currently returns hardcoded data — real Azure + OpenAI calls added in Phase 5.
    """
    transcript = state.get("transcript", "")
    logger.info("[Auditor] Auditing transcript...")

    if not transcript:
        logger.warning("[Auditor] No transcript found. Skipping.")
        return {
            "final_status": "FAIL",
            "final_report": "Audit skipped — no transcript available."
        }

    # --- HARDCODED FOR NOW ---
    # Real version will: query Azure AI Search → build prompt → call GPT-4 → parse JSON
    return {
        "compliance_results": [
            {
                "category": "Misleading Claims",
                "severity": "CRITICAL",
                "description": "Absolute guarantee of results detected — violates FTC guidelines.",
                "timestamp": "00:05"
            }
        ],
        "final_status": "FAIL",
        "final_report": "Video contains 1 critical violation. Absolute health guarantees are prohibited under FTC regulations."
    }
