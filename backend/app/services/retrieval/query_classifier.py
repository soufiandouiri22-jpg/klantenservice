"""
Query classifier – lightweight, rule-based intent detection.
Maps user queries to chunk types for targeted retrieval.
"""
import re

# keyword -> query_type mapping (checked in order, first match wins)
_RULES: list[tuple[re.Pattern, str]] = [
    (re.compile(r"\b(prij[sz]\w*|kost\w*|tariev\w*|tarief\w*|pakket\w*|plan\w*|abonnement\w*|euro|€|betaal\w*|goedkoop\w*|duur|budget\w*|belminut\w*|starter|business|enterprise)\b", re.I), "pricing"),
    (re.compile(r"\b(openingstijd\w*|bereikbaar\w*|bellen|telefoon\w*|email\w*|e-mail\w*|contact\w*|adres\w*|locatie\w*|route\w*)\b", re.I), "contact"),
    (re.compile(r"\b(retour\w*|terugsturen|annuleer\w*|annulering\w*|opzeg\w*|garantie\w*|verzend\w*|lever\w*|bezorg\w*)\b", re.I), "policy"),
    (re.compile(r"\b(faq|veelgesteld\w*|vraag en antwoord)\b", re.I), "faq"),
    (re.compile(r"\b(locatie\w*|vestiging\w*|filiaal\w*|kantoor\w*|winkel\w*|route\w*|parkeer\w*)\b", re.I), "location"),
    (re.compile(r"\b(blog\w*|artikel\w*|nieuws\w*)\b", re.I), "blog"),
    (re.compile(r"\b(product\w*|dienst\w*|service\w*|aanbod\w*|oplossing\w*|feature\w*|functie\w*|mogelijkheid\w*)\b", re.I), "service"),
    (re.compile(
        r"wat\s+(?:doen|doet|bieden|biedt)\s+(?:jullie|je|u|uw|\w+\.?\w*)"  # wat doet/doen X?
        r"|jullie\s+(?:allemaal\s+)?doen"
        r"|wat\s+voor\s+(?:bedrijf|organisatie|bureau)"
        r"|vertel\s+(?:eens\s+)?over\s+(?:jullie|je|uw|het\s+bedrijf)"
        r"|uitleggen\s+wat\s+jullie"
        r"|wat\s+jullie\s+(?:allemaal\s+)?(?:doen|bieden|aanbieden)"
        r"|wat\s+is\s+\S+\s+(?:precies|eigenlijk|voor\s+(?:bedrijf|dienst))"
        r"|waar\s+(?:gaat|staat)\s+\S+\s+voor"
        r"|wie\s+(?:is|zijn)\s+(?:jullie|je|uw)"
        r"|wat\s+houdt\s+\S+\s+in",
        re.I,
    ), "service"),
]


def classify_query(query: str) -> str:
    """Classify a user query into a chunk type for retrieval boosting. Returns 'general' if no match."""
    q = query.strip()
    for pattern, qtype in _RULES:
        if pattern.search(q):
            return qtype
    return "general"
