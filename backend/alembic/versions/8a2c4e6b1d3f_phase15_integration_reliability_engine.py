"""phase15_integration_reliability_engine

Revision ID: 8a2c4e6b1d3f
Revises: 7f1a3b5c8d2e
Create Date: 2026-11-25 18:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '8a2c4e6b1d3f'
down_revision: Union[str, None] = '7f1a3b5c8d2e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Add DEAD_LETTER to outbox_status_enum
    op.execute(sa.text("ALTER TYPE outbox_status_enum ADD VALUE IF NOT EXISTS 'DEAD_LETTER';"))

    # 2. IntegrationConnection columns
    op.execute(sa.text("ALTER TABLE integration_connections ADD COLUMN IF NOT EXISTS slug VARCHAR(100);"))
    op.execute(sa.text("ALTER TABLE integration_connections ADD COLUMN IF NOT EXISTS adapter_type VARCHAR(100) NOT NULL DEFAULT 'GENERIC';"))
    op.execute(sa.text("ALTER TABLE integration_connections ADD COLUMN IF NOT EXISTS webhook_secret VARCHAR(255);"))
    op.execute(sa.text("ALTER TABLE integration_connections ADD COLUMN IF NOT EXISTS api_key VARCHAR(255);"))
    op.execute(sa.text("ALTER TABLE integration_connections ADD COLUMN IF NOT EXISTS health_status VARCHAR(50) NOT NULL DEFAULT 'HEALTHY';"))
    op.execute(sa.text("ALTER TABLE integration_connections ADD COLUMN IF NOT EXISTS consecutive_failures INTEGER NOT NULL DEFAULT 0;"))
    op.execute(sa.text("ALTER TABLE integration_connections ADD COLUMN IF NOT EXISTS stats JSONB NOT NULL DEFAULT '{}';"))

    # 3. WebhookEvent columns
    op.execute(sa.text("ALTER TABLE webhook_events ADD COLUMN IF NOT EXISTS integration_id UUID REFERENCES integration_connections(id) ON DELETE SET NULL;"))
    op.execute(sa.text("ALTER TABLE webhook_events ADD COLUMN IF NOT EXISTS provider VARCHAR(100) NOT NULL DEFAULT 'generic';"))
    op.execute(sa.text("ALTER TABLE webhook_events ADD COLUMN IF NOT EXISTS external_event_id VARCHAR(255);"))
    op.execute(sa.text("ALTER TABLE webhook_events ADD COLUMN IF NOT EXISTS idempotency_key VARCHAR(255);"))
    op.execute(sa.text("ALTER TABLE webhook_events ADD COLUMN IF NOT EXISTS headers JSONB NOT NULL DEFAULT '{}';"))
    op.execute(sa.text("ALTER TABLE webhook_events ADD COLUMN IF NOT EXISTS normalized_payload JSONB NOT NULL DEFAULT '{}';"))
    op.execute(sa.text("ALTER TABLE webhook_events ADD COLUMN IF NOT EXISTS last_attempt_at TIMESTAMP WITH TIME ZONE;"))
    op.execute(sa.text("ALTER TABLE webhook_events ADD COLUMN IF NOT EXISTS next_retry_at TIMESTAMP WITH TIME ZONE;"))
    op.execute(sa.text("ALTER TABLE webhook_events ADD COLUMN IF NOT EXISTS max_retries INTEGER NOT NULL DEFAULT 5;"))
    op.execute(sa.text("ALTER TABLE webhook_events ADD COLUMN IF NOT EXISTS error_type VARCHAR(50);"))
    op.execute(sa.text("ALTER TABLE webhook_events ADD COLUMN IF NOT EXISTS is_dead_letter BOOLEAN NOT NULL DEFAULT false;"))
    op.execute(sa.text("ALTER TABLE webhook_events ADD COLUMN IF NOT EXISTS replay_count INTEGER NOT NULL DEFAULT 0;"))
    op.execute(sa.text("ALTER TABLE webhook_events ADD COLUMN IF NOT EXISTS last_replayed_at TIMESTAMP WITH TIME ZONE;"))
    op.execute(sa.text("ALTER TABLE webhook_events ADD COLUMN IF NOT EXISTS last_replayed_by_id UUID REFERENCES users(id) ON DELETE SET NULL;"))

    # 4. OutboxEvent columns
    op.execute(sa.text("ALTER TABLE outbox_events ADD COLUMN IF NOT EXISTS destination VARCHAR(500);"))
    op.execute(sa.text("ALTER TABLE outbox_events ADD COLUMN IF NOT EXISTS idempotency_key VARCHAR(255);"))
    op.execute(sa.text("ALTER TABLE outbox_events ADD COLUMN IF NOT EXISTS headers JSONB NOT NULL DEFAULT '{}';"))
    op.execute(sa.text("ALTER TABLE outbox_events ADD COLUMN IF NOT EXISTS max_retries INTEGER NOT NULL DEFAULT 5;"))
    op.execute(sa.text("ALTER TABLE outbox_events ADD COLUMN IF NOT EXISTS next_retry_at TIMESTAMP WITH TIME ZONE;"))
    op.execute(sa.text("ALTER TABLE outbox_events ADD COLUMN IF NOT EXISTS locked_at TIMESTAMP WITH TIME ZONE;"))
    op.execute(sa.text("ALTER TABLE outbox_events ADD COLUMN IF NOT EXISTS locked_by VARCHAR(150);"))
    op.execute(sa.text("ALTER TABLE outbox_events ADD COLUMN IF NOT EXISTS is_dead_letter BOOLEAN NOT NULL DEFAULT false;"))
    op.execute(sa.text("ALTER TABLE outbox_events ADD COLUMN IF NOT EXISTS replay_count INTEGER NOT NULL DEFAULT 0;"))
    op.execute(sa.text("ALTER TABLE outbox_events ADD COLUMN IF NOT EXISTS last_replayed_at TIMESTAMP WITH TIME ZONE;"))
    op.execute(sa.text("ALTER TABLE outbox_events ADD COLUMN IF NOT EXISTS last_replayed_by_id UUID REFERENCES users(id) ON DELETE SET NULL;"))

    # 5. Indexes
    op.execute(sa.text("CREATE INDEX IF NOT EXISTS ix_integrations_org_slug ON integration_connections(organization_id, slug);"))
    op.execute(sa.text("CREATE INDEX IF NOT EXISTS ix_webhooks_provider_external_id ON webhook_events(provider, external_event_id);"))
    op.execute(sa.text("CREATE INDEX IF NOT EXISTS ix_webhooks_idempotency_key ON webhook_events(idempotency_key);"))
    op.execute(sa.text("CREATE INDEX IF NOT EXISTS ix_webhooks_dead_letter ON webhook_events(is_dead_letter);"))
    op.execute(sa.text("CREATE INDEX IF NOT EXISTS ix_outbox_next_retry ON outbox_events(next_retry_at);"))
    op.execute(sa.text("CREATE INDEX IF NOT EXISTS ix_outbox_dead_letter ON outbox_events(is_dead_letter);"))


def downgrade() -> None:
    pass
