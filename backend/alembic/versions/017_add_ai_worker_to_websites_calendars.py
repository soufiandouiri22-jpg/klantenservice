"""
Add ai_worker_id to website_knowledge and calendar_integrations tables.
Enforces 1:1 linking of resources to AI workers.
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

# revision identifiers
revision = "017_add_ai_worker_to_websites_calendars"
down_revision = "016_add_trial_used_column"
branch_labels = None
depends_on = None


def upgrade():
    # Add ai_worker_id to website_knowledge
    op.add_column(
        "website_knowledge",
        sa.Column("ai_worker_id", UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_website_knowledge_ai_worker",
        "website_knowledge",
        "ai_workers",
        ["ai_worker_id"],
        ["id"],
        ondelete="SET NULL",
    )

    # Add ai_worker_id to calendar_integrations
    op.add_column(
        "calendar_integrations",
        sa.Column("ai_worker_id", UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_calendar_integrations_ai_worker",
        "calendar_integrations",
        "ai_workers",
        ["ai_worker_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade():
    op.drop_constraint("fk_calendar_integrations_ai_worker", "calendar_integrations", type_="foreignkey")
    op.drop_column("calendar_integrations", "ai_worker_id")
    op.drop_constraint("fk_website_knowledge_ai_worker", "website_knowledge", type_="foreignkey")
    op.drop_column("website_knowledge", "ai_worker_id")
