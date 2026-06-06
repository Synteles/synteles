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

"""Add execution_backend column to agentlets table.

Revision ID: 0004
Revises: 0003
Create Date: 2026-06-06
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None

_SCHEMA = "synteles"


def upgrade() -> None:
    # Add execution_backend column reusing the execution_type enum from migration 0003.
    op.add_column(
        "agentlets",
        sa.Column(
            "execution_backend",
            sa.Enum(name="execution_type", schema=_SCHEMA, create_type=False),
            nullable=False,
            server_default="standard",
        ),
        schema=_SCHEMA,
    )

    # Backfill any existing agentlets that had execution_backend: durable in their YAML.
    op.execute(f"""
        UPDATE {_SCHEMA}.agentlets
        SET execution_backend = 'durable'
        WHERE yaml_definition LIKE '%execution_backend: durable%'
    """)


def downgrade() -> None:
    op.drop_column("agentlets", "execution_backend", schema=_SCHEMA)
