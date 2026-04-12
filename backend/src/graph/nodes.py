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
    Retrieves relevant compliance rules from Azure AI Search,
    sends transcript + rules to GPT-4, returns structured violations.
    """
    import json
    import re
    from langchain_openai import AzureChatOpenAI, AzureOpenAIEmbeddings
    from langchain_community.vectorstores import AzureSearch
    from langchain_core.messages import SystemMessage, HumanMessage

    transcript = state.get("transcript", "")
    ocr_text = state.get("ocr_text", [])
    logger.info("[Auditor] Auditing transcript...")

    if not transcript:
        logger.warning("[Auditor] No transcript found. Skipping.")
        return {
            "final_status": "FAIL",
            "final_report": "Audit skipped — no transcript available."
        }

    # ------------------------------------------------------------------ #
    # STEP 1 — Initialize clients
    # ------------------------------------------------------------------ #
    llm = AzureChatOpenAI(
        azure_deployment=os.getenv("AZURE_OPENAI_CHAT_DEPLOYMENT"),
        openai_api_version=os.getenv("AZURE_OPENAI_API_VERSION"),
        temperature=0.0  # deterministic output — no creativity in compliance
    )

    embeddings = AzureOpenAIEmbeddings(
        azure_deployment=os.getenv("AZURE_OPENAI_EMBEDDING_DEPLOYMENT"),
        openai_api_version=os.getenv("AZURE_OPENAI_API_VERSION"),
    )

    vector_store = AzureSearch(
        azure_search_endpoint=os.getenv("AZURE_SEARCH_ENDPOINT"),
        azure_search_key=os.getenv("AZURE_SEARCH_API_KEY"),
        index_name=os.getenv("AZURE_SEARCH_INDEX_NAME"),
        embedding_function=embeddings.embed_query
    )

    # ------------------------------------------------------------------ #
    # STEP 2 — RAG: retrieve relevant compliance rules
    # Combine transcript + OCR as the search query
    # k=3 means return the 3 most relevant chunks
    # ------------------------------------------------------------------ #
    query_text = f"{transcript} {' '.join(ocr_text)}"
    docs = vector_store.similarity_search(query_text, k=3)
    retrieved_rules = "\n\n".join([doc.page_content for doc in docs])

    logger.info(f"[Auditor] Retrieved {len(docs)} rule chunks from knowledge base.")

    # ------------------------------------------------------------------ #
    # STEP 3 — Build the prompt and call GPT-4
    # Strict JSON schema enforced so parsing never breaks
    # ------------------------------------------------------------------ #
    system_prompt = f"""
You are a Senior Brand Compliance Auditor.

OFFICIAL REGULATORY RULES:
{retrieved_rules}

INSTRUCTIONS:
1. Analyze the transcript and OCR text provided.
2. The transcript includes [HH:MM:SS] timestamps at the start of each line.
3. Identify ANY violations of the rules above.
4. For each violation:
   - Set "timestamp" to the [HH:MM:SS] of the line where the violation occurs.
     If it spans multiple lines or cannot be pinned, set "timestamp" to null.
   - Set "confidence" to a float between 0.0 and 1.0 representing how certain
     you are that this is a genuine violation based on the rules provided.
     Use 0.9+ for clear, unambiguous violations. Use 0.5–0.7 for borderline cases.
5. Return ONLY valid JSON in this exact format — no markdown, no extra text:

{{
    "compliance_results": [
        {{
            "category": "Category name",
            "severity": "CRITICAL or WARNING",
            "description": "Specific explanation of the violation",
            "timestamp": "HH:MM:SS or null",
            "confidence": 0.0 to 1.0
        }}
    ],
    "status": "PASS or FAIL",
    "final_report": "One paragraph summary of findings."
}}

If no violations found, return "status": "PASS" and "compliance_results": [].
"""

    user_message = f"""
VIDEO METADATA: {state.get('video_metadata', {})}
TRANSCRIPT (each line prefixed with [HH:MM:SS]):
{transcript}
ON-SCREEN TEXT (OCR): {ocr_text}
"""

    try:
        response = llm.invoke([
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_message)
        ])

        content = response.content

        # Strip markdown code blocks if GPT-4 wraps response in ```json ... ```
        if "```" in content:
            match = re.search(r"```(?:json)?(.*?)```", content, re.DOTALL)
            if match:
                content = match.group(1)

        audit_data = json.loads(content.strip())

        # ------------------------------------------------------------------ #
        # Post-process violations — apply confidence thresholds
        #
        # >= 0.75 → keep severity as-is (confirmed violation)
        #  0.5–0.74 → downgrade severity to "REVIEW NEEDED" (borderline)
        # < 0.50  → drop entirely (too uncertain to surface)
        # ------------------------------------------------------------------ #
        raw_results = audit_data.get("compliance_results", [])
        results = []
        for r in raw_results:
            r.setdefault("timestamp", None)
            confidence = float(r.get("confidence", 1.0))
            r["confidence"] = round(confidence, 2)

            if confidence < 0.50:
                logger.info(f"[Auditor] Dropping low-confidence violation ({confidence:.2f}): {r.get('category')}")
                continue
            elif confidence < 0.75:
                r["severity"] = "REVIEW NEEDED"

            results.append(r)

        # Derive final status from surviving violations
        if not results:
            final_status = "PASS"
        elif all(r["severity"] == "REVIEW NEEDED" for r in results):
            final_status = "REVIEW"
        else:
            final_status = "FAIL"

        logger.info(f"[Auditor] {len(results)} violation(s) after confidence filtering. Status: {final_status}")

        return {
            "compliance_results": results,
            "final_status": final_status,
            "final_report": audit_data.get("final_report", "No report generated.")
        }

    except Exception as e:
        logger.error(f"[Auditor] Failed: {e}")
        return {
            "errors": [str(e)],
            "final_status": "FAIL",
            "final_report": "Audit failed due to a system error."
        }
