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

"""Add execution_type, workflow_id, signal_name; migrate status to TEXT.

Revision ID: 0003
Revises: 0002
Create Date: 2026-06-04
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None

_SCHEMA = "synteles"

_STANDARD_STATUSES = "('deploying','running','completed','failed','stopped')"
_DURABLE_STATUSES = "('deploying','running','waiting_for_signal','completed','failed','stopped')"


def upgrade() -> None:
    # 1. Drop the partial index on updated_at FIRST — it references the exec_status
    #    enum in its WHERE clause, which prevents the column type change in step 2.
    op.execute(f"""
        DO $$
        DECLARE idx TEXT;
        BEGIN
            SELECT indexname INTO idx
            FROM pg_indexes
            WHERE schemaname = '{_SCHEMA}'
              AND tablename  = 'executions'
              AND indexdef LIKE '%updated_at%'
              AND indexdef LIKE '%WHERE%';
            IF idx IS NOT NULL THEN
                EXECUTE 'DROP INDEX {_SCHEMA}.' || idx;
            END IF;
        END $$;
    """)

    # 2. Convert status column from exec_status enum to TEXT.
    #    All existing rows have standard-compatible values — no data loss.
    op.execute(f"ALTER TABLE {_SCHEMA}.executions ALTER COLUMN status TYPE TEXT USING status::text")

    # 3. Drop the old exec_status PostgreSQL enum type.
    op.execute(f"DROP TYPE {_SCHEMA}.exec_status")

    # 4. Create the execution_type PostgreSQL enum.
    op.execute(f"CREATE TYPE {_SCHEMA}.execution_type AS ENUM ('standard', 'durable')")

    # 5. Add new columns.
    op.add_column(
        "executions",
        sa.Column(
            "execution_type",
            sa.Enum(name="execution_type", schema=_SCHEMA, create_type=False),
            nullable=False,
            server_default="standard",
        ),
        schema=_SCHEMA,
    )
    op.add_column("executions", sa.Column("workflow_id", sa.Text, nullable=True), schema=_SCHEMA)
    op.add_column("executions", sa.Column("signal_name", sa.Text, nullable=True), schema=_SCHEMA)

    # 6. Add check constraint enforcing valid status values per execution type.
    op.execute(f"""
        ALTER TABLE {_SCHEMA}.executions
        ADD CONSTRAINT ck_execution_status CHECK (
            (execution_type = 'standard' AND status IN {_STANDARD_STATUSES})
            OR
            (execution_type = 'durable'  AND status IN {_DURABLE_STATUSES})
        )
    """)

    # 7. Recreate partial index including waiting_for_signal (active durable executions).
    op.execute(f"""
        CREATE INDEX ON {_SCHEMA}.executions (updated_at)
        WHERE status IN ('deploying', 'running', 'waiting_for_signal')
    """)


def downgrade() -> None:
    # Reverse order of upgrade.

    # 1. Drop partial index and check constraint added in upgrade.
    op.execute(f"""
        DO $$
        DECLARE idx TEXT;
        BEGIN
            SELECT indexname INTO idx
            FROM pg_indexes
            WHERE schemaname = '{_SCHEMA}'
              AND tablename  = 'executions'
              AND indexdef LIKE '%updated_at%'
              AND indexdef LIKE '%WHERE%';
            IF idx IS NOT NULL THEN
                EXECUTE 'DROP INDEX {_SCHEMA}.' || idx;
            END IF;
        END $$;
    """)
    op.execute(f"ALTER TABLE {_SCHEMA}.executions DROP CONSTRAINT IF EXISTS ck_execution_status")

    # 2. Drop new columns and the execution_type enum.
    op.drop_column("executions", "signal_name", schema=_SCHEMA)
    op.drop_column("executions", "workflow_id", schema=_SCHEMA)
    op.drop_column("executions", "execution_type", schema=_SCHEMA)
    op.execute(f"DROP TYPE IF EXISTS {_SCHEMA}.execution_type")

    # 3. Recreate exec_status enum and restore the status column.
    op.execute(f"""
        CREATE TYPE {_SCHEMA}.exec_status AS ENUM (
            'deploying', 'running', 'completed', 'failed', 'stopped'
        )
    """)
    op.execute(
        f"ALTER TABLE {_SCHEMA}.executions "
        f"ALTER COLUMN status TYPE {_SCHEMA}.exec_status "
        f"USING status::{_SCHEMA}.exec_status"
    )

    # 4. Recreate the original partial index.
    op.execute(f"""
        CREATE INDEX ON {_SCHEMA}.executions (updated_at)
        WHERE status IN ('deploying', 'running')
    """)
