import uuid
import json
import logging
from dotenv import load_dotenv

load_dotenv(override=True)

from backend.src.graph.workflow import app

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("media-compliance-ai")


def run():
    session_id = str(uuid.uuid4())
    logger.info(f"Starting Audit Session: {session_id}")

    initial_inputs = {
        "video_url": "https://youtu.be/dT7S75eYhcQ",
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


if __name__ == "__main__":
    run()
