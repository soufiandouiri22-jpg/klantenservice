"""
klantenservice.ai - Website Indexer Service

This service crawls websites, extracts content, chunks text,
and stores embeddings in PostgreSQL using pgvector for RAG.
"""
import asyncio
import hashlib
import os
import re
from datetime import datetime
from typing import List, Dict, Optional, Set
from urllib.parse import urljoin, urlparse
from uuid import uuid4
import logging

import httpx
import numpy as np
from bs4 import BeautifulSoup
from sqlalchemy.orm import Session
from sqlalchemy import text

from app.models.website_knowledge import WebsiteKnowledge, KnowledgeChunk, IndexStatus

logger = logging.getLogger(__name__)


class LocalEmbedder:
    """
    Local ONNX-based embedding model for fast inference (~10-20ms) without
    external API calls. Uses paraphrase-multilingual-MiniLM-L12-v2 which
    supports Dutch and outputs 384-dimensional vectors.
    """

    MODEL_REPO = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
    DIMENSIONS = 384
    _instance: Optional["LocalEmbedder"] = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._ready = False
        return cls._instance

    def _ensure_loaded(self):
        if self._ready:
            return

        from transformers import AutoTokenizer
        from huggingface_hub import hf_hub_download
        import onnxruntime as ort

        cache_dir = os.environ.get("HF_HOME", "/tmp/hf_models")

        onnx_path = hf_hub_download(
            self.MODEL_REPO,
            filename="onnx/model.onnx",
            cache_dir=cache_dir,
        )

        self._tokenizer = AutoTokenizer.from_pretrained(
            self.MODEL_REPO, cache_dir=cache_dir
        )

        sess_opts = ort.SessionOptions()
        sess_opts.inter_op_num_threads = 1
        sess_opts.intra_op_num_threads = 4
        sess_opts.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL

        self._session = ort.InferenceSession(
            onnx_path,
            sess_options=sess_opts,
            providers=["CPUExecutionProvider"],
        )
        self._input_names = {inp.name for inp in self._session.get_inputs()}
        self._ready = True
        logger.info("LocalEmbedder loaded (%s, %d dims)", self.MODEL_REPO, self.DIMENSIONS)

    @staticmethod
    def _mean_pool(token_embeddings: np.ndarray, attention_mask: np.ndarray) -> np.ndarray:
        mask = np.expand_dims(attention_mask, -1).astype(token_embeddings.dtype)
        summed = np.sum(token_embeddings * mask, axis=1)
        counts = np.clip(np.sum(mask, axis=1), a_min=1e-9, a_max=None)
        pooled = summed / counts
        norms = np.linalg.norm(pooled, axis=1, keepdims=True)
        return pooled / np.clip(norms, a_min=1e-9, a_max=None)

    def _run(self, texts: List[str]) -> np.ndarray:
        self._ensure_loaded()
        encoded = self._tokenizer(
            texts, padding=True, truncation=True, max_length=512, return_tensors="np"
        )
        feeds = {k: v for k, v in encoded.items() if k in self._input_names}
        outputs = self._session.run(None, feeds)
        return self._mean_pool(outputs[0], encoded["attention_mask"])

    def embed(self, text: str) -> List[float]:
        return self._run([text])[0].tolist()

    def embed_batch(self, texts: List[str]) -> List[List[float]]:
        if not texts:
            return []
        return self._run(texts).tolist()


_embedder = LocalEmbedder()


class WebsiteCrawler:
    """Crawls websites and extracts content."""
    
    def __init__(self, base_url: str, settings: Dict = None):
        self.base_url = base_url.rstrip('/')
        self.domain = urlparse(base_url).netloc
        self.settings = settings or {}
        self.max_pages = self.settings.get('max_pages', 100)
        self.max_depth = self.settings.get('max_depth', 3)
        self.blocked_paths = self.settings.get('blocked_paths', ['/admin', '/login', '/wp-admin'])
        self.user_agent = self.settings.get('user_agent', 'klantenservice-ai-bot/1.0')
        
        self.visited: Set[str] = set()
        self.pages: List[Dict] = []
        
    def normalize_url(self, url: str) -> str:
        """Normalize URL to avoid duplicates."""
        parsed = urlparse(url)
        # Remove fragment and trailing slash
        normalized = f"{parsed.scheme}://{parsed.netloc}{parsed.path.rstrip('/')}"
        if parsed.query:
            normalized += f"?{parsed.query}"
        return normalized
    
    def is_valid_url(self, url: str) -> bool:
        """Check if URL should be crawled."""
        parsed = urlparse(url)
        
        # Must be same domain
        if parsed.netloc != self.domain:
            return False
        
        # Check blocked paths
        for blocked in self.blocked_paths:
            if parsed.path.startswith(blocked):
                return False
        
        # Must be http(s)
        if parsed.scheme not in ('http', 'https'):
            return False
        
        # Skip common non-page extensions
        skip_extensions = ['.pdf', '.jpg', '.jpeg', '.png', '.gif', '.svg', 
                         '.css', '.js', '.ico', '.xml', '.json', '.zip', '.mp4', '.mp3']
        if any(parsed.path.lower().endswith(ext) for ext in skip_extensions):
            return False
        
        return True
    
    async def fetch_page(self, url: str, client: httpx.AsyncClient) -> Optional[Dict]:
        """Fetch a page. Tries static HTML first, falls back to Jina Reader for JS-rendered sites."""
        page = await self._fetch_static(url, client)
        if page:
            return page
        return await self._fetch_rendered(url, client)

    async def _fetch_static(self, url: str, client: httpx.AsyncClient) -> Optional[Dict]:
        """Extract content from raw HTML (fast, works for static / SSR sites)."""
        try:
            response = await client.get(url, follow_redirects=True, timeout=30.0)

            if response.status_code != 200:
                return None

            content_type = response.headers.get('content-type', '')
            if 'text/html' not in content_type:
                return None

            html = response.text
            soup = BeautifulSoup(html, 'lxml')

            title = ""
            title_tag = soup.find('title')
            if title_tag:
                title = title_tag.get_text().strip()

            for element in soup.find_all(['script', 'style', 'nav', 'footer',
                                          'header', 'aside', 'noscript', 'iframe']):
                element.decompose()

            main_content = soup.find('main') or soup.find('article') or soup.find('body')
            if not main_content:
                return None

            text = self._extract_with_headings(main_content)
            text = self._clean_text(text)

            if len(text) < 50:
                return None

            links = []
            for link in soup.find_all('a', href=True):
                href = link['href']
                full_url = urljoin(url, href)
                if self.is_valid_url(full_url):
                    links.append(self.normalize_url(full_url))

            return {
                'url': url,
                'title': title,
                'content': text,
                'links': links,
            }

        except Exception as e:
            logger.debug(f"Static fetch failed for {url}: {e}")
            return None

    async def _fetch_rendered(self, url: str, client: httpx.AsyncClient) -> Optional[Dict]:
        """Fallback: render JS-heavy pages via Jina Reader API and extract content."""
        try:
            jina_url = f"https://r.jina.ai/{url}"
            response = await client.get(
                jina_url,
                headers={'Accept': 'application/json'},
                timeout=60.0,
            )

            if response.status_code != 200:
                logger.warning(f"Jina Reader returned {response.status_code} for {url}")
                return None

            data = response.json().get('data', {})
            title = data.get('title', '')
            content = data.get('content', '')

            if not content or len(content) < 50:
                return None

            links = []
            for match in re.finditer(r'\[.*?\]\((https?://[^\)]+)\)', content):
                link_url = match.group(1)
                if self.is_valid_url(link_url):
                    links.append(self.normalize_url(link_url))

            text = self._clean_markdown(content)

            if len(text) < 50:
                return None

            logger.info(f"Jina Reader rendered {url} ({len(text)} chars)")
            return {
                'url': url,
                'title': title,
                'content': text,
                'links': links,
            }

        except Exception as e:
            logger.warning(f"Jina Reader fallback failed for {url}: {e}")
            return None
    
    def _extract_with_headings(self, element) -> str:
        """Extract text while preserving h1-h6 as markdown headers for topic-based chunking."""
        from bs4 import NavigableString
        for h in element.find_all(['h1', 'h2', 'h3', 'h4', 'h5', 'h6']):
            level = int(h.name[1])
            h_text = h.get_text(separator=' ', strip=True)
            if h_text:
                h.replace_with(NavigableString('\n' + '#' * level + ' ' + h_text + '\n\n'))
        return element.get_text(separator='\n', strip=True)

    def _clean_text(self, text: str) -> str:
        """Clean up extracted text."""
        text = re.sub(r'\n\s*\n', '\n\n', text)
        text = re.sub(r' +', ' ', text)

        lines = text.split('\n')
        cleaned_lines = []
        for line in lines:
            line = line.strip()
            if len(line) > 20 or (cleaned_lines and len(line) > 0):
                cleaned_lines.append(line)

        return '\n'.join(cleaned_lines).strip()

    @staticmethod
    def _clean_markdown(text: str) -> str:
        """Convert markdown to clean plain text for embedding. Preserves ## headers for topic chunking."""
        text = re.sub(r'!\[.*?\]\(.*?\)', '', text)
        text = re.sub(r'\[(.*?)\]\(.*?\)', r'\1', text)
        text = re.sub(r'[*_]{1,3}(.*?)[*_]{1,3}', r'\1', text)
        # Keep ## headers for topic-based chunking (do NOT strip #)
        text = re.sub(r'\n\s*\n', '\n\n', text)
        text = re.sub(r' +', ' ', text)
        return text.strip()
    
    async def _discover_sitemap_urls(self, client: httpx.AsyncClient) -> List[str]:
        """Discover page URLs from sitemap.xml (works for all site types)."""
        urls: List[str] = []
        try:
            sitemap_url = f"{self.base_url}/sitemap.xml"
            response = await client.get(sitemap_url, timeout=10.0)
            if response.status_code == 200 and 'xml' in response.headers.get('content-type', ''):
                for match in re.finditer(r'<loc>(.*?)</loc>', response.text):
                    url = match.group(1).strip()
                    if self.is_valid_url(url):
                        urls.append(self.normalize_url(url))
                logger.info(f"Sitemap: found {len(urls)} URLs for {self.domain}")
        except Exception:
            pass
        return urls

    async def crawl(self) -> List[Dict]:
        """Crawl the website and return all pages."""
        async with httpx.AsyncClient(
            headers={'User-Agent': self.user_agent},
            follow_redirects=True,
        ) as client:
            sitemap_urls = await self._discover_sitemap_urls(client)

            queue: List[tuple] = [(self.base_url, 0)]
            for surl in sitemap_urls:
                if self.normalize_url(surl) != self.normalize_url(self.base_url):
                    queue.append((surl, 1))

            while queue and len(self.pages) < self.max_pages:
                url, depth = queue.pop(0)

                normalized = self.normalize_url(url)
                if normalized in self.visited:
                    continue

                self.visited.add(normalized)

                page = await self.fetch_page(url, client)

                if page:
                    self.pages.append(page)
                    logger.info(f"Crawled: {url} ({len(self.pages)}/{self.max_pages})")

                    if depth < self.max_depth:
                        for link in page['links']:
                            if link not in self.visited:
                                queue.append((link, depth + 1))

                await asyncio.sleep(0.5)

        return self.pages


class TextChunker:
    """Splits text into chunks for embedding. Uses topic-based chunking when headers are present."""

    def __init__(self, chunk_size: int = 1000, chunk_overlap: int = 100):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap

    def chunk_text(self, text: str, metadata: Dict = None) -> List[Dict]:
        """Split text into chunks. Prefers topic-based (header) chunking; falls back to paragraph-based."""
        sections = self._split_by_headers(text)
        if sections:
            return self._chunk_sections(sections, metadata)
        return self._chunk_by_paragraphs(text, metadata)

    def _split_by_headers(self, text: str) -> List[str]:
        """Split text on markdown headers. Returns list of sections (each includes header + its content)."""
        pattern = re.compile(r'^(#{1,6})\s+(.+)$', re.MULTILINE)
        matches = list(pattern.finditer(text))
        if not matches:
            return []
        sections = []
        intro = text[: matches[0].start()].strip()
        for i, m in enumerate(matches):
            start = m.start()
            end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
            section = text[start:end].strip()
            if section:
                if intro and i == 0:
                    section = intro + '\n\n' + section
                    intro = ""
                sections.append(section)
        if intro and not sections:
            sections.append(intro)
        return sections

    def _chunk_sections(self, sections: List[str], metadata: Dict = None) -> List[Dict]:
        """Each section is a topic. If section exceeds chunk_size, split by paragraphs within it."""
        chunks = []
        for section in sections:
            if len(section) <= self.chunk_size:
                if section.strip():
                    chunks.append(self._make_chunk(section.strip(), metadata))
            else:
                # Section too long: split by paragraphs within this topic
                sub_chunks = self._chunk_by_paragraphs(section, metadata)
                chunks.extend(sub_chunks)
        return chunks

    def _chunk_by_paragraphs(self, text: str, metadata: Dict = None) -> List[Dict]:
        """Original paragraph-based splitting with overlap."""
        chunks = []
        paragraphs = text.split('\n\n')
        current_chunk = ""
        for paragraph in paragraphs:
            paragraph = paragraph.strip()
            if not paragraph:
                continue
            if len(current_chunk) + len(paragraph) > self.chunk_size and current_chunk:
                chunks.append(self._make_chunk(current_chunk.strip(), metadata))
                words = current_chunk.split()
                overlap_words = words[-self.chunk_overlap:] if len(words) > self.chunk_overlap else []
                current_chunk = ' '.join(overlap_words) + ' ' + paragraph
            else:
                current_chunk += '\n\n' + paragraph if current_chunk else paragraph
        if current_chunk.strip():
            chunks.append(self._make_chunk(current_chunk.strip(), metadata))
        return chunks

    def _make_chunk(self, content: str, metadata: Dict = None) -> Dict:
        return {
            'content': content,
            'metadata': metadata or {},
            'hash': hashlib.sha256(content.encode()).hexdigest()[:16],
        }


class VectorStore:
    """Manages embeddings in PostgreSQL using pgvector."""

    EMBEDDING_DIMENSIONS = 384

    def __init__(self, company_id: str, db: Session = None):
        self.company_id = str(company_id)
        self.db = db

    def generate_embedding(self, text: str) -> Optional[List[float]]:
        """Generate embedding using local ONNX model."""
        try:
            return _embedder.embed(text)
        except Exception as e:
            logger.error(f"Error generating embedding: {e}")
            return None

    def generate_embeddings(self, texts: List[str]) -> List[List[float]]:
        """Generate embeddings for multiple texts using local ONNX model."""
        if not texts:
            return []
        try:
            return _embedder.embed_batch(texts)
        except Exception as e:
            logger.error(f"Error generating embeddings: {e}")
            return [[] for _ in texts]

    def add_chunks(self, chunks: List[Dict], website_id: str, db: Session = None) -> List[str]:
        """Add chunks to the database with embeddings."""
        db = db or self.db
        if not db:
            logger.error("No database session available")
            return [f"error_{i}" for i in range(len(chunks))]

        ids = []
        documents = [chunk['content'] for chunk in chunks]
        embeddings = self.generate_embeddings(documents)

        for i, chunk in enumerate(chunks):
            chunk_id = f"{website_id}_{chunk['hash']}_{i}"
            ids.append(chunk_id)
            chunk['embedding'] = embeddings[i] if i < len(embeddings) and embeddings[i] else None

        return ids

    def delete_website_chunks(self, website_id: str, db: Session = None):
        """Delete all chunks for a website."""
        db = db or self.db
        if not db:
            logger.warning("No database session - skipping delete")
            return

        try:
            db.query(KnowledgeChunk).filter(
                KnowledgeChunk.website_id == website_id
            ).delete()
            db.commit()
            logger.info(f"Deleted chunks for website {website_id}")
        except Exception as e:
            logger.error(f"Error deleting chunks: {e}")
            db.rollback()

    def search(self, query: str, website_id: str = None, limit: int = 3, db: Session = None) -> List[Dict]:
        """Hybrid search: combines vector (semantic) + full-text (keyword) with RRF fusion."""
        return self.search_hybrid(query, website_id=website_id, limit=limit, db=db)

    def _search_vector(self, query: str, website_id: str = None, limit: int = 50, db: Session = None) -> List[tuple]:
        """Vector similarity search. Returns list of (chunk_dict, rank)."""
        db = db or self.db
        if not db:
            raise RuntimeError("No database session available for search")

        query_embedding = self.generate_embedding(query)
        if not query_embedding:
            return []

        embedding_str = f"[{','.join(map(str, query_embedding))}]"
        where_clause = "kc.company_id = :company_id AND kc.embedding IS NOT NULL"
        params = {'embedding': embedding_str, 'company_id': self.company_id, 'limit': limit}
        if website_id:
            where_clause += " AND kc.website_id = :website_id"
            params['website_id'] = website_id

        sql = text(f"""
            SELECT kc.id, kc.content, kc.source_url, kc.page_title, kc.chunk_metadata,
                   kc.embedding <=> CAST(:embedding AS vector) AS distance
            FROM knowledge_chunks kc
            WHERE {where_clause}
            ORDER BY distance ASC
            LIMIT :limit
        """)
        rows = db.execute(sql, params).fetchall()
        return [
            (
                {
                    'content': row.content,
                    'metadata': {'url': row.source_url, 'title': row.page_title, **(row.chunk_metadata or {})},
                    'distance': float(row.distance),
                },
                rank,
            )
            for rank, row in enumerate(rows, start=1)
        ]

    def _search_fulltext(self, query: str, website_id: str = None, limit: int = 50, db: Session = None) -> List[tuple]:
        """Full-text (BM25-style) search. Returns list of (chunk_dict, rank)."""
        db = db or self.db
        if not db:
            return []

        where_clause = "kc.company_id = :company_id AND kc.content_tsv @@ plainto_tsquery('simple', :query)"
        params = {'query': query, 'company_id': self.company_id, 'limit': limit}
        if website_id:
            where_clause += " AND kc.website_id = :website_id"
            params['website_id'] = website_id

        try:
            sql = text(f"""
                SELECT kc.id, kc.content, kc.source_url, kc.page_title, kc.chunk_metadata,
                       ts_rank_cd(kc.content_tsv, plainto_tsquery('simple', :query)) AS rank
                FROM knowledge_chunks kc
                WHERE {where_clause}
                ORDER BY rank DESC
                LIMIT :limit
            """)
            rows = db.execute(sql, params).fetchall()
            return [
                (
                    {
                        'content': row.content,
                        'metadata': {'url': row.source_url, 'title': row.page_title, **(row.chunk_metadata or {})},
                        'distance': 0,
                    },
                    rank,
                )
                for rank, row in enumerate(rows, start=1)
            ]
        except Exception as e:
            logger.warning("Full-text search failed (content_tsv may not exist): %s", e)
            return []

    def search_hybrid(self, query: str, website_id: str = None, limit: int = 3, db: Session = None) -> List[Dict]:
        """Hybrid search: vector + full-text, fused with Reciprocal Rank Fusion (RRF)."""
        k = 60  # RRF constant
        fetch_limit = min(limit * 4, 50)  # Fetch more candidates for fusion

        vector_results = self._search_vector(query, website_id=website_id, limit=fetch_limit, db=db)
        fulltext_results = self._search_fulltext(query, website_id=website_id, limit=fetch_limit, db=db)

        # Build content->chunk map (use content hash as id since we might not have row id in dict)
        def chunk_key(c: dict) -> str:
            return (c['metadata'].get('url', ''), c['content'][:200])

        rrf_scores: Dict[str, float] = {}
        chunk_by_key: Dict[str, dict] = {}

        for chunk_dict, rank in vector_results:
            key = chunk_key(chunk_dict)
            rrf_scores[key] = rrf_scores.get(key, 0) + 1 / (k + rank)
            chunk_by_key[key] = chunk_dict

        for chunk_dict, rank in fulltext_results:
            key = chunk_key(chunk_dict)
            rrf_scores[key] = rrf_scores.get(key, 0) + 1 / (k + rank)
            chunk_by_key[key] = chunk_dict

        # Sort by RRF score descending
        sorted_keys = sorted(rrf_scores.keys(), key=lambda x: rrf_scores[x], reverse=True)
        return [chunk_by_key[key] for key in sorted_keys[:limit]]


class WebsiteIndexer:
    """Main service that orchestrates website indexing."""
    
    def __init__(self, db: Session):
        self.db = db
        self.chunker = TextChunker()
    
    async def index_website(self, website_id: str) -> bool:
        """Index a website completely."""
        # Get website from database
        website = self.db.query(WebsiteKnowledge).filter(
            WebsiteKnowledge.id == website_id
        ).first()
        
        if not website:
            logger.error(f"Website {website_id} not found")
            return False
        
        try:
            # Update status to indexing
            website.status = IndexStatus.indexing
            website.last_error = None
            self.db.commit()
            
            logger.info(f"Starting indexing for {website.base_url}")
            
            # Initialize vector store with database session
            vector_store = VectorStore(str(website.company_id), self.db)
            
            # Delete existing chunks (now handled by VectorStore which uses PostgreSQL)
            self.db.query(KnowledgeChunk).filter(
                KnowledgeChunk.website_id == website.id
            ).delete()
            self.db.commit()
            
            # Crawl the website
            crawler = WebsiteCrawler(
                website.base_url,
                website.crawl_settings or {}
            )
            pages = await crawler.crawl()
            
            if not pages:
                website.status = IndexStatus.failed
                website.last_error = "Geen pagina's gevonden om te indexeren"
                self.db.commit()
                return False
            
            # Process pages and create chunks
            total_chunks = 0
            
            for page in pages:
                chunks = self.chunker.chunk_text(
                    page['content'],
                    metadata={
                        'url': page['url'],
                        'title': page['title'],
                    }
                )
                
                if chunks:
                    # Generate embeddings for chunks
                    vector_store.add_chunks(chunks, str(website.id), self.db)
                    
                    for i, chunk in enumerate(chunks):
                        db_chunk = KnowledgeChunk(
                            id=uuid4(),
                            website_id=website.id,
                            company_id=website.company_id,
                            source_url=page['url'],
                            page_title=page['title'],
                            content=chunk['content'],
                            content_hash=chunk['hash'],
                            embedding=chunk.get('embedding'),
                            chunk_metadata=chunk.get('metadata', {}),
                        )
                        self.db.add(db_chunk)
                    
                    total_chunks += len(chunks)
            
            # Update website status
            website.status = IndexStatus.completed
            website.pages_indexed = len(pages)
            website.chunks_created = total_chunks
            website.last_indexed_at = datetime.utcnow()
            website.last_error = None
            self.db.commit()
            
            logger.info(f"Indexing complete: {len(pages)} pages, {total_chunks} chunks")
            return True
            
        except Exception as e:
            logger.error(f"Indexing failed: {e}")
            website.status = IndexStatus.failed
            website.last_error = str(e)
            self.db.commit()
            return False


# Singleton for background task management
_indexing_tasks: Dict[str, asyncio.Task] = {}


def start_indexing_task(website_id: str, db: Session):
    """Start a background indexing task."""
    async def run_indexing():
        indexer = WebsiteIndexer(db)
        await indexer.index_website(website_id)
    
    task = asyncio.create_task(run_indexing())
    _indexing_tasks[website_id] = task
    return task


def get_indexing_status(website_id: str) -> Optional[str]:
    """Check if indexing is in progress."""
    task = _indexing_tasks.get(website_id)
    if task and not task.done():
        return "indexing"
    return None
