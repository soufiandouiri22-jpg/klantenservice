#!/usr/bin/env python3
"""
Custom uvicorn runner that uses watchgod instead of watchfiles.
watchgod properly respects reload_dirs unlike watchfiles.
"""
import sys
import os

# Add backend to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def main():
    import uvicorn
    
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        reload_dirs=["app", "alembic"],  # Only watch these directories
        reload_delay=0.5,  # Small delay to batch changes
    )

if __name__ == "__main__":
    main()
