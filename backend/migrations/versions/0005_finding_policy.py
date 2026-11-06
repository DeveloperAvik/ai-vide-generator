"""review findings: objective + policy note

Revision ID: 0005
Revises: 0004
Additive only.
"""
from alembic import op
import sqlalchemy as sa

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("review_findings", sa.Column("objective", sa.Text(), nullable=False, server_default=""))
    op.add_column("review_findings", sa.Column("policy_note", sa.Text(), nullable=False, server_default=""))


def downgrade():
    op.drop_column("review_findings", "policy_note")
    op.drop_column("review_findings", "objective")
