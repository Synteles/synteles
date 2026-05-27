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

"""Unit tests for conversations router helpers."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock

import pytest
from botocore.exceptions import ClientError

from routers.conversations import (
    _CONVERSATION_TTL_DAYS,
    _PRESIGNED_URL_EXPIRY_SECONDS,
    _delete_s3_object,
    _expires_at,
    _presigned_url,
    _put_s3_json,
    _s3_display_key,
    _s3_state_key,
)

# ─── S3 key helpers ────────────────────────────────────────────────────────


def test_s3_display_key_format() -> None:
    key = _s3_display_key("user-123", "conv-456")
    assert key == "conversations/user-123/conv-456/display.json"


def test_s3_state_key_format() -> None:
    key = _s3_state_key("user-123", "conv-456")
    assert key == "conversations/user-123/conv-456/agent_state.json"


def test_s3_keys_embed_user_and_conv_ids() -> None:
    uid, cid = "abc", "xyz"
    assert uid in _s3_display_key(uid, cid)
    assert cid in _s3_display_key(uid, cid)


# ─── _expires_at ───────────────────────────────────────────────────────────


def test_expires_at_is_90_days_from_now() -> None:
    before = datetime.now(UTC)
    result = _expires_at()
    after = datetime.now(UTC)

    assert before + timedelta(days=_CONVERSATION_TTL_DAYS - 1) < result
    assert result < after + timedelta(days=_CONVERSATION_TTL_DAYS + 1)


# ─── _put_s3_json ──────────────────────────────────────────────────────────


def test_put_s3_json_calls_put_object_with_correct_args() -> None:
    s3 = MagicMock()
    _put_s3_json(s3, "my-bucket", "some/key.json", {"foo": "bar"})

    s3.put_object.assert_called_once_with(
        Bucket="my-bucket",
        Key="some/key.json",
        Body='{"foo": "bar"}',
        ContentType="application/json",
    )


# ─── _delete_s3_object ─────────────────────────────────────────────────────


def test_delete_s3_object_calls_delete_object() -> None:
    s3 = MagicMock()
    _delete_s3_object(s3, "bucket", "key")
    s3.delete_object.assert_called_once_with(Bucket="bucket", Key="key")


def test_delete_s3_object_ignores_no_such_key() -> None:
    s3 = MagicMock()
    error = ClientError({"Error": {"Code": "NoSuchKey", "Message": ""}}, "DeleteObject")
    s3.delete_object.side_effect = error
    _delete_s3_object(s3, "bucket", "key")  # must not raise


def test_delete_s3_object_ignores_404() -> None:
    s3 = MagicMock()
    error = ClientError({"Error": {"Code": "404", "Message": ""}}, "DeleteObject")
    s3.delete_object.side_effect = error
    _delete_s3_object(s3, "bucket", "key")  # must not raise


def test_delete_s3_object_reraises_other_errors() -> None:
    s3 = MagicMock()
    error = ClientError({"Error": {"Code": "AccessDenied", "Message": ""}}, "DeleteObject")
    s3.delete_object.side_effect = error
    with pytest.raises(ClientError):
        _delete_s3_object(s3, "bucket", "key")


# ─── _presigned_url ────────────────────────────────────────────────────────


def test_presigned_url_returns_string() -> None:
    s3 = MagicMock()
    s3.generate_presigned_url.return_value = "https://s3.example.com/key?sig=abc"
    result = _presigned_url(s3, "bucket", "some/key")
    assert isinstance(result, str)
    assert result == "https://s3.example.com/key?sig=abc"


def test_presigned_url_passes_correct_params() -> None:
    s3 = MagicMock()
    s3.generate_presigned_url.return_value = "https://url"
    _presigned_url(s3, "my-bucket", "my/key")

    s3.generate_presigned_url.assert_called_once_with(
        "get_object",
        Params={"Bucket": "my-bucket", "Key": "my/key"},
        ExpiresIn=_PRESIGNED_URL_EXPIRY_SECONDS,
    )
