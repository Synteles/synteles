# durable-worker/tests/conftest.py
"""Set env vars before any module-level imports are triggered by test collection."""

import os

os.environ["TEMPORAL_ADDRESS"] = "localhost:7233"
os.environ["TEMPORAL_TASK_QUEUE"] = "test-queue"
os.environ["EXECUTION_ID"] = "test-exec-id"
os.environ["SYNTELES_MANIFEST_URL"] = "http://localhost/manifest.json"
os.environ["OPENAI_MODEL"] = "gpt-4o"
