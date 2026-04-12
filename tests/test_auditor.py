"""
Tests for the Auditor node (audit_content_node).

All Azure and LLM calls are mocked — no real credentials needed.
Run with: pytest tests/test_auditor.py -v
"""

import json
import pytest
from unittest.mock import MagicMock, patch


# ------------------------------------------------------------------ #
# Helpers
# ------------------------------------------------------------------ #

def _make_state(transcript="This is a test ad.", ocr_text=None):
    """Build a minimal VideoAuditState dict for testing."""
    return {
        "video_url": "https://www.youtube.com/watch?v=test",
        "video_id": "vid_test001",
        "transcript": transcript,
        "ocr_text": ocr_text or [],
        "video_metadata": {},
        "compliance_results": [],
        "errors": [],
    }


def _llm_response(payload: dict) -> MagicMock:
    """Return a mock LLM response whose .content is the JSON string of payload."""
    mock_msg = MagicMock()
    mock_msg.content = json.dumps(payload)
    return mock_msg


# ------------------------------------------------------------------ #
# Test 1 — PASS verdict: no violations found
# ------------------------------------------------------------------ #

@patch("langchain_community.vectorstores.AzureSearch")
@patch("langchain_openai.AzureOpenAIEmbeddings")
@patch("langchain_openai.AzureChatOpenAI")
def test_auditor_returns_pass_when_no_violations(mock_llm_cls, mock_emb_cls, mock_search_cls):
    """When GPT-4 finds no violations the node must return status PASS and an empty list."""
    from backend.src.graph.nodes import audit_content_node

    # --- mock vector store returns one dummy doc ---
    mock_doc = MagicMock()
    mock_doc.page_content = "Ads must include clear disclosures."
    mock_search_cls.return_value.similarity_search.return_value = [mock_doc]

    # --- mock LLM returns a clean PASS response ---
    mock_llm_cls.return_value.invoke.return_value = _llm_response({
        "compliance_results": [],
        "status": "PASS",
        "final_report": "No violations found. The ad is fully compliant."
    })

    state = _make_state(transcript="Buy our product today. Ad paid for by ACME Corp.")
    result = audit_content_node(state)

    assert result["final_status"] == "PASS"
    assert result["compliance_results"] == []
    assert "No violations" in result["final_report"]


# ------------------------------------------------------------------ #
# Test 2 — FAIL verdict: violations detected
# ------------------------------------------------------------------ #

@patch("langchain_community.vectorstores.AzureSearch")
@patch("langchain_openai.AzureOpenAIEmbeddings")
@patch("langchain_openai.AzureChatOpenAI")
def test_auditor_returns_violations_on_fail(mock_llm_cls, mock_emb_cls, mock_search_cls):
    """When GPT-4 detects violations the node must return them with correct shape."""
    from backend.src.graph.nodes import audit_content_node

    mock_doc = MagicMock()
    mock_doc.page_content = "Sponsored content must be disclosed within the first 30 seconds."
    mock_search_cls.return_value.similarity_search.return_value = [mock_doc]

    violations = [
        {
            "category": "FTC Disclosure",
            "severity": "CRITICAL",
            "description": "Sponsorship not disclosed at the start of the video."
        }
    ]
    mock_llm_cls.return_value.invoke.return_value = _llm_response({
        "compliance_results": violations,
        "status": "FAIL",
        "final_report": "One critical violation detected: missing FTC disclosure."
    })

    state = _make_state(transcript="This amazing supplement cured my disease overnight!")
    result = audit_content_node(state)

    assert result["final_status"] == "FAIL"
    assert len(result["compliance_results"]) == 1
    assert result["compliance_results"][0]["severity"] == "CRITICAL"
    assert result["compliance_results"][0]["category"] == "FTC Disclosure"
    assert "final_report" in result


# ------------------------------------------------------------------ #
# Test 3 — Missing transcript: node must short-circuit gracefully
# ------------------------------------------------------------------ #

def test_auditor_skips_when_no_transcript():
    """If transcript is empty the node must return FAIL without calling the LLM."""
    from backend.src.graph.nodes import audit_content_node

    state = _make_state(transcript="")
    result = audit_content_node(state)

    assert result["final_status"] == "FAIL"
    assert "skipped" in result["final_report"].lower()


# ------------------------------------------------------------------ #
# Test 4 — LLM wraps response in markdown code block
# ------------------------------------------------------------------ #

@patch("langchain_community.vectorstores.AzureSearch")
@patch("langchain_openai.AzureOpenAIEmbeddings")
@patch("langchain_openai.AzureChatOpenAI")
def test_auditor_handles_markdown_wrapped_json(mock_llm_cls, mock_emb_cls, mock_search_cls):
    """GPT-4 sometimes wraps JSON in ```json ... ``` — node must strip it and still parse."""
    from backend.src.graph.nodes import audit_content_node

    mock_doc = MagicMock()
    mock_doc.page_content = "All claims must be substantiated."
    mock_search_cls.return_value.similarity_search.return_value = [mock_doc]

    raw_payload = {
        "compliance_results": [],
        "status": "PASS",
        "final_report": "Ad is compliant."
    }
    # Simulate GPT-4 wrapping the JSON in a markdown code block
    mock_msg = MagicMock()
    mock_msg.content = f"```json\n{json.dumps(raw_payload)}\n```"
    mock_llm_cls.return_value.invoke.return_value = mock_msg

    state = _make_state(transcript="Our product is great. Tested by experts.")
    result = audit_content_node(state)

    assert result["final_status"] == "PASS"
    assert result["compliance_results"] == []
