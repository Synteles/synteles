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

"""Unit tests for pure helper functions in routers/execute.py."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException

from routers.execute import (
    _copy_input_files,
    _fetch_user_secrets,
    _file_type,
    _generate_output_presigned_url,
    _run_execution,
    _upload_execution_manifest,
)

# ---------------------------------------------------------------------------
# _file_type
# ---------------------------------------------------------------------------

_VALID_UUID = "123e4567-e89b-4d3c-a456-426614174000"


def test_file_type_image_jpg() -> None:
    assert _file_type("photo.jpg") == "image"


def test_file_type_image_jpeg() -> None:
    assert _file_type("photo.jpeg") == "image"


def test_file_type_image_png_uppercase() -> None:
    assert _file_type("banner.PNG") == "image"


def test_file_type_image_gif() -> None:
    assert _file_type("anim.gif") == "image"


def test_file_type_image_webp() -> None:
    assert _file_type("img.webp") == "image"


def test_file_type_document_pdf() -> None:
    assert _file_type("report.pdf") == "document"


def test_file_type_document_csv() -> None:
    assert _file_type("data.csv") == "document"


def test_file_type_document_txt() -> None:
    assert _file_type("README.txt") == "document"


def test_file_type_unknown_extension_is_document() -> None:
    assert _file_type("archive.zip") == "document"


def test_file_type_no_extension_is_document() -> None:
    assert _file_type("Makefile") == "document"


# ---------------------------------------------------------------------------
# _copy_input_files
# ---------------------------------------------------------------------------


def test_copy_input_files_empty_returns_empty() -> None:
    s3 = MagicMock()
    result = _copy_input_files(s3, [], "exec-1")
    assert result == []
    s3.copy_object.assert_not_called()


def test_copy_input_files_copies_and_returns_presigned() -> None:
    s3 = MagicMock()
    s3.generate_presigned_url.return_value = "https://presigned.url/file.pdf"

    with (
        patch("config.S3_UPLOAD_BUCKET", "upload-bucket"),
        patch("config.S3_LOGS_BUCKET", "logs-bucket"),
    ):
        result = _copy_input_files(
            s3,
            [f"s3://upload-bucket/{_VALID_UUID}/report.pdf"],
            "exec-1",
        )

    assert len(result) == 1
    assert result[0]["name"] == "report.pdf"
    assert result[0]["type"] == "document"
    assert result[0]["url"] == "https://presigned.url/file.pdf"
    s3.copy_object.assert_called_once()


def test_copy_input_files_image_type_detected() -> None:
    s3 = MagicMock()
    s3.generate_presigned_url.return_value = "https://presigned.url/photo.jpg"

    with (
        patch("config.S3_UPLOAD_BUCKET", "upload-bucket"),
        patch("config.S3_LOGS_BUCKET", "logs-bucket"),
    ):
        result = _copy_input_files(
            s3,
            [f"s3://upload-bucket/{_VALID_UUID}/photo.jpg"],
            "exec-1",
        )

    assert result[0]["type"] == "image"


def test_copy_input_files_wrong_bucket_raises() -> None:
    s3 = MagicMock()
    with (
        patch("config.S3_UPLOAD_BUCKET", "correct-bucket"),
        patch("config.S3_LOGS_BUCKET", "logs-bucket"),
    ):
        with pytest.raises(RuntimeError, match="wrong bucket"):
            _copy_input_files(s3, ["s3://wrong-bucket/uuid/file.pdf"], "exec-1")


def test_copy_input_files_invalid_upload_id_raises() -> None:
    s3 = MagicMock()
    with (
        patch("config.S3_UPLOAD_BUCKET", "upload-bucket"),
        patch("config.S3_LOGS_BUCKET", "logs-bucket"),
    ):
        with pytest.raises(RuntimeError, match="Invalid upload_id"):
            _copy_input_files(s3, ["s3://upload-bucket/not-a-uuid/file.pdf"], "exec-1")


def test_copy_input_files_copy_failure_raises() -> None:
    s3 = MagicMock()
    s3.copy_object.side_effect = Exception("S3 copy error")

    with (
        patch("config.S3_UPLOAD_BUCKET", "upload-bucket"),
        patch("config.S3_LOGS_BUCKET", "logs-bucket"),
    ):
        with pytest.raises(RuntimeError, match="Failed to copy"):
            _copy_input_files(
                s3,
                [f"s3://upload-bucket/{_VALID_UUID}/report.pdf"],
                "exec-1",
            )


def test_copy_input_files_presign_failure_raises() -> None:
    s3 = MagicMock()
    s3.generate_presigned_url.side_effect = Exception("presign error")

    with (
        patch("config.S3_UPLOAD_BUCKET", "upload-bucket"),
        patch("config.S3_LOGS_BUCKET", "logs-bucket"),
    ):
        with pytest.raises(RuntimeError, match="presigned GET URL"):
            _copy_input_files(
                s3,
                [f"s3://upload-bucket/{_VALID_UUID}/data.csv"],
                "exec-1",
            )


def test_copy_input_files_copy_dest_key_uses_execution_id() -> None:
    s3 = MagicMock()
    s3.generate_presigned_url.return_value = "https://url"

    with (
        patch("config.S3_UPLOAD_BUCKET", "upload-bucket"),
        patch("config.S3_LOGS_BUCKET", "logs-bucket"),
    ):
        _copy_input_files(
            s3,
            [f"s3://upload-bucket/{_VALID_UUID}/report.pdf"],
            "my-exec-id",
        )

    call_kwargs = s3.copy_object.call_args.kwargs
    assert call_kwargs["Key"] == "executions/my-exec-id/input/report.pdf"
    assert call_kwargs["Bucket"] == "logs-bucket"


# ---------------------------------------------------------------------------
# _generate_output_presigned_url
# ---------------------------------------------------------------------------


def test_generate_output_presigned_url_returns_url() -> None:
    s3 = MagicMock()
    s3.generate_presigned_url.return_value = "https://s3.example.com/output.zip"

    with patch("config.S3_LOGS_BUCKET", "logs-bucket"):
        url = _generate_output_presigned_url(s3, "exec-1", 3600)

    assert url == "https://s3.example.com/output.zip"
    s3.generate_presigned_url.assert_called_once_with(
        "put_object",
        Params={"Bucket": "logs-bucket", "Key": "executions/exec-1/output/output.zip"},
        ExpiresIn=3600,
    )


def test_generate_output_presigned_url_caps_expiry() -> None:
    s3 = MagicMock()
    s3.generate_presigned_url.return_value = "https://url"

    with patch("config.S3_LOGS_BUCKET", "logs-bucket"):
        _generate_output_presigned_url(s3, "exec-1", 999999)

    call_kwargs = s3.generate_presigned_url.call_args.kwargs
    assert call_kwargs["ExpiresIn"] == 43200  # _OUTPUT_URL_MAX_EXPIRY_SECONDS


def test_generate_output_presigned_url_raises_on_s3_error() -> None:
    s3 = MagicMock()
    s3.generate_presigned_url.side_effect = Exception("S3 error")

    with patch("config.S3_LOGS_BUCKET", "logs-bucket"):
        with pytest.raises(RuntimeError, match="presigned PUT URL"):
            _generate_output_presigned_url(s3, "exec-1", 3600)


def test_generate_output_presigned_url_small_timeout_not_capped() -> None:
    s3 = MagicMock()
    s3.generate_presigned_url.return_value = "https://url"

    with patch("config.S3_LOGS_BUCKET", "logs-bucket"):
        _generate_output_presigned_url(s3, "exec-1", 60)

    call_kwargs = s3.generate_presigned_url.call_args.kwargs
    assert call_kwargs["ExpiresIn"] == 60


# ---------------------------------------------------------------------------
# _upload_execution_manifest
# ---------------------------------------------------------------------------


def test_upload_execution_manifest_returns_presigned_url() -> None:
    s3 = MagicMock()
    s3.generate_presigned_url.return_value = "https://manifest.presigned.url"

    with patch("config.S3_LOGS_BUCKET", "logs-bucket"):
        url = _upload_execution_manifest(
            s3, "exec-1", "yaml: content", [], "https://output.url", "hello", 3600
        )

    assert url == "https://manifest.presigned.url"
    s3.put_object.assert_called_once()

    put_call = s3.put_object.call_args
    body = json.loads(put_call.kwargs["Body"].decode("utf-8"))
    assert body["prompt"] == "hello"
    assert body["agentlet_yaml"] == "yaml: content"
    assert "timeout" in body


def test_upload_execution_manifest_manifest_structure() -> None:
    s3 = MagicMock()
    s3.generate_presigned_url.return_value = "https://url"

    input_files = [{"name": "file.pdf", "type": "document", "url": "https://file.url"}]

    with patch("config.S3_LOGS_BUCKET", "logs-bucket"):
        _upload_execution_manifest(
            s3, "exec-42", "key: val", input_files, "https://out.url", "my prompt", 120
        )

    body = json.loads(s3.put_object.call_args.kwargs["Body"].decode("utf-8"))
    assert body["output_url"] == "https://out.url"
    assert body["input_files"] == input_files
    # timeout is reduced by 60 to leave headroom for the container to stop
    assert body["timeout"] == 60


def test_upload_execution_manifest_timeout_min_one() -> None:
    """timeout - 60 is clamped to at least 1."""
    s3 = MagicMock()
    s3.generate_presigned_url.return_value = "https://url"

    with patch("config.S3_LOGS_BUCKET", "logs-bucket"):
        _upload_execution_manifest(s3, "exec-1", "", [], "https://out", "", 1)

    body = json.loads(s3.put_object.call_args.kwargs["Body"].decode("utf-8"))
    assert body["timeout"] == 1  # max(1, 1 - 60) == 1


def test_upload_execution_manifest_key_uses_execution_id() -> None:
    s3 = MagicMock()
    s3.generate_presigned_url.return_value = "https://url"

    with patch("config.S3_LOGS_BUCKET", "logs-bucket"):
        _upload_execution_manifest(s3, "my-exec", "", [], "https://out", "", 3600)

    put_kwargs = s3.put_object.call_args.kwargs
    assert put_kwargs["Key"] == "executions/my-exec/manifest.json"
    assert put_kwargs["Bucket"] == "logs-bucket"


def test_upload_execution_manifest_put_failure_raises() -> None:
    s3 = MagicMock()
    s3.put_object.side_effect = Exception("put failed")

    with patch("config.S3_LOGS_BUCKET", "logs-bucket"):
        with pytest.raises(RuntimeError, match="Failed to upload execution manifest"):
            _upload_execution_manifest(s3, "exec-1", "", [], "https://out", "", 3600)


def test_upload_execution_manifest_presign_failure_raises() -> None:
    s3 = MagicMock()
    s3.generate_presigned_url.side_effect = Exception("presign error")

    with patch("config.S3_LOGS_BUCKET", "logs-bucket"):
        with pytest.raises(RuntimeError, match="presigned GET URL for execution manifest"):
            _upload_execution_manifest(s3, "exec-1", "", [], "https://out", "", 3600)


# ---------------------------------------------------------------------------
# _fetch_user_secrets
# ---------------------------------------------------------------------------


async def test_fetch_user_secrets_empty_names_returns_empty() -> None:
    db = AsyncMock()
    result = await _fetch_user_secrets("org-1", "user-1", [], db)
    assert result == {}


async def test_fetch_user_secrets_returns_decrypted_env_vars() -> None:
    db = AsyncMock()
    mock_secret = MagicMock()
    mock_secret.name = "MY_SECRET"
    mock_secret.nonce = b"nonce"
    mock_secret.encrypted_value = b"encrypted"

    mock_repo = MagicMock()
    mock_repo.list_by_user_names = AsyncMock(return_value=[mock_secret])

    decrypted = {"API_KEY": "secret-value"}

    with (
        patch("routers.execute.SecretRepo", return_value=mock_repo),
        patch("routers.execute.decrypt", return_value=decrypted),
    ):
        result = await _fetch_user_secrets(
            "00000000-0000-0000-0000-000000000001",
            "00000000-0000-0000-0000-000000000002",
            ["MY_SECRET"],
            db,
        )

    assert result == {"API_KEY": "secret-value"}


async def test_fetch_user_secrets_non_string_values_filtered() -> None:
    """decrypt() returning non-string values must be filtered out."""
    db = AsyncMock()
    mock_secret = MagicMock()
    mock_secret.name = "MY_SECRET"
    mock_secret.nonce = b"nonce"
    mock_secret.encrypted_value = b"encrypted"

    mock_repo = MagicMock()
    mock_repo.list_by_user_names = AsyncMock(return_value=[mock_secret])

    # decrypted dict has a mix of valid and invalid value types
    decrypted = {"GOOD_KEY": "value", "BAD_KEY": 42}

    with (
        patch("routers.execute.SecretRepo", return_value=mock_repo),
        patch("routers.execute.decrypt", return_value=decrypted),
    ):
        result = await _fetch_user_secrets(
            "00000000-0000-0000-0000-000000000001",
            "00000000-0000-0000-0000-000000000002",
            ["MY_SECRET"],
            db,
        )

    assert result == {"GOOD_KEY": "value"}
    assert "BAD_KEY" not in result


async def test_fetch_user_secrets_decrypt_failure_returns_empty() -> None:
    """If decrypt() raises, the secret is skipped and we return an empty dict."""
    db = AsyncMock()
    mock_secret = MagicMock()
    mock_secret.name = "BAD_SECRET"
    mock_secret.nonce = b"nonce"
    mock_secret.encrypted_value = b"bad"

    mock_repo = MagicMock()
    mock_repo.list_by_user_names = AsyncMock(return_value=[mock_secret])

    with (
        patch("routers.execute.SecretRepo", return_value=mock_repo),
        patch("routers.execute.decrypt", side_effect=Exception("decrypt error")),
    ):
        result = await _fetch_user_secrets(
            "00000000-0000-0000-0000-000000000001",
            "00000000-0000-0000-0000-000000000002",
            ["BAD_SECRET"],
            db,
        )

    assert result == {}


async def test_fetch_user_secrets_repo_failure_returns_empty() -> None:
    """If the repo call raises, we swallow and return empty."""
    db = AsyncMock()
    mock_repo = MagicMock()
    mock_repo.list_by_user_names = AsyncMock(side_effect=Exception("DB error"))

    with patch("routers.execute.SecretRepo", return_value=mock_repo):
        result = await _fetch_user_secrets(
            "00000000-0000-0000-0000-000000000001",
            "00000000-0000-0000-0000-000000000002",
            ["SECRET"],
            db,
        )

    assert result == {}


# ---------------------------------------------------------------------------
# _run_execution — early validation guards (no DB interaction needed)
# ---------------------------------------------------------------------------


async def test_run_execution_too_many_input_files_raises_400() -> None:
    db = AsyncMock()
    with pytest.raises(HTTPException) as exc_info:
        await _run_execution(
            agentlet_name="a",
            org_id="00000000-0000-0000-0000-000000000001",
            user_id="00000000-0000-0000-0000-000000000002",
            prompt="",
            timeout_seconds=60,
            input_objects=[f"s3://bucket/{i}/file.pdf" for i in range(21)],
            db=db,
        )
    assert exc_info.value.status_code == 400


async def test_run_execution_invalid_timeout_zero_raises_400() -> None:
    db = AsyncMock()
    with pytest.raises(HTTPException) as exc_info:
        await _run_execution(
            agentlet_name="a",
            org_id="00000000-0000-0000-0000-000000000001",
            user_id="00000000-0000-0000-0000-000000000002",
            prompt="",
            timeout_seconds=0,
            input_objects=[],
            db=db,
        )
    assert exc_info.value.status_code == 400


async def test_run_execution_timeout_too_large_raises_400() -> None:
    db = AsyncMock()
    with pytest.raises(HTTPException) as exc_info:
        await _run_execution(
            agentlet_name="a",
            org_id="00000000-0000-0000-0000-000000000001",
            user_id="00000000-0000-0000-0000-000000000002",
            prompt="",
            timeout_seconds=86401,
            input_objects=[],
            db=db,
        )
    assert exc_info.value.status_code == 400


async def test_run_execution_non_list_input_objects_raises_400() -> None:
    db = AsyncMock()
    with pytest.raises(HTTPException) as exc_info:
        await _run_execution(
            agentlet_name="a",
            org_id="00000000-0000-0000-0000-000000000001",
            user_id="00000000-0000-0000-0000-000000000002",
            prompt="",
            timeout_seconds=60,
            input_objects="not-a-list",  # type: ignore[arg-type]
            db=db,
        )
    assert exc_info.value.status_code == 400


async def test_run_execution_input_objects_checked_before_timeout() -> None:
    """The file-count guard fires before the timeout guard (order matters)."""
    db = AsyncMock()
    # 21 files + invalid timeout: file count guard must fire first
    with pytest.raises(HTTPException) as exc_info:
        await _run_execution(
            agentlet_name="a",
            org_id="00000000-0000-0000-0000-000000000001",
            user_id="00000000-0000-0000-0000-000000000002",
            prompt="",
            timeout_seconds=0,  # also invalid
            input_objects=[f"s3://bucket/{i}/file.pdf" for i in range(21)],
            db=db,
        )
    # The detail message should match the "too many input files" guard, not timeout
    assert exc_info.value.status_code == 400
    assert "Too many input files" in exc_info.value.detail
