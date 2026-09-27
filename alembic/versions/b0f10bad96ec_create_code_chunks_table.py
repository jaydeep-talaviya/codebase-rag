"""create code chunks table

Revision ID: b0f10bad96ec
Revises: f2633c13b9fa
Create Date: 2026-09-27 09:58:48.657520

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from pgvector.sqlalchemy import Vector


# revision identifiers, used by Alembic.
revision: str = 'b0f10bad96ec'
down_revision: Union[str, Sequence[str], None] = 'f2633c13b9fa'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.create_table(
        'code_chunks',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('repository_id', sa.Integer(), nullable=False),
        sa.Column('file_path', sa.String(), nullable=False),
        sa.Column('file_name', sa.String(), nullable=False),
        sa.Column('language', sa.String(), nullable=False),
        sa.Column('chunk_index', sa.Integer(), nullable=False),
        sa.Column('content', sa.String(), nullable=False),
        sa.Column('start_line', sa.Integer(), nullable=False),
        sa.Column('end_line', sa.Integer(), nullable=False),
        sa.Column('embedding', Vector(384), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_code_chunks_repository_id'), 'code_chunks', ['repository_id'])


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_code_chunks_repository_id'), table_name='code_chunks')
    op.drop_table('code_chunks')
