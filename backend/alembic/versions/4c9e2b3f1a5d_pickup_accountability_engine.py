"""Pickup Accountability Engine and Recovery Workflow

Revision ID: 4c9e2b3f1a5d
Revises: 3b8f1a2c9d4e
Create Date: 2026-11-24 18:30:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '4c9e2b3f1a5d'
down_revision = '3b8f1a2c9d4e'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. Expand commitment_status_enum
    with op.get_context().autocommit_block():
        for val in ['REMINDER_SENT', 'AT_RISK', 'ARRIVED', 'STARTED', 'COMPLETED', 'MISSED']:
            op.execute(sa.text(f"ALTER TYPE commitment_status_enum ADD VALUE IF NOT EXISTS '{val}'"))

    # 2. Add columns to pickup_commitments
    op.add_column('pickup_commitments', sa.Column('booking_id', sa.UUID(), nullable=True))
    op.add_column('pickup_commitments', sa.Column('pickup_deadline', sa.DateTime(timezone=True), nullable=True))
    op.add_column('pickup_commitments', sa.Column('expected_arrival', sa.DateTime(timezone=True), nullable=True))
    op.add_column('pickup_commitments', sa.Column('assigned_vehicle_id', sa.UUID(), nullable=True))
    op.add_column('pickup_commitments', sa.Column('assigned_driver_id', sa.UUID(), nullable=True))
    op.add_column('pickup_commitments', sa.Column('commitment_metadata', postgresql.JSONB(astext_type=sa.Text()), nullable=True))

    op.create_foreign_key(
        'fk_pickup_commitments_booking_id',
        'pickup_commitments', 'transporter_bookings',
        ['booking_id'], ['id'],
        ondelete='CASCADE'
    )
    op.create_foreign_key(
        'fk_pickup_commitments_vehicle_id',
        'pickup_commitments', 'vehicles',
        ['assigned_vehicle_id'], ['id'],
        ondelete='SET NULL'
    )
    op.create_foreign_key(
        'fk_pickup_commitments_driver_id',
        'pickup_commitments', 'drivers',
        ['assigned_driver_id'], ['id'],
        ondelete='SET NULL'
    )

    op.create_index('ix_pickup_commitments_booking_id', 'pickup_commitments', ['booking_id'])
    op.create_index('ix_pickup_commitments_deadline_status', 'pickup_commitments', ['pickup_deadline', 'status'])

    # 3. Add columns to recovery_cases
    op.add_column('recovery_cases', sa.Column('shipment_id', sa.UUID(), nullable=True))
    op.add_column('recovery_cases', sa.Column('original_transporter_id', sa.UUID(), nullable=True))
    op.add_column('recovery_cases', sa.Column('original_booking_id', sa.UUID(), nullable=True))
    op.add_column('recovery_cases', sa.Column('replacement_transporter_id', sa.UUID(), nullable=True))
    op.add_column('recovery_cases', sa.Column('replacement_booking_id', sa.UUID(), nullable=True))
    op.add_column('recovery_cases', sa.Column('approval_status', sa.String(length=50), server_default='PENDING_APPROVAL', nullable=False))
    op.add_column('recovery_cases', sa.Column('approved_by_user_id', sa.UUID(), nullable=True))
    op.add_column('recovery_cases', sa.Column('approved_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('recovery_cases', sa.Column('failure_data', postgresql.JSONB(astext_type=sa.Text()), nullable=True))
    op.add_column('recovery_cases', sa.Column('alternatives_data', postgresql.JSONB(astext_type=sa.Text()), nullable=True))

    op.create_foreign_key(
        'fk_recovery_cases_shipment_id',
        'recovery_cases', 'shipments',
        ['shipment_id'], ['id'],
        ondelete='CASCADE'
    )
    op.create_foreign_key(
        'fk_recovery_cases_orig_transporter_id',
        'recovery_cases', 'transporters',
        ['original_transporter_id'], ['id'],
        ondelete='SET NULL'
    )
    op.create_foreign_key(
        'fk_recovery_cases_orig_booking_id',
        'recovery_cases', 'transporter_bookings',
        ['original_booking_id'], ['id'],
        ondelete='SET NULL'
    )
    op.create_foreign_key(
        'fk_recovery_cases_repl_transporter_id',
        'recovery_cases', 'transporters',
        ['replacement_transporter_id'], ['id'],
        ondelete='SET NULL'
    )
    op.create_foreign_key(
        'fk_recovery_cases_repl_booking_id',
        'recovery_cases', 'transporter_bookings',
        ['replacement_booking_id'], ['id'],
        ondelete='SET NULL'
    )
    op.create_foreign_key(
        'fk_recovery_cases_approved_by_user_id',
        'recovery_cases', 'users',
        ['approved_by_user_id'], ['id'],
        ondelete='SET NULL'
    )

    op.create_index('ix_recovery_cases_shipment_id', 'recovery_cases', ['shipment_id'])

    # 4. Add unique partial index on exceptions to prevent duplicate open MISSED_PICKUP exceptions
    op.create_index(
        'uq_open_missed_pickup_per_shipment',
        'exceptions',
        ['shipment_id'],
        unique=True,
        postgresql_where=sa.text("exception_type = 'MISSED_PICKUP' AND status IN ('OPEN', 'INVESTIGATING', 'RECOVERY_IN_PROGRESS')")
    )


def downgrade() -> None:
    op.drop_index('uq_open_missed_pickup_per_shipment', table_name='exceptions')
    op.drop_index('ix_recovery_cases_shipment_id', table_name='recovery_cases')
    op.drop_constraint('fk_recovery_cases_approved_by_user_id', 'recovery_cases', type_='foreignkey')
    op.drop_constraint('fk_recovery_cases_repl_booking_id', 'recovery_cases', type_='foreignkey')
    op.drop_constraint('fk_recovery_cases_repl_transporter_id', 'recovery_cases', type_='foreignkey')
    op.drop_constraint('fk_recovery_cases_orig_booking_id', 'recovery_cases', type_='foreignkey')
    op.drop_constraint('fk_recovery_cases_orig_transporter_id', 'recovery_cases', type_='foreignkey')
    op.drop_constraint('fk_recovery_cases_shipment_id', 'recovery_cases', type_='foreignkey')

    op.drop_column('recovery_cases', 'alternatives_data')
    op.drop_column('recovery_cases', 'failure_data')
    op.drop_column('recovery_cases', 'approved_at')
    op.drop_column('recovery_cases', 'approved_by_user_id')
    op.drop_column('recovery_cases', 'approval_status')
    op.drop_column('recovery_cases', 'replacement_booking_id')
    op.drop_column('recovery_cases', 'replacement_transporter_id')
    op.drop_column('recovery_cases', 'original_booking_id')
    op.drop_column('recovery_cases', 'original_transporter_id')
    op.drop_column('recovery_cases', 'shipment_id')

    op.drop_index('ix_pickup_commitments_deadline_status', table_name='pickup_commitments')
    op.drop_index('ix_pickup_commitments_booking_id', table_name='pickup_commitments')
    op.drop_constraint('fk_pickup_commitments_driver_id', 'pickup_commitments', type_='foreignkey')
    op.drop_constraint('fk_pickup_commitments_vehicle_id', 'pickup_commitments', type_='foreignkey')
    op.drop_constraint('fk_pickup_commitments_booking_id', 'pickup_commitments', type_='foreignkey')

    op.drop_column('pickup_commitments', 'commitment_metadata')
    op.drop_column('pickup_commitments', 'assigned_driver_id')
    op.drop_column('pickup_commitments', 'assigned_vehicle_id')
    op.drop_column('pickup_commitments', 'expected_arrival')
    op.drop_column('pickup_commitments', 'pickup_deadline')
    op.drop_column('pickup_commitments', 'booking_id')
