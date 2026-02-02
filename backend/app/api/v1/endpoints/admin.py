"""
klantenservice.ai - Admin API Endpoints

Endpoints for platform administrators to manage system-wide settings.
"""
from typing import List, Optional
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_db, get_current_user
from app.models.user import User
from app.models.system_prompt import SystemPrompt, DEFAULT_SYSTEM_PROMPTS
from app.schemas.system_prompt import (
    SystemPromptCreate,
    SystemPromptUpdate,
    SystemPromptResponse,
    SystemPromptListResponse,
    SystemPromptPreview,
)

router = APIRouter()


def require_superadmin(current_user: User = Depends(get_current_user)) -> User:
    """
    Dependency that requires the current user to be a superadmin.
    """
    if not current_user.is_superadmin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Alleen platform administrators hebben toegang tot deze functie"
        )
    return current_user


@router.get("/prompts", response_model=SystemPromptListResponse)
async def get_system_prompts(
    category: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_superadmin),
):
    """
    Get all system prompts, optionally filtered by category.
    """
    query = db.query(SystemPrompt)
    
    if category:
        query = query.filter(SystemPrompt.category == category)
    
    prompts = query.order_by(SystemPrompt.display_order, SystemPrompt.created_at).all()
    
    # Add updated_by_name to each prompt
    prompt_responses = []
    for prompt in prompts:
        response = SystemPromptResponse(
            id=prompt.id,
            key=prompt.key,
            name=prompt.name,
            description=prompt.description,
            category=prompt.category,
            content=prompt.content,
            is_active=prompt.is_active,
            display_order=prompt.display_order,
            created_at=prompt.created_at,
            updated_at=prompt.updated_at,
            updated_by_id=prompt.updated_by_id,
            updated_by_name=prompt.updated_by.full_name if prompt.updated_by else None,
        )
        prompt_responses.append(response)
    
    return SystemPromptListResponse(
        prompts=prompt_responses,
        total=len(prompt_responses)
    )


@router.get("/prompts/preview", response_model=SystemPromptPreview)
async def preview_combined_prompt(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_superadmin),
):
    """
    Preview the combined system prompt that will be sent to the AI.
    """
    prompts = db.query(SystemPrompt).filter(
        SystemPrompt.is_active == True
    ).order_by(SystemPrompt.display_order).all()
    
    # Combine all active prompts
    combined_parts = []
    categories = set()
    
    for prompt in prompts:
        combined_parts.append(f"## {prompt.name}\n{prompt.content}")
        categories.add(prompt.category)
    
    combined_prompt = "\n\n".join(combined_parts)
    
    return SystemPromptPreview(
        combined_prompt=combined_prompt,
        active_prompts=len(prompts),
        categories=sorted(list(categories))
    )


@router.get("/prompts/{prompt_id}", response_model=SystemPromptResponse)
async def get_system_prompt(
    prompt_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_superadmin),
):
    """
    Get a specific system prompt by ID.
    """
    prompt = db.query(SystemPrompt).filter(SystemPrompt.id == prompt_id).first()
    
    if not prompt:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Prompt niet gevonden"
        )
    
    return SystemPromptResponse(
        id=prompt.id,
        key=prompt.key,
        name=prompt.name,
        description=prompt.description,
        category=prompt.category,
        content=prompt.content,
        is_active=prompt.is_active,
        display_order=prompt.display_order,
        created_at=prompt.created_at,
        updated_at=prompt.updated_at,
        updated_by_id=prompt.updated_by_id,
        updated_by_name=prompt.updated_by.full_name if prompt.updated_by else None,
    )


@router.post("/prompts", response_model=SystemPromptResponse, status_code=status.HTTP_201_CREATED)
async def create_system_prompt(
    data: SystemPromptCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_superadmin),
):
    """
    Create a new system prompt.
    """
    # Check if key already exists
    existing = db.query(SystemPrompt).filter(SystemPrompt.key == data.key).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Een prompt met key '{data.key}' bestaat al"
        )
    
    prompt = SystemPrompt(
        key=data.key,
        name=data.name,
        description=data.description,
        category=data.category,
        content=data.content,
        is_active=data.is_active,
        display_order=data.display_order,
        updated_by_id=current_user.id,
    )
    
    db.add(prompt)
    db.commit()
    db.refresh(prompt)
    
    return SystemPromptResponse(
        id=prompt.id,
        key=prompt.key,
        name=prompt.name,
        description=prompt.description,
        category=prompt.category,
        content=prompt.content,
        is_active=prompt.is_active,
        display_order=prompt.display_order,
        created_at=prompt.created_at,
        updated_at=prompt.updated_at,
        updated_by_id=prompt.updated_by_id,
        updated_by_name=current_user.full_name,
    )


@router.put("/prompts/{prompt_id}", response_model=SystemPromptResponse)
async def update_system_prompt(
    prompt_id: UUID,
    data: SystemPromptUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_superadmin),
):
    """
    Update an existing system prompt.
    """
    prompt = db.query(SystemPrompt).filter(SystemPrompt.id == prompt_id).first()
    
    if not prompt:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Prompt niet gevonden"
        )
    
    # Check if new key conflicts with existing
    if data.key and data.key != prompt.key:
        existing = db.query(SystemPrompt).filter(SystemPrompt.key == data.key).first()
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Een prompt met key '{data.key}' bestaat al"
            )
    
    # Update fields
    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(prompt, field, value)
    
    prompt.updated_by_id = current_user.id
    
    db.commit()
    db.refresh(prompt)
    
    return SystemPromptResponse(
        id=prompt.id,
        key=prompt.key,
        name=prompt.name,
        description=prompt.description,
        category=prompt.category,
        content=prompt.content,
        is_active=prompt.is_active,
        display_order=prompt.display_order,
        created_at=prompt.created_at,
        updated_at=prompt.updated_at,
        updated_by_id=prompt.updated_by_id,
        updated_by_name=current_user.full_name,
    )


@router.delete("/prompts/{prompt_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_system_prompt(
    prompt_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_superadmin),
):
    """
    Delete a system prompt.
    """
    prompt = db.query(SystemPrompt).filter(SystemPrompt.id == prompt_id).first()
    
    if not prompt:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Prompt niet gevonden"
        )
    
    db.delete(prompt)
    db.commit()


@router.post("/prompts/seed", response_model=SystemPromptListResponse)
async def seed_default_prompts(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_superadmin),
):
    """
    Seed the database with default system prompts.
    Only creates prompts that don't already exist (by key).
    """
    created = []
    
    for prompt_data in DEFAULT_SYSTEM_PROMPTS:
        existing = db.query(SystemPrompt).filter(
            SystemPrompt.key == prompt_data["key"]
        ).first()
        
        if not existing:
            prompt = SystemPrompt(
                key=prompt_data["key"],
                name=prompt_data["name"],
                description=prompt_data.get("description"),
                category=prompt_data["category"],
                content=prompt_data["content"],
                is_active=prompt_data.get("is_active", True),
                display_order=prompt_data.get("display_order", 0),
                updated_by_id=current_user.id,
            )
            db.add(prompt)
            created.append(prompt)
    
    db.commit()
    
    # Refresh and build response
    prompt_responses = []
    for prompt in created:
        db.refresh(prompt)
        prompt_responses.append(SystemPromptResponse(
            id=prompt.id,
            key=prompt.key,
            name=prompt.name,
            description=prompt.description,
            category=prompt.category,
            content=prompt.content,
            is_active=prompt.is_active,
            display_order=prompt.display_order,
            created_at=prompt.created_at,
            updated_at=prompt.updated_at,
            updated_by_id=prompt.updated_by_id,
            updated_by_name=current_user.full_name,
        ))
    
    return SystemPromptListResponse(
        prompts=prompt_responses,
        total=len(prompt_responses)
    )


@router.get("/categories", response_model=List[dict])
async def get_prompt_categories(
    current_user: User = Depends(require_superadmin),
):
    """
    Get list of available prompt categories.
    """
    return [
        {"key": "communication", "name": "Communicatie", "icon": "💬"},
        {"key": "safety", "name": "Veiligheid", "icon": "🛡️"},
        {"key": "privacy", "name": "Privacy", "icon": "🔒"},
        {"key": "quality", "name": "Kwaliteit", "icon": "⭐"},
        {"key": "edge_cases", "name": "Bijzondere Situaties", "icon": "⚠️"},
        {"key": "general", "name": "Algemeen", "icon": "📋"},
    ]
