"""
klantenservice.ai - Transcript Service

Fetches conversation transcripts from ElevenLabs Conversational AI API
and stores them as CallTranscript records for sentiment analysis.
"""
import logging
import asyncio
from datetime import datetime, timedelta
from typing import Optional, Tuple
from uuid import UUID

import httpx
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.call_log import CallLog, CallTranscript

logger = logging.getLogger(__name__)

ELEVENLABS_API_BASE = "https://api.elevenlabs.io/v1"

# Conversation statuses that mean "transcript not ready yet"
_PENDING_STATUSES = frozenset({"initiated", "in-progress", "processing"})

# Retry schedule: (initial_delay_s, max_attempts, backoff_delays)
_INITIAL_WAIT_SECS = 8
_MAX_FETCH_ATTEMPTS = 6
_RETRY_DELAYS = [5, 8, 12, 15, 20]


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
                    "[TRANSCRIPT] Matched conversation_id=%s (time_diff=%ds)",
                    best_match, best_diff,
                )
                return best_match

            logger.warning(
                "[TRANSCRIPT] No close match found (best_diff=%ds, %d candidates)",
                best_diff, len(conversations),
            )
            return None

    except Exception as e:
        logger.warning("[TRANSCRIPT] Conversations list lookup failed: %s", e)
        return None


def _extract_transcript(data: dict) -> list[dict]:
    """
    Extract transcript entries from an ElevenLabs conversation detail response.

    The canonical field is ``data["transcript"]``, but we also check alternative
    nesting locations in case the API structure changes.
    """
    # Primary: top-level "transcript"
    transcript = data.get("transcript")
    if isinstance(transcript, list) and transcript:
        return transcript

    # Alternative 1: nested under "conversation" → "transcript"
    conv_obj = data.get("conversation")
    if isinstance(conv_obj, dict):
        nested = conv_obj.get("transcript")
        if isinstance(nested, list) and nested:
            logger.info("[TRANSCRIPT] Found transcript under 'conversation.transcript'")
            return nested

    # Alternative 2: "messages" key (older API versions / alternate format)
    messages = data.get("messages")
    if isinstance(messages, list) and messages:
        logger.info("[TRANSCRIPT] Found transcript under 'messages' key")
        return messages

    # Alternative 3: nested under "analysis" → "transcript"
    analysis = data.get("analysis")
    if isinstance(analysis, dict):
        at = analysis.get("transcript")
        if isinstance(at, list) and at:
            logger.info("[TRANSCRIPT] Found transcript under 'analysis.transcript'")
            return at

    return []


async def fetch_elevenlabs_transcript(
    conversation_id: str,
) -> Tuple[Optional[list[dict]], str]:
    """
    Fetch transcript from ElevenLabs conversation detail endpoint.

    Returns (transcript_entries, final_status) where final_status is
    the last observed ``status`` field (e.g. "done", "processing", "failed").

    The function is **status-aware**: if the conversation is still
    ``processing`` and the transcript is empty, it retries with backoff
    instead of returning immediately.
    """
    url = f"{ELEVENLABS_API_BASE}/convai/conversations/{conversation_id}"
    headers = {"xi-api-key": settings.ELEVENLABS_API_KEY}
    last_status = "unknown"

    for attempt in range(_MAX_FETCH_ATTEMPTS):
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.get(url, headers=headers)

                if resp.status_code == 404:
                    logger.warning(
                        "[TRANSCRIPT] Conversation %s not found (attempt %d/%d)",
                        conversation_id, attempt + 1, _MAX_FETCH_ATTEMPTS,
                    )
                    if attempt < _MAX_FETCH_ATTEMPTS - 1:
                        delay = _RETRY_DELAYS[min(attempt, len(_RETRY_DELAYS) - 1)]
                        await asyncio.sleep(delay)
                        continue
                    return None, "not_found"

                resp.raise_for_status()
                data = resp.json()

                last_status = data.get("status", "unknown")
                transcript = _extract_transcript(data)

                top_keys = sorted(data.keys())
                logger.info(
                    "[TRANSCRIPT] conversation=%s attempt=%d/%d status=%s "
                    "transcript_len=%d top_keys=%s",
                    conversation_id, attempt + 1, _MAX_FETCH_ATTEMPTS,
                    last_status, len(transcript), top_keys,
                )

                if transcript:
                    return transcript, last_status

                # Transcript empty — decide whether to retry
                if last_status in _PENDING_STATUSES:
                    if attempt < _MAX_FETCH_ATTEMPTS - 1:
                        delay = _RETRY_DELAYS[min(attempt, len(_RETRY_DELAYS) - 1)]
                        logger.info(
                            "[TRANSCRIPT] Status '%s' — transcript not ready, "
                            "retrying in %ds (attempt %d/%d)",
                            last_status, delay, attempt + 1, _MAX_FETCH_ATTEMPTS,
                        )
                        await asyncio.sleep(delay)
                        continue
                    else:
                        logger.warning(
                            "[TRANSCRIPT] Status still '%s' after %d attempts — giving up",
                            last_status, _MAX_FETCH_ATTEMPTS,
                        )
                        return None, last_status

                if last_status == "failed":
                    logger.warning(
                        "[TRANSCRIPT] Conversation %s has status 'failed'",
                        conversation_id,
                    )
                    return None, "failed"

                # status == "done" but transcript empty
                logger.warning(
                    "[TRANSCRIPT] Conversation %s status='%s' but transcript empty",
                    conversation_id, last_status,
                )
                return [], last_status

        except Exception as e:
            logger.warning(
                "[TRANSCRIPT] Fetch error for %s (attempt %d/%d): %s",
                conversation_id, attempt + 1, _MAX_FETCH_ATTEMPTS, e,
            )
            if attempt < _MAX_FETCH_ATTEMPTS - 1:
                delay = _RETRY_DELAYS[min(attempt, len(_RETRY_DELAYS) - 1)]
                await asyncio.sleep(delay)

    return None, last_status


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
            "[TRANSCRIPT] Skipping save — %d records already exist for call_log %s",
            existing, call_log_id,
        )
        return 0

    base_time = call_started_at or datetime.utcnow()
    saved = 0

    for entry in transcript:
        role = entry.get("role", "")
        message = (entry.get("message") or entry.get("text") or "").strip()
        raw_time = entry.get("time_in_call_secs") or entry.get("timestamp") or 0
        time_secs = raw_time if isinstance(raw_time, (int, float)) else 0

        if not message:
            continue

        speaker = "caller" if role in ("user", "caller", "human") else "ai"
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
        logger.info(
            "[TRANSCRIPT] Saved %d transcript records for call_log %s",
            saved, call_log_id,
        )

    return saved


def build_transcript_text(transcript: list[dict]) -> str:
    """Build a single text string from ElevenLabs transcript entries for sentiment analysis."""
    lines = []
    for entry in transcript:
        role = entry.get("role", "")
        message = (entry.get("message") or entry.get("text") or "").strip()
        if not message:
            continue
        label = "Klant" if role in ("user", "caller", "human") else "AI"
        lines.append(f"{label}: {message}")
    return "\n".join(lines)


async def fetch_and_process_transcript(
    db: Session,
    call_log: CallLog,
) -> Optional[str]:
    """
    Full pipeline: fetch transcript from ElevenLabs, save records, run sentiment.
    Returns the sentiment result or None.

    ElevenLabs needs time after a call ends to finalize the transcript (the
    conversation transitions through ``processing`` → ``done``). We wait
    before the first attempt and let ``fetch_elevenlabs_transcript`` handle
    status-aware retries with backoff.
    """
    conversation_id = call_log.elevenlabs_conversation_id
    if not conversation_id:
        logger.info(
            "[TRANSCRIPT] No conversation_id for call_log %s — "
            "trying conversations list fallback",
            call_log.id,
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
            "[TRANSCRIPT] Could not find conversation_id for call_log %s",
            call_log.id,
        )
        return None

    if not settings.ELEVENLABS_API_KEY:
        logger.warning("[TRANSCRIPT] ELEVENLABS_API_KEY not set — skipping")
        return None

    await asyncio.sleep(_INITIAL_WAIT_SECS)

    transcript, final_status = await fetch_elevenlabs_transcript(conversation_id)

    logger.info(
        "[TRANSCRIPT] Pipeline result: conversation=%s final_status=%s messages=%d",
        conversation_id, final_status, len(transcript) if transcript else 0,
    )

    if not transcript:
        logger.warning(
            "[TRANSCRIPT] No transcript data for conversation %s "
            "(final_status=%s)",
            conversation_id, final_status,
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
                "[TRANSCRIPT] Sentiment for call_log %s: %s",
                call_log.id, sentiment,
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

            # Run call quality evaluation (non-blocking)
            try:
                from app.services.langsmith_service import evaluate_call
                await evaluate_call(db, call_log)
            except Exception:
                logger.warning("[TRANSCRIPT] Call evaluation failed (non-blocking)", exc_info=True)

            return sentiment
    except Exception as e:
        logger.warning("[TRANSCRIPT] Sentiment analysis failed: %s", e)

    return None
