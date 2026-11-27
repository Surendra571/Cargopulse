"""transporter_booking_and_dispatch

Revision ID: 3b8f1a2c9d4e
Revises: 1ee6cea47415
Create Date: 2026-11-24 11:35:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = '3b8f1a2c9d4e'
down_revision: Union[str, None] = '1ee6cea47415'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Add new enum values to booking_status_enum in autocommit block
    with op.get_context().autocommit_block():
        for val in ['DRAFT', 'PENDING_ACCEPTANCE', 'CONFIRMED']:
            op.execute(f"ALTER TYPE booking_status_enum ADD VALUE IF NOT EXISTS '{val}'")

    # 2. Add columns to transporter_bookings
    op.add_column('transporter_bookings', sa.Column('booking_reference', sa.String(length=50), nullable=True))
    op.create_index('ix_bookings_reference', 'transporter_bookings', ['booking_reference'], unique=False)

    op.add_column('transporter_bookings', sa.Column('vehicle_id', sa.UUID(), nullable=True))
    op.create_foreign_key('fk_transporter_bookings_vehicle_id', 'transporter_bookings', 'vehicles', ['vehicle_id'], ['id'], ondelete='SET NULL')
    op.create_index('ix_transporter_bookings_vehicle_id', 'transporter_bookings', ['vehicle_id'], unique=False)

    op.add_column('transporter_bookings', sa.Column('driver_id', sa.UUID(), nullable=True))
    op.create_foreign_key('fk_transporter_bookings_driver_id', 'transporter_bookings', 'drivers', ['driver_id'], ['id'], ondelete='SET NULL')
    op.create_index('ix_transporter_bookings_driver_id', 'transporter_bookings', ['driver_id'], unique=False)

    op.add_column('transporter_bookings', sa.Column('rejection_reason', sa.Text(), nullable=True))
    op.add_column('transporter_bookings', sa.Column('responded_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('transporter_bookings', sa.Column('confirmed_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('transporter_bookings', sa.Column('cancelled_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('transporter_bookings', sa.Column('booking_metadata', postgresql.JSONB(astext_type=sa.Text()), server_default='{}', nullable=False))


def downgrade() -> None:
    op.drop_column('transporter_bookings', 'booking_metadata')
    op.drop_column('transporter_bookings', 'cancelled_at')
    op.drop_column('transporter_bookings', 'confirmed_at')
    op.drop_column('transporter_bookings', 'responded_at')
    op.drop_column('transporter_bookings', 'rejection_reason')
    op.drop_index('ix_transporter_bookings_driver_id', table_name='transporter_bookings')
    op.drop_constraint('fk_transporter_bookings_driver_id', 'transporter_bookings', type_='foreignkey')
    op.drop_column('transporter_bookings', 'driver_id')
    op.drop_index('ix_transporter_bookings_vehicle_id', table_name='transporter_bookings')
    op.drop_constraint('fk_transporter_bookings_vehicle_id', 'transporter_bookings', type_='foreignkey')
    op.drop_column('transporter_bookings', 'vehicle_id')
    op.drop_index('ix_bookings_reference', table_name='transporter_bookings')
    op.drop_column('transporter_bookings', 'booking_reference')
