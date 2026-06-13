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

"""Drop unused signal_name column from executions.

The signal name is always 'provide_user_input' for durable executions and is
hardcoded in the signal delivery path. The column was never written or read.

Revision ID: 0005
Revises: 0004
Create Date: 2026-06-06
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None
__all__ = ["branch_labels", "depends_on", "down_revision", "revision"]

_SCHEMA = "synteles"


def upgrade() -> None:
    op.drop_column("executions", "signal_name", schema=_SCHEMA)


def downgrade() -> None:
    op.add_column(
        "executions",
        sa.Column("signal_name", sa.Text, nullable=True),
        schema=_SCHEMA,
    )
