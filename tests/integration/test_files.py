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

"""Integration tests for file exchange endpoints.

Covered:
  POST /api/files                                   — create upload session, get presigned POST URLs, upload files to S3
  GET  /api/executions/{execution_id}/files         — list input + output files

File combination scenarios tested:
  1. Input files only  — execution launched with input_objects, no output produced yet
  2. No files          — execution launched without input_objects
  3. Output only       — verified via the files endpoint shape (output.zip absent until container runs)

Note: Tests do NOT wait for execution completion. They assert the files endpoint
responds correctly for in-flight executions where container hasn't uploaded output yet.
"""

import io
import uuid

import httpx
import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _upload_file_via_presigned_post(upload_url: str, fields: dict, content: bytes, filename: str) -> int:
    """POST a file to S3 using a presigned POST envelope. Returns HTTP status."""
    multipart = {k: (None, v) for k, v in fields.items()}
    multipart["file"] = (filename, io.BytesIO(content), "application/octet-stream")
    with httpx.Client(timeout=30.0, follow_redirects=True) as c:
        resp = c.post(upload_url, files=multipart)
    return resp.status_code


@pytest.fixture()
def uploaded_files(client: httpx.Client) -> list[dict]:
    """Upload two small test files to the staging bucket; return the files list from the API."""
    response = client.post(
        "/api/files",
        json={"files": [{"name": "input.txt"}, {"name": "config.json"}]},
    )
    assert response.status_code == 201, (
        f"Failed to create upload session: {response.text}"
    )
    data = response.json()
    assert "upload_id" in data
    assert len(data["files"]) == 2

    for entry in data["files"]:
        status = _upload_file_via_presigned_post(
            upload_url=entry["upload_url"],
            fields=entry["upload_fields"],
            content=b"integration test file content",
            filename=entry["name"],
        )
        assert status in (200, 204), (
            f"S3 presigned POST for {entry['name']!r} failed with HTTP {status}"
        )

    return data["files"]


@pytest.fixture()
def execution_with_files(
    client: httpx.Client,
    org_id: str,
    shared_agentlet: dict,
    uploaded_files: list[dict],
) -> dict:
    """Launch an execution with input files; terminate on teardown."""
    input_objects = [f["s3_uri"] for f in uploaded_files]
    agentlet_id = shared_agentlet["id"]

    response = client.post(
        "/api/executions",
        json={"agentlet_id": agentlet_id, "timeout": 60, "input_objects": input_objects},
    )
    assert response.status_code == 202, (
        f"Failed to launch execution with files: {response.text}"
    )
    execution = response.json()

    yield execution

    client.delete(f"/api/executions/{execution['execution_id']}")


@pytest.fixture()
def execution_without_files(
    client: httpx.Client,
    org_id: str,
    shared_agentlet: dict,
) -> dict:
    """Launch a plain execution with no input files; terminate on teardown."""
    agentlet_id = shared_agentlet["id"]
    response = client.post(
        "/api/executions",
        json={"agentlet_id": agentlet_id, "timeout": 60},
    )
    assert response.status_code == 202, (
        f"Failed to launch execution without files: {response.text}"
    )
    execution = response.json()

    yield execution

    client.delete(f"/api/executions/{execution['execution_id']}")


# ---------------------------------------------------------------------------
# POST /api/files
# ---------------------------------------------------------------------------

class TestUploadUrls:
    def test_returns_presigned_post_urls(self, client: httpx.Client) -> None:
        response = client.post(
            "/api/files",
            json={"files": [{"name": "test.csv"}]},
        )

        assert response.status_code == 201
        data = response.json()
        assert "upload_id" in data
        assert len(data["files"]) == 1
        f = data["files"][0]
        assert f["name"] == "test.csv"
        assert f["s3_uri"].startswith("s3://")
        assert f["upload_url"].startswith(("http://", "https://"))
        assert isinstance(f["upload_fields"], dict)

    def test_multiple_files_share_upload_id(self, client: httpx.Client) -> None:
        response = client.post(
            "/api/files",
            json={"files": [{"name": "a.txt"}, {"name": "b.txt"}]},
        )

        assert response.status_code == 201
        data = response.json()
        upload_id = data["upload_id"]
        for f in data["files"]:
            assert f["s3_uri"].startswith(f"s3://"), "URIs must start with s3://"
            assert f"/{upload_id}/" in f["s3_uri"], "All files must share upload_id in path"

    def test_file_actually_uploads_via_presigned_post(self, client: httpx.Client) -> None:
        response = client.post(
            "/api/files",
            json={"files": [{"name": "hello.txt"}]},
        )
        assert response.status_code == 201
        entry = response.json()["files"][0]

        status = _upload_file_via_presigned_post(
            upload_url=entry["upload_url"],
            fields=entry["upload_fields"],
            content=b"hello from integration test",
            filename="hello.txt",
        )

        assert status in (200, 204), f"S3 upload returned HTTP {status}"

    def test_empty_files_list_rejected(self, client: httpx.Client) -> None:
        response = client.post("/api/files", json={"files": []})

        assert response.status_code == 400

    def test_too_many_files_rejected(self, client: httpx.Client) -> None:
        response = client.post(
            "/api/files",
            json={"files": [{"name": f"f{i}.txt"} for i in range(21)]},
        )

        assert response.status_code == 400

    def test_no_token_returns_401(self, unauth_client: httpx.Client) -> None:
        response = unauth_client.post(
            "/api/files",
            json={"files": [{"name": "test.txt"}]},
        )

        assert response.status_code == 401


# ---------------------------------------------------------------------------
# GET /api/executions/{execution_id}/files
# ---------------------------------------------------------------------------

class TestExecutionFiles:
    def test_input_files_appear_after_launch(
        self, client: httpx.Client, execution_with_files: dict
    ) -> None:
        """Case 1: execution launched with input files — files endpoint shows them."""
        execution_id = execution_with_files["execution_id"]
        response = client.get(f"/api/executions/{execution_id}/files")

        assert response.status_code == 200
        data = response.json()
        assert data["execution_id"] == execution_id
        assert len(data["input_files"]) == 2
        names = {f["name"] for f in data["input_files"]}
        assert names == {"input.txt", "config.json"}
        for f in data["input_files"]:
            assert "download_url" in f
            assert f["download_url"].startswith(("http://", "https://"))
            assert f["size"] > 0

    def test_no_output_zip_while_running(
        self, client: httpx.Client, execution_with_files: dict
    ) -> None:
        """Output zip not present for in-flight execution (container hasn't finished)."""
        execution_id = execution_with_files["execution_id"]
        response = client.get(f"/api/executions/{execution_id}/files")

        assert response.status_code == 200
        data = response.json()
        # Container is still running — output.zip not uploaded yet
        assert data["output_zip"]["exists"] is False
        assert data["output_zip"]["download_url"] is None

    def test_no_input_files_when_launched_without_files(
        self, client: httpx.Client, execution_without_files: dict
    ) -> None:
        """Case 2/3 baseline: no input files when none were provided."""
        execution_id = execution_without_files["execution_id"]
        response = client.get(f"/api/executions/{execution_id}/files")

        assert response.status_code == 200
        data = response.json()
        assert data["input_files"] == []
        assert data["output_zip"]["exists"] is False

    def test_response_shape_is_complete(
        self, client: httpx.Client, execution_without_files: dict
    ) -> None:
        """Files endpoint always returns both input_files and output_zip fields."""
        execution_id = execution_without_files["execution_id"]
        response = client.get(f"/api/executions/{execution_id}/files")

        assert response.status_code == 200
        data = response.json()
        assert "execution_id" in data
        assert "input_files" in data
        assert "output_zip" in data
        assert "exists" in data["output_zip"]
        assert "download_url" in data["output_zip"]

    def test_input_file_download_urls_are_accessible(
        self, client: httpx.Client, execution_with_files: dict
    ) -> None:
        """Presigned GET URLs returned by the files endpoint should be reachable."""
        execution_id = execution_with_files["execution_id"]
        response = client.get(f"/api/executions/{execution_id}/files")
        assert response.status_code == 200
        data = response.json()

        for f in data["input_files"]:
            with httpx.Client(timeout=15.0) as c:
                dl = c.get(f["download_url"])
            # Presigned GET may return 200 or redirect; not 4xx/5xx
            assert dl.status_code < 400, (
                f"Presigned GET for {f['name']!r} returned {dl.status_code}"
            )

    def test_no_token_returns_401(
        self, unauth_client: httpx.Client, execution_without_files: dict
    ) -> None:
        execution_id = execution_without_files["execution_id"]
        response = unauth_client.get(f"/api/executions/{execution_id}/files")

        assert response.status_code == 401

    def test_nonexistent_execution_returns_404(self, client: httpx.Client) -> None:
        response = client.get(
            f"/api/executions/00000000-0000-4000-8000-000000000000/files"
        )

        assert response.status_code == 404

    def test_invalid_uuid_returns_400(self, client: httpx.Client) -> None:
        response = client.get("/api/executions/not-a-uuid/files")

        assert response.status_code == 400
