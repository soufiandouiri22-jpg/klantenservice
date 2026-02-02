"""
klantenservice.ai - Website Knowledge Endpoints
"""
import asyncio
from datetime import datetime
from typing import List
from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from sqlalchemy.orm import Session
from uuid import UUID, uuid4
import secrets

from app.core.database import get_db
from app.models.user import User
from app.models.company import Company
from app.models.website_knowledge import WebsiteKnowledge, KnowledgeChunk, IndexStatus
from app.schemas.website import (
    WebsiteKnowledgeCreate,
    WebsiteKnowledgeUpdate,
    WebsiteKnowledgeResponse,
    KnowledgeChunkResponse,
    TestQuestionRequest,
    TestQuestionResponse,
    IndexTriggerResponse,
    WebhookSetupResponse,
)
from app.api.deps import get_current_user, get_current_company, require_admin
from app.services.website_indexer import WebsiteIndexer, VectorStore

router = APIRouter()


@router.get("", response_model=List[WebsiteKnowledgeResponse])
async def list_websites(
    current_user: User = Depends(get_current_user),
    company: Company = Depends(get_current_company),
    db: Session = Depends(get_db)
):
    """
    List all website knowledge sources.
    """
    websites = db.query(WebsiteKnowledge).filter(
        WebsiteKnowledge.company_id == company.id
    ).all()
    return websites


async def run_indexing(website_id: str, db_url: str):
    """Background task to run website indexing."""
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    
    engine = create_engine(db_url)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = SessionLocal()
    
    try:
        indexer = WebsiteIndexer(db)
        await indexer.index_website(website_id)
    finally:
        db.close()


@router.post("", response_model=WebsiteKnowledgeResponse, status_code=status.HTTP_201_CREATED)
async def create_website(
    data: WebsiteKnowledgeCreate,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(require_admin),
    company: Company = Depends(get_current_company),
    db: Session = Depends(get_db)
):
    """
    Add a new website to index.
    """
    from app.core.config import settings
    
    # Check if URL already exists for this company
    existing = db.query(WebsiteKnowledge).filter(
        WebsiteKnowledge.company_id == company.id,
        WebsiteKnowledge.base_url == str(data.base_url)
    ).first()
    
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Deze website is al toegevoegd",
        )
    
    website = WebsiteKnowledge(
        id=uuid4(),
        company_id=company.id,
        base_url=str(data.base_url),
        sitemap_url=str(data.sitemap_url) if data.sitemap_url else None,
        crawl_settings=data.crawl_settings.model_dump() if data.crawl_settings else {},
        status=IndexStatus.pending,
        webhook_secret=secrets.token_urlsafe(32),
        is_active=True,
    )
    
    db.add(website)
    db.commit()
    db.refresh(website)
    
    # Trigger background indexing job
    asyncio.create_task(run_indexing(str(website.id), settings.DATABASE_URL))
    
    return website


@router.get("/{website_id}", response_model=WebsiteKnowledgeResponse)
async def get_website(
    website_id: UUID,
    current_user: User = Depends(get_current_user),
    company: Company = Depends(get_current_company),
    db: Session = Depends(get_db)
):
    """
    Get a specific website knowledge source.
    """
    website = db.query(WebsiteKnowledge).filter(
        WebsiteKnowledge.id == website_id,
        WebsiteKnowledge.company_id == company.id
    ).first()
    
    if not website:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Website niet gevonden",
        )
    
    return website


@router.patch("/{website_id}", response_model=WebsiteKnowledgeResponse)
async def update_website(
    website_id: UUID,
    data: WebsiteKnowledgeUpdate,
    current_user: User = Depends(require_admin),
    company: Company = Depends(get_current_company),
    db: Session = Depends(get_db)
):
    """
    Update website knowledge settings.
    """
    website = db.query(WebsiteKnowledge).filter(
        WebsiteKnowledge.id == website_id,
        WebsiteKnowledge.company_id == company.id
    ).first()
    
    if not website:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Website niet gevonden",
        )
    
    update_data = data.model_dump(exclude_unset=True)
    
    for field, value in update_data.items():
        if field == "crawl_settings" and value:
            value = value.model_dump() if hasattr(value, 'model_dump') else value
        if field in ["sitemap_url", "base_url"] and value:
            value = str(value)
        setattr(website, field, value)
    
    db.commit()
    db.refresh(website)
    
    return website


@router.delete("/{website_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_website(
    website_id: UUID,
    current_user: User = Depends(require_admin),
    company: Company = Depends(get_current_company),
    db: Session = Depends(get_db)
):
    """
    Delete a website knowledge source.
    """
    website = db.query(WebsiteKnowledge).filter(
        WebsiteKnowledge.id == website_id,
        WebsiteKnowledge.company_id == company.id
    ).first()
    
    if not website:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Website niet gevonden",
        )
    
    # Delete from vector store
    try:
        vector_store = VectorStore(str(company.id))
        vector_store.delete_website_chunks(str(website_id))
    except Exception as e:
        print(f"Error deleting from vector store: {e}")
    
    db.delete(website)
    db.commit()


@router.post("/{website_id}/reindex", response_model=IndexTriggerResponse)
async def reindex_website(
    website_id: UUID,
    current_user: User = Depends(require_admin),
    company: Company = Depends(get_current_company),
    db: Session = Depends(get_db)
):
    """
    Trigger re-indexing of website content.
    """
    from app.core.config import settings
    
    website = db.query(WebsiteKnowledge).filter(
        WebsiteKnowledge.id == website_id,
        WebsiteKnowledge.company_id == company.id
    ).first()
    
    if not website:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Website niet gevonden",
        )
    
    if website.status == IndexStatus.indexing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Website wordt momenteel al geïndexeerd",
        )
    
    website.status = IndexStatus.pending
    db.commit()
    
    # Trigger background indexing job
    asyncio.create_task(run_indexing(str(website.id), settings.DATABASE_URL))
    
    return IndexTriggerResponse(
        message="Indexering gestart",
        status=website.status,
        estimated_time_minutes=5,
    )


@router.post("/{website_id}/test", response_model=TestQuestionResponse)
async def test_question(
    website_id: UUID,
    request: TestQuestionRequest,
    current_user: User = Depends(get_current_user),
    company: Company = Depends(get_current_company),
    db: Session = Depends(get_db)
):
    """
    Test a question against the knowledge base.
    """
    website = db.query(WebsiteKnowledge).filter(
        WebsiteKnowledge.id == website_id,
        WebsiteKnowledge.company_id == company.id
    ).first()
    
    if not website:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Website niet gevonden",
        )
    
    if website.status != IndexStatus.completed:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Website is nog niet volledig geïndexeerd",
        )
    
    # Search in vector store
    vector_store = VectorStore(str(company.id))
    results = vector_store.search(request.question, str(website_id), limit=5)
    
    if not results:
        return TestQuestionResponse(
            question=request.question,
            answer="Geen relevante informatie gevonden in de geïndexeerde inhoud.",
            sources=[],
            confidence=0.0,
        )
    
    # Build answer from found chunks
    context = "\n\n".join([r['content'] for r in results])
    sources = [
        {
            "url": r['metadata'].get('url', website.base_url),
            "snippet": r['content'][:200] + "..." if len(r['content']) > 200 else r['content'],
        }
        for r in results
    ]
    
    # Calculate confidence based on distance (lower distance = higher confidence)
    avg_distance = sum(r.get('distance', 1.0) for r in results) / len(results)
    confidence = max(0, min(1, 1 - avg_distance))
    
    return TestQuestionResponse(
        question=request.question,
        answer=f"Op basis van de website-inhoud heb ik het volgende gevonden:\n\n{results[0]['content'][:500]}...",
        sources=sources,
        confidence=round(confidence, 2),
    )


@router.get("/{website_id}/chunks", response_model=List[KnowledgeChunkResponse])
async def list_chunks(
    website_id: UUID,
    limit: int = 50,
    offset: int = 0,
    current_user: User = Depends(get_current_user),
    company: Company = Depends(get_current_company),
    db: Session = Depends(get_db)
):
    """
    List indexed content chunks.
    """
    website = db.query(WebsiteKnowledge).filter(
        WebsiteKnowledge.id == website_id,
        WebsiteKnowledge.company_id == company.id
    ).first()
    
    if not website:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Website niet gevonden",
        )
    
    chunks = db.query(KnowledgeChunk).filter(
        KnowledgeChunk.website_id == website_id
    ).offset(offset).limit(limit).all()
    
    return chunks


@router.get("/{website_id}/webhook", response_model=WebhookSetupResponse)
async def get_webhook_info(
    website_id: UUID,
    current_user: User = Depends(require_admin),
    company: Company = Depends(get_current_company),
    db: Session = Depends(get_db)
):
    """
    Get webhook URL for automatic re-indexing triggers.
    """
    website = db.query(WebsiteKnowledge).filter(
        WebsiteKnowledge.id == website_id,
        WebsiteKnowledge.company_id == company.id
    ).first()
    
    if not website:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Website niet gevonden",
        )
    
    return WebhookSetupResponse(
        webhook_url=f"https://api.klantenservice.ai/api/v1/webhooks/website/{website_id}/update",
        webhook_secret=website.webhook_secret,
    )
