import os
import logging
from azure.monitor.opentelemetry import configure_azure_monitor

logger = logging.getLogger("media-compliance-ai-telemetry")


def setup_telemetry():
    """
    Initializes Azure Monitor (Application Insights) telemetry.
    Once called, automatically tracks all FastAPI requests,
    response times, errors, and dependency calls (Azure Search, OpenAI).
    Silently skips if connection string is not configured.
    """
    connection_string = os.getenv("APPLICATIONINSIGHTS_CONNECTION_STRING")

    if not connection_string:
        logger.warning("App Insights not configured. Telemetry is disabled.")
        return

    try:
        configure_azure_monitor(
            connection_string=connection_string,
            logger_name="media-compliance-ai-tracer"
        )
        logger.info("Azure Monitor telemetry enabled.")
    except Exception as e:
        logger.error(f"Failed to initialize telemetry: {e}")
        # Don't crash the app if telemetry fails — it's observability, not core logic
