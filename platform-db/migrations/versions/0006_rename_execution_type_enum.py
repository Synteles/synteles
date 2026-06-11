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

"""Rename PostgreSQL enum type execution_type to execution_backend.

Revision ID: 0006
Revises: 0005
Create Date: 2026-06-11
"""

from __future__ import annotations

from alembic import op

revision: str = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None

_SCHEMA = "synteles"


def upgrade() -> None:
    op.execute(f"ALTER TYPE {_SCHEMA}.execution_type RENAME TO execution_backend")


def downgrade() -> None:
    op.execute(f"ALTER TYPE {_SCHEMA}.execution_backend RENAME TO execution_type")
