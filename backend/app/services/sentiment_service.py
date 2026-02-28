"""
klantenservice.ai - Post-call sentiment analysis using OpenAI
"""
import logging
from typing import Optional

from app.core.config import settings

logger = logging.getLogger(__name__)


async def analyze_sentiment(transcript_text: str) -> Optional[str]:
    """
    Analyze the sentiment of a call transcript.
    Returns 'positive', 'neutral', or 'negative'.
    """
    if not transcript_text or not transcript_text.strip():
        return None

    if not settings.OPENAI_API_KEY:
        logger.warning("OPENAI_API_KEY not set — skipping sentiment analysis")
        return None

    try:
        from openai import OpenAI

        client = OpenAI(api_key=settings.OPENAI_API_KEY)

        response = client.chat.completions.create(
            model="gpt-4o-mini",
            temperature=0,
            max_tokens=10,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "Je bent een sentimentanalyse-assistent. "
                        "Analyseer het volgende telefoongesprek en bepaal het sentiment van de BELLER (klant). "
                        "Antwoord met exact één woord: positive, neutral, of negative."
                    ),
                },
                {"role": "user", "content": transcript_text},
            ],
        )

        result = response.choices[0].message.content.strip().lower()
        if result in ("positive", "neutral", "negative"):
            return result

        logger.warning(f"Unexpected sentiment result: {result}")
        return "neutral"

    except Exception as e:
        logger.warning(f"Sentiment analysis failed: {e}")
        return None
