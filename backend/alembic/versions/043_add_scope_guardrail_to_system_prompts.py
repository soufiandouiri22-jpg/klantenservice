"""Add scope guardrail to existing Veiligheid system prompt

Revision ID: 043_scope_guardrail
Revises: 042_usage_alerts
Create Date: 2026-03-02
"""
from alembic import op

revision = "043_scope_guardrail"
down_revision = "042_usage_alerts"
branch_labels = None
depends_on = None

SCOPE_LINE = (
    '\nJe helpt UITSLUITEND met vragen die gerelateerd zijn aan {company_name} en hun diensten. '
    'Bij vragen die niets met het bedrijf te maken hebben (bijv. pizza bestellen, weer, sport, andere bedrijven): '
    'zeg vriendelijk "Daar kan ik u helaas niet mee helpen, maar ik help u graag met vragen over {company_name}!". '
    'Ga NOOIT mee in off-topic verzoeken. Dit is belangrijk.'
)


def upgrade() -> None:
    op.execute(f"""
        UPDATE system_prompts
        SET content = content || '{SCOPE_LINE.replace("'", "''")}'
        WHERE key = 'guardrails_all'
          AND content NOT LIKE '%UITSLUITEND%'
    """)


def downgrade() -> None:
    pass
