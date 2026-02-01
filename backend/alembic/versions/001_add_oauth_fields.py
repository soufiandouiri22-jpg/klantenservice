"""Add OAuth fields to users table

Revision ID: 001_add_oauth
Revises: 
Create Date: 2026-01-27

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '001_add_oauth'
down_revision = '000_initial'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Note: OAuth fields are now included in initial migration (000_initial)
    # This migration is kept for historical compatibility
    # All fields already exist, so we use IF NOT EXISTS checks
    
    # Create the oauth_provider enum type if not exists
    op.execute("DO $$ BEGIN CREATE TYPE oauthprovider AS ENUM ('email', 'google'); EXCEPTION WHEN duplicate_object THEN null; END $$;")
    
    # Add columns only if they don't exist
    op.execute("""
        DO $$ BEGIN
            ALTER TABLE users ADD COLUMN oauth_provider oauthprovider DEFAULT 'email' NOT NULL;
        EXCEPTION WHEN duplicate_column THEN null;
        END $$;
    """)
    
    op.execute("""
        DO $$ BEGIN
            ALTER TABLE users ADD COLUMN google_id VARCHAR(255) UNIQUE;
        EXCEPTION WHEN duplicate_column THEN null;
        END $$;
    """)
    
    # Create index if not exists
    op.execute("CREATE INDEX IF NOT EXISTS ix_users_google_id ON users(google_id)")
    
    # Make hashed_password nullable (safe to run multiple times)
    op.execute("ALTER TABLE users ALTER COLUMN hashed_password DROP NOT NULL")


def downgrade() -> None:
    # Remove index
    op.drop_index('ix_users_google_id', table_name='users')
    
    # Remove columns
    op.drop_column('users', 'google_id')
    op.drop_column('users', 'oauth_provider')
    
    # Drop the enum type
    sa.Enum(name='oauthprovider').drop(op.get_bind(), checkfirst=True)
    
    # Make hashed_password required again (this may fail if OAuth users exist)
    op.alter_column('users', 'hashed_password',
        existing_type=sa.String(255),
        nullable=False
    )
