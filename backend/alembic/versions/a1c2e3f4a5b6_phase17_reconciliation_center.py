"""phase17_reconciliation_center

Revision ID: a1c2e3f4a5b6
Revises: 9b3d5f7a2c4e
Create Date: 2026-11-25 20:10:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'a1c2e3f4a5b6'
down_revision: Union[str, None] = '9b3d5f7a2c4e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Add CLOSED to reconciliation_status_enum if not present
    op.execute(sa.text("""
        DO $$
        BEGIN
            ALTER TYPE reconciliation_status_enum ADD VALUE IF NOT EXISTS 'CLOSED';
        EXCEPTION
            WHEN duplicate_object THEN null;
        END $$;
    """))

    # 2. Create logistics_reconciliation_items table for granular discrepancy tracking across the 6 categories
    op.execute(sa.text("""
        CREATE TABLE IF NOT EXISTS logistics_reconciliation_items (
            id UUID PRIMARY KEY,
            organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
            shipment_id UUID NOT NULL REFERENCES shipments(id) ON DELETE CASCADE,
            reconciliation_id UUID REFERENCES reconciliation_records(id) ON DELETE CASCADE,
            category VARCHAR(50) NOT NULL,
            status VARCHAR(50) NOT NULL DEFAULT 'OPEN',
            expected_value TEXT,
            actual_value TEXT,
            discrepancy_delta VARCHAR(255),
            severity VARCHAR(50) NOT NULL DEFAULT 'MEDIUM',
            is_matched BOOLEAN NOT NULL DEFAULT false,
            is_missing_data BOOLEAN NOT NULL DEFAULT false,
            assigned_user_id UUID REFERENCES users(id) ON DELETE SET NULL,
            investigation_notes TEXT,
            resolution_notes TEXT,
            resolved_by_user_id UUID REFERENCES users(id) ON DELETE SET NULL,
            resolved_at TIMESTAMP WITH TIME ZONE,
            closed_at TIMESTAMP WITH TIME ZONE,
            item_metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
            created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),
            updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),
            is_deleted BOOLEAN NOT NULL DEFAULT false,
            deleted_at TIMESTAMP WITH TIME ZONE
        );
    """))
    op.execute(sa.text("CREATE INDEX IF NOT EXISTS ix_reconcil_items_shipment ON logistics_reconciliation_items(shipment_id)"))
    op.execute(sa.text("CREATE INDEX IF NOT EXISTS ix_reconcil_items_org_status ON logistics_reconciliation_items(organization_id, status)"))
    op.execute(sa.text("CREATE INDEX IF NOT EXISTS ix_reconcil_items_category ON logistics_reconciliation_items(category)"))
    op.execute(sa.text("CREATE INDEX IF NOT EXISTS ix_reconcil_items_assigned ON logistics_reconciliation_items(assigned_user_id)"))

    # 3. Enhance reconciliation_records table
    op.execute(sa.text("ALTER TABLE reconciliation_records ADD COLUMN IF NOT EXISTS total_discrepancies INTEGER NOT NULL DEFAULT 0"))
    op.execute(sa.text("ALTER TABLE reconciliation_records ADD COLUMN IF NOT EXISTS resolved_discrepancies INTEGER NOT NULL DEFAULT 0"))
    op.execute(sa.text("ALTER TABLE reconciliation_records ADD COLUMN IF NOT EXISTS has_mismatches BOOLEAN NOT NULL DEFAULT false"))
    op.execute(sa.text("ALTER TABLE reconciliation_records ADD COLUMN IF NOT EXISTS has_missing_data BOOLEAN NOT NULL DEFAULT false"))
    op.execute(sa.text("ALTER TABLE reconciliation_records ADD COLUMN IF NOT EXISTS investigation_notes TEXT"))
    op.execute(sa.text("ALTER TABLE reconciliation_records ADD COLUMN IF NOT EXISTS resolution_notes TEXT"))
    op.execute(sa.text("ALTER TABLE reconciliation_records ADD COLUMN IF NOT EXISTS closed_by_user_id UUID REFERENCES users(id) ON DELETE SET NULL"))
    op.execute(sa.text("ALTER TABLE reconciliation_records ADD COLUMN IF NOT EXISTS closed_at TIMESTAMP WITH TIME ZONE"))
    op.execute(sa.text("ALTER TABLE reconciliation_records ADD COLUMN IF NOT EXISTS summary_data JSONB NOT NULL DEFAULT '{}'::jsonb"))


def downgrade() -> None:
    pass
