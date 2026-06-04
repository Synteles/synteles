import os

TEMPORAL_ADDRESS: str = os.environ.get("TEMPORAL_ADDRESS", "localhost:7233")
TEMPORAL_TASK_QUEUE: str = os.environ.get("TEMPORAL_TASK_QUEUE", "synteles-activities")
CORE_SERVICE_URL: str = os.environ.get("CORE_SERVICE_URL", "http://core-service:8000")
