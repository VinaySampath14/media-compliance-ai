import streamlit as st
import requests

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
# Audit
# ------------------------------------------------------------------ #
if run and video_url:
    with st.spinner("Auditing video... this may take a few minutes."):
        try:
            response = requests.post(
                "http://localhost:8000/audit",
                json={"video_url": video_url},
                timeout=600  # 10 min max — Azure VI takes time
            )
            response.raise_for_status()
            data = response.json()

        except requests.exceptions.Timeout:
            st.error("Request timed out. Azure Video Indexer is still processing — try again.")
            st.stop()
        except requests.exceptions.ConnectionError:
            st.error("Cannot connect to the API. Make sure the FastAPI server is running.")
            st.stop()
        except Exception as e:
            st.error(f"Something went wrong: {e}")
            st.stop()

    # ------------------------------------------------------------------ #
    # Results
    # ------------------------------------------------------------------ #
    st.divider()

    # Status badge
    status = data.get("status", "UNKNOWN")
    if status == "PASS":
        st.success("PASS — No compliance violations found.")
    else:
        st.error("FAIL — Compliance violations detected.")

    # Metadata
    col1, col2 = st.columns(2)
    col1.metric("Session ID", data.get("session_id", "")[:8] + "...")
    col2.metric("Video ID", data.get("video_id", ""))

    # Violations
    violations = data.get("compliance_results", [])
    if violations:
        st.subheader(f"Violations ({len(violations)})")
        for v in violations:
            severity = v.get("severity", "WARNING")
            color = "🔴" if severity == "CRITICAL" else "🟡"
            with st.expander(f"{color} [{severity}] {v.get('category')}"):
                st.write(v.get("description"))
    else:
        st.info("No violations found.")

    # Summary
    st.subheader("Summary")
    st.write(data.get("final_report", "No report generated."))
