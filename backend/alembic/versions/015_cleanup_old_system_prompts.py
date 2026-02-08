"""Remove redundant system prompts absorbed into code-level instructions

Revision ID: 015_cleanup_old_system_prompts
Revises: 014_register_consents
Create Date: 2026-02-08

The following 5 prompts were absorbed into build_system_instructions() and
are now duplicate. Only privacy_gdpr and ai_disclosure remain as
admin-editable policies.
"""
from alembic import op

revision = '015_cleanup_old_system_prompts'
down_revision = '014_register_consents'
branch_labels = None
depends_on = None

# Keys that are now handled entirely in code
OBSOLETE_KEYS = [
    'language_rules',
    'safety_rules',
    'edge_cases',
    'quality_standards',
    'conversation_flow',
]


def upgrade():
    for key in OBSOLETE_KEYS:
        op.execute(
            f"DELETE FROM system_prompts WHERE key = '{key}'"
        )


def downgrade():
    # Re-inserting old prompts is not necessary; they can be re-seeded
    # via the admin "Standaard laden" button if ever needed.
    pass
