"""
Add trial_used column to companies table.
Tracks whether a company has already used their trial period.
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers
revision = "016"
down_revision = "015"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "companies",
        sa.Column("trial_used", sa.Boolean(), nullable=True, server_default="false"),
    )
    # Mark existing companies that have/had a trial as trial_used=True
    op.execute("""
        UPDATE companies 
        SET trial_used = true 
        WHERE subscription_started_at IS NOT NULL 
           OR stripe_customer_id IS NOT NULL
    """)


def downgrade():
    op.drop_column("companies", "trial_used")
