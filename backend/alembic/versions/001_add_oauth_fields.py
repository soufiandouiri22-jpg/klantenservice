"""Add OAuth fields to users table

Revision ID: 001_add_oauth
Revises: 
Create Date: 2026-01-27

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '001_add_oauth'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create the oauth_provider enum type
    oauth_provider_enum = sa.Enum('email', 'google', name='oauthprovider')
    oauth_provider_enum.create(op.get_bind(), checkfirst=True)
    
    # Add oauth_provider column with default 'email'
    op.add_column('users', sa.Column(
        'oauth_provider',
        sa.Enum('email', 'google', name='oauthprovider'),
        nullable=False,
        server_default='email'
    ))
    
    # Add google_id column
    op.add_column('users', sa.Column(
        'google_id',
        sa.String(255),
        nullable=True,
        unique=True
    ))
    
    # Create index on google_id
    op.create_index('ix_users_google_id', 'users', ['google_id'], unique=True)
    
    # Make hashed_password nullable (for OAuth-only accounts)
    op.alter_column('users', 'hashed_password',
        existing_type=sa.String(255),
        nullable=True
    )


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
