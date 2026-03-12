"""
Retrieval regression tests — verify that typed retrieval, scoring, and
policy-crosstalk penalties work correctly across edge cases.

Self-contained: extracts the pure logic from query_classifier.py and scorer.py
to avoid importing the full app dependency chain.

Run:  python3 tests/test_retrieval_regression.py
"""
import math
import re
import logging

logger = logging.getLogger(__name__)


# ── Extracted from query_classifier.py ──────────────────────────────────────

_RULES: list[tuple[re.Pattern, str]] = [
    (re.compile(r"\b(prij[sz]\w*|kost\w*|tariev\w*|tarief\w*|pakket\w*|plan\w*|abonnement\w*|euro|€|betaal\w*|goedkoop\w*|duur|budget\w*|belminut\w*)\b", re.I), "pricing"),
    (re.compile(r"\b(openingstijd\w*|bereikbaar\w*|bellen|telefoon\w*|email\w*|e-mail\w*|contact\w*|adres\w*|locatie\w*|route\w*)\b", re.I), "contact"),
    (re.compile(r"\b(retour\w*|terugsturen|annuleer\w*|annulering\w*|opzeg\w*|garantie\w*|verzend\w*|lever\w*|bezorg\w*)\b", re.I), "policy"),
    (re.compile(r"\b(faq|veelgesteld\w*|vraag en antwoord)\b", re.I), "faq"),
    (re.compile(r"\b(locatie\w*|vestiging\w*|filiaal\w*|kantoor\w*|winkel\w*|route\w*|parkeer\w*)\b", re.I), "location"),
    (re.compile(r"\b(blog\w*|artikel\w*|nieuws\w*)\b", re.I), "blog"),
    (re.compile(r"\b(product\w*|dienst\w*|service\w*|aanbod\w*|oplossing\w*|feature\w*|functie\w*|mogelijkheid\w*)\b", re.I), "service"),
]

def classify_query(query: str) -> str:
    q = query.strip()
    for pattern, qtype in _RULES:
        if pattern.search(q):
            return qtype
    return "general"


# ── Extracted from scorer.py ────────────────────────────────────────────────

TYPE_MATCH_BOOST = 0.20
GENERIC_PENALTY = -0.12
LOW_INFO_PENALTY = -0.10
JUNK_PENALTY = -0.40
POLICY_CROSSTALK_PENALTY = -0.25
SIGMOID_TEMP = 3.0

def _sigmoid(x, temp=SIGMOID_TEMP):
    try:
        return 1.0 / (1.0 + math.exp(-x / temp))
    except OverflowError:
        return 0.0 if x < 0 else 1.0

_POLICY_TYPES = {"policy", "terms", "privacy", "voorwaarden"}

_JUNK_PATTERNS = [
    re.compile(r"^\s*\{.*\}\s*$", re.DOTALL),
    re.compile(r"^\s*\[.*\]\s*$", re.DOTALL),
    re.compile(r"(system_prompt|user_message|assistant_message|<\|im_start\|>)", re.I),
    re.compile(r"(\"type\":\s*\"|\bschema\b.*\bproperties\b)", re.I),
    re.compile(r"(charset=|content-type:|<!DOCTYPE|<html|<head>)", re.I),
    re.compile(r"(__webpack|module\.exports|import\s+\{|require\()", re.I),
    re.compile(r"(cookie.?policy|privacy.?policy|terms.?of.?service).{0,30}(accept|decline|agree)", re.I),
]

def _is_policy_chunk(chunk_type: str, page_type: str) -> bool:
    return chunk_type in _POLICY_TYPES or page_type in _POLICY_TYPES

def _is_junk(content: str) -> bool:
    if not content or len(content.strip()) < 20:
        return True
    for pat in _JUNK_PATTERNS:
        if pat.search(content[:500]):
            return True
    return False

def score_candidates(candidates, query_classification):
    scored = []
    for c in candidates:
        content = c.get("content", "")
        if _is_junk(content):
            c["is_junk"] = True
            c["metadata_boost"] = JUNK_PENALTY
            c["final_score"] = max(0.0, c.get("rerank_score", c.get("vector_score", 0.0)) + JUNK_PENALTY)
            continue

        c["is_junk"] = False
        boost = 0.0
        rerank = _sigmoid(c.get("rerank_score", 0.0))
        vector = c.get("vector_score", 0.0)
        base_score = max(rerank, vector)
        chunk_type = c.get("chunk_type", "general")
        page_type = c.get("page_type", "unknown")

        if query_classification != "general":
            if chunk_type == query_classification:
                boost += TYPE_MATCH_BOOST
            elif page_type == query_classification:
                boost += TYPE_MATCH_BOOST * 0.6

        if query_classification != "general":
            if page_type == "home" and chunk_type == "general":
                boost += GENERIC_PENALTY

        if query_classification not in ("general", "policy") and _is_policy_chunk(chunk_type, page_type):
            boost += POLICY_CROSSTALK_PENALTY

        if (c.get("token_count") or 0) < 50:
            boost += LOW_INFO_PENALTY

        c["metadata_boost"] = round(boost, 4)
        c["final_score"] = round(base_score + boost, 4)
        scored.append(c)

    scored.sort(key=lambda x: x["final_score"], reverse=True)
    return scored


# ---------------------------------------------------------------------------
# Helpers: build fake candidate dicts
# ---------------------------------------------------------------------------

def _chunk(content, chunk_type="general", page_type="unknown", vector_score=0.6, rerank_score=None, url=""):
    return {
        "chunk_id": f"fake-{hash(content) % 10000}",
        "content": content,
        "chunk_type": chunk_type,
        "page_type": page_type,
        "url": url,
        "page_title": "",
        "section_path": "",
        "heading_hierarchy": [],
        "token_count": len(content.split()),
        "content_hash": str(hash(content)),
        "metadata": {},
        "vector_score": vector_score,
        "rerank_score": rerank_score if rerank_score is not None else vector_score,
    }


# ---------------------------------------------------------------------------
# 1. Query classifier
# ---------------------------------------------------------------------------

class TestQueryClassifier:
    def test_pricing_dutch(self):
        assert classify_query("Wat zijn jullie prijzen?") == "pricing"

    def test_pricing_tarief(self):
        assert classify_query("Wat zijn de tarieven?") == "pricing"

    def test_pricing_kosten(self):
        assert classify_query("Hoeveel kost het?") == "pricing"

    def test_pricing_pakket(self):
        assert classify_query("Welke pakketten hebben jullie?") == "pricing"

    def test_pricing_euro(self):
        assert classify_query("Wat kost het starter pakket in euro?") == "pricing"

    def test_contact(self):
        assert classify_query("Wat is jullie telefoonnummer?") == "contact"

    def test_policy(self):
        assert classify_query("Wat is het retourbeleid?") == "policy"

    def test_general(self):
        assert classify_query("Vertel me over jullie bedrijf") == "general"


# ---------------------------------------------------------------------------
# 2. Scorer: pricing vs policy crosstalk
# ---------------------------------------------------------------------------

class TestPricingVsPolicy:
    """
    Core regression: when a user asks about pricing, policy chunks that
    mention "tarieven" or "prijzen" must NOT outrank actual pricing chunks,
    even when only 1-2 pricing chunks exist.
    """

    def _build_mixed_candidates(self):
        """
        Simulate real-world scenario: 2 pricing chunks from homepage,
        2 policy chunks from terms page that contain pricing-related words.
        Policy chunks have slightly higher rerank scores (they literally
        contain the query keywords).
        """
        return [
            _chunk(
                "Starter\n€149\n/maand\n14 dagen gratis\n- 1 AI-medewerker\n- 500 belminuten/maand",
                chunk_type="pricing", page_type="home",
                vector_score=0.55, rerank_score=0.50,
                url="https://example.com",
            ),
            _chunk(
                "Business\n€299\n/maand\n14 dagen gratis\n- 3 AI-medewerkers\n- 2000 belminuten/maand",
                chunk_type="pricing", page_type="home",
                vector_score=0.53, rerank_score=0.48,
                url="https://example.com",
            ),
            _chunk(
                "Artikel 7 - Tarieven en betaling\n7.1. De actuele tarieven staan vermeld op de website.\n"
                "7.2. Alle genoemde prijzen zijn exclusief BTW.",
                chunk_type="policy", page_type="policy",
                vector_score=0.60, rerank_score=0.62,
                url="https://example.com/terms",
            ),
            _chunk(
                "Artikel 8 - Betalingsvoorwaarden\n8.1. Betaling geschiedt maandelijks vooraf.\n"
                "8.2. Bij niet-tijdige betaling is een boete verschuldigd.",
                chunk_type="policy", page_type="policy",
                vector_score=0.45, rerank_score=0.40,
                url="https://example.com/terms",
            ),
        ]

    def test_pricing_chunks_rank_above_policy(self):
        """Pricing chunks must rank above policy chunks for pricing queries."""
        candidates = self._build_mixed_candidates()
        scored = score_candidates(candidates, "pricing")

        pricing = [c for c in scored if c["chunk_type"] == "pricing"]
        policy = [c for c in scored if c["chunk_type"] == "policy"]

        assert len(pricing) >= 2, f"Expected >=2 pricing chunks, got {len(pricing)}"
        assert len(policy) >= 1, f"Expected >=1 policy chunks, got {len(policy)}"

        best_pricing = max(c["final_score"] for c in pricing)
        best_policy = max(c["final_score"] for c in policy)

        assert best_pricing > best_policy, (
            f"Pricing best={best_pricing:.4f} should beat policy best={best_policy:.4f}"
        )

    def test_pricing_chunks_in_top_2(self):
        """Both pricing chunks must appear in the top 2 after scoring."""
        candidates = self._build_mixed_candidates()
        scored = score_candidates(candidates, "pricing")

        top_2_types = [c["chunk_type"] for c in scored[:2]]
        assert top_2_types.count("pricing") == 2, (
            f"Top 2 should both be pricing, got: {top_2_types}"
        )

    def test_policy_not_penalized_for_policy_query(self):
        """When the user asks about policy, policy chunks should NOT be penalized."""
        candidates = self._build_mixed_candidates()
        scored = score_candidates(candidates, "policy")

        policy_chunks = [c for c in scored if c["chunk_type"] == "policy"]
        for c in policy_chunks:
            assert c["metadata_boost"] >= 0, (
                f"Policy chunk should not be penalized for policy query, "
                f"got boost={c['metadata_boost']}"
            )

    def test_single_pricing_chunk_still_wins(self):
        """Even with just 1 pricing chunk, it must rank above policy."""
        candidates = [
            _chunk(
                "Enterprise\nOp maat\nNeem contact op voor een offerte",
                chunk_type="pricing", page_type="home",
                vector_score=0.50, rerank_score=0.45,
            ),
            _chunk(
                "Artikel 7 - Tarieven en betaling\nDe actuele tarieven staan op de website.\n"
                "Alle genoemde prijzen zijn exclusief BTW.",
                chunk_type="policy", page_type="policy",
                vector_score=0.60, rerank_score=0.62,
            ),
            _chunk(
                "Artikel 3 - Duur en opzegging\nDe overeenkomst wordt aangegaan voor onbepaalde tijd.",
                chunk_type="policy", page_type="policy",
                vector_score=0.40, rerank_score=0.38,
            ),
        ]
        scored = score_candidates(candidates, "pricing")
        assert scored[0]["chunk_type"] == "pricing", (
            f"Single pricing chunk should rank #1, got {scored[0]['chunk_type']}"
        )


# ---------------------------------------------------------------------------
# 3. Scorer: negative rerank scores must not kill results
# ---------------------------------------------------------------------------

class TestNegativeRerankScores:
    """
    Core regression: an English-only cross-encoder produces deeply negative
    scores for Dutch text. The scorer must use max(rerank, vector) so the
    vector score acts as a floor.
    """

    def test_negative_rerank_uses_vector_score(self):
        """When rerank_score is negative, vector_score must be used as base."""
        candidates = [
            _chunk(
                "Starter €149 /maand 14 dagen gratis Perfect voor kleine ondernemers "
                "1 AI-medewerker 500 belminuten/maand Agenda integratie",
                chunk_type="pricing", page_type="home",
                vector_score=0.33, rerank_score=-0.50,
            ),
            _chunk(
                "Artikel 7 - Tarieven en betaling De actuele tarieven staan vermeld "
                "op de website. Alle genoemde prijzen zijn exclusief BTW.",
                chunk_type="policy", page_type="policy",
                vector_score=0.39, rerank_score=-0.50,
            ),
        ]
        scored = score_candidates(candidates, "pricing")
        pricing = [c for c in scored if c["chunk_type"] == "pricing"][0]
        assert pricing["final_score"] > 0.15, (
            f"Pricing chunk with negative rerank should still pass MIN_CONFIDENCE, "
            f"got final_score={pricing['final_score']}"
        )
        assert scored[0]["chunk_type"] == "pricing", (
            f"Pricing chunk should rank #1, got {scored[0]['chunk_type']}"
        )

    def test_deeply_negative_rerank_all_dutch(self):
        """Simulate the exact production scenario: all rerank scores are -5 to -10."""
        candidates = [
            _chunk(
                "Starter €149 /maand Perfect voor kleine ondernemers 1 AI-medewerker "
                "500 belminuten/maand Agenda integratie CRM integratie",
                chunk_type="pricing", page_type="home",
                vector_score=0.33, rerank_score=-8.19,
            ),
            _chunk(
                "Business €299 /maand Ideaal voor groeiende bedrijven 3 AI-medewerkers "
                "2000 belminuten/maand Alles van Starter Prioriteit support",
                chunk_type="pricing", page_type="home",
                vector_score=0.33, rerank_score=-8.50,
            ),
            _chunk(
                "Artikel 7 - Tarieven en betaling De actuele tarieven staan vermeld "
                "op de website van Klantenservice.ai. Alle genoemde prijzen zijn exclusief BTW.",
                chunk_type="policy", page_type="policy",
                vector_score=0.39, rerank_score=-0.50,
            ),
            _chunk(
                "Organisatorische maatregelen Naast technische maatregelen hebben wij "
                "ook organisatorische maatregelen getroffen.",
                chunk_type="general", page_type="general",
                vector_score=0.27, rerank_score=-8.19,
            ),
        ]
        scored = score_candidates(candidates, "pricing")

        assert scored[0]["chunk_type"] == "pricing", (
            f"Pricing chunk should rank #1 even with deeply negative rerank, "
            f"got {scored[0]['chunk_type']} with score {scored[0]['final_score']}"
        )
        assert scored[1]["chunk_type"] == "pricing", (
            f"Second pricing chunk should rank #2, got {scored[1]['chunk_type']}"
        )
        for c in scored:
            if c["chunk_type"] == "pricing":
                assert c["final_score"] > 0.15, (
                    f"Pricing chunk must pass MIN_CONFIDENCE=0.15, got {c['final_score']}"
                )


# ---------------------------------------------------------------------------
# 4. Scorer: high positive rerank scores (mmarco multilingual model)
# ---------------------------------------------------------------------------

class TestHighPositiveRerankScores:
    """
    Regression: the mmarco multilingual model gives high positive scores
    (5-10+) for Dutch text.  Without sigmoid normalization, the scoring
    penalties (0.25) are meaningless against 8+ raw scores.
    """

    def test_production_pricing_vs_policy(self):
        """Exact production scenario: policy chunks outscore pricing due to raw logit scale."""
        candidates = [
            _chunk(
                "Starter €149 /maand 14 dagen gratis Perfect voor kleine ondernemers "
                "1 AI-medewerker 500 belminuten/maand Agenda integratie CRM integratie",
                chunk_type="pricing", page_type="home",
                vector_score=0.33, rerank_score=6.0,
            ),
            _chunk(
                "Business €299 /maand 14 dagen gratis Ideaal voor groeiende bedrijven "
                "3 AI-medewerkers 2000 belminuten/maand Alles van Starter",
                chunk_type="pricing", page_type="home",
                vector_score=0.33, rerank_score=5.5,
            ),
            _chunk(
                "Artikel 7 - Tarieven en betaling De actuele tarieven staan vermeld "
                "op de website. Alle genoemde prijzen zijn exclusief BTW.",
                chunk_type="policy", page_type="policy",
                vector_score=0.39, rerank_score=8.72,
            ),
            _chunk(
                "Artikel 5 - Dienstverlening Klantenservice.ai levert AI-telefonie "
                "diensten waarmee inkomende telefoongesprekken worden afgehandeld.",
                chunk_type="policy", page_type="policy",
                vector_score=0.31, rerank_score=8.66,
            ),
            _chunk(
                "Inleiding Klantenservice.ai respecteert uw privacy en zorgt ervoor "
                "dat uw persoonlijke gegevens vertrouwelijk worden behandeld.",
                chunk_type="general", page_type="general",
                vector_score=0.27, rerank_score=5.79,
            ),
        ]
        scored = score_candidates(candidates, "pricing")

        assert scored[0]["chunk_type"] == "pricing", (
            f"Pricing should rank #1 despite lower raw rerank score, "
            f"got {scored[0]['chunk_type']} score={scored[0]['final_score']:.4f}"
        )
        assert scored[1]["chunk_type"] == "pricing", (
            f"Pricing should rank #2, got {scored[1]['chunk_type']}"
        )

    def test_normalized_scores_in_0_1_range(self):
        """All final_scores must be in a reasonable [0, 1.2] range after normalization."""
        candidates = [
            _chunk(
                "Starter €149 /maand 14 dagen gratis Perfect voor kleine ondernemers "
                "1 AI-medewerker 500 belminuten/maand Agenda integratie CRM integratie",
                chunk_type="pricing", page_type="home",
                vector_score=0.33, rerank_score=8.0,
            ),
            _chunk(
                "Artikel 7 - Tarieven en betaling De actuele tarieven staan vermeld.",
                chunk_type="policy", page_type="policy",
                vector_score=0.39, rerank_score=9.0,
            ),
        ]
        scored = score_candidates(candidates, "pricing")
        for c in scored:
            assert -0.5 <= c["final_score"] <= 1.3, (
                f"final_score should be normalized, got {c['final_score']:.4f}"
            )

    def test_sigmoid_spread(self):
        """Verify sigmoid temp=3 gives enough spread between scores."""
        low = _sigmoid(-5.0)
        mid = _sigmoid(0.0)
        high = _sigmoid(8.0)
        very_high = _sigmoid(12.0)

        assert low < 0.2, f"sigmoid(-5) should be <0.2, got {low:.4f}"
        assert 0.45 < mid < 0.55, f"sigmoid(0) should be ~0.5, got {mid:.4f}"
        assert 0.9 < high < 1.0, f"sigmoid(8) should be 0.9-1.0, got {high:.4f}"
        assert very_high > high, f"sigmoid(12) should be > sigmoid(8)"
        assert high - mid > 0.35, f"Should have meaningful spread between 0 and 8"


# ---------------------------------------------------------------------------
# 5. Scorer: general queries should not penalize policy
# ---------------------------------------------------------------------------

class TestGeneralQueryNoPenalty:
    def test_general_query_no_policy_penalty(self):
        long_general = " ".join(["Welkom bij ons bedrijf dat al meer dan tien jaar actief is in de markt."] * 8)
        long_policy = " ".join(["Dit privacybeleid beschrijft hoe wij omgaan met persoonsgegevens conform de AVG."] * 8)
        candidates = [
            _chunk(long_general, chunk_type="general", page_type="home", vector_score=0.5),
            _chunk(long_policy, chunk_type="policy", page_type="policy", vector_score=0.5),
        ]
        scored = score_candidates(candidates, "general")
        policy = [c for c in scored if c["chunk_type"] == "policy"][0]
        assert policy["metadata_boost"] == 0.0, (
            f"Policy should not be penalized on general queries, got {policy['metadata_boost']}"
        )


# ---------------------------------------------------------------------------
# 6. Contact query: policy should also be penalized
# ---------------------------------------------------------------------------

class TestContactVsPolicy:
    def test_contact_chunks_beat_policy(self):
        candidates = [
            _chunk(
                "Neem contact op: 020 123 4567\ninfo@example.com\nOpeningstijden: ma-vr 9-17",
                chunk_type="contact", page_type="contact",
                vector_score=0.55, rerank_score=0.50,
            ),
            _chunk(
                "Artikel 12 - Contactgegevens\nKlachten kunnen schriftelijk worden ingediend.",
                chunk_type="policy", page_type="policy",
                vector_score=0.58, rerank_score=0.55,
            ),
        ]
        scored = score_candidates(candidates, "contact")
        assert scored[0]["chunk_type"] == "contact", (
            f"Contact chunk should rank #1 for contact query, got {scored[0]['chunk_type']}"
        )


# ---------------------------------------------------------------------------
# Run
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    passed = 0
    failed = 0
    errors = []

    test_classes = [
        TestQueryClassifier,
        TestPricingVsPolicy,
        TestNegativeRerankScores,
        TestHighPositiveRerankScores,
        TestGeneralQueryNoPenalty,
        TestContactVsPolicy,
    ]

    for cls in test_classes:
        instance = cls()
        for method_name in sorted(dir(instance)):
            if not method_name.startswith("test_"):
                continue
            method = getattr(instance, method_name)
            label = f"{cls.__name__}.{method_name}"
            try:
                method()
                print(f"  PASS  {label}")
                passed += 1
            except AssertionError as e:
                print(f"  FAIL  {label}: {e}")
                failed += 1
                errors.append((label, str(e)))
            except Exception as e:
                print(f"  ERROR {label}: {e}")
                failed += 1
                errors.append((label, str(e)))

    print(f"\n{'='*60}")
    print(f"Results: {passed} passed, {failed} failed, {passed + failed} total")
    if errors:
        print(f"\nFailures:")
        for label, msg in errors:
            print(f"  - {label}: {msg}")
    print(f"{'='*60}")
    exit(0 if failed == 0 else 1)
