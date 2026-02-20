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
        """Fetch a single page and extract content."""
        try:
            response = await client.get(url, follow_redirects=True, timeout=30.0)
            
            if response.status_code != 200:
                return None
            
            content_type = response.headers.get('content-type', '')
            if 'text/html' not in content_type:
                return None
            
            html = response.text
            soup = BeautifulSoup(html, 'lxml')
            
            # Extract title
            title = ""
            title_tag = soup.find('title')
            if title_tag:
                title = title_tag.get_text().strip()
            
            # Remove unwanted elements
            for element in soup.find_all(['script', 'style', 'nav', 'footer', 
                                          'header', 'aside', 'noscript', 'iframe']):
                element.decompose()
            
            # Extract main content
            main_content = soup.find('main') or soup.find('article') or soup.find('body')
            if not main_content:
                return None
            
            # Get text content
            text = main_content.get_text(separator='\n', strip=True)
            
            # Clean up text
            text = self._clean_text(text)
            
            if len(text) < 50:  # Skip pages with too little content
                return None
            
            # Extract links for further crawling
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
            print(f"Error fetching {url}: {e}")
            return None
    
    def _clean_text(self, text: str) -> str:
        """Clean up extracted text."""
        # Remove excessive whitespace
        text = re.sub(r'\n\s*\n', '\n\n', text)
        text = re.sub(r' +', ' ', text)
        
        # Remove very short lines (likely menu items)
        lines = text.split('\n')
        cleaned_lines = []
        for line in lines:
            line = line.strip()
            if len(line) > 20 or (cleaned_lines and len(line) > 0):
                cleaned_lines.append(line)
        
        return '\n'.join(cleaned_lines).strip()
    
    async def crawl(self) -> List[Dict]:
        """Crawl the website and return all pages."""
        async with httpx.AsyncClient(
            headers={'User-Agent': self.user_agent},
            follow_redirects=True,
        ) as client:
            # Start with the base URL
            queue = [(self.base_url, 0)]  # (url, depth)
            
            while queue and len(self.pages) < self.max_pages:
                url, depth = queue.pop(0)
                
                normalized = self.normalize_url(url)
                if normalized in self.visited:
                    continue
                
                self.visited.add(normalized)
                
                page = await self.fetch_page(url, client)
                
                if page:
                    self.pages.append(page)
                    print(f"Crawled: {url} ({len(self.pages)}/{self.max_pages})")
                    
                    # Add new links to queue if within depth limit
                    if depth < self.max_depth:
                        for link in page['links']:
                            if link not in self.visited:
                                queue.append((link, depth + 1))
                
                # Be nice to the server
                await asyncio.sleep(0.5)
        
        return self.pages


class TextChunker:
    """Splits text into chunks for embedding."""
    
    def __init__(self, chunk_size: int = 500, chunk_overlap: int = 50):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
    
    def chunk_text(self, text: str, metadata: Dict = None) -> List[Dict]:
        """Split text into overlapping chunks."""
        chunks = []
        
        # Split by paragraphs first
        paragraphs = text.split('\n\n')
        
        current_chunk = ""
        
        for paragraph in paragraphs:
            paragraph = paragraph.strip()
            if not paragraph:
                continue
            
            # If adding this paragraph exceeds chunk size, save current and start new
            if len(current_chunk) + len(paragraph) > self.chunk_size and current_chunk:
                chunks.append({
                    'content': current_chunk.strip(),
                    'metadata': metadata or {},
                    'hash': hashlib.sha256(current_chunk.encode()).hexdigest()[:16],
                })
                # Keep overlap from end of previous chunk
                words = current_chunk.split()
                overlap_words = words[-self.chunk_overlap:] if len(words) > self.chunk_overlap else []
                current_chunk = ' '.join(overlap_words) + ' ' + paragraph
            else:
                current_chunk += '\n\n' + paragraph if current_chunk else paragraph
        
        # Don't forget the last chunk
        if current_chunk.strip():
            chunks.append({
                'content': current_chunk.strip(),
                'metadata': metadata or {},
                'hash': hashlib.sha256(current_chunk.encode()).hexdigest()[:16],
            })
        
        return chunks


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
        """Search for relevant chunks using cosine similarity.

        Raises on infrastructure errors so callers can distinguish
        'no results' from 'search broken'.
        """
        db = db or self.db
        if not db:
            raise RuntimeError("No database session available for search")

        query_embedding = self.generate_embedding(query)
        if not query_embedding:
            raise RuntimeError("Could not generate query embedding")

        embedding_str = f"[{','.join(map(str, query_embedding))}]"

        if website_id:
            sql = text("""
                SELECT kc.id, kc.content, kc.source_url, kc.page_title,
                       kc.chunk_metadata,
                       kc.embedding <=> CAST(:embedding AS vector) AS distance
                FROM knowledge_chunks kc
                WHERE kc.company_id = :company_id
                  AND kc.website_id = :website_id
                  AND kc.embedding IS NOT NULL
                ORDER BY distance ASC
                LIMIT :limit
            """)
            results = db.execute(sql, {
                'embedding': embedding_str,
                'company_id': self.company_id,
                'website_id': website_id,
                'limit': limit,
            }).fetchall()
        else:
            sql = text("""
                SELECT kc.id, kc.content, kc.source_url, kc.page_title,
                       kc.chunk_metadata,
                       kc.embedding <=> CAST(:embedding AS vector) AS distance
                FROM knowledge_chunks kc
                WHERE kc.company_id = :company_id
                  AND kc.embedding IS NOT NULL
                ORDER BY distance ASC
                LIMIT :limit
            """)
            results = db.execute(sql, {
                'embedding': embedding_str,
                'company_id': self.company_id,
                'limit': limit,
            }).fetchall()

        return [
            {
                'content': row.content,
                'metadata': {
                    'url': row.source_url,
                    'title': row.page_title,
                    **(row.chunk_metadata or {}),
                },
                'distance': float(row.distance),
            }
            for row in results
        ]


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
