"""lesson.draft: quick unreviewed draft videos

Revision ID: 0006
Revises: 0005
Additive only.
"""
from alembic import op
import sqlalchemy as sa

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("lessons", sa.Column("draft", sa.Boolean(), nullable=False, server_default=sa.false()))


def downgrade():
    op.drop_column("lessons", "draft")
