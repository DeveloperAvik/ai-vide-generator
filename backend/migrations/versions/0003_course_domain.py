"""course subject domain

Revision ID: 0003
Revises: 0002
Additive only. Courses created before this migration were all cybersecurity, so they keep that domain.
"""
from alembic import op
import sqlalchemy as sa

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("courses", sa.Column("domain", sa.String(48), nullable=False, server_default="cybersecurity"))
    op.alter_column("courses", "domain", server_default="general")


def downgrade():
    op.drop_column("courses", "domain")
