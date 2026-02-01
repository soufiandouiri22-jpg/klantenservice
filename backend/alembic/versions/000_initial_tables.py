"""Create initial tables (companies and users)

Revision ID: 000_initial
Revises: 
Create Date: 2026-01-26

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID


# revision identifiers
revision = '000_initial'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    # Create ENUM types first
    op.execute("DO $$ BEGIN CREATE TYPE subscriptionplan AS ENUM ('starter', 'business', 'enterprise'); EXCEPTION WHEN duplicate_object THEN null; END $$;")
    op.execute("DO $$ BEGIN CREATE TYPE userrole AS ENUM ('owner', 'admin', 'manager', 'viewer'); EXCEPTION WHEN duplicate_object THEN null; END $$;")
    op.execute("DO $$ BEGIN CREATE TYPE oauthprovider AS ENUM ('email', 'google'); EXCEPTION WHEN duplicate_object THEN null; END $$;")
    
    # Create companies table
    op.execute("""
        CREATE TABLE IF NOT EXISTS companies (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            name VARCHAR(255) NOT NULL,
            slug VARCHAR(100) UNIQUE NOT NULL,
            email VARCHAR(255) NOT NULL,
            phone VARCHAR(20),
            address VARCHAR(255),
            city VARCHAR(100),
            postal_code VARCHAR(10),
            country VARCHAR(50) DEFAULT 'Nederland',
            kvk_number VARCHAR(20),
            btw_number VARCHAR(20),
            subscription_plan subscriptionplan DEFAULT 'starter',
            subscription_status VARCHAR(20) DEFAULT 'active',
            subscription_started_at TIMESTAMP,
            subscription_ends_at TIMESTAMP,
            max_ai_workers INTEGER DEFAULT 1,
            disclosure_message TEXT DEFAULT 'U spreekt met de digitale assistent van {company_name}',
            default_language VARCHAR(10) DEFAULT 'nl-NL',
            timezone VARCHAR(50) DEFAULT 'Europe/Amsterdam',
            data_retention_days INTEGER DEFAULT 90,
            call_recording_enabled BOOLEAN DEFAULT false,
            call_recording_consent_required BOOLEAN DEFAULT true,
            is_active BOOLEAN DEFAULT true,
            is_verified BOOLEAN DEFAULT false,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    # Create index on slug
    op.execute("CREATE INDEX IF NOT EXISTS ix_companies_slug ON companies(slug)")
    
    # Create users table
    op.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            company_id UUID NOT NULL REFERENCES companies(id),
            email VARCHAR(255) UNIQUE NOT NULL,
            hashed_password VARCHAR(255),
            oauth_provider oauthprovider DEFAULT 'email' NOT NULL,
            google_id VARCHAR(255) UNIQUE,
            first_name VARCHAR(100) NOT NULL,
            last_name VARCHAR(100) NOT NULL,
            phone VARCHAR(20),
            role userrole DEFAULT 'viewer' NOT NULL,
            is_active BOOLEAN DEFAULT true,
            is_verified BOOLEAN DEFAULT false,
            last_login_at TIMESTAMP,
            password_changed_at TIMESTAMP,
            failed_login_attempts INTEGER DEFAULT 0,
            locked_until TIMESTAMP,
            verification_token VARCHAR(255),
            verification_sent_at TIMESTAMP,
            verified_at TIMESTAMP,
            reset_token VARCHAR(255),
            reset_token_expires_at TIMESTAMP,
            invite_token VARCHAR(255) UNIQUE,
            invite_token_expires_at TIMESTAMP,
            invited_by_id UUID REFERENCES users(id),
            invited_at TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    # Create indexes
    op.execute("CREATE INDEX IF NOT EXISTS ix_users_email ON users(email)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_users_google_id ON users(google_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_users_invite_token ON users(invite_token)")


def downgrade():
    op.execute("DROP TABLE IF EXISTS users CASCADE")
    op.execute("DROP TABLE IF EXISTS companies CASCADE")
    op.execute("DROP TYPE IF EXISTS oauthprovider")
    op.execute("DROP TYPE IF EXISTS userrole")
    op.execute("DROP TYPE IF EXISTS subscriptionplan")
