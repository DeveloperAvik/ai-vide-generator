"""claim locations (de-duplicated claims keep every script section they appear in)

Revision ID: 0004
Revises: 0003
Additive only.
"""
from alembic import op
import sqlalchemy as sa

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("technical_claims", sa.Column("locations", sa.JSON(), nullable=False, server_default="[]"))


def downgrade():
    op.drop_column("technical_claims", "locations")
