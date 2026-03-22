"""
klantenservice.ai - Database Configuration
"""
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import QueuePool

from app.core.config import settings

# Create database engine with connection pooling
# Configured for long-running WebSocket connections
engine = create_engine(
    settings.DATABASE_URL,
    poolclass=QueuePool,
    pool_size=settings.DATABASE_POOL_SIZE,
    max_overflow=10,
    pool_pre_ping=True,  # Enable connection health checks
    pool_recycle=300,  # Recycle connections after 5 minutes
    pool_timeout=30,  # Wait max 30 seconds for a connection
    connect_args={
        "connect_timeout": 10,  # Connection timeout
        "keepalives": 1,  # Enable TCP keepalives
        "keepalives_idle": 30,  # Start keepalives after 30 seconds idle
        "keepalives_interval": 10,  # Send keepalives every 10 seconds
        "keepalives_count": 5,  # Max keepalive retries
    },
    echo=settings.DEBUG,
)

# Session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Base class for models
Base = declarative_base()


def get_db():
    """
    Database session dependency.
    Yields a database session and ensures it's closed after use.
    """
    db = SessionLocal()
    try:
        yield db
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
