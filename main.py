import uuid
import json
import logging
from dotenv import load_dotenv

load_dotenv(override=True)

from backend.src.graph.workflow import app

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

# Suppress noisy Azure SDK and OpenTelemetry logs
logging.getLogger("azure").setLevel(logging.WARNING)
logging.getLogger("opentelemetry").setLevel(logging.WARNING)
logging.getLogger("urllib3").setLevel(logging.WARNING)

logger = logging.getLogger("media-compliance-ai")


def run():
    session_id = str(uuid.uuid4())
    logger.info(f"Starting Audit Session: {session_id}")

    initial_inputs = {
        "video_url": "https://www.youtube.com/watch?v=idnwh6iDnXA",
        "video_id": f"vid_{session_id[:8]}",
        "compliance_results": [],
        "errors": []
    }

    print("\n--- INPUT ---")
    print(json.dumps(initial_inputs, indent=2))

    final_state = app.invoke(initial_inputs)

    print("\n=== COMPLIANCE AUDIT REPORT ===")
    print(f"Video ID : {final_state.get('video_id')}")
    print(f"Status   : {final_state.get('final_status')}")

    print("\n[ VIOLATIONS ]")
    results = final_state.get("compliance_results", [])
    if results:
        for issue in results:
            print(f"- [{issue.get('severity')}] {issue.get('category')}: {issue.get('description')}")
    else:
        print("No violations found.")

    print("\n[ SUMMARY ]")
    print(final_state.get("final_report"))

    print("\n[ TRANSCRIPT ]")
    print(final_state.get("transcript", "No transcript"))



if __name__ == "__main__":
    run()
