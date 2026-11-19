"""word photos (instead of emoji pictures)

Revision ID: 0007
Revises: 0006
Create Date: 2026-11-06 10:00:00
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = '0007'
down_revision: Union[str, None] = '0006'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('words', sa.Column('image_path', sa.String(length=255), nullable=True))
    op.add_column('words', sa.Column('image_file_id', sa.String(length=255), nullable=True))


def downgrade() -> None:
    op.drop_column('words', 'image_file_id')
    op.drop_column('words', 'image_path')
