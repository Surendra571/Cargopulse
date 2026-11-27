"""phase16_ai_logistics_coordinator

Revision ID: 9b3d5f7a2c4e
Revises: 8a2c4e6b1d3f
Create Date: 2026-11-25 19:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '9b3d5f7a2c4e'
down_revision: Union[str, None] = '8a2c4e6b1d3f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Create ai_conversations table
    op.execute(sa.text("""
        CREATE TABLE IF NOT EXISTS ai_conversations (
            id UUID PRIMARY KEY,
            organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
            user_id UUID REFERENCES users(id) ON DELETE SET NULL,
            title VARCHAR(255) NOT NULL,
            shipment_id UUID REFERENCES shipments(id) ON DELETE SET NULL,
            created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),
            updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),
            is_deleted BOOLEAN NOT NULL DEFAULT false,
            deleted_at TIMESTAMP WITH TIME ZONE
        )
    """))
    op.execute(sa.text("CREATE INDEX IF NOT EXISTS ix_ai_conversations_org ON ai_conversations(organization_id)"))
    op.execute(sa.text("CREATE INDEX IF NOT EXISTS ix_ai_conversations_user ON ai_conversations(user_id)"))
    op.execute(sa.text("CREATE INDEX IF NOT EXISTS ix_ai_conversations_shipment ON ai_conversations(shipment_id)"))

    # 2. Create ai_messages table
    op.execute(sa.text("""
        CREATE TABLE IF NOT EXISTS ai_messages (
            id UUID PRIMARY KEY,
            conversation_id UUID NOT NULL REFERENCES ai_conversations(id) ON DELETE CASCADE,
            sender_type VARCHAR(50) NOT NULL,
            content TEXT NOT NULL,
            tool_calls JSONB NOT NULL DEFAULT '[]'::jsonb,
            tool_results JSONB NOT NULL DEFAULT '[]'::jsonb,
            action_proposal JSONB,
            created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now()
        )
    """))
    op.execute(sa.text("CREATE INDEX IF NOT EXISTS ix_ai_messages_conversation ON ai_messages(conversation_id)"))
    op.execute(sa.text("CREATE INDEX IF NOT EXISTS ix_ai_messages_created_at ON ai_messages(created_at)"))

    # 3. Enhance ai_action_records table
    op.execute(sa.text("ALTER TABLE ai_action_records ADD COLUMN IF NOT EXISTS conversation_id UUID REFERENCES ai_conversations(id) ON DELETE SET NULL"))
    op.execute(sa.text("ALTER TABLE ai_action_records ADD COLUMN IF NOT EXISTS status VARCHAR(50) NOT NULL DEFAULT 'PENDING'"))
    op.execute(sa.text("ALTER TABLE ai_action_records ADD COLUMN IF NOT EXISTS action_payload JSONB NOT NULL DEFAULT '{}'::jsonb"))
    op.execute(sa.text("ALTER TABLE ai_action_records ADD COLUMN IF NOT EXISTS execution_result JSONB NOT NULL DEFAULT '{}'::jsonb"))
    op.execute(sa.text("ALTER TABLE ai_action_records ADD COLUMN IF NOT EXISTS rejection_reason TEXT"))
    op.execute(sa.text("ALTER TABLE ai_action_records ADD COLUMN IF NOT EXISTS rejected_by_user_id UUID REFERENCES users(id) ON DELETE SET NULL"))
    op.execute(sa.text("ALTER TABLE ai_action_records ADD COLUMN IF NOT EXISTS rejected_at TIMESTAMP WITH TIME ZONE"))
    op.execute(sa.text("ALTER TABLE ai_action_records ADD COLUMN IF NOT EXISTS initiated_by_user_id UUID REFERENCES users(id) ON DELETE SET NULL"))
    op.execute(sa.text("CREATE INDEX IF NOT EXISTS ix_ai_action_records_status ON ai_action_records(status)"))
    op.execute(sa.text("CREATE INDEX IF NOT EXISTS ix_ai_action_records_conversation ON ai_action_records(conversation_id)"))


def downgrade() -> None:
    pass
