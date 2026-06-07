import os

TEMPORAL_ADDRESS: str = os.environ.get("TEMPORAL_ADDRESS", "localhost:7233")
TEMPORAL_TASK_QUEUE: str = os.environ.get("TEMPORAL_TASK_QUEUE", "")
EXECUTION_ID: str = os.environ.get("EXECUTION_ID", "")
SYNTELES_MANIFEST_URL: str = os.environ.get("SYNTELES_MANIFEST_URL", "")
