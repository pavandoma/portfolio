"""file contents in the database (RIP_STORAGE=db)

Revision ID: 0002
Revises: 0001
Create Date: 2026-10-28 18:00:00
"""
from alembic import op
import sqlalchemy as sa


revision = '0002'
down_revision = '0001'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table('stored_files',
    sa.Column('key', sa.String(length=500), nullable=False),
    sa.Column('content', sa.LargeBinary(), nullable=False),
    sa.Column('sha256', sa.String(length=64), nullable=False),
    sa.Column('size_bytes', sa.Integer(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.PrimaryKeyConstraint('key')
    )


def downgrade() -> None:
    op.drop_table('stored_files')
