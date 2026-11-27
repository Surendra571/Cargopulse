"""phase14_digital_proof_of_delivery

Revision ID: 7f1a3b5c8d2e
Revises: 6e9b2a1c4f5d
Create Date: 2026-11-24 21:05:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '7f1a3b5c8d2e'
down_revision: Union[str, None] = '6e9b2a1c4f5d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add new columns to proof_of_delivery
    op.add_column('proof_of_delivery', sa.Column('recipient_phone', sa.String(length=50), nullable=True))
    op.add_column('proof_of_delivery', sa.Column('recipient_email', sa.String(length=150), nullable=True))
    op.add_column('proof_of_delivery', sa.Column('delivery_photo_urls', postgresql.JSONB(astext_type=sa.Text()), server_default='[]', nullable=False))
    
    op.add_column('proof_of_delivery', sa.Column('expected_quantity', sa.Integer(), server_default='0', nullable=False))
    op.add_column('proof_of_delivery', sa.Column('received_quantity', sa.Integer(), server_default='0', nullable=False))
    op.add_column('proof_of_delivery', sa.Column('is_shortage', sa.Boolean(), server_default='false', nullable=False))
    op.add_column('proof_of_delivery', sa.Column('shortage_quantity', sa.Integer(), server_default='0', nullable=False))
    op.add_column('proof_of_delivery', sa.Column('shortage_description', sa.Text(), nullable=True))
    
    op.add_column('proof_of_delivery', sa.Column('is_damaged', sa.Boolean(), server_default='false', nullable=False))
    op.add_column('proof_of_delivery', sa.Column('damage_severity', sa.String(length=50), nullable=True))
    op.add_column('proof_of_delivery', sa.Column('damage_description', sa.Text(), nullable=True))
    op.add_column('proof_of_delivery', sa.Column('damage_photo_urls', postgresql.JSONB(astext_type=sa.Text()), server_default='[]', nullable=False))
    
    op.add_column('proof_of_delivery', sa.Column('driver_id', sa.UUID(), nullable=True))
    op.add_column('proof_of_delivery', sa.Column('vehicle_id', sa.UUID(), nullable=True))
    op.add_column('proof_of_delivery', sa.Column('driver_name', sa.String(length=150), nullable=True))
    op.add_column('proof_of_delivery', sa.Column('vehicle_plate', sa.String(length=50), nullable=True))
    op.add_column('proof_of_delivery', sa.Column('acknowledgement_type', sa.String(length=50), server_default='SIGNATURE', nullable=False))
    op.add_column('proof_of_delivery', sa.Column('additional_notes', sa.Text(), nullable=True))
    
    op.add_column('proof_of_delivery', sa.Column('delivery_location_name', sa.String(length=255), nullable=True))
    op.add_column('proof_of_delivery', sa.Column('distance_to_destination_meters', sa.Float(), nullable=True))
    op.add_column('proof_of_delivery', sa.Column('is_geofence_verified', sa.Boolean(), server_default='false', nullable=False))
    
    op.add_column('proof_of_delivery', sa.Column('file_metadata', postgresql.JSONB(astext_type=sa.Text()), server_default='{}', nullable=False))
    op.add_column('proof_of_delivery', sa.Column('submission_history', postgresql.JSONB(astext_type=sa.Text()), server_default='[]', nullable=False))
    op.add_column('proof_of_delivery', sa.Column('is_modified', sa.Boolean(), server_default='false', nullable=False))

    # Foreign keys and indexes
    op.create_foreign_key('fk_pod_driver', 'proof_of_delivery', 'drivers', ['driver_id'], ['id'], ondelete='SET NULL')
    op.create_foreign_key('fk_pod_vehicle', 'proof_of_delivery', 'vehicles', ['vehicle_id'], ['id'], ondelete='SET NULL')
    op.create_index(op.f('ix_proof_of_delivery_driver_id'), 'proof_of_delivery', ['driver_id'], unique=False)
    op.create_index(op.f('ix_proof_of_delivery_vehicle_id'), 'proof_of_delivery', ['vehicle_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_proof_of_delivery_vehicle_id'), table_name='proof_of_delivery')
    op.drop_index(op.f('ix_proof_of_delivery_driver_id'), table_name='proof_of_delivery')
    op.drop_constraint('fk_pod_vehicle', 'proof_of_delivery', type_='foreignkey')
    op.drop_constraint('fk_pod_driver', 'proof_of_delivery', type_='foreignkey')

    op.drop_column('proof_of_delivery', 'is_modified')
    op.drop_column('proof_of_delivery', 'submission_history')
    op.drop_column('proof_of_delivery', 'file_metadata')
    op.drop_column('proof_of_delivery', 'is_geofence_verified')
    op.drop_column('proof_of_delivery', 'distance_to_destination_meters')
    op.drop_column('proof_of_delivery', 'delivery_location_name')
    op.drop_column('proof_of_delivery', 'additional_notes')
    op.drop_column('proof_of_delivery', 'acknowledgement_type')
    op.drop_column('proof_of_delivery', 'vehicle_plate')
    op.drop_column('proof_of_delivery', 'driver_name')
    op.drop_column('proof_of_delivery', 'vehicle_id')
    op.drop_column('proof_of_delivery', 'driver_id')
    op.drop_column('proof_of_delivery', 'damage_photo_urls')
    op.drop_column('proof_of_delivery', 'damage_description')
    op.drop_column('proof_of_delivery', 'damage_severity')
    op.drop_column('proof_of_delivery', 'is_damaged')
    op.drop_column('proof_of_delivery', 'shortage_description')
    op.drop_column('proof_of_delivery', 'shortage_quantity')
    op.drop_column('proof_of_delivery', 'is_shortage')
    op.drop_column('proof_of_delivery', 'received_quantity')
    op.drop_column('proof_of_delivery', 'expected_quantity')
    op.drop_column('proof_of_delivery', 'delivery_photo_urls')
    op.drop_column('proof_of_delivery', 'recipient_email')
    op.drop_column('proof_of_delivery', 'recipient_phone')
