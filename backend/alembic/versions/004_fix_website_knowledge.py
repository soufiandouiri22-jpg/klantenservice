"""Add missing columns to website_knowledge table

Revision ID: 004_fix_website
Revises: 003_create_all
Create Date: 2026-01-29

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers
revision = '004_fix_website'
down_revision = '003_create_all'
branch_labels = None
depends_on = None


def upgrade():
    # Add missing columns to website_knowledge table
    op.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                          WHERE table_name='website_knowledge' AND column_name='webhook_secret') THEN
                ALTER TABLE website_knowledge ADD COLUMN webhook_secret VARCHAR(64);
            END IF;
            
            IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                          WHERE table_name='website_knowledge' AND column_name='last_indexed_at') THEN
                ALTER TABLE website_knowledge ADD COLUMN last_indexed_at TIMESTAMP;
            END IF;
            
            IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                          WHERE table_name='website_knowledge' AND column_name='next_index_at') THEN
                ALTER TABLE website_knowledge ADD COLUMN next_index_at TIMESTAMP;
            END IF;
            
            IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                          WHERE table_name='website_knowledge' AND column_name='is_active') THEN
                ALTER TABLE website_knowledge ADD COLUMN is_active BOOLEAN DEFAULT TRUE;
            END IF;
        END $$;
    """)


def downgrade():
    pass
