"""Seed default training rules for existing companies

Revision ID: 007_seed_training_rules
Revises: 006_add_business_number_fields
Create Date: 2026-02-01

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import table, column
from uuid import uuid4
from datetime import datetime


# revision identifiers, used by Alembic.
revision = '007_seed_training_rules'
down_revision = '006_business_number'
branch_labels = None
depends_on = None


# Default training rules that every company gets
DEFAULT_TRAINING_RULES = [
    {
        "rule_key": "use_formal_address",
        "rule_name": "Gebruik u-vorm",
        "rule_description": "Spreek de klant aan met 'u' in plaats van 'jij'.",
        "is_enabled": True,
        "display_order": 1,
    },
    {
        "rule_key": "apologize_on_complaints",
        "rule_name": "Excuses bij klachten",
        "rule_description": "Bied excuses aan wanneer een klant een klacht heeft.",
        "is_enabled": True,
        "display_order": 2,
    },
    {
        "rule_key": "offer_alternatives",
        "rule_name": "Altijd alternatieven aanbieden",
        "rule_description": "Bied altijd een alternatief aan als iets niet mogelijk is.",
        "is_enabled": True,
        "display_order": 3,
    },
    {
        "rule_key": "never_guess",
        "rule_name": "Nooit gokken",
        "rule_description": "Geef nooit informatie waar je niet zeker van bent. Verwijs door indien nodig.",
        "is_enabled": True,
        "display_order": 4,
    },
    {
        "rule_key": "confirm_appointments",
        "rule_name": "Afspraken bevestigen",
        "rule_description": "Herhaal altijd de datum en tijd van een afspraak ter bevestiging.",
        "is_enabled": True,
        "display_order": 5,
    },
    {
        "rule_key": "summarize_at_end",
        "rule_name": "Samenvatten aan einde",
        "rule_description": "Vat aan het einde van het gesprek kort samen wat er is besproken.",
        "is_enabled": True,
        "display_order": 6,
    },
    {
        "rule_key": "collect_callback_number",
        "rule_name": "Terugbelnummer vragen",
        "rule_description": "Vraag om een terugbelnummer als de vraag niet direct beantwoord kan worden.",
        "is_enabled": True,
        "display_order": 7,
    },
]


def upgrade():
    # Get connection
    conn = op.get_bind()
    
    # Get all companies
    companies_result = conn.execute(sa.text("SELECT id FROM companies"))
    companies = companies_result.fetchall()
    
    for company in companies:
        company_id = company[0]
        
        # Check if company already has training rules
        existing_rules = conn.execute(
            sa.text("SELECT COUNT(*) FROM training_rules WHERE company_id = :company_id"),
            {"company_id": company_id}
        ).fetchone()[0]
        
        if existing_rules == 0:
            # Insert default training rules for this company
            for rule_data in DEFAULT_TRAINING_RULES:
                conn.execute(
                    sa.text("""
                        INSERT INTO training_rules 
                        (id, company_id, rule_key, rule_name, rule_description, is_enabled, display_order, created_at, updated_at)
                        VALUES (:id, :company_id, :rule_key, :rule_name, :rule_description, :is_enabled, :display_order, :created_at, :updated_at)
                    """),
                    {
                        "id": str(uuid4()),
                        "company_id": company_id,
                        "rule_key": rule_data["rule_key"],
                        "rule_name": rule_data["rule_name"],
                        "rule_description": rule_data["rule_description"],
                        "is_enabled": rule_data["is_enabled"],
                        "display_order": rule_data["display_order"],
                        "created_at": datetime.utcnow(),
                        "updated_at": datetime.utcnow(),
                    }
                )
            print(f"Added default training rules for company {company_id}")


def downgrade():
    # We don't want to remove the rules on downgrade as they may have been modified
    pass
