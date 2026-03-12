"""
klantenservice.ai - Website Knowledge Endpoints (new indexing pipeline)
"""
import asyncio
from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from uuid import UUID, uuid4

from app.core.database import get_db
from app.core.config import settings
from app.models.user import User
from app.models.company import Company
from app.models.ai_worker import AIWorker
from app.services.indexing.models import IdxSite, IdxChunk, IdxPage, SiteStatus
from app.services.indexing.schemas import (
    SiteCreate, SiteUpdate, SiteResponse,
    ChunkResponse, TestQuestionRequest, TestQuestionResponse,
    IndexTriggerResponse,
)
from app.services.indexing.orchestrator import IndexingOrchestrator
from app.services.retrieval import RetrievalService
from app.api.deps import get_current_user, get_current_company, require_admin

router = APIRouter()


# ---------------------------------------------------------------------------
# Background indexing helper
# ---------------------------------------------------------------------------

async def _run_indexing_background(site_id: str, db_url: str):
    """Run indexing in background with a fresh DB session."""
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from app.services.notification_service import create_notification
    from app.models.notification import NotificationType

    engine = create_engine(db_url)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = SessionLocal()

    try:
        orchestrator = IndexingOrchestrator(db)
        success = await orchestrator.index_site(site_id)

        site = db.query(IdxSite).filter(IdxSite.id == site_id).first()
        if site:
            if success:
                stats = site.stats or {}
                create_notification(
                    db=db,
                    company_id=str(site.company_id),
                    type=NotificationType.WEBSITE_INDEXED,
                    title=f"Website geïndexeerd: {site.base_url}",
                    message=f"{stats.get('pages_crawled', 0)} pagina's, {stats.get('chunks_created', 0)} chunks.",
                    url="/dashboard/knowledge",
                )
            else:
                create_notification(
                    db=db,
                    company_id=str(site.company_id),
                    type=NotificationType.WEBSITE_FAILED,
                    title=f"Indexering mislukt: {site.base_url}",
                    message=site.last_error or "Onbekende fout.",
                    url="/dashboard/knowledge",
                )
    finally:
        db.close()


# ---------------------------------------------------------------------------
# CRUD endpoints
# ---------------------------------------------------------------------------

@router.get("", response_model=List[SiteResponse])
async def list_websites(
    current_user: User = Depends(get_current_user),
    company: Company = Depends(get_current_company),
    db: Session = Depends(get_db),
):
    sites = db.query(IdxSite).filter(IdxSite.company_id == company.id).all()
    return sites


@router.post("", response_model=SiteResponse, status_code=status.HTTP_201_CREATED)
async def create_website(
    data: SiteCreate,
    current_user: User = Depends(require_admin),
    company: Company = Depends(get_current_company),
    db: Session = Depends(get_db),
):
    if data.ai_worker_id:
        worker = db.query(AIWorker).filter(
            AIWorker.id == data.ai_worker_id, AIWorker.company_id == company.id,
        ).first()
        if not worker:
            raise HTTPException(status_code=400, detail="AI-medewerker niet gevonden.")

        existing_link = db.query(IdxSite).filter(
            IdxSite.ai_worker_id == data.ai_worker_id, IdxSite.company_id == company.id,
        ).first()
        if existing_link:
            raise HTTPException(
                status_code=400,
                detail=f"AI-medewerker '{worker.name}' heeft al een website ({existing_link.base_url}).",
            )

    existing = db.query(IdxSite).filter(
        IdxSite.company_id == company.id, IdxSite.base_url == str(data.base_url),
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail="Deze website is al toegevoegd.")

    site = IdxSite(
        id=uuid4(),
        company_id=company.id,
        ai_worker_id=data.ai_worker_id,
        base_url=str(data.base_url),
        sitemap_url=str(data.sitemap_url) if data.sitemap_url else None,
        crawl_config=data.crawl_config.model_dump() if data.crawl_config else {},
    )
    db.add(site)
    db.commit()
    db.refresh(site)

    asyncio.create_task(_run_indexing_background(str(site.id), settings.DATABASE_URL))
    return site


@router.get("/{website_id}", response_model=SiteResponse)
async def get_website(
    website_id: UUID,
    current_user: User = Depends(get_current_user),
    company: Company = Depends(get_current_company),
    db: Session = Depends(get_db),
):
    site = db.query(IdxSite).filter(IdxSite.id == website_id, IdxSite.company_id == company.id).first()
    if not site:
        raise HTTPException(status_code=404, detail="Website niet gevonden")
    return site


@router.patch("/{website_id}", response_model=SiteResponse)
async def update_website(
    website_id: UUID,
    data: SiteUpdate,
    current_user: User = Depends(require_admin),
    company: Company = Depends(get_current_company),
    db: Session = Depends(get_db),
):
    site = db.query(IdxSite).filter(IdxSite.id == website_id, IdxSite.company_id == company.id).first()
    if not site:
        raise HTTPException(status_code=404, detail="Website niet gevonden")

    update = data.model_dump(exclude_unset=True)
    for field, value in update.items():
        if field == "crawl_config" and value and hasattr(value, "model_dump"):
            value = value.model_dump()
        if field in ("sitemap_url", "base_url") and value:
            value = str(value)
        setattr(site, field, value)

    db.commit()
    db.refresh(site)
    return site


@router.delete("/{website_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_website(
    website_id: UUID,
    current_user: User = Depends(require_admin),
    company: Company = Depends(get_current_company),
    db: Session = Depends(get_db),
):
    site = db.query(IdxSite).filter(IdxSite.id == website_id, IdxSite.company_id == company.id).first()
    if not site:
        raise HTTPException(status_code=404, detail="Website niet gevonden")
    db.delete(site)
    db.commit()


# ---------------------------------------------------------------------------
# Indexing endpoints
# ---------------------------------------------------------------------------

@router.post("/{website_id}/reindex", response_model=IndexTriggerResponse)
async def reindex_website(
    website_id: UUID,
    current_user: User = Depends(require_admin),
    company: Company = Depends(get_current_company),
    db: Session = Depends(get_db),
):
    site = db.query(IdxSite).filter(IdxSite.id == website_id, IdxSite.company_id == company.id).first()
    if not site:
        raise HTTPException(status_code=404, detail="Website niet gevonden")

    if site.status in (SiteStatus.crawling, SiteStatus.processing):
        raise HTTPException(status_code=400, detail="Website wordt momenteel al geïndexeerd")

    site.status = SiteStatus.pending
    db.commit()

    asyncio.create_task(_run_indexing_background(str(site.id), settings.DATABASE_URL))

    return IndexTriggerResponse(message="Indexering gestart", status=site.status, estimated_time_minutes=5)


@router.post("/{website_id}/test", response_model=TestQuestionResponse)
async def test_question(
    website_id: UUID,
    request: TestQuestionRequest,
    current_user: User = Depends(get_current_user),
    company: Company = Depends(get_current_company),
    db: Session = Depends(get_db),
):
    site = db.query(IdxSite).filter(IdxSite.id == website_id, IdxSite.company_id == company.id).first()
    if not site:
        raise HTTPException(status_code=404, detail="Website niet gevonden")

    if site.status != SiteStatus.ready:
        raise HTTPException(status_code=400, detail="Website is nog niet volledig geïndexeerd")

    retrieval = RetrievalService(db)
    result = await retrieval.search(
        company_id=str(company.id),
        query=request.question,
        limit=5,
        site_id=str(website_id),
    )

    results = result.get("results", [])
    confidence = result.get("confidence", 0.0)

    if not results:
        return TestQuestionResponse(
            question=request.question,
            answer="Geen relevante informatie gevonden.",
            sources=[],
            confidence=0.0,
        )

    sources = [
        {"url": r.get("url", ""), "snippet": r["content"][:200]}
        for r in results
    ]

    return TestQuestionResponse(
        question=request.question,
        answer=results[0]["content"][:500],
        sources=sources,
        confidence=confidence,
    )


# ---------------------------------------------------------------------------
# Chunk inspection endpoint
# ---------------------------------------------------------------------------

@router.get("/{website_id}/chunks", response_model=List[ChunkResponse])
async def list_chunks(
    website_id: UUID,
    limit: int = 50,
    offset: int = 0,
    chunk_type: str = None,
    current_user: User = Depends(get_current_user),
    company: Company = Depends(get_current_company),
    db: Session = Depends(get_db),
):
    site = db.query(IdxSite).filter(IdxSite.id == website_id, IdxSite.company_id == company.id).first()
    if not site:
        raise HTTPException(status_code=404, detail="Website niet gevonden")

    query = db.query(IdxChunk).filter(IdxChunk.site_id == website_id)
    if chunk_type:
        query = query.filter(IdxChunk.chunk_type == chunk_type)

    chunks = query.order_by(IdxChunk.position_on_page).offset(offset).limit(limit).all()
    return chunks
