"""Update disclosure_message default to time-aware greeting

Revision ID: 022_disclosure_greeting
Revises: 021_optimize_vector_search
Create Date: 2026-02-20
"""
from alembic import op

revision = "022_disclosure_greeting"
down_revision = "021_optimize_vector_search"
branch_labels = None
depends_on = None

OLD_DEFAULT = "U spreekt met {ai_worker_name}, de digitale assistent van {company_name}"
NEW_DEFAULT = "{greeting}, met {ai_worker_name} van {company_name}, waarmee kan ik u helpen?"


def upgrade() -> None:
    op.execute(
        f"""
        UPDATE companies
        SET disclosure_message = '{NEW_DEFAULT}'
        WHERE disclosure_message = '{OLD_DEFAULT}'
           OR disclosure_message IS NULL
           OR disclosure_message = ''
        """
    )

    op.alter_column(
        "companies",
        "disclosure_message",
        server_default=NEW_DEFAULT,
    )


def downgrade() -> None:
    op.execute(
        f"""
        UPDATE companies
        SET disclosure_message = '{OLD_DEFAULT}'
        WHERE disclosure_message = '{NEW_DEFAULT}'
        """
    )

    op.alter_column(
        "companies",
        "disclosure_message",
        server_default=OLD_DEFAULT,
    )
