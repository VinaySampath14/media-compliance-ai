import uuid
import logging
from typing import List, Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from dotenv import load_dotenv

# CRITICAL: load env vars before importing anything that needs them
load_dotenv(override=True)

from backend.src.api.telemetry import setup_telemetry
setup_telemetry()

from backend.src.graph.workflow import app as compliance_graph

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("api-server")


# ------------------------------------------------------------------ #
# FastAPI app
# ------------------------------------------------------------------ #
app = FastAPI(
    title="Media Compliance AI",
    description="Audits video content against brand compliance rules.",
    version="1.0.0"
)


# ------------------------------------------------------------------ #
# Pydantic models — define the shape of requests and responses
# FastAPI validates automatically — wrong format = 422 error
# ------------------------------------------------------------------ #

class AuditRequest(BaseModel):
    video_url: str          # YouTube URL from the client


class ComplianceIssue(BaseModel):
    category: str
    severity: str
    description: str


class AuditResponse(BaseModel):
    session_id: str
    video_id: str
    status: str
    final_report: str
    compliance_results: List[ComplianceIssue]


# ------------------------------------------------------------------ #
# Endpoints
# ------------------------------------------------------------------ #

@app.post("/audit", response_model=AuditResponse)
async def audit_video(request: AuditRequest):
    """
    Triggers the full compliance audit pipeline.
    POST /audit
    Body: {"video_url": "https://youtu.be/..."}
    """
    session_id = str(uuid.uuid4())
    video_id = f"vid_{session_id[:8]}"

    logger.info(f"Audit request received: {request.video_url} (session: {session_id})")

    initial_inputs = {
        "video_url": request.video_url,
        "video_id": video_id,
        "compliance_results": [],
        "errors": []
    }

    try:
        # invoke() runs: START → indexer → auditor → END
        # NOTE: this is a blocking call — for production use ainvoke()
        final_state = compliance_graph.invoke(initial_inputs)

        return AuditResponse(
            session_id=session_id,
            video_id=final_state.get("video_id", video_id),
            status=final_state.get("final_status", "UNKNOWN"),
            final_report=final_state.get("final_report", "No report generated."),
            compliance_results=final_state.get("compliance_results", [])
        )

    except Exception as e:
        logger.error(f"Audit failed: {e}")
        raise HTTPException(status_code=500, detail=f"Workflow failed: {str(e)}")


@app.get("/health")
def health_check():
    """
    Simple alive check.
    GET /health → {"status": "healthy"}
    """
    return {"status": "healthy", "service": "Media Compliance AI"}
