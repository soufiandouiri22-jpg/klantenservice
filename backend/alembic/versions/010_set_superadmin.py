"""Set superadmin for anarchyamsterdam@gmail.com

Revision ID: 010_set_superadmin
Revises: 009_add_pgvector
Create Date: 2026-02-03

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '010_set_superadmin'
down_revision = '009_add_pgvector'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Set is_superadmin = true for anarchyamsterdam@gmail.com
    op.execute("""
        UPDATE users 
        SET is_superadmin = true 
        WHERE email = 'anarchyamsterdam@gmail.com'
    """)


def downgrade() -> None:
    # Remove superadmin status
    op.execute("""
        UPDATE users 
        SET is_superadmin = false 
        WHERE email = 'anarchyamsterdam@gmail.com'
    """)
