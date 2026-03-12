"""
klantenservice.ai - Transcript Service

Fetches conversation transcripts from ElevenLabs Conversational AI API
and stores them as CallTranscript records for sentiment analysis.
"""
import logging
import asyncio
from datetime import datetime, timedelta
from typing import Optional
from uuid import UUID

import httpx
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.call_log import CallLog, CallTranscript

logger = logging.getLogger(__name__)

ELEVENLABS_API_BASE = "https://api.elevenlabs.io/v1"


async def find_conversation_id(
    call_started_at: datetime,
    call_duration_seconds: int,
) -> Optional[str]:
    """
    Search ElevenLabs conversations list API to find the conversation_id
    for a call that we couldn't extract from the register-call response.
    Matches by agent_id and time range.
    """
    if not settings.ELEVENLABS_API_KEY or not settings.ELEVENLABS_AGENT_ID:
        return None

    start_unix = int(call_started_at.timestamp()) - 60
    headers = {"xi-api-key": settings.ELEVENLABS_API_KEY}
    params = {
        "agent_id": settings.ELEVENLABS_AGENT_ID,
        "call_start_after_unix": start_unix,
        "page_size": 20,
    }

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(
                f"{ELEVENLABS_API_BASE}/convai/conversations",
                headers=headers,
                params=params,
            )
            resp.raise_for_status()
            data = resp.json()
            conversations = data.get("conversations", [])

            if not conversations:
                return None

            call_end_unix = int(call_started_at.timestamp()) + call_duration_seconds

            best_match = None
            best_diff = float("inf")

            for conv in conversations:
                meta = conv.get("metadata", {})
                conv_start = meta.get("start_time_unix_secs", 0)
                conv_duration = meta.get("call_duration_secs", 0)
                conv_end = conv_start + conv_duration

                start_diff = abs(conv_start - int(call_started_at.timestamp()))
                end_diff = abs(conv_end - call_end_unix)
                total_diff = start_diff + end_diff

                if total_diff < best_diff:
                    best_diff = total_diff
                    best_match = conv.get("conversation_id")

            if best_match and best_diff < 120:
                logger.info(
                    f"[TRANSCRIPT] Matched conversation_id={best_match} "
                    f"(time_diff={best_diff}s)"
                )
                return best_match

            logger.warning(
                f"[TRANSCRIPT] No close match found "
                f"(best_diff={best_diff}s, {len(conversations)} candidates)"
            )
            return None

    except Exception as e:
        logger.warning(f"[TRANSCRIPT] Conversations list lookup failed: {e}")
        return None


async def fetch_elevenlabs_transcript(conversation_id: str) -> Optional[list[dict]]:
    """
    Fetch transcript from ElevenLabs API.
    Returns list of {"role": "user"|"ai", "message": str, "time_in_call_secs": float}
    or None on failure.
    """
    url = f"{ELEVENLABS_API_BASE}/convai/conversations/{conversation_id}"
    headers = {"xi-api-key": settings.ELEVENLABS_API_KEY}

    for attempt in range(3):
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.get(url, headers=headers)

                if resp.status_code == 404:
                    logger.warning(
                        f"[TRANSCRIPT] Conversation {conversation_id} not found (attempt {attempt + 1})"
                    )
                    if attempt < 2:
                        await asyncio.sleep(5 * (attempt + 1))
                        continue
                    return None

                resp.raise_for_status()
                data = resp.json()
                transcript = data.get("transcript", [])
                logger.info(
                    f"[TRANSCRIPT] Fetched {len(transcript)} messages "
                    f"for conversation {conversation_id}"
                )
                return transcript

        except Exception as e:
            logger.warning(
                f"[TRANSCRIPT] Fetch failed for {conversation_id} "
                f"(attempt {attempt + 1}): {e}"
            )
            if attempt < 2:
                await asyncio.sleep(3 * (attempt + 1))

    return None


def save_transcript_records(
    db: Session,
    call_log_id: UUID,
    transcript: list[dict],
    call_started_at: Optional[datetime] = None,
) -> int:
    """
    Save ElevenLabs transcript entries as CallTranscript rows.
    Returns number of records saved.
    """
    existing = db.query(CallTranscript).filter(
        CallTranscript.call_log_id == call_log_id
    ).count()
    if existing > 0:
        logger.info(
            f"[TRANSCRIPT] Skipping save — {existing} records already exist "
            f"for call_log {call_log_id}"
        )
        return 0

    base_time = call_started_at or datetime.utcnow()
    saved = 0

    for entry in transcript:
        role = entry.get("role", "")
        message = (entry.get("message") or "").strip()
        time_secs = entry.get("time_in_call_secs", 0)

        if not message:
            continue

        speaker = "caller" if role == "user" else "ai"
        ts = base_time + timedelta(seconds=time_secs)

        record = CallTranscript(
            call_log_id=call_log_id,
            speaker=speaker,
            message=message,
            timestamp=ts,
        )
        db.add(record)
        saved += 1

    if saved:
        db.commit()
        logger.info(f"[TRANSCRIPT] Saved {saved} transcript records for call_log {call_log_id}")

    return saved


def build_transcript_text(transcript: list[dict]) -> str:
    """Build a single text string from ElevenLabs transcript entries for sentiment analysis."""
    lines = []
    for entry in transcript:
        role = entry.get("role", "")
        message = (entry.get("message") or "").strip()
        if not message:
            continue
        label = "Klant" if role == "user" else "AI"
        lines.append(f"{label}: {message}")
    return "\n".join(lines)


async def fetch_and_process_transcript(
    db: Session,
    call_log: CallLog,
) -> Optional[str]:
    """
    Full pipeline: fetch transcript from ElevenLabs, save records, run sentiment.
    Returns the sentiment result or None.

    ElevenLabs needs a few seconds after the call ends to finalize the transcript,
    so we wait briefly before the first attempt.
    """
    conversation_id = call_log.elevenlabs_conversation_id
    if not conversation_id:
        logger.info(
            f"[TRANSCRIPT] No conversation_id for call_log {call_log.id} — "
            f"trying conversations list fallback"
        )
        if call_log.started_at and call_log.duration_seconds:
            conversation_id = await find_conversation_id(
                call_log.started_at,
                call_log.duration_seconds,
            )
            if conversation_id:
                call_log.elevenlabs_conversation_id = conversation_id
                db.commit()

    if not conversation_id:
        logger.warning(
            f"[TRANSCRIPT] Could not find conversation_id for call_log {call_log.id}"
        )
        return None

    if not settings.ELEVENLABS_API_KEY:
        logger.warning("[TRANSCRIPT] ELEVENLABS_API_KEY not set — skipping")
        return None

    await asyncio.sleep(5)

    transcript = await fetch_elevenlabs_transcript(conversation_id)
    if not transcript:
        logger.warning(
            f"[TRANSCRIPT] No transcript data for conversation {conversation_id}"
        )
        return None

    save_transcript_records(db, call_log.id, transcript, call_log.started_at)

    transcript_text = build_transcript_text(transcript)
    if not transcript_text:
        return None

    try:
        from app.services.sentiment_service import analyze_sentiment
        sentiment = await analyze_sentiment(transcript_text)
        if sentiment:
            call_log.sentiment = sentiment
            db.commit()
            logger.info(
                f"[TRANSCRIPT] Sentiment for call_log {call_log.id}: {sentiment}"
            )

            if sentiment == "negative":
                try:
                    from app.services.notification_service import create_notification
                    from app.models.notification import NotificationType
                    caller = call_log.caller_number or "Onbekend nummer"
                    create_notification(
                        db=db,
                        company_id=str(call_log.company_id),
                        type=NotificationType.CALL_ERROR,
                        title="Ontevreden klant",
                        message=f"Gesprek met {caller} is als negatief beoordeeld.",
                        url="/dashboard/calls",
                    )
                except Exception:
                    logger.warning(
                        "Failed to create negative-sentiment notification",
                        exc_info=True,
                    )

            return sentiment
    except Exception as e:
        logger.warning(f"[TRANSCRIPT] Sentiment analysis failed: {e}")

    return None
