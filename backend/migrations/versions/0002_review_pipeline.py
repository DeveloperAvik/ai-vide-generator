"""source provenance, claims, technical review, quality gate

Revision ID: 0002
Revises: 0001
Additive only: new nullable-safe columns (with server defaults) and new tables. No data is dropped.
"""
from alembic import op
import sqlalchemy as sa

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None

TS = lambda: [sa.Column("created_at", sa.DateTime(timezone=True), nullable=False), sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False)]


def upgrade():
    for name, typ in [("title", sa.String(512)), ("publisher", sa.String(128)), ("category", sa.String(32)), ("published_at", sa.String(64)),
                      ("section", sa.String(512)), ("content_hash", sa.String(64)), ("status", sa.String(32))]:
        op.add_column("research_sources", sa.Column(name, typ, nullable=False, server_default=""))
    op.add_column("research_sources", sa.Column("full_text", sa.Text(), nullable=False, server_default=""))
    op.add_column("lesson_scripts", sa.Column("change_note", sa.Text(), nullable=False, server_default=""))

    op.create_table("review_runs", sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("lesson_id", sa.Integer(), sa.ForeignKey("lessons.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("script_version", sa.Integer(), nullable=False), sa.Column("kind", sa.String(24), nullable=False),
        sa.Column("reviewer_model", sa.String(128), nullable=False), sa.Column("simulated", sa.Boolean(), nullable=False),
        sa.Column("status", sa.String(16), nullable=False), sa.Column("error", sa.Text(), nullable=False),
        sa.Column("summary", sa.JSON(), nullable=False), sa.Column("finished_at", sa.DateTime(timezone=True)), *TS())
    op.create_table("technical_claims", sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("lesson_id", sa.Integer(), sa.ForeignKey("lessons.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("run_id", sa.Integer(), sa.ForeignKey("review_runs.id", ondelete="CASCADE"), index=True),
        sa.Column("script_version", sa.Integer(), nullable=False), sa.Column("section", sa.String(64), nullable=False),
        sa.Column("text", sa.Text(), nullable=False), sa.Column("category", sa.String(32), nullable=False),
        sa.Column("critical", sa.Boolean(), nullable=False), sa.Column("status", sa.String(24), nullable=False),
        sa.Column("source_ids", sa.JSON(), nullable=False), sa.Column("evidence_excerpt", sa.Text(), nullable=False),
        sa.Column("evidence_section", sa.String(512), nullable=False), sa.Column("reviewer_notes", sa.Text(), nullable=False),
        sa.Column("confidence", sa.Float()), sa.Column("needs_human", sa.Boolean(), nullable=False),
        sa.Column("human_decision", sa.String(16), nullable=False), sa.Column("human_note", sa.Text(), nullable=False), *TS())
    op.create_table("review_findings", sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("run_id", sa.Integer(), sa.ForeignKey("review_runs.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("lesson_id", sa.Integer(), sa.ForeignKey("lessons.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("script_version", sa.Integer(), nullable=False), sa.Column("severity", sa.String(16), nullable=False),
        sa.Column("category", sa.String(32), nullable=False), sa.Column("section", sa.String(64), nullable=False),
        sa.Column("problem_text", sa.Text(), nullable=False), sa.Column("explanation", sa.Text(), nullable=False),
        sa.Column("evidence", sa.Text(), nullable=False), sa.Column("recommended_correction", sa.Text(), nullable=False),
        sa.Column("blocks_approval", sa.Boolean(), nullable=False), sa.Column("status", sa.String(16), nullable=False, index=True),
        sa.Column("decided_by", sa.Integer(), sa.ForeignKey("users.id")), sa.Column("decision_note", sa.Text(), nullable=False),
        sa.Column("applied_version", sa.Integer()), *TS())
    op.create_table("quality_gate_results", sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("lesson_id", sa.Integer(), sa.ForeignKey("lessons.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("stage", sa.String(16), nullable=False), sa.Column("script_version", sa.Integer(), nullable=False),
        sa.Column("storyboard_version", sa.Integer()), sa.Column("passed", sa.Boolean(), nullable=False),
        sa.Column("checks", sa.JSON(), nullable=False), *TS())


def downgrade():
    for t in ("quality_gate_results", "review_findings", "technical_claims", "review_runs"):
        op.drop_table(t)
    op.drop_column("lesson_scripts", "change_note")
    for c in ("full_text", "status", "content_hash", "section", "published_at", "category", "publisher", "title"):
        op.drop_column("research_sources", c)
