"""word emoji, synonyms and antonyms

Revision ID: 0006
Revises: 0005
Create Date: 2026-11-02 15:30:00
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = '0006'
down_revision: Union[str, None] = '0005'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('words', sa.Column('emoji', sa.String(length=16), nullable=True))
    op.add_column('words', sa.Column('synonyms', sa.JSON(), nullable=True))
    op.add_column('words', sa.Column('antonyms', sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column('words', 'antonyms')
    op.drop_column('words', 'synonyms')
    op.drop_column('words', 'emoji')
