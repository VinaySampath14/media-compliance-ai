import uuid
import asyncio
import logging
from typing import List, Dict, Optional
from enum import Enum

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from dotenv import load_dotenv

# CRITICAL: load env vars before importing anything that needs them
load_dotenv(override=True)

from backend.src.api.telemetry import setup_telemetry
setup_telemetry()

from backend.src.graph.workflow import app as compliance_graph

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logging.getLogger("azure").setLevel(logging.WARNING)
logging.getLogger("opentelemetry").setLevel(logging.WARNING)
logging.getLogger("urllib3").setLevel(logging.WARNING)

logger = logging.getLogger("api-server")


# ------------------------------------------------------------------ #
# In-memory job store
# Maps job_id → job result dict.
# Replace with Redis or Azure Cosmos DB for multi-instance deployments.
# ------------------------------------------------------------------ #
_jobs: Dict[str, dict] = {}


class JobStatus(str, Enum):
    PENDING   = "PENDING"
    RUNNING   = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED    = "FAILED"


class AuditVerdict(str, Enum):
    PASS   = "PASS"
    REVIEW = "REVIEW"   # only borderline violations (confidence 0.5–0.74)
    FAIL   = "FAIL"


# ------------------------------------------------------------------ #
# FastAPI app
# ------------------------------------------------------------------ #
app = FastAPI(
    title="Media Compliance AI",
    description="Audits video content against brand compliance rules.",
    version="1.0.0"
)


# ------------------------------------------------------------------ #
# Pydantic models
# ------------------------------------------------------------------ #

class AuditRequest(BaseModel):
    video_url: str


class AuditJobResponse(BaseModel):
    job_id: str
    status: JobStatus
    message: str


class ComplianceIssue(BaseModel):
    category: str
    severity: str                      # "CRITICAL", "WARNING", or "REVIEW NEEDED"
    description: str
    timestamp: Optional[str] = None    # HH:MM:SS pinpointing where in the video
    confidence: float = 1.0            # 0.0–1.0 GPT-4 certainty score


class AuditResult(BaseModel):
    job_id: str
    session_id: str
    video_id: str
    status: JobStatus
    final_status: Optional[AuditVerdict] = None
    final_report: Optional[str] = None
    compliance_results: List[ComplianceIssue] = []
    error: Optional[str] = None


# ------------------------------------------------------------------ #
# Background worker
# ------------------------------------------------------------------ #

async def _run_audit(job_id: str, session_id: str, video_id: str, video_url: str):
    """Runs the LangGraph pipeline in the background and updates _jobs."""
    _jobs[job_id]["status"] = JobStatus.RUNNING
    logger.info(f"[{job_id}] Audit started: {video_url}")

    initial_inputs = {
        "video_url": video_url,
        "video_id": video_id,
        "compliance_results": [],
        "errors": []
    }

    try:
        # ainvoke() — non-blocking, yields control back to the event loop
        final_state = await compliance_graph.ainvoke(initial_inputs)

        _jobs[job_id].update({
            "status":             JobStatus.COMPLETED,
            "final_status":       final_state.get("final_status", "UNKNOWN"),
            "final_report":       final_state.get("final_report", "No report generated."),
            "compliance_results": final_state.get("compliance_results", []),
        })
        logger.info(f"[{job_id}] Audit completed: {_jobs[job_id]['final_status']}")

    except Exception as e:
        logger.error(f"[{job_id}] Audit failed: {e}")
        _jobs[job_id].update({
            "status": JobStatus.FAILED,
            "error":  str(e),
        })


# ------------------------------------------------------------------ #
# Endpoints
# ------------------------------------------------------------------ #

@app.post("/audit", response_model=AuditJobResponse, status_code=202)
async def start_audit(request: AuditRequest):
    """
    Accepts a YouTube URL and immediately returns a job_id.
    The audit runs in the background — poll GET /audit/{job_id} for results.

    POST /audit
    Body: {"video_url": "https://youtu.be/..."}
    Returns: {"job_id": "...", "status": "PENDING", "message": "..."}
    """
    session_id = str(uuid.uuid4())
    job_id     = str(uuid.uuid4())
    video_id   = f"vid_{session_id[:8]}"

    # Register job as pending before background task starts
    _jobs[job_id] = {
        "status":             JobStatus.PENDING,
        "session_id":         session_id,
        "video_id":           video_id,
        "final_status":       None,
        "final_report":       None,
        "compliance_results": [],
        "error":              None,
    }

    # Fire and forget — does not block the response
    asyncio.create_task(_run_audit(job_id, session_id, video_id, request.video_url))

    logger.info(f"Audit job queued: {job_id} for {request.video_url}")

    return AuditJobResponse(
        job_id=job_id,
        status=JobStatus.PENDING,
        message=f"Audit started. Poll GET /audit/{job_id} for results."
    )


@app.get("/audit/{job_id}", response_model=AuditResult)
async def get_audit_result(job_id: str):
    """
    Returns the current status and results of an audit job.

    GET /audit/{job_id}
    - status=PENDING   → job is queued
    - status=RUNNING   → pipeline is processing
    - status=COMPLETED → results are ready
    - status=FAILED    → audit failed, check error field
    """
    job = _jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"Job '{job_id}' not found.")

    return AuditResult(
        job_id=job_id,
        session_id=job["session_id"],
        video_id=job["video_id"],
        status=job["status"],
        final_status=job.get("final_status"),
        final_report=job.get("final_report"),
        compliance_results=job.get("compliance_results", []),
        error=job.get("error"),
    )


@app.get("/health")
def health_check():
    """
    Simple alive check.
    GET /health → {"status": "healthy"}
    """
    return {"status": "healthy", "service": "Media Compliance AI"}
