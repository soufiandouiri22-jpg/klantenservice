"""Add 'handled' value to calloutcome enum

Revision ID: 011
Revises: 010
Create Date: 2026-02-03
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers
revision = '011'
down_revision = '010'
branch_labels = None
depends_on = None


def upgrade():
    """Add 'handled' to the calloutcome enum."""
    # PostgreSQL requires special handling to add values to an enum
    op.execute("ALTER TYPE calloutcome ADD VALUE IF NOT EXISTS 'handled'")


def downgrade():
    """
    Note: PostgreSQL doesn't support removing values from enums easily.
    To properly downgrade, you would need to:
    1. Create a new enum without 'handled'
    2. Update all columns using the old enum
    3. Drop the old enum
    4. Rename the new enum
    
    For simplicity, we just leave the enum as-is on downgrade.
    """
    pass
