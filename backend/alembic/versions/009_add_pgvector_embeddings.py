"""Add pgvector extension and embeddings column

Revision ID: 009
Revises: 008
Create Date: 2026-02-01
"""
from alembic import op
import sqlalchemy as sa
from pgvector.sqlalchemy import Vector


# revision identifiers
revision = '009'
down_revision = '008'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create pgvector extension
    op.execute('CREATE EXTENSION IF NOT EXISTS vector')
    
    # Add embedding column to knowledge_chunks table
    # Using 384 dimensions for all-MiniLM-L6-v2 model
    op.add_column(
        'knowledge_chunks',
        sa.Column('embedding', Vector(384), nullable=True)
    )
    
    # Create an index for faster similarity search
    op.execute('''
        CREATE INDEX IF NOT EXISTS idx_knowledge_chunks_embedding 
        ON knowledge_chunks 
        USING ivfflat (embedding vector_cosine_ops)
        WITH (lists = 100)
    ''')


def downgrade() -> None:
    # Drop the index
    op.execute('DROP INDEX IF EXISTS idx_knowledge_chunks_embedding')
    
    # Remove embedding column
    op.drop_column('knowledge_chunks', 'embedding')
    
    # Note: We don't drop the vector extension as other tables might use it
