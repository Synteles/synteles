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

"""Initial synteles schema.

Revision ID: 0001
Revises:
Create Date: 2026-05-24
"""

from __future__ import annotations

from pathlib import Path

from alembic import op

revision: str = "0001"
down_revision = None
branch_labels = None
depends_on = None

_UPGRADE_SQL = (Path(__file__).parent / "synteles.sql").read_text()
_DOWNGRADE_SQL = "DROP SCHEMA IF EXISTS synteles CASCADE;"


def upgrade() -> None:
    op.execute(_UPGRADE_SQL)


def downgrade() -> None:
    op.execute(_DOWNGRADE_SQL)
