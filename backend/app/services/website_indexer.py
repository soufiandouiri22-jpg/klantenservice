"""
klantenservice.ai - Website Indexer Service

This service crawls websites, extracts content, chunks text,
and stores embeddings in ChromaDB for RAG.
"""
import asyncio
import hashlib
import re
from datetime import datetime
from typing import List, Dict, Optional, Set
from urllib.parse import urljoin, urlparse
from uuid import uuid4

import httpx
from bs4 import BeautifulSoup
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.website_knowledge import WebsiteKnowledge, KnowledgeChunk, IndexStatus

# Try to import ChromaDB - it's optional for local development
try:
    import chromadb
    from chromadb.config import Settings as ChromaSettings
    CHROMA_AVAILABLE = True
except ImportError:
    CHROMA_AVAILABLE = False
    print("ChromaDB not available - running in mock mode")

# Try to import sentence-transformers for local embeddings
try:
    from sentence_transformers import SentenceTransformer
    EMBEDDINGS_AVAILABLE = True
except ImportError:
    EMBEDDINGS_AVAILABLE = False
    print("Sentence-transformers not available - embeddings disabled")


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
    """Manages embeddings in ChromaDB."""
    
    def __init__(self, company_id: str):
        self.company_id = str(company_id)
        self.collection_name = f"company_{self.company_id}"
        
        if CHROMA_AVAILABLE:
            # Connect to ChromaDB
            self.client = chromadb.HttpClient(
                host="localhost",
                port=8001,  # ChromaDB port from docker-compose
            )
            self.collection = self.client.get_or_create_collection(
                name=self.collection_name,
                metadata={"company_id": self.company_id}
            )
        else:
            self.client = None
            self.collection = None
        
        # Load embedding model if available
        if EMBEDDINGS_AVAILABLE:
            self.embedding_model = SentenceTransformer('all-MiniLM-L6-v2')
        else:
            self.embedding_model = None
    
    def add_chunks(self, chunks: List[Dict], website_id: str) -> List[str]:
        """Add chunks to the vector store."""
        if not self.collection or not self.embedding_model:
            # Return mock IDs if not available
            return [f"mock_{i}" for i in range(len(chunks))]
        
        ids = []
        documents = []
        embeddings = []
        metadatas = []
        
        for i, chunk in enumerate(chunks):
            chunk_id = f"{website_id}_{chunk['hash']}_{i}"
            ids.append(chunk_id)
            documents.append(chunk['content'])
            metadatas.append({
                **chunk.get('metadata', {}),
                'website_id': str(website_id),
                'company_id': self.company_id,
            })
        
        # Generate embeddings
        embeddings = self.embedding_model.encode(documents).tolist()
        
        # Add to ChromaDB
        self.collection.add(
            ids=ids,
            documents=documents,
            embeddings=embeddings,
            metadatas=metadatas,
        )
        
        return ids
    
    def delete_website_chunks(self, website_id: str):
        """Delete all chunks for a website."""
        if not self.collection:
            return
        
        try:
            # Get all chunks for this website
            results = self.collection.get(
                where={"website_id": str(website_id)}
            )
            
            if results['ids']:
                self.collection.delete(ids=results['ids'])
        except Exception as e:
            print(f"Error deleting chunks: {e}")
    
    def search(self, query: str, website_id: str = None, limit: int = 5) -> List[Dict]:
        """Search for relevant chunks."""
        if not self.collection or not self.embedding_model:
            return []
        
        query_embedding = self.embedding_model.encode([query]).tolist()
        
        # Build filter for ChromaDB (use $and for multiple conditions)
        if website_id:
            where_filter = {
                "$and": [
                    {"company_id": {"$eq": self.company_id}},
                    {"website_id": {"$eq": str(website_id)}}
                ]
            }
        else:
            where_filter = {"company_id": {"$eq": self.company_id}}
        
        results = self.collection.query(
            query_embeddings=query_embedding,
            n_results=limit,
            where=where_filter,
            include=["documents", "metadatas", "distances"]
        )
        
        chunks = []
        if results['documents'] and results['documents'][0]:
            for i, doc in enumerate(results['documents'][0]):
                chunks.append({
                    'content': doc,
                    'metadata': results['metadatas'][0][i],
                    'distance': results['distances'][0][i],
                })
        
        return chunks


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
            print(f"Website {website_id} not found")
            return False
        
        try:
            # Update status to indexing
            website.status = IndexStatus.indexing
            website.last_error = None
            self.db.commit()
            
            print(f"Starting indexing for {website.base_url}")
            
            # Initialize vector store
            vector_store = VectorStore(str(website.company_id))
            
            # Delete existing chunks
            vector_store.delete_website_chunks(str(website.id))
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
                    # Store in vector database
                    vector_ids = vector_store.add_chunks(chunks, str(website.id))
                    
                    # Store in PostgreSQL for reference
                    for i, chunk in enumerate(chunks):
                        db_chunk = KnowledgeChunk(
                            id=uuid4(),
                            website_id=website.id,
                            source_url=page['url'],
                            page_title=page['title'],
                            content=chunk['content'],
                            content_hash=chunk['hash'],
                            vector_id=vector_ids[i] if i < len(vector_ids) else None,
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
            
            print(f"Indexing complete: {len(pages)} pages, {total_chunks} chunks")
            return True
            
        except Exception as e:
            print(f"Indexing failed: {e}")
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
