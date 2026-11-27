"""Shipment Tracking and Milestone Management

Revision ID: 6e9b2a1c4f5d
Revises: 5d8a1c3f9e2b
Create Date: 2026-11-24 20:20:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '6e9b2a1c4f5d'
down_revision = '5d8a1c3f9e2b'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. Add columns to shipments table
    op.add_column('shipments', sa.Column('current_milestone', sa.String(length=50), nullable=True))
    op.add_column('shipments', sa.Column('last_tracking_event_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('shipments', sa.Column('last_known_location', sa.String(length=255), nullable=True))
    op.add_column('shipments', sa.Column('last_known_latitude', sa.Float(), nullable=True))
    op.add_column('shipments', sa.Column('last_known_longitude', sa.Float(), nullable=True))
    op.add_column('shipments', sa.Column('is_tracking_stale', sa.Boolean(), server_default='false', nullable=False))
    op.add_column('shipments', sa.Column('eta_updated_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('shipments', sa.Column('eta_delay_minutes', sa.Integer(), server_default='0', nullable=False))

    op.create_index(op.f('ix_shipments_current_milestone'), 'shipments', ['current_milestone'], unique=False)
    op.create_index(op.f('ix_shipments_last_tracking_event_at'), 'shipments', ['last_tracking_event_at'], unique=False)
    op.create_index(op.f('ix_shipments_is_tracking_stale'), 'shipments', ['is_tracking_stale'], unique=False)

    # 2. Add columns to shipment_events table
    op.add_column('shipment_events', sa.Column('milestone', sa.String(length=50), nullable=True))
    op.add_column('shipment_events', sa.Column('idempotency_key', sa.String(length=100), nullable=True))
    op.add_column('shipment_events', sa.Column('estimated_delivery_at', sa.DateTime(timezone=True), nullable=True))

    op.create_index(op.f('ix_shipment_events_milestone'), 'shipment_events', ['milestone'], unique=False)
    op.create_index(op.f('ix_shipment_events_idempotency_key'), 'shipment_events', ['idempotency_key'], unique=False)
    op.create_index('ix_shipment_events_idempotency', 'shipment_events', ['shipment_id', 'idempotency_key'], unique=False)


def downgrade() -> None:
    op.drop_index('ix_shipment_events_idempotency', table_name='shipment_events')
    op.drop_index(op.f('ix_shipment_events_idempotency_key'), table_name='shipment_events')
    op.drop_index(op.f('ix_shipment_events_milestone'), table_name='shipment_events')
    op.drop_column('shipment_events', 'estimated_delivery_at')
    op.drop_column('shipment_events', 'idempotency_key')
    op.drop_column('shipment_events', 'milestone')

    op.drop_index(op.f('ix_shipments_is_tracking_stale'), table_name='shipments')
    op.drop_index(op.f('ix_shipments_last_tracking_event_at'), table_name='shipments')
    op.drop_index(op.f('ix_shipments_current_milestone'), table_name='shipments')
    op.drop_column('shipments', 'eta_delay_minutes')
    op.drop_column('shipments', 'eta_updated_at')
    op.drop_column('shipments', 'is_tracking_stale')
    op.drop_column('shipments', 'last_known_longitude')
    op.drop_column('shipments', 'last_known_latitude')
    op.drop_column('shipments', 'last_known_location')
    op.drop_column('shipments', 'last_tracking_event_at')
    op.drop_column('shipments', 'current_milestone')
