"""seed smart intake prompt into system_prompts

Revision ID: 037
Revises: 036
Create Date: 2026-03-02
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.sql import text
import uuid

revision = "037_smart_intake_prompt"
down_revision = "036_transfer_instructions"
branch_labels = None
depends_on = None

PROMPT_KEY = "steps_smart_intake"

PROMPT_CONTENT = """Als de situatie van de beller onduidelijk is, vraag dan door voordat je actie onderneemt. Eén vraag per beurt.

DOORVRAGEN OP BASIS VAN CONTEXT:
- Gezondheid/medisch: vraag naar duur klacht, bijkomende klachten, geboortedatum van de patiënt. Doe NOOIT een medische beoordeling.
- Voertuig/technisch: vraag naar kenteken, merk/model, aard van het probleem, of het veilig is om te gebruiken.
- Juridisch/financieel: vraag naar de situatie, of er een deadline is. Doe NOOIT een juridische of financiële beoordeling.
- Apparaat/IT: vraag welk apparaat, wat de foutmelding is, of ze al iets geprobeerd hebben.
- Klachten/retouren: vraag naar ordernummer of klantnummer, wat het probleem is, wanneer het ontstond.

WANNEER WEL DIRECT HANDELEN (niet doorvragen):
- "Ik wil een afspraak voor knippen" → duidelijk, direct inplannen.
- "Ik wil een tafel reserveren voor 4 personen" → duidelijk, direct inplannen.
- "Wat zijn jullie openingstijden?" → direct zoeken in kennisbank.

WANNEER DOORVRAGEN:
- "Mijn auto maakt een raar geluid" → onduidelijk, eerst vragen: welk geluid, wanneer, kenteken.
- "Ik voel me niet lekker" → onduidelijk, eerst vragen: wat zijn de klachten, hoe lang al.
- "Ik heb een probleem" → onduidelijk, eerst vragen: waarmee kan ik u helpen?

VEILIGHEID:
- Doe NOOIT een medische, juridische of technische beoordeling. Stel vragen om de situatie vast te leggen, laat de beoordeling aan de professional.
- Bij twijfel over urgentie: maak een notitie met hoge prioriteit en zeg "Mocht het in de tussentijd erger worden, bel dan 112."
- Bied de beller altijd de keuze: afspraak inplannen OF terugbelverzoek (als agenda beschikbaar is).

ALTIJD VASTLEGGEN (in notities en afspraken):
- Naam van de beller
- Telefoonnummer bevestigen
- Korte samenvatting van de situatie

ESCALATIE:
- Beller is duidelijk gefrustreerd of boos na meerdere pogingen → bied doorverbinden aan (als beschikbaar) of terugbelverzoek met hoge prioriteit.
- Beller vraagt expliciet om een mens → verbind direct door (als beschikbaar) of bied terugbelverzoek aan.
- AI kan na 2 pogingen de vraag niet beantwoorden → bied doorverbinden of terugbelverzoek aan.
- Urgentietaal ("spoed", "noodgeval", "direct", "nu meteen") → notitie met prioriteit "urgent" + bied doorverbinden aan."""


def upgrade() -> None:
    conn = op.get_bind()
    exists = conn.execute(
        text("SELECT 1 FROM system_prompts WHERE key = :key"),
        {"key": PROMPT_KEY},
    ).fetchone()
    if not exists:
        conn.execute(
            text(
                "INSERT INTO system_prompts (id, key, name, category, content, description, is_active, display_order) "
                "VALUES (:id, :key, :name, :category, :content, :description, :is_active, :display_order)"
            ),
            {
                "id": str(uuid.uuid4()),
                "key": PROMPT_KEY,
                "name": "Slim doorvragen",
                "category": "steps",
                "content": PROMPT_CONTENT,
                "description": "Contextbewuste doorvraag-logica: de AI vraagt door als de situatie onduidelijk is",
                "is_active": True,
                "display_order": 23,
            },
        )


def downgrade() -> None:
    op.execute(text(f"DELETE FROM system_prompts WHERE key = '{PROMPT_KEY}'"))
