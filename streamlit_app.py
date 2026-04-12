import time
import requests
import streamlit as st

BASE_URL = "http://localhost:8000"

# ------------------------------------------------------------------ #
# Page config
# ------------------------------------------------------------------ #
st.set_page_config(
    page_title="Media Compliance AI",
    page_icon="🎬",
    layout="centered"
)

st.title("Media Compliance AI")
st.caption("Audit YouTube videos against brand compliance rules.")

# ------------------------------------------------------------------ #
# Input
# ------------------------------------------------------------------ #
video_url = st.text_input(
    "YouTube URL",
    placeholder="https://youtu.be/..."
)

run = st.button("Run Audit", type="primary", disabled=not video_url)

# ------------------------------------------------------------------ #
# Audit — submit then poll
# ------------------------------------------------------------------ #
if run and video_url:

    # 1. Submit the job
    try:
        submit = requests.post(
            f"{BASE_URL}/audit",
            json={"video_url": video_url},
            timeout=15
        )
        submit.raise_for_status()
        job = submit.json()
        job_id = job["job_id"]
    except requests.exceptions.ConnectionError:
        st.error("Cannot connect to the API. Make sure the FastAPI server is running.")
        st.stop()
    except Exception as e:
        st.error(f"Failed to submit audit: {e}")
        st.stop()

    st.info(f"Audit queued — Job ID: `{job_id}`")

    # 2. Poll for results
    status_placeholder = st.empty()
    MAX_WAIT_SECONDS = 600   # 10 min
    POLL_INTERVAL    = 5     # seconds between polls
    elapsed          = 0

    with st.spinner("Auditing video... this may take a few minutes."):
        while elapsed < MAX_WAIT_SECONDS:
            try:
                poll = requests.get(f"{BASE_URL}/audit/{job_id}", timeout=10)
                poll.raise_for_status()
                data = poll.json()
            except Exception as e:
                st.error(f"Error polling for results: {e}")
                st.stop()

            status = data.get("status")
            status_placeholder.caption(f"Status: **{status}** ({elapsed}s elapsed)")

            if status == "COMPLETED":
                break
            elif status == "FAILED":
                st.error(f"Audit failed: {data.get('error', 'Unknown error')}")
                st.stop()

            time.sleep(POLL_INTERVAL)
            elapsed += POLL_INTERVAL
        else:
            st.error("Audit timed out after 10 minutes. Try again.")
            st.stop()

    status_placeholder.empty()

    # ------------------------------------------------------------------ #
    # Results
    # ------------------------------------------------------------------ #
    st.divider()

    final_status = data.get("final_status", "UNKNOWN")
    if final_status == "PASS":
        st.success("PASS — No compliance violations found.")
    elif final_status == "REVIEW":
        st.warning("REVIEW NEEDED — Borderline violations detected. Human review recommended.")
    else:
        st.error("FAIL — Compliance violations detected.")

    # Metadata
    col1, col2 = st.columns(2)
    col1.metric("Session ID", data.get("session_id", "")[:8] + "...")
    col2.metric("Video ID",   data.get("video_id", ""))

    # Violations
    violations = data.get("compliance_results", [])
    if violations:
        st.subheader(f"Violations ({len(violations)})")
        for v in violations:
            severity   = v.get("severity", "WARNING")
            timestamp  = v.get("timestamp")
            confidence = v.get("confidence", 1.0)
            ts_label   = f" · ⏱ {timestamp}" if timestamp else ""

            if severity == "CRITICAL":
                color = "🔴"
            elif severity == "REVIEW NEEDED":
                color = "🟠"
            else:
                color = "🟡"

            with st.expander(f"{color} [{severity}] {v.get('category')}{ts_label}"):
                st.write(v.get("description"))

                col1, col2 = st.columns([3, 1])
                col1.progress(confidence, text=f"Confidence: {int(confidence * 100)}%")
                if timestamp:
                    col2.caption(f"⏱ `{timestamp}`")
    else:
        st.info("No violations found.")

    # Summary
    st.subheader("Summary")
    st.write(data.get("final_report", "No report generated."))
