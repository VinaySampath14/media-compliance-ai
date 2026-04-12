from dotenv import load_dotenv
load_dotenv(override=True)
from backend.src.graph.nodes import audit_content_node

result = audit_content_node({
    "video_url": "",
    "video_id": "test",
    "compliance_results": [],
    "errors": [],
    "transcript": "I lost 30 pounds in 2 weeks using this supplement. Results guaranteed for everyone. This video is not sponsored.",
    "ocr_text": ["GUARANTEED RESULTS", "BUY NOW", "100% CURE"],
    "video_metadata": {}
})

print("Status:", result.get("final_status"))
for v in result.get("compliance_results", []):
    print(f"- [{v['severity']}] {v['category']}: {v['description']}")
