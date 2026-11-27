"""phase18_analytics_and_audit

Revision ID: b2d3f4a5b6c7
Revises: a1c2e3f4a5b6
Create Date: 2026-11-25 20:40:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'b2d3f4a5b6c7'
down_revision: Union[str, None] = 'a1c2e3f4a5b6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Add audit columns to audit_logs table individually
    op.execute(sa.text("""
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'audit_logs' AND column_name = 'actor_email'
            ) THEN
                ALTER TABLE audit_logs ADD COLUMN actor_email VARCHAR(255);
            END IF;

            IF NOT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'audit_logs' AND column_name = 'correlation_id'
            ) THEN
                ALTER TABLE audit_logs ADD COLUMN correlation_id VARCHAR(100);
            END IF;

            IF NOT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'audit_logs' AND column_name = 'resource_type'
            ) THEN
                ALTER TABLE audit_logs ADD COLUMN resource_type VARCHAR(100);
            END IF;

            IF NOT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'audit_logs' AND column_name = 'resource_id'
            ) THEN
                ALTER TABLE audit_logs ADD COLUMN resource_id UUID;
            END IF;
        END $$;
    """))

    # 2. Backfill resource_type and resource_id from entity_name and entity_id
    op.execute(sa.text("""
        UPDATE audit_logs
        SET resource_type = entity_name,
            resource_id = entity_id
        WHERE resource_type IS NULL OR resource_id IS NULL
    """))

    # 3. Create indexes individually to comply with asyncpg single-statement execution
    op.execute(sa.text("CREATE INDEX IF NOT EXISTS ix_audit_logs_org_action ON audit_logs (organization_id, action)"))
    op.execute(sa.text("CREATE INDEX IF NOT EXISTS ix_audit_logs_correlation_id ON audit_logs (correlation_id)"))
    op.execute(sa.text("CREATE INDEX IF NOT EXISTS ix_audit_logs_actor_email ON audit_logs (actor_email)"))
    op.execute(sa.text("CREATE INDEX IF NOT EXISTS ix_audit_logs_resource ON audit_logs (resource_type, resource_id)"))


def downgrade() -> None:
    op.execute(sa.text("DROP INDEX IF EXISTS ix_audit_logs_resource"))
    op.execute(sa.text("DROP INDEX IF EXISTS ix_audit_logs_actor_email"))
    op.execute(sa.text("DROP INDEX IF EXISTS ix_audit_logs_correlation_id"))
    op.execute(sa.text("DROP INDEX IF EXISTS ix_audit_logs_org_action"))

    op.execute(sa.text("ALTER TABLE audit_logs DROP COLUMN IF EXISTS resource_id"))
    op.execute(sa.text("ALTER TABLE audit_logs DROP COLUMN IF EXISTS resource_type"))
    op.execute(sa.text("ALTER TABLE audit_logs DROP COLUMN IF EXISTS correlation_id"))
    op.execute(sa.text("ALTER TABLE audit_logs DROP COLUMN IF EXISTS actor_email"))
