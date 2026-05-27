# Copyright 2026 Emin Askerov
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Integration tests for execution lifecycle endpoints.

Covered:
  POST   /api/executions
  GET    /api/executions
  GET    /api/executions/{execution_id}
  GET    /api/executions/{execution_id}/logs
  POST   /api/executions/{execution_id}/cancel

Note: Tests do NOT wait for execution completion. They assert that
execution is accepted (202) and that the status/logs endpoints respond
correctly for an in-flight execution.
"""

import io

import httpx
import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

@pytest.fixture()
def launched_execution(
    client: httpx.Client, org_id: str, shared_agentlet: dict
) -> dict:
    """Launch a single execution; terminate it on teardown."""
    agentlet_id = shared_agentlet["id"]
    response = client.post(
        "/api/executions",
        json={"agentlet_id": agentlet_id, "timeout": 60},
    )
    assert response.status_code == 202, (
        f"Failed to launch execution for test: {response.text}"
    )
    execution = response.json()

    yield execution

    execution_id = execution["execution_id"]
    client.post(f"/api/executions/{execution_id}/cancel")


# ---------------------------------------------------------------------------
# Launch execution
# ---------------------------------------------------------------------------

class TestLaunchExecution:
    def test_happy_path_returns_202(
        self, client: httpx.Client, org_id: str, shared_agentlet: dict
    ) -> None:
        agentlet_id = shared_agentlet["id"]
        response = client.post(
            "/api/executions",
            json={"agentlet_id": agentlet_id, "timeout": 60},
        )

        assert response.status_code == 202
        data = response.json()
        assert "execution_id" in data
        assert data["agentlet_id"] == agentlet_id

        # cleanup
        client.post(f"/api/executions/{data['execution_id']}/cancel")

    def test_no_token_returns_401(
        self, unauth_client: httpx.Client, org_id: str, shared_agentlet: dict
    ) -> None:
        agentlet_id = shared_agentlet["id"]
        response = unauth_client.post(
            "/api/executions",
            json={"agentlet_id": agentlet_id},
        )

        assert response.status_code == 401

    def test_nonexistent_agentlet_returns_404(
        self, client: httpx.Client, org_id: str
    ) -> None:
        import uuid as _uuid
        agentlet_id = f"nonexistent_{_uuid.uuid4().hex[:12]}"
        response = client.post(
            "/api/executions",
            json={"agentlet_id": agentlet_id},
        )

        assert response.status_code in (404, 500)


# ---------------------------------------------------------------------------
# List executions
# ---------------------------------------------------------------------------

class TestListExecutions:
    def test_happy_path_returns_list(
        self, client: httpx.Client, launched_execution: dict
    ) -> None:
        response = client.get("/api/executions")

        assert response.status_code == 200
        data = response.json()
        assert "executions" in data
        assert isinstance(data["executions"], list)

    def test_no_token_returns_401(self, unauth_client: httpx.Client) -> None:
        response = unauth_client.get("/api/executions")

        assert response.status_code == 401

    def test_filter_by_agentlet_id(
        self, client: httpx.Client, shared_agentlet: dict, launched_execution: dict
    ) -> None:
        agentlet_id = shared_agentlet["id"]
        response = client.get("/api/executions", params={"agentlet_id": agentlet_id})

        assert response.status_code == 200
        data = response.json()
        for execution in data["executions"]:
            assert execution["agentlet_id"] == agentlet_id

    def test_filter_by_status(
        self, client: httpx.Client, launched_execution: dict
    ) -> None:
        response = client.get("/api/executions", params={"status": "deploying"})

        assert response.status_code == 200
        data = response.json()
        assert "executions" in data
        for execution in data["executions"]:
            assert execution["status"] == "deploying"


# ---------------------------------------------------------------------------
# Get execution status
# ---------------------------------------------------------------------------

class TestGetExecutionStatus:
    def test_happy_path_returns_status(
        self, client: httpx.Client, launched_execution: dict
    ) -> None:
        execution_id = launched_execution["execution_id"]
        response = client.get(f"/api/executions/{execution_id}")

        assert response.status_code == 200
        data = response.json()
        assert "status" in data
        assert data["status"] in ("deploying", "running", "completed", "failed", "terminated")

    def test_no_token_returns_401(
        self, unauth_client: httpx.Client, launched_execution: dict
    ) -> None:
        execution_id = launched_execution["execution_id"]
        response = unauth_client.get(f"/api/executions/{execution_id}")

        assert response.status_code == 401

    def test_nonexistent_execution_returns_404(self, client: httpx.Client) -> None:
        response = client.get("/api/executions/00000000-0000-0000-0000-000000000000")

        assert response.status_code == 404


# ---------------------------------------------------------------------------
# Get execution logs
# ---------------------------------------------------------------------------

class TestGetExecutionLogs:
    def test_happy_path_in_flight_returns_202(
        self, client: httpx.Client, launched_execution: dict
    ) -> None:
        execution_id = launched_execution["execution_id"]
        response = client.get(f"/api/executions/{execution_id}/logs")

        # Execution just launched; logs are not yet available
        assert response.status_code in (200, 202)
        if response.status_code == 202:
            data = response.json()
            assert data.get("logs_available") is False

    def test_no_token_returns_401(
        self, unauth_client: httpx.Client, launched_execution: dict
    ) -> None:
        execution_id = launched_execution["execution_id"]
        response = unauth_client.get(f"/api/executions/{execution_id}/logs")

        assert response.status_code == 401

    def test_format_json_returns_json_response(
        self, client: httpx.Client, launched_execution: dict
    ) -> None:
        execution_id = launched_execution["execution_id"]
        response = client.get(
            f"/api/executions/{execution_id}/logs", params={"format": "json"}
        )

        assert response.status_code in (200, 202)
        # When format=json the response body must be valid JSON
        data = response.json()
        assert "execution_id" in data

    def test_download_flag_accepted(
        self, client: httpx.Client, launched_execution: dict
    ) -> None:
        execution_id = launched_execution["execution_id"]
        response = client.get(
            f"/api/executions/{execution_id}/logs", params={"download": "true"}
        )

        # Should not error out; still returns 200 or 202 depending on execution state
        assert response.status_code in (200, 202)

    def test_nonexistent_execution_returns_404(self, client: httpx.Client) -> None:
        response = client.get("/api/executions/00000000-0000-0000-0000-000000000000/logs")

        assert response.status_code == 404


# ---------------------------------------------------------------------------
# Terminate execution
# ---------------------------------------------------------------------------

class TestTerminateExecution:
    def test_happy_path_terminates_execution(
        self, client: httpx.Client, org_id: str, shared_agentlet: dict
    ) -> None:
        # Launch a fresh execution specifically to terminate it
        agentlet_id = shared_agentlet["id"]
        launch = client.post(
            "/api/executions",
            json={"agentlet_id": agentlet_id, "timeout": 60},
        )
        assert launch.status_code == 202
        execution_id = launch.json()["execution_id"]

        response = client.post(f"/api/executions/{execution_id}/cancel")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "terminated"

    def test_no_token_returns_401(
        self, unauth_client: httpx.Client, launched_execution: dict
    ) -> None:
        execution_id = launched_execution["execution_id"]
        response = unauth_client.post(f"/api/executions/{execution_id}/cancel")

        assert response.status_code == 401

    def test_nonexistent_execution_returns_404(self, client: httpx.Client) -> None:
        response = client.post("/api/executions/00000000-0000-0000-0000-000000000000/cancel")

        assert response.status_code == 404


# ---------------------------------------------------------------------------
# Launch execution with input files
# ---------------------------------------------------------------------------

def _upload_test_file(client: httpx.Client, filename: str, content: bytes) -> str:
    """Get a presigned POST URL, upload a file to S3, return the s3_uri."""
    r = client.post("/api/files", json={"files": [{"name": filename}]})
    assert r.status_code == 201, f"POST /api/files failed: {r.text}"
    entry = r.json()["files"][0]

    multipart = {k: (None, v) for k, v in entry["upload_fields"].items()}
    multipart["file"] = (filename, io.BytesIO(content), "application/octet-stream")
    with httpx.Client(timeout=30.0, follow_redirects=True) as c:
        up = c.post(entry["upload_url"], files=multipart)
    assert up.status_code in (200, 204), f"S3 upload returned {up.status_code}"

    return entry["s3_uri"]


class TestLaunchExecutionWithFiles:
    def test_launch_with_input_files_returns_202(
        self, client: httpx.Client, org_id: str, shared_agentlet: dict
    ) -> None:
        s3_uri = _upload_test_file(client, "data.csv", b"col1,col2\n1,2\n3,4\n")

        agentlet_id = shared_agentlet["id"]
        response = client.post(
            "/api/executions",
            json={"agentlet_id": agentlet_id, "timeout": 60, "input_objects": [s3_uri]},
        )

        assert response.status_code == 202
        data = response.json()
        assert "execution_id" in data
        assert data["agentlet_id"] == agentlet_id

        client.post(f"/api/executions/{data['execution_id']}/cancel")

    def test_input_files_visible_in_files_endpoint_after_launch(
        self, client: httpx.Client, org_id: str, shared_agentlet: dict
    ) -> None:
        s3_uri = _upload_test_file(client, "input.txt", b"hello world")

        agentlet_id = shared_agentlet["id"]
        launch = client.post(
            "/api/executions",
            json={"agentlet_id": agentlet_id, "timeout": 60, "input_objects": [s3_uri]},
        )
        assert launch.status_code == 202
        execution_id = launch.json()["execution_id"]

        files_response = client.get(f"/api/executions/{execution_id}/files")

        assert files_response.status_code == 200
        data = files_response.json()
        assert len(data["input_files"]) == 1
        assert data["input_files"][0]["name"] == "input.txt"

        client.post(f"/api/executions/{execution_id}/cancel")

    def test_too_many_input_objects_rejected(
        self, client: httpx.Client, org_id: str, shared_agentlet: dict
    ) -> None:
        agentlet_id = shared_agentlet["id"]
        fake_uris = [f"s3://bucket/uid/f{i}.txt" for i in range(21)]

        response = client.post(
            "/api/executions",
            json={"agentlet_id": agentlet_id, "timeout": 60, "input_objects": fake_uris},
        )

        assert response.status_code == 400


# ---------------------------------------------------------------------------
# List executions — date filter regression tests
# ---------------------------------------------------------------------------

class TestListExecutionsDateFilters:
    """Regression tests for the created_at_start/end filter bug.

    The KeyConditionExpression previously used lowercase 'created_at' instead
    of the DynamoDB attribute name 'CreatedAt', so date filters were silently
    ignored and all executions were returned regardless of the filter value.
    """

    def test_created_at_start_far_future_returns_empty(
        self, client: httpx.Client, launched_execution: dict
    ) -> None:
        """A start date far in the future must filter out all existing executions."""
        response = client.get(
            "/api/executions",
            params={"created_at_start": "2099-01-01T00:00:00Z"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["executions"] == [], (
            "created_at_start filter was ignored — returned executions when none expected"
        )

    def test_created_at_end_far_past_returns_empty(
        self, client: httpx.Client, launched_execution: dict
    ) -> None:
        """An end date far in the past must filter out all existing executions."""
        response = client.get(
            "/api/executions",
            params={"created_at_end": "2000-01-01T00:00:00Z"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["executions"] == [], (
            "created_at_end filter was ignored — returned executions when none expected"
        )

    def test_created_at_start_before_execution_returns_it(
        self, client: httpx.Client, shared_agentlet: dict, launched_execution: dict
    ) -> None:
        """A start date before the execution's CreatedAt must include it."""
        agentlet_id = shared_agentlet["id"]
        created_at = launched_execution["created_at"]

        response = client.get(
            "/api/executions",
            params={
                "agentlet_id": agentlet_id,
                "created_at_start": "2000-01-01T00:00:00Z",
            },
        )

        assert response.status_code == 200
        data = response.json()
        exec_ids = [e["execution_id"] for e in data["executions"]]
        assert launched_execution["execution_id"] in exec_ids, (
            f"Execution with created_at={created_at} was unexpectedly filtered out "
            "by created_at_start=2000-01-01"
        )

    def test_created_at_range_far_past_returns_empty(
        self, client: httpx.Client, shared_agentlet: dict, launched_execution: dict
    ) -> None:
        """A date range entirely in the past must return no executions."""
        agentlet_id = shared_agentlet["id"]
        response = client.get(
            "/api/executions",
            params={
                "agentlet_id": agentlet_id,
                "created_at_start": "2000-01-01T00:00:00Z",
                "created_at_end": "2000-12-31T23:59:59Z",
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["executions"] == [], (
            "created_at range filter was ignored — returned executions when none expected"
        )


# ---------------------------------------------------------------------------
# List executions — pagination structure
# ---------------------------------------------------------------------------

class TestListExecutionsPagination:
    def test_response_has_count_field(
        self, client: httpx.Client, launched_execution: dict
    ) -> None:
        response = client.get("/api/executions")

        assert response.status_code == 200
        data = response.json()
        assert "count" in data
        assert isinstance(data["count"], int)

    def test_next_token_absent_when_results_fit_single_page(
        self, client: httpx.Client, shared_agentlet: dict, launched_execution: dict
    ) -> None:
        """next_token must be absent when results fit in one page.

        Scoped to the session agentlet to avoid depending on total execution
        count in the live database (which grows across test runs).
        """
        agentlet_id = shared_agentlet["id"]
        response = client.get(
            "/api/executions",
            params={"agentlet_id": agentlet_id, "limit": "100"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data.get("next_token") is None
