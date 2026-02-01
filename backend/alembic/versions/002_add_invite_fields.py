"""Add invite fields to users table

Revision ID: 002_add_invite
Revises: 001_add_oauth
Create Date: 2026-01-29

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID


# revision identifiers
revision = '002_add_invite'
down_revision = '001_add_oauth'
branch_labels = None
depends_on = None


def upgrade():
    # Note: Invite fields are now included in initial migration (000_initial)
    # This migration is kept for historical compatibility
    # Add columns only if they don't exist
    
    op.execute("""
        DO $$ BEGIN
            ALTER TABLE users ADD COLUMN invite_token VARCHAR(255) UNIQUE;
        EXCEPTION WHEN duplicate_column THEN null;
        END $$;
    """)
    op.execute("""
        DO $$ BEGIN
            ALTER TABLE users ADD COLUMN invite_token_expires_at TIMESTAMP;
        EXCEPTION WHEN duplicate_column THEN null;
        END $$;
    """)
    op.execute("""
        DO $$ BEGIN
            ALTER TABLE users ADD COLUMN invited_by_id UUID REFERENCES users(id);
        EXCEPTION WHEN duplicate_column THEN null;
        END $$;
    """)
    op.execute("""
        DO $$ BEGIN
            ALTER TABLE users ADD COLUMN invited_at TIMESTAMP;
        EXCEPTION WHEN duplicate_column THEN null;
        END $$;
    """)
    
    # Create index if not exists
    op.execute("CREATE INDEX IF NOT EXISTS ix_users_invite_token ON users(invite_token)")


def downgrade():
    op.drop_column('users', 'invited_at')
    op.drop_column('users', 'invited_by_id')
    op.drop_column('users', 'invite_token_expires_at')
    op.drop_column('users', 'invite_token')
