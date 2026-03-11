"""
Query classifier – lightweight, rule-based intent detection.
Maps user queries to chunk types for targeted retrieval.
"""
import re

# keyword -> query_type mapping (checked in order, first match wins)
_RULES: list[tuple[re.Pattern, str]] = [
    (re.compile(r"\b(prijs|kost|tarief|pakket|plan|abonnement|euro|€|betaal|goedkoop|duur|budget)\b", re.I), "pricing"),
    (re.compile(r"\b(openingstijd|bereikbaar|bellen|telefoon|email|e-mail|contact|adres|locatie|route)\b", re.I), "contact"),
    (re.compile(r"\b(retour|terugsturen|annuleer|annulering|opzeg|garantie|verzend|lever|bezorg)\b", re.I), "policy"),
    (re.compile(r"\b(faq|veelgesteld|vraag en antwoord)\b", re.I), "faq"),
    (re.compile(r"\b(locatie|vestiging|filiaal|kantoor|winkel|route|parkeer)\b", re.I), "location"),
    (re.compile(r"\b(blog|artikel|nieuws)\b", re.I), "blog"),
    (re.compile(r"\b(product|dienst|service|aanbod|oplossing|feature|functie|mogelijkheid)\b", re.I), "service"),
]


def classify_query(query: str) -> str:
    """Classify a user query into a chunk type for retrieval boosting. Returns 'general' if no match."""
    q = query.strip()
    for pattern, qtype in _RULES:
        if pattern.search(q):
            return qtype
    return "general"
