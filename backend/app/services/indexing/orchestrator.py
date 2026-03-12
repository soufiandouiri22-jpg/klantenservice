"""
Indexing orchestrator – end-to-end pipeline:
  URL -> crawl -> clean -> classify -> chunk -> embed -> store -> ready

Coordinates all services and writes results to the database.
"""
import logging
from datetime import datetime
from typing import Optional
from uuid import uuid4

from sqlalchemy.orm import Session

from app.core.config import settings
from .models import (
    IdxSite, IdxCrawlJob, IdxPage, IdxChunk, IdxError,
    SiteStatus, CrawlJobStatus,
)
from .crawl import CrawlerService
from .crawl.url_utils import normalize_url
from .cleaning import ContentCleaner
from .chunking import SemanticChunker, classify_page_type, extract_faq_chunks, extract_pricing_chunks, extract_contact_chunks
from .embedding import OpenAIEmbeddingProvider, EmbeddingPipeline

logger = logging.getLogger(__name__)


class IndexingOrchestrator:
    """Run the full indexing pipeline for a site."""

    def __init__(self, db: Session):
        self.db = db
        self._cleaner = ContentCleaner()
        self._chunker = SemanticChunker()

    async def index_site(self, site_id: str) -> bool:
        """Run the complete indexing pipeline for a site."""
        site = self.db.query(IdxSite).filter(IdxSite.id == site_id).first()
        if not site:
            logger.error("Site %s not found", site_id)
            return False

        # Create crawl job
        crawl_job = IdxCrawlJob(
            id=uuid4(),
            site_id=site.id,
            company_id=site.company_id,
            provider=(site.crawl_config or {}).get("provider", "auto"),
            config=site.crawl_config or {},
            started_at=datetime.utcnow(),
        )
        self.db.add(crawl_job)

        site.status = SiteStatus.crawling
        site.last_error = None
        self.db.commit()

        try:
            # --- Phase 1: Crawl ---
            crawl_job.status = CrawlJobStatus.running
            self.db.commit()

            config = site.crawl_config or {}
            crawler = CrawlerService(
                provider=config.get("provider", "auto"),
                max_pages=config.get("max_pages", 100),
                max_depth=config.get("max_depth", 3),
                blocked_paths=config.get("blocked_paths", ["/admin", "/login", "/wp-admin"]),
            )

            crawled_pages = await crawler.crawl_site(site.base_url)
            crawl_job.stats = crawler.get_stats()

            if not crawled_pages:
                raise ValueError("Geen pagina's gevonden om te indexeren")

            logger.info("Crawled %d pages for %s", len(crawled_pages), site.base_url)

            # --- Phase 2: Clean + classify + store pages ---
            site.status = SiteStatus.processing
            self.db.commit()

            # Delete existing pages/chunks for this site (full re-index)
            self.db.query(IdxChunk).filter(IdxChunk.site_id == site.id).delete()
            self.db.query(IdxPage).filter(IdxPage.site_id == site.id).delete()
            self.db.commit()

            all_chunk_dicts = []
            page_map = {}  # page_id -> IdxPage

            for cp in crawled_pages:
                cleaned = self._cleaner.clean(cp.html)
                content_hash = self._cleaner.content_hash(cleaned) if cleaned else None

                page_type = classify_page_type(
                    url=cp.url, title=cp.title, h1=cp.h1,
                    content=cleaned or "",
                )

                page = IdxPage(
                    id=uuid4(),
                    site_id=site.id,
                    crawl_job_id=crawl_job.id,
                    company_id=site.company_id,
                    url=cp.url,
                    normalized_url=normalize_url(cp.url),
                    final_url=cp.final_url,
                    title=cp.title,
                    meta_description=cp.meta_description,
                    h1=cp.h1,
                    raw_html=cp.html,
                    cleaned_content=cleaned,
                    status_code=cp.status_code,
                    content_type=cp.content_type,
                    language=cp.language,
                    page_type=page_type,
                    content_hash=content_hash,
                )
                self.db.add(page)
                page_map[page.id] = page

                if not cleaned:
                    self._log_error(site.id, crawl_job.id, "clean", cp.url, "EmptyContent", "No useful content after cleaning")
                    continue

                # --- Phase 3: Chunk ---
                chunks = self._chunk_page(cleaned, page_type, cp.url, cp.title, page)

                for chunk in chunks:
                    chunk_dict = {
                        "page_id": str(page.id),
                        "site_id": str(site.id),
                        "company_id": str(site.company_id),
                        "url": cp.url,
                        "page_title": cp.title,
                        "page_type": page_type,
                        "chunk_type": chunk.chunk_type,
                        "section_path": chunk.section_path,
                        "heading_hierarchy": chunk.heading_hierarchy,
                        "content": chunk.content,
                        "token_count": chunk.token_count,
                        "position_on_page": chunk.position_on_page,
                        "content_hash": chunk.content_hash,
                        "extra_meta": chunk.metadata,
                    }
                    all_chunk_dicts.append(chunk_dict)

            self.db.commit()
            logger.info("Processed %d pages, produced %d chunks", len(page_map), len(all_chunk_dicts))

            # --- Phase 4: Embed ---
            if all_chunk_dicts and settings.OPENAI_API_KEY:
                provider = OpenAIEmbeddingProvider(settings.OPENAI_API_KEY)
                pipeline = EmbeddingPipeline(provider)
                try:
                    all_chunk_dicts = await pipeline.embed_chunks(all_chunk_dicts)
                except Exception as exc:
                    logger.error("Embedding failed: %s", exc)
                    self._log_error(site.id, crawl_job.id, "embed", None, type(exc).__name__, str(exc))
                finally:
                    await pipeline.close()
            elif not settings.OPENAI_API_KEY:
                logger.warning("OPENAI_API_KEY not set, skipping embeddings")

            # --- Phase 5: Store chunks ---
            for cd in all_chunk_dicts:
                db_chunk = IdxChunk(
                    id=uuid4(),
                    page_id=cd["page_id"],
                    site_id=cd["site_id"],
                    company_id=cd["company_id"],
                    url=cd["url"],
                    page_title=cd["page_title"],
                    page_type=cd["page_type"],
                    chunk_type=cd["chunk_type"],
                    section_path=cd["section_path"],
                    heading_hierarchy=cd["heading_hierarchy"],
                    content=cd["content"],
                    token_count=cd["token_count"],
                    position_on_page=cd["position_on_page"],
                    content_hash=cd["content_hash"],
                    embedding=cd.get("embedding"),
                    embedding_model=cd.get("embedding_model"),
                    embedding_version=cd.get("embedding_version"),
                    extra_meta=cd.get("extra_meta", {}),
                )
                self.db.add(db_chunk)

            # Finalize
            crawl_job.status = CrawlJobStatus.completed
            crawl_job.completed_at = datetime.utcnow()
            site.status = SiteStatus.ready
            site.last_crawled_at = datetime.utcnow()
            site.stats = {
                "pages_crawled": len(crawled_pages),
                "pages_cleaned": len(page_map),
                "chunks_created": len(all_chunk_dicts),
                **crawler.get_stats(),
            }
            self.db.commit()

            # --- Phase 6: Infer business type ---
            self._run_domain_inference(site.company_id)

            logger.info(
                "Indexing complete for %s: %d pages, %d chunks",
                site.base_url, len(crawled_pages), len(all_chunk_dicts),
            )
            return True

        except Exception as exc:
            logger.error("Indexing failed for %s: %s", site.base_url, exc)
            crawl_job.status = CrawlJobStatus.failed
            crawl_job.error = str(exc)
            crawl_job.completed_at = datetime.utcnow()
            site.status = SiteStatus.failed
            site.last_error = str(exc)
            self.db.commit()
            self._log_error(site.id, crawl_job.id, "orchestrator", None, type(exc).__name__, str(exc))
            return False

    def _run_domain_inference(self, company_id) -> None:
        """Infer the company's business type from indexed content."""
        try:
            from app.models.company import Company
            from app.services.domain_inference import update_company_inference

            company = self.db.query(Company).filter(
                Company.id == company_id,
            ).first()
            if company:
                update_company_inference(self.db, company)
        except Exception:
            logger.warning("Domain inference failed for company %s", company_id, exc_info=True)

    def _chunk_page(self, cleaned_text: str, page_type: str, url: str, title: str, page) -> list:
        """Run semantic chunker + special extractors on cleaned page text."""
        all_chunks = []

        # Special extractors first (may override general chunks)
        if page_type in ("faq",) or cleaned_text.count("?") >= 4:
            faq_chunks = extract_faq_chunks(cleaned_text)
            all_chunks.extend(faq_chunks)

        if page_type in ("pricing",) or "€" in cleaned_text:
            pricing_chunks = extract_pricing_chunks(cleaned_text)
            all_chunks.extend(pricing_chunks)

        if page_type in ("contact",):
            contact_chunks = extract_contact_chunks(cleaned_text)
            all_chunks.extend(contact_chunks)

        # General semantic chunking
        general_chunks = self._chunker.chunk(cleaned_text, page_type=page_type, url=url)

        # Merge: add general chunks that don't heavily overlap with special chunks
        special_content = {c.content_hash for c in all_chunks}
        for gc in general_chunks:
            if gc.content_hash not in special_content:
                all_chunks.append(gc)

        return all_chunks

    def _log_error(
        self, site_id, crawl_job_id, phase: str,
        url: Optional[str], error_type: str, message: str,
    ):
        err = IdxError(
            id=uuid4(),
            site_id=site_id,
            crawl_job_id=crawl_job_id,
            phase=phase,
            url=url,
            error_type=error_type,
            error_message=message,
        )
        self.db.add(err)
        try:
            self.db.commit()
        except Exception:
            self.db.rollback()
