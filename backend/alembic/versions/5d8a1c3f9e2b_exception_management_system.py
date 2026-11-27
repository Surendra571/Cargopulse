"""Exception Management System

Revision ID: 5d8a1c3f9e2b
Revises: 4c9e2b3f1a5d
Create Date: 2026-11-24 19:15:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '5d8a1c3f9e2b'
down_revision = '4c9e2b3f1a5d'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. Expand exception_type_enum
    with op.get_context().autocommit_block():
        for val in [
            'PICKUP_OVERDUE',
            'BOOKING_REJECTED',
            'BOOKING_EXPIRED',
            'VEHICLE_UNAVAILABLE',
            'TRACKING_STALE',
            'DELIVERY_DELAYED',
            'POD_MISSING',
            'DELIVERY_DISCREPANCY',
            'WEBHOOK_FAILURE',
            'INTEGRATION_FAILURE',
        ]:
            op.execute(sa.text(f"ALTER TYPE exception_type_enum ADD VALUE IF NOT EXISTS '{val}'"))

        # 2. Expand exception_status_enum
        for val in ['ACKNOWLEDGED', 'RESOLVING']:
            op.execute(sa.text(f"ALTER TYPE exception_status_enum ADD VALUE IF NOT EXISTS '{val}'"))

    # 3. Alter exceptions table
    op.alter_column('exceptions', 'shipment_id', existing_type=sa.UUID(), nullable=True)

    op.add_column('exceptions', sa.Column('priority', sa.String(length=20), server_default='MEDIUM', nullable=False))
    op.add_column('exceptions', sa.Column('transporter_id', sa.UUID(), nullable=True))
    op.add_column('exceptions', sa.Column('assigned_owner_id', sa.UUID(), nullable=True))
    op.add_column('exceptions', sa.Column('root_cause', sa.Text(), nullable=True))
    op.add_column('exceptions', sa.Column('escalation_level', sa.Integer(), server_default='0', nullable=False))
    op.add_column('exceptions', sa.Column('escalated_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('exceptions', sa.Column('acknowledged_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('exceptions', sa.Column('acknowledged_by_user_id', sa.UUID(), nullable=True))
    op.add_column('exceptions', sa.Column('closed_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('exceptions', sa.Column('closed_by_user_id', sa.UUID(), nullable=True))
    op.add_column('exceptions', sa.Column('closure_reason', sa.Text(), nullable=True))

    op.create_foreign_key(
        'fk_exceptions_transporter_id',
        'exceptions', 'transporters',
        ['transporter_id'], ['id'],
        ondelete='SET NULL'
    )
    op.create_foreign_key(
        'fk_exceptions_assigned_owner_id',
        'exceptions', 'users',
        ['assigned_owner_id'], ['id'],
        ondelete='SET NULL'
    )
    op.create_foreign_key(
        'fk_exceptions_acknowledged_by_user_id',
        'exceptions', 'users',
        ['acknowledged_by_user_id'], ['id'],
        ondelete='SET NULL'
    )
    op.create_foreign_key(
        'fk_exceptions_closed_by_user_id',
        'exceptions', 'users',
        ['closed_by_user_id'], ['id'],
        ondelete='SET NULL'
    )

    op.create_index('ix_exceptions_transporter_id', 'exceptions', ['transporter_id'])
    op.create_index('ix_exceptions_assigned_owner_id', 'exceptions', ['assigned_owner_id'])
    op.create_index('ix_exceptions_priority', 'exceptions', ['priority'])


def downgrade() -> None:
    op.drop_index('ix_exceptions_priority', table_name='exceptions')
    op.drop_index('ix_exceptions_assigned_owner_id', table_name='exceptions')
    op.drop_index('ix_exceptions_transporter_id', table_name='exceptions')

    op.drop_constraint('fk_exceptions_closed_by_user_id', 'exceptions', type_='foreignkey')
    op.drop_constraint('fk_exceptions_acknowledged_by_user_id', 'exceptions', type_='foreignkey')
    op.drop_constraint('fk_exceptions_assigned_owner_id', 'exceptions', type_='foreignkey')
    op.drop_constraint('fk_exceptions_transporter_id', 'exceptions', type_='foreignkey')

    op.drop_column('exceptions', 'closure_reason')
    op.drop_column('exceptions', 'closed_by_user_id')
    op.drop_column('exceptions', 'closed_at')
    op.drop_column('exceptions', 'acknowledged_by_user_id')
    op.drop_column('exceptions', 'acknowledged_at')
    op.drop_column('exceptions', 'escalated_at')
    op.drop_column('exceptions', 'escalation_level')
    op.drop_column('exceptions', 'root_cause')
    op.drop_column('exceptions', 'assigned_owner_id')
    op.drop_column('exceptions', 'transporter_id')
    op.drop_column('exceptions', 'priority')

    op.alter_column('exceptions', 'shipment_id', existing_type=sa.UUID(), nullable=False)
