import os
import logging
from typing import Dict, Any

from backend.src.graph.state import VideoAuditState
from backend.src.services.video_indexer import VideoIndexerService

logger = logging.getLogger("media-compliance-ai")


# --- NODE 1: INDEXER ---
def index_video_node(state: VideoAuditState) -> Dict[str, Any]:
    """
    Downloads video, sends to Azure Video Indexer, extracts transcript + OCR.
    """
    video_url = state.get("video_url")
    video_id = state.get("video_id", "vid_demo")
    logger.info(f"[Indexer] Processing: {video_url}")

    local_filename = "temp_audit_video.mp4"

    try:
        vi_service = VideoIndexerService()

        # 1. Download YouTube video locally
        local_path = vi_service.download_youtube_video(video_url, output_path=local_filename)

        # 2. Upload to Azure Video Indexer
        azure_video_id = vi_service.upload_video(local_path, video_name=video_id)

        # 3. Delete local temp file — no longer needed
        if os.path.exists(local_path):
            os.remove(local_path)

        # 4. Wait for Azure to finish processing
        raw_insights = vi_service.wait_for_processing(azure_video_id)

        # 5. Extract transcript + OCR from the response
        return vi_service.extract_data(raw_insights)

    except Exception as e:
        logger.error(f"[Indexer] Failed: {e}")
        return {
            "errors": [str(e)],
            "final_status": "FAIL",
            "transcript": "",
            "ocr_text": []
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
