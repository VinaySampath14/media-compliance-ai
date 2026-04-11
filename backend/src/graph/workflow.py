from langgraph.graph import StateGraph, END

from backend.src.graph.state import VideoAuditState
from backend.src.graph.nodes import index_video_node, audit_content_node


def create_graph():
    # 1. Create a graph that uses VideoAuditState as the shared whiteboard
    workflow = StateGraph(VideoAuditState)

    # 2. Register the nodes (the workers)
    workflow.add_node("indexer", index_video_node)
    workflow.add_node("auditor", audit_content_node)

    # 3. Define the flow
    workflow.set_entry_point("indexer")   # START → indexer
    workflow.add_edge("indexer", "auditor")  # indexer → auditor
    workflow.add_edge("auditor", END)        # auditor → END

    # 4. Compile into a runnable
    return workflow.compile()


# Expose the compiled graph for import by main.py and server.py
app = create_graph()
